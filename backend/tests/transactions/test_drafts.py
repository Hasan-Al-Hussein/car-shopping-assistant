"""Auth/Store/session draft cases authored under T6; real Inventory remains a gate."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.sessions import SessionSelectionRequest
from app.core.errors import ApiFailure
from app.database.models import (
    ActiveRules,
    BookingReview,
    ConversationSession,
)
from app.database.models import (
    BookingDraft as DraftRow,
)
from app.database.store import StoreError
from app.identity.service import utc_text
from app.viewings.drafts import DraftService
from tests.platform.session_cases import ref
from tests.transactions.draft_fixtures import DraftHarness, make_draft_harness, update


@pytest.fixture
def drafts() -> DraftHarness:
    return make_draft_harness()


def test_incomplete_draft_is_useful_and_never_an_action(drafts: DraftHarness) -> None:
    result = drafts.service.create(drafts.base.context(), drafts.command(complete=False))
    assert result.state == "needs_details" and result.required_fields == ["appointment"]
    assert result.ref.model_dump() == ref().model_dump() and result.review is None
    assert drafts.counts() == (1, 0, 0, 0, 0, 0)
    completed = drafts.service.update(
        drafts.base.context(),
        result.draft_id,
        update(
            result,
            "edit",
            appointment=drafts.appointment().model_dump(mode="json"),
        ),
    )
    assert completed.state == "reviewable" and completed.revision == 2
    assert drafts.counts() == (1, 1, 0, 0, 0, 0)


def test_full_review_binds_every_material_field_without_lead_capture(drafts: DraftHarness) -> None:
    command = drafts.command()
    result = drafts.service.create(drafts.base.context(), command)
    review = result.review
    assert review is not None
    assert (
        review.ref.model_dump() == command.ref.model_dump() and review.draft_id == result.draft_id
    )
    assert review.session_id == command.session_id and review.draft_revision == result.revision
    assert review.resource_id == drafts.inventory.resources["12"]
    assert command.appointment is not None
    assert review.starts_at_utc == command.appointment.starts_at_utc
    assert review.ends_at_utc == utc_text(drafts.base.clock.value + timedelta(days=1, minutes=30))
    assert review.timezone == "Asia/Dubai" and review.local_start.endswith("+04:00")
    assert review.simulation and review.appointment_type == "viewing"
    assert review.store_generation == drafts.base.store.generation
    assert len(review.operation_key) == 43
    assert review.expires_at == utc_text(drafts.base.clock.value + timedelta(minutes=5))
    assert review.lead_change.mode == "create_from_review"
    assert review.lead_change.values.budget.state == "missing"
    assert (
        review.lead_change.values.email.state == review.lead_change.values.phone.state == "missing"
    )
    assert review.lead_change.values.requirements == []
    assert [item.model_dump() for item in review.lead_change.values.selected_refs] == [
        ref().model_dump()
    ]
    session = drafts.base.service.get(drafts.base.context(), command.session_id)
    assert review.lead_change.source_session_revision == session.revision
    assert session.pending_intent.kind == "viewing_review"
    assert drafts.counts() == (1, 1, 0, 0, 0, 0)


def test_edit_invalidates_old_review_and_replay_returns_current(drafts: DraftHarness) -> None:
    create = drafts.command()
    first = drafts.service.create(drafts.base.context(), create)
    assert first.review is not None
    change = update(first, "edit", ref=ref("13").model_dump())
    second = drafts.service.update(drafts.base.context(), first.draft_id, change)
    assert second.ref.model_dump() == ref("13").model_dump() and second.review is not None
    assert second.review.resource_id == drafts.inventory.resources["13"]
    assert second.review.operation_key != first.review.operation_key
    original_id = first.review.review_id
    assert (
        drafts.base.store.read(
            lambda db: db.scalar(
                select(BookingReview.state).where(
                    BookingReview.id == original_id,
                )
            )
        )
        == "invalidated"
    )
    calls = drafts.inventory.prepares
    assert drafts.service.create(drafts.base.context(), create) == second
    assert drafts.service.update(drafts.base.context(), second.draft_id, change) == second
    assert drafts.inventory.prepares == calls
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        drafts.service.update(drafts.base.context(), first.draft_id, update(first, "suspend"))
    assert drafts.counts() == (1, 2, 0, 0, 0, 0)


def test_changed_payload_same_action_conflicts(drafts: DraftHarness) -> None:
    command = drafts.command()
    drafts.service.create(drafts.base.context(), command)
    command.ref = ref("13")
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        drafts.service.create(drafts.base.context(), command)
    assert drafts.counts() == (1, 1, 0, 0, 0, 0)


def test_suspend_browse_and_resume_preserves_original_car(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    suspended = drafts.service.update(
        drafts.base.context(), first.draft_id, update(first, "suspend")
    )
    assert suspended.state == "suspended" and suspended.review is None
    current = drafts.base.service.get(drafts.base.context(), drafts.sessions[0])
    drafts.base.service.select(
        drafts.base.context(),
        current.session_id,
        SessionSelectionRequest(
            expected_revision=current.revision,
            client_action_id=str(uuid4()),
            selected_ref=ref("13"),
        ),
    )
    assert (
        drafts.service.get(drafts.base.context(), first.draft_id).ref.model_dump()
        == ref().model_dump()
    )
    resumed = drafts.service.update(
        drafts.base.context(), first.draft_id, update(suspended, "refresh_review")
    )
    assert resumed.ref.model_dump() == ref().model_dump()
    assert resumed.state == "reviewable" and resumed.review is not None
    assert first.review is not None and resumed.review.operation_key != first.review.operation_key


def test_discard_is_terminal_for_that_draft_only(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    removed = drafts.service.update(drafts.base.context(), first.draft_id, update(first, "discard"))
    assert removed.state == "discarded" and removed.review is None
    session = drafts.base.service.get(drafts.base.context(), drafts.sessions[0])
    assert session.current_draft_id is None
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        drafts.service.update(
            drafts.base.context(), first.draft_id, update(removed, "refresh_review")
        )
    new = drafts.service.create(drafts.base.context(), drafts.command())
    assert new.draft_id != first.draft_id and drafts.counts()[2:] == (0, 0, 0, 0)


@pytest.mark.parametrize("minutes", [5, 30])
def test_expiry_read_and_replay_are_observational_until_explicit_refresh(
    drafts: DraftHarness, minutes: int
) -> None:
    command = drafts.command()
    first = drafts.service.create(drafts.base.context(), command)
    assert first.review is not None
    drafts.base.clock.value += timedelta(minutes=minutes)
    before = drafts.counts()
    observed = drafts.service.get(drafts.base.context(), first.draft_id)
    assert observed.state == "needs_details" and observed.review is not None
    assert observed.required_fields == (["draft_expired"] if minutes == 30 else ["review_refresh"])
    assert observed.review.state == "expired" and observed.expires_at == first.expires_at
    assert drafts.service.create(drafts.base.context(), command) == observed
    assert drafts.counts() == before
    fresh = drafts.service.update(
        drafts.base.context(), first.draft_id, update(observed, "refresh_review")
    )
    assert fresh.state == "reviewable" and fresh.expires_at > first.expires_at
    assert fresh.review is not None and fresh.review.operation_key != first.review.operation_key


def test_rules_change_invalidates_observation_without_rewriting_history(
    drafts: DraftHarness,
) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())

    def change(db: Session) -> None:
        active = db.get(ActiveRules, 1)
        assert active is not None
        active.revision += 1

    drafts.base.store.write(change)
    observed = drafts.service.get(drafts.base.context(), first.draft_id)
    assert observed.state == "needs_details" and observed.review is not None
    assert observed.review.state == "invalidated"
    assert drafts.counts() == (1, 1, 0, 0, 0, 0)
    refreshed = drafts.service.update(
        drafts.base.context(), first.draft_id, update(observed, "refresh_review")
    )
    assert refreshed.state == "reviewable"


def test_foreign_owner_and_read_authority_cannot_change_draft(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        drafts.service.get(drafts.base.context(1), first.draft_id)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        drafts.service.update(drafts.base.context(1), first.draft_id, update(first, "discard"))
    with pytest.raises(ApiFailure, match="CSRF_DENIED"):
        drafts.service.update(
            drafts.base.context(write=False), first.draft_id, update(first, "discard")
        )


def test_unavailable_adapter_and_midflight_failure_preserve_no_partial_state(
    drafts: DraftHarness,
) -> None:
    with pytest.raises(ApiFailure, match="ELIGIBILITY_UNAVAILABLE"):
        DraftService(drafts.base.auth).create(drafts.base.context(), drafts.command())
    drafts.inventory.fail_recheck = True
    with pytest.raises(StoreError, match="SYNTHETIC_INTEGRITY_UNAVAILABLE"):
        drafts.service.create(drafts.base.context(), drafts.command())
    assert drafts.counts() == (0, 0, 0, 0, 0, 0)


def test_reads_do_not_rewrite_state_revision_or_expiry(drafts: DraftHarness) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())

    def snapshot(db: Session) -> tuple[int, str, str, str]:
        row = db.get(DraftRow, first.draft_id)
        assert row is not None and row.active_review_id is not None
        review = db.get(BookingReview, row.active_review_id)
        assert review is not None
        return row.revision, row.expires_at, row.state, review.state

    before = drafts.base.store.read(snapshot)
    drafts.base.clock.value += timedelta(minutes=31)
    for _ in range(2):
        drafts.service.get(drafts.base.context(), first.draft_id)
    assert drafts.base.store.read(snapshot) == before


@pytest.mark.parametrize("suffix", ["Z", ".0Z", ".000Z"])
@pytest.mark.parametrize("operation", ["create", "edit"])
def test_equivalent_utc_spellings_have_consistent_draft_review(
    drafts: DraftHarness, suffix: str, operation: str
) -> None:
    command = drafts.command()
    assert command.appointment is not None
    canonical_start = command.appointment.starts_at_utc
    command.appointment.starts_at_utc = canonical_start.split(".")[0] + suffix
    if operation == "create":
        result = drafts.service.create(drafts.base.context(), command)
    else:
        prior = drafts.service.create(drafts.base.context(), drafts.command(complete=False))
        result = drafts.service.update(
            drafts.base.context(),
            prior.draft_id,
            update(
                prior,
                "edit",
                appointment=command.appointment.model_dump(mode="json"),
            ),
        )
    assert (
        result.state == "reviewable"
        and result.review is not None
        and result.appointment is not None
    )
    assert result.appointment.starts_at_utc == result.review.starts_at_utc == canonical_start


@pytest.mark.parametrize("operation", ["create", "update"])
def test_session_revision_exhaustion_has_no_partial_effects(
    drafts: DraftHarness, operation: str
) -> None:
    first = (
        drafts.service.create(drafts.base.context(), drafts.command())
        if operation == "update"
        else None
    )

    def exhaust(db: Session) -> None:
        row = db.get(ConversationSession, drafts.sessions[0])
        assert row is not None
        row.revision = 2_147_483_647

    drafts.base.store.write(exhaust)
    before = drafts.counts()
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        if first is None:
            drafts.service.create(drafts.base.context(), drafts.command())
        else:
            drafts.service.update(
                drafts.base.context(), first.draft_id, update(first, "refresh_review")
            )
    assert drafts.counts() == before
