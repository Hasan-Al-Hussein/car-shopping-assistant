"""Real Session/T7/lead/draft transaction composition; synthetic Inventory ports only."""

from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.operations import OperationRejected, OperationSucceeded
from app.api.schemas.sessions import ClarificationReply, ExplicitConfirmation, MessageRequest, MessageResult
from app.api.schemas.viewings import BookingDraft
from app.core.errors import ApiFailure
from app.database.models import ExportState, OperationOutcome
from app.database.store import StoreError
from tests.platform.memory_shortlist_cases import failed_commit
from tests.platform.session_cases import ref
from tests.platform.test_identity import snapshot
from tests.transactions.confirmation_fixtures import ConfirmationHarness, make_confirmation_harness
from tests.transactions.draft_fixtures import confirmation, update


@pytest.fixture
def h() -> ConfirmationHarness:
    return make_confirmation_harness()


def body(h: ConfirmationHarness, draft: BookingDraft, *, who: int = 0) -> MessageRequest:
    base = h.drafts.base
    state = base.service.get(base.context(who), draft.session_id)
    return MessageRequest(
        client_message_id=str(uuid4()), expected_revision=state.revision,
        text="Confirm this simulated viewing.",
        explicit_confirmation=ExplicitConfirmation.model_validate({
            **confirmation(draft).model_dump(mode="json"), "draft_id": draft.draft_id,
        }),
    )


def confirm(h: ConfirmationHarness, draft: BookingDraft, request: MessageRequest, *, who: int = 0) -> MessageResult:
    base = h.drafts.base
    return base.service.confirm_turn(
        base.context(who), draft.session_id, request, participant=h.participant
    )


def test_reviewed_r(h: ConfirmationHarness) -> None:
    draft = h.create()
    request = body(h, draft)
    saved = confirm(h, draft, request)
    assert isinstance(saved.operation, OperationSucceeded)
    assert saved.turn_revision == saved.current_revision == request.expected_revision + 1
    assert saved.operation.booking.review.model_dump(mode="json", exclude={"state"}) == (
        draft.review.model_dump(mode="json", exclude={"state"}) if draft.review else None
    )
    assert saved.pending_intent.kind == "none" and saved.persistence == "saved"
    assert h.counts() == (1, 1, 1, 1, 1)
    base = h.drafts.base
    current = base.service.get(base.context(), draft.session_id)
    assert current.revision == saved.current_revision and current.current_draft_id is None
    transcript = base.service.transcript(base.context(), draft.session_id)
    assert len(transcript.items) == 1 and transcript.items[0].assistant_result == saved
    assert transcript.items[0].accepted_revision == request.expected_revision + 1


