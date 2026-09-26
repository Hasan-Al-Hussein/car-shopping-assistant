"""Authored real-service collection cases, not executed acceptance evidence."""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.api.schemas.leads import ContactValue, LeadSaveRequest, LeadValues, ReviewedLeadCreation
from app.api.schemas.sessions import SessionCreateRequest, ViewingReviewIntent
from app.api.schemas.viewings import BookingDraftCreate, BookingDraftUpdate
from app.core.errors import ApiFailure
from app.database.store import StoreError
from app.sessions.collection import CollectionUpdate, CollectionValues, FieldSource
from app.sessions.service import DraftChange, LeadChange, TurnAdmission
from tests.platform.collection_cases import begin, collect, public_content
from tests.platform.memory_shortlist_cases import failed_commit
from tests.platform.session_cases import answer, ref
from tests.platform.test_identity import snapshot
from tests.transactions.draft_fixtures import DraftHarness, make_draft_harness
from tests.transactions.lead_fixtures import LeadHarness, make_lead_harness


@pytest.fixture
def leads() -> LeadHarness:
    return make_lead_harness()


def save_turn(h: LeadHarness) -> tuple[TurnAdmission, LeadChange]:
    base, session_id = h.sessions, h.session_ids[0]
    collect(base, session_id, CollectionValues(requirements=["Quiet cabin"], requirements_state="provided"), ask="save")
    admission = begin(base, session_id, "Save this local enquiry")
    assert admission.ticket is not None
    observed = base.service.read_collection(base.context(), admission.ticket)
    assert observed.collection is not None
    values = observed.collection.values
    command = LeadSaveRequest(
        client_action_id=str(uuid4()), session_id=session_id, intent="save_local_enquiry",
        values=LeadValues(budget=values.budget, requirements=values.requirements, selected_refs=[],
                         email=ContactValue(state="missing"), phone=ContactValue(state="missing")),
    )
    return admission, LeadChange(command)


def test_private_preserved_and_expiry_not_renewed(leads: LeadHarness) -> None:
    base, sid = leads.sessions, leads.session_ids[0]
    collect(base, sid, CollectionValues(requirements=["Foldable bicycle space"], requirements_state="provided"))
    first = begin(base, sid, "Tell me about tyre care")
    assert first.ticket is not None
    before = base.service.read_collection(base.context(), first.ticket)
    assert before.collection is not None
    base.clock.value += timedelta(minutes=2)
    result = base.service.complete(base.context(), first.ticket, answer(first), update=public_content(first))
    assert result.persistence == "saved"
    second = begin(base, sid, "What about tyre pressure?")
    assert second.ticket is not None
    after = base.service.read_collection(base.context(), second.ticket)
    assert after.collection == before.collection and after.digest == before.digest
    assert "collection" not in second.session.model_dump()
    assert "Foldable bicycle space" not in second.session.model_dump_json()
    base.clock.value += timedelta(minutes=29)
    expired = base.service.read_collection(base.context(), second.ticket)
    assert expired.expired and expired.collection == before.collection


