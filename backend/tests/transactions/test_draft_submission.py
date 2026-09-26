"""Caller-unit submit marking, retained uncertainty and controlled edit race."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.schemas.operations import OperationRejected
from app.core.errors import ApiFailure
from app.database.models import BookingReview, OperationOutcome
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from tests.transactions.draft_fixtures import DraftHarness, confirmation, make_draft_harness, update


@pytest.fixture
def drafts() -> DraftHarness:
    return make_draft_harness()


def test_edit_wins_and_original_confirm_is_stale(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    command = confirmation(first)
    changed = drafts.service.update(drafts.base.context(), first.draft_id, update(first, "suspend"))
    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        drafts.base.auth.write(
            drafts.base.context(),
            lambda unit: drafts.service.mark_submitted(
                unit,
                first.draft_id,
                command,
                generation=drafts.base.store.generation,
                now=utc_text(drafts.base.clock.value),
            ),
        )
    assert drafts.service.get(drafts.base.context(), first.draft_id) == changed
    assert drafts.counts()[2:] == (0, 0, 0, 0)


def test_submit_wins_blocks_edit_and_cross_session_replacement(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    command = confirmation(first)
    revision = drafts.base.service.get(drafts.base.context(), drafts.sessions[0]).revision
    drafts.base.auth.write(
        drafts.base.context(),
        lambda unit: drafts.service.mark_submitted(
            unit,
            first.draft_id,
            command,
            generation=drafts.base.store.generation,
            now=utc_text(drafts.base.clock.value),
        ),
    )
    assert drafts.base.service.get(drafts.base.context(), drafts.sessions[0]).revision == revision
    for intent in ("discard", "suspend", "refresh_review"):
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            drafts.service.update(drafts.base.context(), first.draft_id, update(first, intent))
    another = drafts.base.create(0)
    request = drafts.command()
    request.session_id, request.expected_session_revision = another.session_id, another.revision
    with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
        drafts.service.create(drafts.base.context(), request)
    drafts.base.clock.value += timedelta(hours=1)
    observed = drafts.service.get(drafts.base.context(), first.draft_id)
    assert observed.state == "unresolved" and observed.review is not None
    assert observed.review.operation_key == command.operation_key
    other = drafts.service.create(drafts.base.context(1), drafts.command(who=1))
    assert other.state == "reviewable"


def test_read_unit_or_caller_failure_cannot_commit_submit_mark(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    command = confirmation(first)
    with pytest.raises(StoreError, match="DRAFT_REQUIRES_CALLER_WRITE_UNIT"):
        drafts.base.auth.read(
            drafts.base.context(write=False),
            lambda unit: drafts.service.mark_submitted(
                unit,
                first.draft_id,
                command,
                generation=drafts.base.store.generation,
                now=utc_text(drafts.base.clock.value),
            ),
        )

    def fail(unit: OwnerUnit) -> None:
        drafts.service.mark_submitted(
            unit,
            first.draft_id,
            command,
            generation=drafts.base.store.generation,
            now=utc_text(drafts.base.clock.value),
        )
        raise StoreError("SYNTHETIC_CALLER_ROLLBACK")

    with pytest.raises(StoreError, match="SYNTHETIC_CALLER_ROLLBACK"):
        drafts.base.auth.write(drafts.base.context(), fail)
    assert drafts.service.get(drafts.base.context(), first.draft_id) == first


@pytest.mark.parametrize("fault", ["key", "rules", "generation", "revision", "owner"])
def test_exact_confirmation_identity_and_owner_are_required(
    drafts: DraftHarness, fault: str
) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    command = confirmation(first)
    if fault == "key":
        command.operation_key = "X" * 43
    elif fault == "rules":
        command.rules_version = "other-config"
    elif fault == "generation":
        command.store_generation = str(uuid4())
    elif fault == "revision":
        command.expected_draft_revision += 1
    with pytest.raises(ApiFailure):
        drafts.base.auth.write(
            drafts.base.context(1 if fault == "owner" else 0),
            lambda unit: drafts.service.mark_submitted(
                unit,
                first.draft_id,
                command,
                generation=drafts.base.store.generation,
                now=utc_text(drafts.base.clock.value),
            ),
        )
    assert drafts.service.get(drafts.base.context(), first.draft_id) == first


@pytest.mark.parametrize("terminal", ["valid_rejection", "absent", "malformed"])
def test_consumed_authority_requires_verified_terminal_before_new_viewing(
    drafts: DraftHarness, terminal: str
) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    assert first.review is not None
    review_id = first.review.review_id

    def consume(unit: OwnerUnit) -> None:
        row = unit.review(review_id)
        row.state = "consumed"
        if terminal == "absent":
            return
        now = utc_text(drafts.base.clock.value)
        expires = utc_text(drafts.base.clock.value + timedelta(days=90))
        result = OperationRejected.model_validate(
            dict(
                state="rejected",
                operation_key=row.operation_key,
                review_id=row.id,
                original_store_generation=row.store_generation,
                terminal_at=now,
                replay_valid_until=expires,
                rejection_code="CAPACITY_UNAVAILABLE",
                booking={"state": "not_created"},
                lead={"state": "not_requested"},
                csv={"state": "not_requested"},
            )
        )
        unit.db.add(
            OperationOutcome(
                id=str(uuid4()),
                owner_id=unit.owner_id,
                operation_key=row.operation_key,
                review_id=row.id,
                payload_hash=row.payload_hash,
                store_generation=row.store_generation,
                terminal_state="REJECTED",
                terminal_at=now,
                replay_valid_until=expires,
                terminal_result_json=result.model_dump(mode="json")
                if terminal == "valid_rejection"
                else {},
            )
        )

    drafts.base.auth.write(drafts.base.context(), consume)
    observed = drafts.service.get(drafts.base.context(), first.draft_id)
    assert observed.state == ("resolved" if terminal == "valid_rejection" else "unresolved")
    next_session = drafts.base.create()
    command = drafts.command()
    command.session_id, command.expected_session_revision = (
        next_session.session_id,
        next_session.revision,
    )
    if terminal == "valid_rejection":
        result = drafts.service.create(drafts.base.context(), command)
        assert result.draft_id != first.draft_id
    else:
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            drafts.service.create(drafts.base.context(), command)


def test_submit_edit_barrier_uses_the_same_store_write_serialization(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    command, change = confirmation(first), update(first, "refresh_review")
    context = drafts.base.context()
    marked, prepared, release = Event(), Event(), Event()

    def submit() -> None:
        def write(unit: OwnerUnit) -> None:
            drafts.service.mark_submitted(
                unit,
                first.draft_id,
                command,
                generation=drafts.base.store.generation,
                now=utc_text(drafts.base.clock.value),
            )
            marked.set()
            if not release.wait(5):
                raise AssertionError("TEST_RELEASE_TIMEOUT")

        drafts.base.auth.write(context, write)

    drafts.inventory.after_prepare = prepared.set
    with ThreadPoolExecutor(max_workers=2) as pool:
        submitting = pool.submit(submit)
        try:
            assert marked.wait(5)
            editing = pool.submit(drafts.service.update, context, first.draft_id, change)
            assert prepared.wait(5)
        finally:
            release.set()
        submitting.result(timeout=5)
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            editing.result(timeout=5)
    assert drafts.counts() == (1, 1, 0, 0, 0, 0)
    original = drafts.base.store.read(
        lambda db: db.scalar(
            select(BookingReview.operation_key).where(
                BookingReview.id == command.review_id,
            )
        )
    )
    assert original == command.operation_key
