"""Authority and late-write cases over real services, with synthetic Inventory."""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.api.schemas.leads import ContactValue, LeadUpdateRequest, ReviewedExistingLead
from app.api.schemas.sessions import ClarificationIntent, ClarificationReply, MessageRequest
from app.api.schemas.viewings import BookingDraftCreate, BookingDraftUpdate
from app.core.errors import ApiFailure
from app.leads.service import LeadService
from app.sessions.collection import CollectionUpdate, CollectionValues, FieldSource, LeadBinding
from app.sessions.service import DraftChange, LeadChange
from tests.platform.collection_cases import begin, collect
from tests.platform.session_cases import answer, ref
from tests.platform.test_collection_turn import create_viewing, save_turn
from tests.platform.test_identity import snapshot
from tests.transactions.draft_fixtures import make_draft_harness
from tests.transactions.lead_fixtures import LeadInventoryFake, buyer_values, correction, make_lead_harness, save_request


@pytest.mark.parametrize("wrong_part", ["id", "revision"])
def test_wrong_echo_is_rejected_without_admitting_message(wrong_part: str) -> None:
    h = make_lead_harness()
    base, sid = h.sessions, h.session_ids[0]
    collect(base, sid, CollectionValues(), ask="save")
    state = base.service.get(base.context(), sid)
    question = state.pending_intent
    assert isinstance(question, ClarificationIntent)
    reply = ClarificationReply(
        intent_id=str(uuid4()) if wrong_part == "id" else question.intent_id,
        created_revision=question.created_revision - 1 if wrong_part == "revision" else question.created_revision,
    )
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        base.service.begin(base.context(), sid, MessageRequest(
            client_message_id=str(uuid4()), expected_revision=state.revision,
            text="Save these exact local enquiry values", clarification_reply=reply,
        ))
    assert snapshot(base.store) == before


def test_draft_question_cannot_authorize_a_message_without_exact_echo() -> None:
    h = make_draft_harness()
    base, sid = h.base, h.sessions[0]
    appointment = h.appointment()
    local = datetime.fromisoformat(appointment.starts_at_utc).astimezone(ZoneInfo("Asia/Dubai"))
    values = CollectionValues(ref=ref(), local_date=local.date().isoformat(), local_time=local.strftime("%H:%M"))
    collect(base, sid, values, purpose="viewing", ask="time")
    state = base.service.get(base.context(), sid)
    admitted = base.service.begin(base.context(), sid, MessageRequest(
        client_message_id=str(uuid4()), expected_revision=state.revision,
        text="Prepare my viewing at this exact time",
    ))
    assert admitted.ticket is not None
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        base.service.complete_action(base.context(), admitted.ticket, answer(admitted),
            draft=DraftChange(BookingDraftCreate(client_action_id=str(uuid4()), session_id=sid,
                expected_session_revision=admitted.session.revision, ref=ref(), appointment=appointment)),
            draft_service=h.service)
    assert snapshot(base.store) == before


def test_displayed_lead_summary_requires_the_original_exact_echo() -> None:
    h = make_lead_harness()
    base, sid = h.sessions, h.session_ids[0]
    values = buyer_values().model_copy(update={"phone": ContactValue(state="missing")})
    collect(base, sid, CollectionValues(requirements=values.requirements, requirements_state="provided"), ask="save")
    current = base.service.get(base.context(), sid)
    admitted = base.service.begin(base.context(), sid, MessageRequest(
        client_message_id=str(uuid4()), expected_revision=current.revision,
        text="Save these exact local enquiry values",
    ))
    assert admitted.ticket is not None
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        base.service.complete_action(base.context(), admitted.ticket, answer(admitted),
            lead=LeadChange(save_request(sid, values)), lead_service=h.service)
    assert snapshot(base.store) == before