def test_message_replay(h: ConfirmationHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = h.create()
    request = body(h, draft)
    saved = confirm(h, draft, request)
    base = h.drafts.base
    base.clock.value += timedelta(days=2)
    before = snapshot(base.store)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("MESSAGE_REPLAY_CALLED_T7")

    for name in ("lookup_in_unit", "prepare", "apply_in_unit", "observe_csv_in_unit"):
        monkeypatch.setattr(h.participant, name, forbidden)
    assert confirm(h, draft, request) == saved
    assert snapshot(base.store) == before
    changed = request.model_copy(update={"text": "Different request"})
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        confirm(h, draft, changed)
    assert snapshot(base.store) == before


def test_ui_terminal_new_message(h: ConfirmationHarness) -> None:
    draft = h.create()
    committed = h.commit(draft, h.prepare(draft)).terminal
    assert isinstance(committed, OperationSucceeded)
    base = h.drafts.base
    base.clock.value += timedelta(days=2)
    h.drafts.inventory.fail_recheck = True
    counters = h.drafts.inventory.prepares, h.lead_inventory.reads
    request = body(h, draft)
    saved = confirm(h, draft, request)
    assert isinstance(saved.operation, OperationSucceeded)
    assert saved.operation.booking == committed.booking and saved.operation.lead == committed.lead
    assert saved.current_revision == request.expected_revision + 1
    assert h.counts() == (1, 1, 1, 1, 1)
    assert counters == (h.drafts.inventory.prepares, h.lead_inventory.reads)
    stale = body(h, draft).model_copy(update={"expected_revision": request.expected_revision})
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        confirm(h, draft, stale)
    assert snapshot(base.store) == before


@pytest.mark.parametrize("field", ["ref", "proof", "reply", "missing"])
def test_combined_fields(h: ConfirmationHarness, field: str) -> None:
    draft = h.create()
    request = body(h, draft)
    if field == "ref":
        request.selected_ref = ref()
    elif field == "proof":
        request.presentation_id = str(uuid4())
    elif field == "reply":
        request.clarification_reply = ClarificationReply(intent_id=str(uuid4()), created_revision=0)
    else:
        request.explicit_confirmation = None
    before = snapshot(h.drafts.base.store)
    count = h.drafts.inventory.prepares
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        confirm(h, draft, request)
    assert snapshot(h.drafts.base.store) == before and h.drafts.inventory.prepares == count


def test_wrong_session(h: ConfirmationHarness) -> None:
    draft = h.create()
    request = body(h, draft)
    base = h.drafts.base
    other = base.create()
    request.expected_revision = other.revision
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        base.service.confirm_turn(base.context(), other.session_id, request, participant=h.participant)
    assert snapshot(base.store) == before and h.counts() == (0, 0, 0, 0, 0)


def test_begin_is_not_confirmation(h: ConfirmationHarness) -> None:
    draft = h.create()
    request = body(h, draft)
    base = h.drafts.base
    admission = base.service.begin(base.context(), draft.session_id, request)
    assert admission.status == "accepted"
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        confirm(h, draft, request)
    assert snapshot(base.store) == before and h.counts() == (0, 0, 0, 0, 0)
    new = body(h, draft)
    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        confirm(h, draft, new)
    assert h.counts() == (0, 0, 0, 0, 0)


def test_edit_between_units(h: ConfirmationHarness) -> None:
    draft = h.create()
    request = body(h, draft)
    base = h.drafts.base

    def edit() -> None:
        h.drafts.inventory.after_prepare = None
        h.drafts.service.update(base.context(), draft.draft_id, update(draft, "suspend"))

    h.drafts.inventory.after_prepare = edit
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        confirm(h, draft, request)
    assert h.counts() == (0, 0, 0, 0, 0)
    assert base.service.transcript(base.context(), draft.session_id).items == []
    assert h.drafts.service.get(base.context(), draft.draft_id).state == "suspended"


def test_capacity_between_units(h: ConfirmationHarness) -> None:
    draft, competing = h.create(), h.create(who=1)
    request = body(h, draft)

    def occupy() -> None:
        h.drafts.inventory.after_prepare = None
        h.commit(competing, h.prepare(competing, who=1), who=1)

    h.drafts.inventory.after_prepare = occupy
    result = confirm(h, draft, request)
    assert isinstance(result.operation, OperationRejected)
    assert result.operation.rejection_code == "CAPACITY_UNAVAILABLE"
    assert result.pending_intent.kind == "none" and result.current_revision == request.expected_revision + 1
    assert h.counts() == (1, 2, 1, 1, 1)
    assert confirm(h, draft, request) == result
    assert h.counts() == (1, 2, 1, 1, 1)


@pytest.mark.parametrize("failure", ["observe", "resolve", "commit"])
def test_transaction_rollback(h: ConfirmationHarness, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    draft = h.create()
    request = body(h, draft)
    base = h.drafts.base
    before = snapshot(base.store)
    if failure == "commit":
        with failed_commit(), pytest.raises(StoreError, match="SYNTHETIC_COMMIT_FAILURE"):
            confirm(h, draft, request)
    else:
        name = "observe_csv_in_unit" if failure == "observe" else "resolve_session_in_unit"
        original = getattr(h.participant, name)
        def fail(*args: Any, **kwargs: Any) -> Any:
            original(*args, **kwargs)
            raise ApiFailure("UNSUPPORTED_STATE")
        with monkeypatch.context() as patch:
            patch.setattr(h.participant, name, fail)
            with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
                confirm(h, draft, request)
    assert snapshot(base.store) == before and h.counts() == (0, 0, 0, 0, 0)
    result = confirm(h, draft, request)
    assert isinstance(result.operation, OperationSucceeded) and h.counts() == (1, 1, 1, 1, 1)


def test_lost_response(h: ConfirmationHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = h.create()
    request = body(h, draft)
    base = h.drafts.base
    write = base.auth.write
    def lose(*args: Any, **kwargs: Any) -> Any:
        write(*args, **kwargs)
        raise StoreError("SYNTHETIC_RESPONSE_LOST")
    with monkeypatch.context() as patch:
        patch.setattr(base.auth, "write", lose)
        with pytest.raises(StoreError, match="SYNTHETIC_RESPONSE_LOST"):
            confirm(h, draft, request)
    assert h.counts() == (1, 1, 1, 1, 1)
    before = snapshot(base.store)
    replay = confirm(h, draft, request)
    assert isinstance(replay.operation, OperationSucceeded)
    assert snapshot(base.store) == before and h.counts() == (1, 1, 1, 1, 1)


def test_csv_receipt_is_history(h: ConfirmationHarness) -> None:
    draft = h.create()
    request = body(h, draft)
    saved = confirm(h, draft, request)
    assert isinstance(saved.operation, OperationSucceeded) and saved.operation.csv.state == "pending"
    base = h.drafts.base
    terminal = base.store.read(lambda db: db.scalar(select(OperationOutcome.terminal_result_json)))
    def fail_csv(db: Session) -> None:
        state = db.get(ExportState, 1)
        assert state is not None
        state.state = "failed"
    base.store.write(fail_csv)
    current = h.participant.status(base.context(), operation_key=confirmation(draft).operation_key,
        submitted_generation=base.store.generation)
    assert isinstance(current, OperationSucceeded) and current.csv.state == "failed"
    assert confirm(h, draft, request).operation == saved.operation
    newer = confirm(h, draft, body(h, draft))
    assert isinstance(newer.operation, OperationSucceeded) and newer.operation.csv.state == "failed"
    assert newer.operation.booking == saved.operation.booking and newer.operation.lead == saved.operation.lead
    assert base.store.read(lambda db: db.scalar(select(OperationOutcome.terminal_result_json))) == terminal
    assert h.counts() == (1, 1, 1, 1, 1)