def test_lead_actual_receipt_and_replay_skip_participants(leads: LeadHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    base = leads.sessions
    admission, change = save_turn(leads)
    assert admission.ticket is not None
    saved = base.service.complete_action(base.context(), admission.ticket, answer(admission), lead=change, lead_service=leads.service)
    assert saved.actions.lead.state == "succeeded"
    assert saved.actions.lead.result.lead.values.requirements == ["Quiet cabin"]
    assert saved.current_revision == admission.session.revision + 1
    assert saved.pending_intent.kind == "none" and leads.counts() == (1, 1, 0, 0, 1)
    assert base.service.transcript(base.context(), admission.session.session_id).items[-1].assistant_result == saved
    after = snapshot(base.store)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("REPLAY_CALLED_PARTICIPANT")

    monkeypatch.setattr(leads.service, "prepare_change", forbidden)
    monkeypatch.setattr(leads.service, "change_in_unit", forbidden)
    assert base.service.complete_action(base.context(), admission.ticket, answer(admission), lead=change, lead_service=leads.service) == saved
    assert snapshot(base.store) == after


def test_actual_effect_failure_rolls_back_and_retains_owner_fence(leads: LeadHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    base = leads.sessions
    admission, change = save_turn(leads)
    assert admission.ticket is not None
    original = leads.service.change_in_unit
    before_effect = snapshot(base.store)

    def fail(*args: Any, **kwargs: Any) -> Any:
        original(*args, **kwargs)
        raise ApiFailure("UNSUPPORTED_STATE")

    with monkeypatch.context() as patched:
        patched.setattr(leads.service, "change_in_unit", fail)
        with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
            base.service.complete_action(base.context(), admission.ticket, answer(admission), lead=change, lead_service=leads.service)
    assert leads.counts() == (0, 0, 0, 0, 0)
    after_effect = snapshot(base.store)
    for name in before_effect:
        if name != "messages":
            assert after_effect[name] == before_effect[name]
    retained = base.service.read_collection(base.context(), admission.ticket)
    assert retained.unresolved is not None and retained.unresolved.command == change.command
    assert base.service.transcript(base.context(), admission.session.session_id).items[-1].state == "pending"
    new_session = base.service.create(base.context(), SessionCreateRequest(client_action_id=str(uuid4())))
    other = begin(base, new_session.session_id, "Start another enquiry")
    assert other.ticket is not None
    assert base.service.read_collection(base.context(), other.ticket).unresolved == retained.unresolved
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
        base.service.complete(base.context(), other.ticket, answer(other), collection_update=CollectionUpdate(
            expected_digest=None, purpose="local_enquiry", values=CollectionValues(),
        ))
    assert snapshot(base.store) == before


def test_same_current_original_retries_after_failure_without_new_key(leads: LeadHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    base = leads.sessions
    admission, change = save_turn(leads)
    assert admission.ticket is not None
    original = leads.service.prepare_change

    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("SYNTHETIC_PREPARATION_UNAVAILABLE")

    monkeypatch.setattr(leads.service, "prepare_change", unavailable)
    with pytest.raises(RuntimeError, match="SYNTHETIC"):
        base.service.complete_action(base.context(), admission.ticket, answer(admission), lead=change, lead_service=leads.service)
    retained = base.service.read_collection(base.context(), admission.ticket).unresolved
    assert retained is not None
    monkeypatch.setattr(leads.service, "prepare_change", original)
    saved = base.service.complete_action(base.context(), admission.ticket, answer(admission), lead=change, lead_service=leads.service)
    assert saved.actions.lead.state == "succeeded"
    assert saved.actions.lead.client_action_id == retained.command.client_action_id
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_final_commit_failure_preserves_only_original_command(leads: LeadHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    base = leads.sessions
    admission, change = save_turn(leads)
    assert admission.ticket is not None
    original_prepare = leads.service.prepare_change
    manager = failed_commit()
    armed = False
    retained_snapshot = None

    def prepare(*args: Any, **kwargs: Any) -> Any:
        nonlocal armed, retained_snapshot
        prepared = original_prepare(*args, **kwargs)
        retained_snapshot = snapshot(base.store)
        manager.__enter__()  # Retention already committed; fail actual effect-unit commit.
        armed = True
        return prepared

    monkeypatch.setattr(leads.service, "prepare_change", prepare)
    try:
        with pytest.raises(StoreError, match="SYNTHETIC_COMMIT_FAILURE"):
            base.service.complete_action(base.context(), admission.ticket, answer(admission), lead=change, lead_service=leads.service)
    finally:
        if armed:
            manager.__exit__(None, None, None)
    assert leads.counts() == (0, 0, 0, 0, 0)
    assert retained_snapshot is not None and snapshot(base.store) == retained_snapshot
    observed = base.service.read_collection(base.context(), admission.ticket)
    assert observed.unresolved is not None and observed.unresolved.command == change.command
    assert base.service.transcript(base.context(), admission.session.session_id).items[-1].state == "pending"


def test_response_lost_after_commit_recovers_original_message(leads: LeadHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    base = leads.sessions
    admission, change = save_turn(leads)
    assert admission.ticket is not None
    original_write = base.auth.write
    writes = 0

    def lose(context: Any, work: Any) -> Any:
        nonlocal writes
        result = original_write(context, work)
        writes += 1
        if writes == 2:
            raise RuntimeError("SYNTHETIC_COMMITTED_RESPONSE_LOST")
        return result

    with monkeypatch.context() as patched:
        patched.setattr(base.auth, "write", lose)
        with pytest.raises(RuntimeError, match="COMMITTED_RESPONSE_LOST"):
            base.service.complete_action(base.context(), admission.ticket, answer(admission), lead=change, lead_service=leads.service)
    assert writes == 2 and leads.counts() == (1, 1, 0, 0, 1)
    committed = snapshot(base.store)
    replay = base.service.begin(base.context(), admission.session.session_id, admission.request)
    assert replay.status == "completed" and replay.result is not None
    assert replay.result.actions.lead.state == "succeeded"
    assert replay.result.actions.lead.client_action_id == change.command.client_action_id
    assert snapshot(base.store) == committed


def test_collection_cas_and_owner_context_are_exact(leads: LeadHarness) -> None:
    base, sid = leads.sessions, leads.session_ids[0]
    collect(base, sid, CollectionValues())
    admission = begin(base, sid, "My needs changed")
    assert admission.ticket is not None
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        base.service.complete(base.context(), admission.ticket, answer(admission), collection_update=CollectionUpdate(
            expected_digest="0" * 64, purpose="local_enquiry", values=None,
        ))
    assert snapshot(base.store) == before
    with pytest.raises(ApiFailure):
        base.service.read_collection(base.context(1), admission.ticket)
    assert snapshot(base.store) == before


def create_viewing(h: DraftHarness) -> tuple[TurnAdmission, str]:
    base, sid = h.base, h.sessions[0]
    appointment = h.appointment()
    local = datetime.fromisoformat(appointment.starts_at_utc).astimezone(ZoneInfo("Asia/Dubai"))
    collect(base, sid, CollectionValues(ref=ref(), local_date=local.date().isoformat()), purpose="viewing", ask="time")
    admission = begin(base, sid, "Viewing time: " + local.strftime("%H:%M"))
    assert admission.ticket is not None
    observed = base.service.read_collection(base.context(), admission.ticket)
    assert observed.collection is not None
    values = observed.collection.values.model_copy(update={"local_time": local.strftime("%H:%M")})
    command = BookingDraftCreate(client_action_id=str(uuid4()), session_id=sid,
        expected_session_revision=admission.session.revision, ref=ref(), appointment=appointment)
    result = base.service.complete_action(base.context(), admission.ticket, answer(admission),
        draft=DraftChange(command), draft_service=h.service, collection_update=CollectionUpdate(
            expected_digest=observed.digest, purpose="viewing", values=values,
            sources=[FieldSource(field="local_time", start=0, end=len(admission.request.text))],
        ))
    assert isinstance(result.pending_intent, ViewingReviewIntent)
    actual = h.service.get(base.context(), result.pending_intent.draft_id)
    assert actual.review is not None and actual.review.state == "valid"
    assert result.current_revision == admission.session.revision + 1
    assert isinstance(actual.review.lead_change, ReviewedLeadCreation)
    assert actual.review.lead_change.source_session_revision == result.current_revision
    return admission, actual.draft_id


def test_owned_time_reply_creates_real_shared_review() -> None:
    h = make_draft_harness()
    _, draft_id = create_viewing(h)
    assert h.service.get(h.base.context(), draft_id).state == "reviewable"
    assert h.counts() == (1, 1, 0, 0, 0, 0)


def test_material_correction_suspends_review_atomically() -> None:
    h = make_draft_harness()
    _, draft_id = create_viewing(h)
    base = h.base
    original = h.service.get(base.context(), draft_id)
    admission = begin(base, h.sessions[0], "My requirements are a quiet cabin")
    assert admission.ticket is not None
    observed = base.service.read_collection(base.context(), admission.ticket)
    assert observed.collection is not None
    values = observed.collection.values.model_copy(update={"requirements": ["quiet cabin"], "requirements_state": "provided"})
    result = base.service.complete_action(base.context(), admission.ticket, answer(admission),
        draft=DraftChange(BookingDraftUpdate(client_action_id=str(uuid4()), expected_revision=original.revision, intent="suspend"), draft_id),
        draft_service=h.service, collection_update=CollectionUpdate(expected_digest=observed.digest,
            purpose="viewing", values=values, sources=[FieldSource(field="requirements", start=0, end=len(admission.request.text))]))
    assert result.pending_intent.kind == "none"
    actual = h.service.get(base.context(), draft_id)
    assert actual.state == "suspended" and actual.revision == original.revision + 1
    assert actual.review is None or actual.review.state != "valid"
    assert h.counts()[2:] == (0, 0, 0, 0)


def test_refresh_cannot_reissue_a_different_collected_appointment() -> None:
    h = make_draft_harness()
    _, draft_id = create_viewing(h)
    base = h.base
    original = h.service.get(base.context(), draft_id)
    admission = begin(base, h.sessions[0], "Refresh my viewing review")
    assert admission.ticket is not None
    observed = base.service.read_collection(base.context(), admission.ticket)
    assert observed.collection is not None
    # A new settled value cannot silently be ignored by refresh_review's absent overrides.
    changed = observed.collection.values.model_copy(update={"local_time": "19:00"})
    assert changed.local_time != observed.collection.values.local_time
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        base.service.complete_action(base.context(), admission.ticket, answer(admission),
            draft=DraftChange(BookingDraftUpdate(client_action_id=str(uuid4()), expected_revision=original.revision,
                intent="refresh_review"), draft_id), draft_service=h.service,
            collection_update=CollectionUpdate(expected_digest=observed.digest, purpose="viewing", values=changed,
                sources=[FieldSource(field="local_time", start=0, end=len(admission.request.text))]))
    assert snapshot(base.store) == before


@pytest.mark.parametrize("value", ["1٢:30", "10:3٢", "24:00", "12", "00:60"])
def test_noncanonical_time_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        CollectionValues(local_time=value)