@pytest.mark.parametrize("late_change", ["superseded", "expired"])
def test_collection_effect_rechecks_currentness_after_outside_preparation(
    late_change: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = make_lead_harness()
    base = h.sessions
    admitted, command = save_turn(h)
    assert admitted.ticket is not None
    original = h.service.prepare_change
    before_write = None

    def prepare(*args: Any, **kwargs: Any) -> Any:
        nonlocal before_write
        prepared = original(*args, **kwargs)
        if late_change == "superseded":
            begin(base, admitted.session.session_id, "A separate follow-up question")
        else:
            base.clock.value += timedelta(minutes=31)
        before_write = snapshot(base.store)
        return prepared

    monkeypatch.setattr(h.service, "prepare_change", prepare)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        base.service.complete_action(base.context(), admitted.ticket, answer(admitted), lead=command, lead_service=h.service)
    assert before_write is not None and snapshot(base.store) == before_write
    assert h.counts() == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("failure", [None, "contacts", "stale_binding"])
def test_bound_chat_correction_preserves_exact_form_contacts(failure: str | None) -> None:
    h = make_lead_harness()
    base, sid = h.sessions, h.session_ids[0]
    supplied = buyer_values().model_copy(update={
        "email": ContactValue(state="provided", value="buyer@example.test"),
        "phone": ContactValue(state="provided", value="+971501234567"),
    })
    original = h.service.save(base.context(), save_request(sid, supplied)).lead
    collected = CollectionValues(requirements=["A foldable bicycle must fit"], requirements_state="provided")
    binding = LeadBinding(lead_id=original.lead_id, revision=original.revision)
    collect(base, sid, collected, ask="save", binding=binding)
    if failure == "stale_binding":
        h.service.update(base.context(), original.lead_id, correction(sid, original.revision, original.values))
    admitted = begin(base, sid, "Correct the local enquiry to these exact needs")
    assert admitted.ticket is not None
    corrected = original.values.model_copy(update={"requirements": collected.requirements})
    if failure == "contacts":
        corrected = corrected.model_copy(update={"email": ContactValue(state="missing")})
    command = LeadChange(LeadUpdateRequest(client_action_id=str(uuid4()), session_id=sid,
        expected_revision=original.revision, intent="correct_local_enquiry", values=corrected), original.lead_id)
    before = snapshot(base.store)
    if failure is not None:
        with pytest.raises(ApiFailure, match="VALIDATION_ERROR" if failure == "contacts" else "REVISION_CONFLICT"):
            base.service.complete_action(base.context(), admitted.ticket, answer(admitted), lead=command, lead_service=h.service)
        assert snapshot(base.store) == before
    else:
        saved = base.service.complete_action(base.context(), admitted.ticket, answer(admitted), lead=command, lead_service=h.service)
        assert saved.actions.lead.state == "succeeded"
        actual = saved.actions.lead.result.lead
        assert actual.lead_id == original.lead_id and actual.revision == original.revision + 1
        assert actual.values.requirements == collected.requirements
        assert (actual.values.email, actual.values.phone) == (original.values.email, original.values.phone)


def test_unsaved_rich_needs_cannot_be_silently_dropped_from_review() -> None:
    h = make_draft_harness()
    base, sid = h.base, h.sessions[0]
    appointment = h.appointment()
    local = datetime.fromisoformat(appointment.starts_at_utc).astimezone(ZoneInfo("Asia/Dubai"))
    collect(base, sid, CollectionValues(ref=ref(), local_date=local.date().isoformat(),
        local_time=local.strftime("%H:%M"), requirements=["Quiet cabin"], requirements_state="provided"), purpose="viewing")
    admitted = begin(base, sid, "Prepare the viewing for these exact needs")
    assert admitted.ticket is not None
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        base.service.complete_action(base.context(), admitted.ticket, answer(admitted),
            draft=DraftChange(BookingDraftCreate(client_action_id=str(uuid4()), session_id=sid,
                expected_session_revision=admitted.session.revision, ref=ref(), appointment=appointment)), draft_service=h.service)
    assert snapshot(base.store) == before


@pytest.mark.parametrize("matching_values", [True, False])
def test_rich_review_uses_exact_saved_lead_binding_and_values(matching_values: bool) -> None:
    h = make_draft_harness()
    base, sid = h.base, h.sessions[0]
    leads = LeadService(base.auth, inventory=LeadInventoryFake(base))
    supplied = buyer_values().model_copy(update={"selected_refs": [ref()]})
    saved = leads.save(base.context(), save_request(sid, supplied)).lead
    appointment = h.appointment()
    local = datetime.fromisoformat(appointment.starts_at_utc).astimezone(ZoneInfo("Asia/Dubai"))
    values = CollectionValues(ref=ref(), local_date=local.date().isoformat(), local_time=local.strftime("%H:%M"),
        requirements=supplied.requirements if matching_values else ["Unsaved different needs"], requirements_state="provided")
    collect(base, sid, values, purpose="viewing", binding=LeadBinding(lead_id=saved.lead_id, revision=saved.revision))
    admitted = begin(base, sid, "Prepare my viewing with the saved enquiry")
    assert admitted.ticket is not None
    change = DraftChange(BookingDraftCreate(client_action_id=str(uuid4()), session_id=sid,
        expected_session_revision=admitted.session.revision, ref=ref(), appointment=appointment))
    before = snapshot(base.store)
    if not matching_values:
        with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
            base.service.complete_action(base.context(), admitted.ticket, answer(admitted), draft=change, draft_service=h.service)
        assert snapshot(base.store) == before
    else:
        result = base.service.complete_action(base.context(), admitted.ticket, answer(admitted), draft=change, draft_service=h.service)
        assert result.pending_intent.kind == "viewing_review"
        actual = h.service.get(base.context(), result.pending_intent.draft_id)
        assert actual.review is not None and isinstance(actual.review.lead_change, ReviewedExistingLead)
        assert (actual.review.lead_change.lead_id, actual.review.lead_change.expected_revision) == (saved.lead_id, saved.revision)


def test_suspended_date_correction_reports_accepted_temporary_values() -> None:
    h = make_draft_harness()
    _, draft_id = create_viewing(h)
    base, sid = h.base, h.sessions[0]
    original = h.service.get(base.context(), draft_id)
    admitted = begin(base, sid, "Change the viewing date to 2026-10-09")
    assert admitted.ticket is not None
    observed = base.service.read_collection(base.context(), admitted.ticket)
    assert observed.collection is not None
    values = observed.collection.values.model_copy(update={"local_date": "2026-10-09"})
    assert values.local_date != observed.collection.values.local_date
    result = base.service.complete_action(base.context(), admitted.ticket, answer(admitted),
        draft=DraftChange(BookingDraftUpdate(client_action_id=str(uuid4()), expected_revision=original.revision,
            intent="suspend"), draft_id), draft_service=h.service,
        collection_update=CollectionUpdate(expected_digest=observed.digest, purpose="viewing", values=values,
            sources=[FieldSource(field="local_date", start=26, end=36)]))
    assert "Temporary viewing details (Dubai): 2026-10-09" in result.text
    assert "This change does not book a viewing." in result.text
    assert h.service.get(base.context(), draft_id).state == "suspended"
    assert h.counts()[2:] == (0, 0, 0, 0)
