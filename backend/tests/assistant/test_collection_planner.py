"""A9 pure planning/authority tests; actual Platform/T9 integration remains separate."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.api.schemas.leads import LeadRecord, NoLead
from app.api.schemas.sessions import ClarificationIntent, ClarificationReply, ViewingReviewIntent
from app.api.schemas.viewings import AppointmentSelection, BookingDraft
from app.assistant.collection_language import CollectionLanguageError, parse_collection_request
from app.assistant.collection_planner import CollectionObservation, matched_collection_question, plan_collection
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.core.config import DemoPolicy
from app.sessions.collection import (
    CollectionEnvelope, CollectionSnapshot, CollectionValues, LeadBinding, StoredFieldSource,
    collection_digest, collection_values_digest,
)
from app.viewings.scheduling import ViewingRules

from .conversation_fakes import ref
from .test_action_bridge import admission

NOW = "2026-09-24T21:15:00Z"
RULES = ViewingRules(DemoPolicy())


def intent(command: str, fields: list[tuple[str, str]] | None = None, reference=None) -> TurnIntent:
    return TurnIntent.model_validate({
        "operation": "smalltalk", "scope": "session", "deferred": ["viewing"],
        "collection": {"command": command, "fields": [{"field": name, "quote": quote} for name, quote in fields or []]},
        "references": [] if reference is None else [reference.model_dump(mode="json")],
    })


def envelope(turn, *, purpose="viewing", values=None, question=None, displayed=False, binding=None, supplied=()):
    value = CollectionValues() if values is None else values
    return CollectionEnvelope(
        collection_id=str(uuid4()), revision=2, owner_id=str(uuid4()),
        session_id=turn.session.session_id, store_generation=str(uuid4()),
        created_at="2026-09-24T21:00:00Z", expires_at="2026-09-24T21:30:00Z",
        source_message_id=str(uuid4()), updated_message_id=str(uuid4()), purpose=purpose,
        values=value, question=question, lead_binding=binding,
        displayed_values_digest=collection_values_digest(value, binding) if displayed else None,
        provenance=[StoredFieldSource(field=name, message_id=str(uuid4()), start=0, end=10) for name in supplied],
    )


def observed(value=None, *, lead=None, expired=False, now=NOW) -> CollectionObservation:
    return CollectionObservation(
        CollectionSnapshot(collection=value, digest=collection_digest(value), expired=expired, now=now, unresolved=None),
        NoLead(state="not_created") if lead is None else lead, None,
    )


def ready_values() -> CollectionValues:
    return CollectionValues(ref=ref("second"), local_date="2026-10-03", local_time="14:30")


def saved_lead(turn, *, refs=None) -> LeadRecord:
    return LeadRecord.model_validate({
        "lead_id": str(uuid4()), "journey_id": turn.session.journey_id, "revision": 6,
        "stage": "interested", "values": {
            "budget": {"state": "provided", "value": {"maximum": 5000000, "currency": "AED"}},
            "requirements": ["quiet cabin"], "selected_refs": [item.model_dump(mode="json") for item in (refs or [ref("second")])],
            "email": {"state": "provided", "value": "form-only@example.test"},
            "phone": {"state": "declined"},
        }, "booking_ids": [], "updated_at": NOW, "expires_at": "2026-12-23T21:15:00Z",
        "delivery": "local_only", "csv": {
            "state": "pending", "store_generation": str(uuid4()), "observed_at": NOW,
            "canonical_version": 1, "exported_version": None, "code": None,
        },
    })


@pytest.mark.parametrize("amount,maximum", [("45000", 4500000), ("62.5k", 6250000)])
def test_generic_cash_field_uses_original_bytes_and_minor_units(amount: str, maximum: int) -> None:
    text = f"My cash budget is AED {amount}"
    proposal = intent("fields", [("budget", text)])
    request = parse_collection_request(text, proposal, matched_question=None)
    turn = admission(text)
    state = observed(envelope(turn, purpose="local_enquiry"))
    plan = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    assert plan.collection_update.values.budget.value.maximum == maximum
    source = plan.collection_update.sources[0]
    assert turn.request.text[source.start:source.end] == text
    assert plan.lead is None and plan.draft is None


@pytest.mark.parametrize("text,command", [
    ("Save this local enquiry?", "save_enquiry"),
    ("Discard this unsubmitted viewing draft?", "discard_draft"),
])
def test_question_punctuation_cannot_become_effect_permission(text: str, command: str) -> None:
    with pytest.raises(CollectionLanguageError):
        parse_collection_request(text, intent(command), matched_question=None)


@pytest.mark.parametrize("currency", ["JPY", "KWD", "ZZZ"])
def test_unsupported_currency_does_not_invent_minor_unit_scale(currency: str) -> None:
    text = f"My cash budget is {currency} 50000"
    with pytest.raises(CollectionLanguageError):
        parse_collection_request(text, intent("fields", [("budget", text)]), matched_question=None)


@pytest.mark.parametrize("text", [
    "Do not prepare a viewing of the first Honda",
    "Prepare a viewing of the first Honda if it has warranty",
    "Prepare a viewing of the first Honda 2019",
    "Prepare a viewing of the first Honda or the Toyota",
])
def test_positive_model_reference_substring_cannot_hide_residual_instruction(text: str) -> None:
    proposal = intent("start_viewing", reference=ReferenceRequest(source="ordinal", position=0, make="Honda", quote="the first Honda"))
    with pytest.raises(CollectionLanguageError):
        parse_collection_request(text, proposal, matched_question=None)


def test_exact_requirements_and_quoted_action_words_remain_data() -> None:
    text = 'My requirements are "quiet café cabin" and "save this local enquiry"'
    request = parse_collection_request(text, intent("fields", [("requirements", text)]), matched_question=None)
    assert request.fields[0].value == ("quiet café cabin", "save this local enquiry")
    assert request.command == "fields"
    with pytest.raises(CollectionLanguageError):
        parse_collection_request(text, intent("fields", [("requirements", '"quiet café cabin"')]), matched_question=None)


def test_private_bare_time_requires_the_actual_echoed_viewing_question() -> None:
    turn = admission("14:30")
    question = ClarificationIntent(kind="clarification", intent_id=str(uuid4()), created_revision=7,
                                   purpose="viewing_details", targets=["appointment"], question="Which time?")
    turn.session.pending_intent = question
    state = observed(envelope(turn, question=question))
    proposal = intent("fields", [("local_time", "14:30")])
    with pytest.raises(CollectionLanguageError):
        parse_collection_request(turn.request.text, proposal, matched_question=matched_collection_question(turn, state))
    turn.request.clarification_reply = ClarificationReply(intent_id=question.intent_id, created_revision=7)
    parsed = parse_collection_request(turn.request.text, proposal, matched_question=matched_collection_question(turn, state))
    assert parsed.fields[0].value == "14:30"


def test_partial_relative_date_is_concrete_and_new_question_binds_actual_f() -> None:
    text = "Viewing date: tomorrow"
    turn = admission(text)
    state = observed(envelope(turn, values=CollectionValues(ref=ref("second"))))
    request = parse_collection_request(text, intent("fields", [("local_date", text)]), matched_question=None)
    plan = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    assert plan.collection_update.values.local_date == "2026-09-26"
    assert "Dubai date: 2026-09-26" in plan.result.text
    assert plan.collection_update.values.local_time is None
    assert plan.collection_update.question.created_revision == turn.session.revision + 1
    assert plan.result.pending_intent == plan.collection_update.question


@pytest.mark.parametrize("expired", [False, True])
def test_no_save_from_bare_yes_even_with_a_matching_question(expired: bool) -> None:
    turn = admission("yes")
    question = ClarificationIntent(kind="clarification", intent_id=str(uuid4()), created_revision=7,
                                   purpose="action_intent", targets=["confirmation"], question="Save enquiry?")
    turn.session.pending_intent = question
    turn.request.clarification_reply = ClarificationReply(intent_id=question.intent_id, created_revision=7)
    state = observed(envelope(turn, purpose="local_enquiry", question=question, displayed=True), expired=expired)
    with pytest.raises(CollectionLanguageError):
        parse_collection_request("yes", intent("save_enquiry"), matched_question=matched_collection_question(turn, state))


def test_exact_displayed_correction_preserves_owned_form_contacts_and_action_identity() -> None:
    turn = admission("Update my saved local enquiry")
    lead = saved_lead(turn)
    values = CollectionValues(budget=lead.values.budget, requirements=lead.values.requirements,
                              requirements_state="provided", ref=lead.values.selected_refs[0])
    binding = LeadBinding(lead_id=lead.lead_id, revision=lead.revision)
    question = ClarificationIntent(kind="clarification", intent_id=str(uuid4()), created_revision=7,
                                   purpose="action_intent", targets=["confirmation"], question="Correct enquiry?")
    turn.session.pending_intent = question
    turn.request.clarification_reply = ClarificationReply(intent_id=question.intent_id, created_revision=7)
    state = observed(envelope(turn, purpose="local_enquiry", values=values, binding=binding, question=question, displayed=True), lead=lead)
    request = parse_collection_request(turn.request.text, intent("correct_enquiry"), matched_question=question)
    plan = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    again = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    assert plan.lead.command.values.email == lead.values.email
    assert plan.lead.command.values.phone == lead.values.phone
    assert plan.lead.command.expected_revision == 6
    assert plan.lead.command.client_action_id == again.lead.command.client_action_id
    assert "email" not in values.model_dump() and "phone" not in values.model_dump()
    bad = state.snapshot.collection.model_copy(update={"displayed_values_digest": "0" * 64})
    with pytest.raises(CollectionLanguageError):
        plan_collection(turn, observed(bad, lead=lead), request, resolved_ref=None, rules=RULES)
    with pytest.raises(CollectionLanguageError):
        plan_collection(turn, observed(state.snapshot.collection, lead=lead, expired=True), request, resolved_ref=None, rules=RULES)


@pytest.mark.parametrize("multiple", [False, True])
def test_new_correction_collection_cannot_drop_untouched_values_or_extra_refs(multiple: bool) -> None:
    turn = admission("Review my local enquiry")
    lead = saved_lead(turn, refs=[ref("second"), ref("third")] if multiple else None)
    state = observed(envelope(turn, purpose="local_enquiry"), lead=lead)
    request = parse_collection_request(turn.request.text, intent("review_enquiry"), matched_question=None)
    with pytest.raises(CollectionLanguageError):
        plan_collection(turn, state, request, resolved_ref=None, rules=RULES)


def test_prepare_viewing_uses_accepted_a_and_never_manufactures_confirmation() -> None:
    turn = admission("Prepare the viewing review")
    state = observed(envelope(turn, values=ready_values()))
    request = parse_collection_request(turn.request.text, intent("prepare_viewing"), matched_question=None)
    plan = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    assert plan.draft.command.expected_session_revision == turn.session.revision
    assert plan.draft.command.appointment.starts_at_utc == "2026-10-03T10:30:00Z"
    assert plan.result.operation is None and plan.result.actions.lead.state == "not_requested"
    assert plan.collection_update.question is None


def test_reference_uses_real_selection_seam_and_only_changed_field_sources() -> None:
    turn = admission("Use the first Honda")
    proposal = intent("fields", reference=ReferenceRequest(source="ordinal", position=0, make="Honda", quote="the first Honda"))
    parsed = parse_collection_request(turn.request.text, proposal, matched_question=None)
    state = observed(envelope(turn, purpose="local_enquiry"))
    plan = plan_collection(turn, state, parsed, resolved_ref=ref("second"), rules=RULES)
    assert plan.selection == ref("second")
    assert plan.update.selected_ref == turn.session.selected_ref
    assert [source.field for source in plan.collection_update.sources] == ["ref"]
    same = observed(envelope(turn, purpose="local_enquiry", values=CollectionValues(ref=ref("second"))))
    replay_value = plan_collection(turn, same, parsed, resolved_ref=ref("second"), rules=RULES)
    assert replay_value.collection_update.sources == []
    assert replay_value.selection == ref("second")


def current_draft(turn, *, status="suspended", source="second", instant="2026-10-03T10:30:00Z") -> BookingDraft:
    return BookingDraft(
        draft_id=str(uuid4()), session_id=turn.session.session_id, revision=4,
        ref=ref(source), appointment=AppointmentSelection(starts_at_utc=instant),
        state=status, expires_at="2026-10-03T10:30:00Z", required_fields=[], review=None,
    )


@pytest.mark.parametrize("different", [False, True])
def test_existing_draft_refreshes_or_edits_only_the_changed_detail(different: bool) -> None:
    turn = admission("Prepare the viewing review")
    draft = current_draft(turn, instant="2026-10-03T09:30:00Z" if different else "2026-10-03T10:30:00Z")
    turn.session.current_draft_id = draft.draft_id
    state = replace(observed(envelope(turn, values=ready_values())), draft=draft)
    request = parse_collection_request(turn.request.text, intent("prepare_viewing"), matched_question=None)
    plan = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    assert plan.draft.command.intent == ("edit" if different else "refresh_review")
    assert plan.draft.command.ref is None
    assert (plan.draft.command.appointment is not None) == different


def test_material_viewing_correction_suspends_without_installing_a_new_question() -> None:
    text = "Viewing time: 15:00"
    turn = admission(text)
    draft = current_draft(turn, status="needs_details")
    turn.session.current_draft_id = draft.draft_id
    state = replace(observed(envelope(turn, values=ready_values())), draft=draft)
    request = parse_collection_request(text, intent("fields", [("local_time", text)]), matched_question=None)
    plan = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    assert plan.draft.command.intent == "suspend"
    assert plan.update is None and plan.collection_update.question is None
    assert plan.collection_update.values.local_time == "15:00"
    assert [item.field for item in plan.collection_update.sources] == ["local_time"]


@pytest.mark.parametrize("status", ["resolved", "unresolved"])
def test_submitted_viewing_cannot_be_discarded_or_replaced(status: str) -> None:
    turn = admission("Stop this viewing preparation")
    draft = current_draft(turn, status=status)
    turn.session.current_draft_id = draft.draft_id
    state = replace(observed(envelope(turn, values=ready_values())), draft=draft)
    request = parse_collection_request(turn.request.text, intent("stop_viewing"), matched_question=None)
    with pytest.raises(CollectionLanguageError):
        plan_collection(turn, state, request, resolved_ref=None, rules=RULES)


def test_stop_enquiry_preserves_a_separate_viewing_draft_and_review() -> None:
    turn = admission("Stop this enquiry preparation")
    draft = current_draft(turn)
    turn.session.current_draft_id = draft.draft_id
    turn.session.pending_intent = ViewingReviewIntent(
        kind="viewing_review", draft_id=draft.draft_id, review_id=str(uuid4()), operation_key="k" * 43,
    )
    state = replace(observed(envelope(turn, purpose="local_enquiry")), draft=draft)
    request = parse_collection_request(turn.request.text, intent("stop_enquiry"), matched_question=None)
    plan = plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    assert plan.draft is None and plan.lead is None and plan.update is None
    assert plan.collection_update.values is None
    assert plan.result.pending_intent == turn.session.pending_intent


def test_enquiry_field_cannot_suspend_a_separate_viewing_draft() -> None:
    text = 'My requirements are "quiet cabin"'
    turn = admission(text)
    draft = current_draft(turn, status="needs_details")
    turn.session.current_draft_id = draft.draft_id
    state = replace(observed(envelope(turn, purpose="local_enquiry")), draft=draft)
    request = parse_collection_request(text, intent("fields", [("requirements", text)]), matched_question=None)
    with pytest.raises(CollectionLanguageError):
        plan_collection(turn, state, request, resolved_ref=None, rules=RULES)


def test_equal_saved_values_do_not_substitute_for_the_exact_lead_binding() -> None:
    turn = admission("Prepare the viewing review")
    lead = saved_lead(turn)
    values = ready_values().model_copy(update={
        "budget": lead.values.budget, "requirements": lead.values.requirements, "requirements_state": "provided",
    })
    state = observed(envelope(turn, values=values), lead=lead)
    request = parse_collection_request(turn.request.text, intent("prepare_viewing"), matched_question=None)
    with pytest.raises(CollectionLanguageError):
        plan_collection(turn, state, request, resolved_ref=None, rules=RULES)
    bound = observed(envelope(turn, values=values, binding=LeadBinding(lead_id=lead.lead_id, revision=lead.revision)), lead=lead)
    plan = plan_collection(turn, bound, request, resolved_ref=None, rules=RULES)
    assert plan.draft is not None
    assert plan.collection_update.lead_binding == LeadBinding(lead_id=lead.lead_id, revision=lead.revision)
