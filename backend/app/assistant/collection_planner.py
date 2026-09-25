"""Pure collection transitions using exact Platform state and shared command DTOs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4, uuid5

from app.api.schemas.common import InventoryRef
from app.api.schemas.leads import (
    BudgetValue, ContactValue, LeadRecord, LeadSaveRequest, LeadUpdateRequest, LeadValues, NoLead,
)
from app.api.schemas.sessions import (
    ActionUnresolved, ClarificationIntent, MessageResult, NoPendingIntent, UnresolvedOperationIntent,
    ViewingReviewIntent,
)
from app.api.schemas.viewings import BookingDraft, BookingDraftCreate, BookingDraftUpdate
from app.sessions.collection import (
    CollectionSnapshot, CollectionUpdate, CollectionValues, LeadBinding, collection_values_digest,
)
from app.sessions.service import DraftChange, LeadChange, TurnAdmission
from app.sessions.state import SessionContent
from app.viewings.scheduling import ViewingRules

from .collection_fields import appointment_selection, viewing_date, viewing_time
from .collection_language import CollectionLanguageError, CollectionRequest


@dataclass(frozen=True)
class CollectionObservation:
    snapshot: CollectionSnapshot
    lead: LeadRecord | NoLead | None
    draft: BookingDraft | None


@dataclass(frozen=True)
class CollectionPlan:
    result: MessageResult
    update: SessionContent | None = None
    collection_update: CollectionUpdate | None = None
    lead: LeadChange | None = None
    draft: DraftChange | None = None
    selection: InventoryRef | None = None


def collection_result(admission: TurnAdmission, text: str, *, provider: bool = True) -> MessageResult:
    return MessageResult(
        client_message_id=admission.request.client_message_id,
        session_id=admission.session.session_id,
        turn_revision=admission.session.revision,
        current_revision=admission.session.revision,
        state="answered", text=text, pending_intent=admission.session.pending_intent,
        persistence="not_saved", provider_state="available" if provider else "not_used",
    )


def matched_collection_question(
    admission: TurnAdmission, observation: CollectionObservation,
) -> ClarificationIntent | None:
    stored = observation.snapshot.collection
    pending, reply = admission.session.pending_intent, admission.request.clarification_reply
    if (
        stored is None or observation.snapshot.expired or stored.question is None
        or not isinstance(pending, ClarificationIntent) or pending != stored.question
        or reply is None
        or (reply.intent_id, reply.created_revision) != (pending.intent_id, pending.created_revision)
    ):
        return None
    return pending


def _content(admission: TurnAdmission, pending: object) -> SessionContent:
    session = admission.session
    return SessionContent.model_validate({
        "criteria": session.criteria.model_dump(mode="json"),
        "selected_ref": None if session.selected_ref is None else session.selected_ref.model_dump(mode="json"),
        "active_presentation_id": session.active_presentation_id,
        "current_draft_id": session.current_draft_id,
        "pending_intent": pending,
    })


def _question(
    admission: TurnAdmission, purpose: Literal["listing_reference", "viewing_details", "action_intent"],
    text: str,
) -> ClarificationIntent:
    target = {"listing_reference": "selected_ref", "viewing_details": "appointment", "action_intent": "confirmation"}[purpose]
    return ClarificationIntent(
        kind="clarification", intent_id=str(uuid4()), created_revision=admission.session.revision + 1,
        purpose=purpose, targets=[target], question=text,
    )


def _action_id(admission: TurnAdmission, domain: str) -> str:
    return str(uuid5(UUID(admission.message_id), f"{domain}:v1"))


def _lead_binding(lead: LeadRecord | NoLead | None) -> LeadBinding | None:
    if lead is None:
        raise CollectionLanguageError("The current local enquiry could not be read; no change was made.")
    return LeadBinding(lead_id=lead.lead_id, revision=lead.revision) if isinstance(lead, LeadRecord) else None


def _summary(values: CollectionValues, binding: LeadBinding | None) -> str:
    budget = values.budget
    budget_text: str
    if budget.value is None:
        budget_text = budget.state
    else:
        bounds = budget.value
        if bounds.currency != "AED":
            raise CollectionLanguageError("This budget uses a currency outside the supported AED chat entry. Review it in the local enquiry form without changing its units.")
        if bounds.minimum is not None and bounds.maximum is not None:
            budget_text = (
                f"{bounds.currency} {bounds.minimum / 100:.2f} "
                f"to {bounds.maximum / 100:.2f} cash"
            )
        elif bounds.maximum is not None:
            budget_text = f"{bounds.currency} up to {bounds.maximum / 100:.2f} cash"
        else:
            # BudgetRange validation requires at least one bound.
            assert bounds.minimum is not None
            budget_text = f"{bounds.currency} from {bounds.minimum / 100:.2f} cash"
    needs = "; ".join(values.requirements) if values.requirements_state == "provided" else values.requirements_state
    car = "missing" if values.ref is None else f"listing {values.ref.source_id} ({values.ref.namespace})"
    verb = "Update my saved local enquiry" if binding else "Save this local enquiry"
    return (
        f"Local enquiry to review: cash budget {budget_text}; requirements {needs}; car {car}. "
        "Contact details are optional and managed in the local enquiry form; existing form contacts are preserved. "
        "Saving stores this enquiry locally and queues its local CSV projection; nothing is sent to a dealer. "
        f"To save these exact reviewed values, reply: {verb}."
    )


def _check_correction_baseline(
    observation: CollectionObservation, values: CollectionValues,
) -> None:
    current, old = observation.lead, observation.snapshot.collection
    if not isinstance(current, LeadRecord):
        return
    if len(current.values.selected_refs) > 1:
        raise CollectionLanguageError("This enquiry contains several cars. Use the local enquiry form to correct it without losing those references.")
    supplied = {source.field for source in old.provenance} if old is not None else set()
    differences = {
        "budget": current.values.budget != values.budget,
        "requirements": current.values.requirements != values.requirements,
        "ref": current.values.selected_refs != ([] if values.ref is None else [values.ref]),
    }
    missing = [field for field, different in differences.items() if different and field not in supplied]
    if missing:
        raise CollectionLanguageError(
            "Restate the existing " + ", ".join(missing) + " or explicitly change those fields before review; untouched enquiry values cannot be silently removed."
        )


def unresolved_collection_plan(
    admission: TurnAdmission, observation: CollectionObservation, *, provider: bool = False,
) -> CollectionPlan:
    original = observation.snapshot.unresolved
    if original is None:
        raise CollectionLanguageError("No original unresolved command was supplied.")
    result = collection_result(
        admission, "The original local action is unresolved. Keep its original message and action identity; "
        "do not submit it as a new request. Current records alone cannot prove its outcome.", provider=provider,
    )
    if original.kind == "lead":
        result.actions.lead = ActionUnresolved(
            state="unresolved", client_action_id=original.command.client_action_id,
            submitted_store_generation=original.submitted_store_generation,
            recovery="operator_reconciliation",
        )
    return CollectionPlan(result)


def plan_collection(
    admission: TurnAdmission, observation: CollectionObservation, requested: CollectionRequest,
    *, resolved_ref: InventoryRef | None, rules: ViewingRules,
) -> CollectionPlan:
    snapshot, session = observation.snapshot, admission.session
    if snapshot.unresolved is not None:
        return unresolved_collection_plan(admission, observation)
    old = snapshot.collection
    pending = session.pending_intent
    if isinstance(pending, UnresolvedOperationIntent) or (
        observation.draft is not None and observation.draft.state in {"unresolved", "resolved"}
    ):
        raise CollectionLanguageError("Read the original viewing outcome before another change; this cannot cancel a submitted booking.")
    if isinstance(pending, ClarificationIntent) and (old is None or pending != old.question):
        raise CollectionLanguageError(pending.question)
    start = requested.command in {"start_enquiry", "start_viewing"}
    if start:
        if old is not None and not snapshot.expired:
            raise CollectionLanguageError("A preparation is already active. Continue it or explicitly stop that preparation first.")
        if session.current_draft_id is not None:
            raise CollectionLanguageError("Read or discard the current unsubmitted draft before starting another preparation.")
        purpose: Literal["local_enquiry", "viewing"] = "viewing" if requested.command == "start_viewing" else "local_enquiry"
        values, binding = CollectionValues(), None
    else:
        if old is None or snapshot.expired:
            raise CollectionLanguageError("Start a new enquiry or viewing preparation explicitly; the earlier temporary details are unavailable or expired.")
        purpose, values, binding = old.purpose, old.values, old.lead_binding
    values = CollectionValues.model_validate(values.model_dump(mode="json"))
    if requested.command in {"stop_enquiry", "stop_viewing", "discard_draft"}:
        expected = "local_enquiry" if requested.command == "stop_enquiry" else "viewing"
        if purpose != expected:
            raise CollectionLanguageError("Name the active preparation you want to stop.")
        draft = observation.draft
        change = None
        if purpose == "viewing" and draft is not None and draft.state != "discarded":
            change = DraftChange(BookingDraftUpdate(
                client_action_id=_action_id(admission, "draft"), expected_revision=draft.revision, intent="discard",
            ), draft_id=draft.draft_id)
        if requested.command == "discard_draft" and change is None:
            raise CollectionLanguageError("There is no current unsubmitted draft to discard.")
        update = CollectionUpdate(expected_digest=snapshot.digest, purpose=purpose, values=None)
        result = collection_result(admission, "The uncommitted preparation has been abandoned. Previously saved enquiries and preferences remain.")
        own_question = old is not None and old.question is not None and pending == old.question
        if own_question or (purpose == "viewing" and change is not None):
            result.pending_intent = NoPendingIntent(kind="none")
        public_update = _content(admission, {"kind": "none"}) if own_question and change is None else None
        return CollectionPlan(result, public_update, update, draft=change)

    if purpose == "local_enquiry" and session.current_draft_id is not None:
        raise CollectionLanguageError("A separate viewing draft is active. Finish or explicitly discard that draft before changing this enquiry preparation.")

    data = values.model_dump(mode="json")
    now = datetime.fromisoformat(snapshot.now.replace("Z", "+00:00"))
    for field in requested.fields:
        if field.name == "ref":
            if resolved_ref is None:
                raise CollectionLanguageError("Choose the exact car before continuing.")
            data["ref"] = resolved_ref.model_dump(mode="json")
        elif field.name == "budget":
            value = field.value if isinstance(field.value, BudgetValue) else BudgetValue(state="missing" if field.value == "clear" else "declined")
            data["budget"] = value.model_dump(mode="json")
        elif field.name == "requirements":
            data["requirements"] = list(field.value) if isinstance(field.value, tuple) else []
            data["requirements_state"] = "provided" if isinstance(field.value, tuple) else "missing" if field.value == "clear" else "declined"
        elif field.name == "local_date":
            if purpose != "viewing" or not isinstance(field.value, str):
                raise CollectionLanguageError("A viewing date belongs to an active viewing preparation.")
            data["local_date"] = viewing_date(field.value, rules=rules, now=now)
        elif field.name == "local_time":
            if purpose != "viewing" or not isinstance(field.value, str):
                raise CollectionLanguageError("A viewing time belongs to an active viewing preparation.")
            data["local_time"] = viewing_time(field.value)
    updated = CollectionValues.model_validate(data)
    changed_fields = {
        "budget": updated.budget != values.budget,
        "requirements": (updated.requirements_state, updated.requirements) != (values.requirements_state, values.requirements),
        "ref": updated.ref != values.ref,
        "local_date": updated.local_date != values.local_date,
        "local_time": updated.local_time != values.local_time,
    }
    sources = [field.source for field in requested.fields if changed_fields[field.name]]
    selection = resolved_ref if resolved_ref is not None and resolved_ref != session.selected_ref else None
    changed = updated != values
    if requested.command == "fields" and not changed and isinstance(pending, ViewingReviewIntent):
        return CollectionPlan(collection_result(admission, "Those preparation values are unchanged. Use the current shared viewing review for its actual terms."))
    change = None
    draft = observation.draft
    if changed and draft is not None and draft.state not in {"discarded", "suspended"}:
        change = DraftChange(BookingDraftUpdate(
            client_action_id=_action_id(admission, "draft"), expected_revision=draft.revision, intent="suspend",
        ), draft_id=draft.draft_id)
    question = None
    display = False
    text = "Temporary details updated; no local enquiry or viewing has been confirmed."
    if purpose == "viewing":
        text += f" Dubai date: {updated.local_date or 'not set'}; time: {updated.local_time or 'not set'}."

    if requested.command in {"save_enquiry", "correct_enquiry"}:
        assert old is not None
        matched = matched_collection_question(admission, observation)
        if (
            matched is None or matched.purpose != "action_intent" or matched.targets != ["confirmation"]
            or old.displayed_values_digest != collection_values_digest(values, old.lead_binding)
            or requested.fields
        ):
            raise CollectionLanguageError("Review the current local enquiry, then explicitly save those exact values through its current question.")
        actual_binding = _lead_binding(observation.lead)
        if actual_binding != old.lead_binding:
            raise CollectionLanguageError("The local enquiry changed. Review it again before correcting it.")
        correcting = requested.command == "correct_enquiry"
        if correcting != (actual_binding is not None):
            raise CollectionLanguageError("Use the exact save or correction choice shown in the current enquiry review.")
        current = observation.lead
        payload = LeadValues(
            budget=values.budget, requirements=values.requirements,
            selected_refs=[] if values.ref is None else [values.ref],
            email=current.values.email if isinstance(current, LeadRecord) else ContactValue(state="missing"),
            phone=current.values.phone if isinstance(current, LeadRecord) else ContactValue(state="missing"),
        )
        if actual_binding is None:
            lead = LeadChange(LeadSaveRequest(
                client_action_id=_action_id(admission, "lead"), session_id=session.session_id,
                intent="save_local_enquiry", values=payload,
            ))
        else:
            lead = LeadChange(LeadUpdateRequest(
                client_action_id=_action_id(admission, "lead"), session_id=session.session_id,
                expected_revision=actual_binding.revision, intent="correct_local_enquiry", values=payload,
            ), lead_id=actual_binding.lead_id)
        # Platform clears the exact save question/digest and binds the actual saved lead.
        return CollectionPlan(collection_result(admission, "Saving the reviewed local enquiry."), lead=lead)

    if requested.command == "review_enquiry":
        binding = _lead_binding(observation.lead)
        _check_correction_baseline(observation, updated)
        if isinstance(pending, ViewingReviewIntent):
            if draft is None:
                raise CollectionLanguageError("The exact current draft could not be read.")
            change = DraftChange(BookingDraftUpdate(
                client_action_id=_action_id(admission, "draft"), expected_revision=draft.revision, intent="suspend",
            ), draft_id=draft.draft_id)
            update = CollectionUpdate(
                expected_digest=snapshot.digest, purpose=purpose, values=updated,
                question=None, lead_binding=binding,
            )
            return CollectionPlan(collection_result(
                admission, "Suspend the current viewing review first. Then say 'Review my local enquiry' to review and explicitly save its values.",
            ), collection_update=update, draft=change)
        question = _question(admission, "action_intent", "Explicitly save or correct the local enquiry values shown in this answer?")
        text, display = _summary(updated, binding), True
    elif requested.command in {"prepare_viewing", "refresh_viewing"}:
        if purpose != "viewing" or updated.ref is None or updated.local_date is None or updated.local_time is None:
            raise CollectionLanguageError("Set the exact car, viewing date and viewing time before preparing its review.")
        rich = updated.budget.state != "missing" or updated.requirements_state != "missing"
        actual = observation.lead
        if rich and (
            not isinstance(actual, LeadRecord) or actual.values.budget != updated.budget
            or actual.values.requirements != updated.requirements
            or actual.values.selected_refs != [updated.ref]
            or binding != _lead_binding(actual)
        ):
            raise CollectionLanguageError("Review and explicitly save these enquiry values first; then prepare the viewing review.")
        if old is not None and old.displayed_values_digest is not None:
            raise CollectionLanguageError("Resolve the current local-enquiry save question before preparing a viewing review.")
        appointment = appointment_selection(updated.local_date, updated.local_time, rules=rules, now=now)
        if draft is None or draft.state == "discarded":
            if requested.command == "refresh_viewing":
                raise CollectionLanguageError("There is no current draft to refresh; explicitly prepare a viewing review.")
            change = DraftChange(BookingDraftCreate(
                client_action_id=_action_id(admission, "draft"), session_id=session.session_id,
                expected_session_revision=session.revision, ref=updated.ref, appointment=appointment,
            ))
        else:
            ref_changed, time_changed = draft.ref != updated.ref, draft.appointment != appointment
            if (ref_changed or time_changed) and isinstance(pending, ClarificationIntent) and pending.purpose == "action_intent":
                raise CollectionLanguageError("Restate the changed car or time first to resolve this preparation question, then explicitly prepare the updated review.")
            change = DraftChange(BookingDraftUpdate(
                client_action_id=_action_id(admission, "draft"), expected_revision=draft.revision,
                intent="edit" if ref_changed or time_changed else "refresh_review",
                ref=updated.ref if ref_changed else None,
                appointment=appointment if time_changed else None,
            ), draft_id=draft.draft_id)
        text = "Preparing the shared viewing review; explicit confirmation remains required."
    elif purpose == "viewing" and change is None:
        if updated.ref is None:
            question = _question(admission, "listing_reference", "Which exact car and original result do you want to view?")
        elif updated.local_date is None:
            question = _question(admission, "viewing_details", "Which viewing date in Dubai? Use YYYY-MM-DD, today or tomorrow.")
        elif updated.local_time is None:
            question = _question(admission, "viewing_details", "Which Dubai viewing time? Use HH:MM or an explicit am/pm time.")
        elif draft is None or draft.state == "discarded":
            question = _question(admission, "action_intent", "Prepare the viewing review, or first review and save your local enquiry values?")
        if question is not None:
            text += " " + question.question
        else:
            text += " Say 'Prepare the viewing review' to use these exact details, or first review and explicitly save the local enquiry."
    else:
        text += " Add a cash budget or quoted requirements, then say 'Review my local enquiry'. Optional contacts use the local form."
    collection_update = CollectionUpdate(
        expected_digest=snapshot.digest, purpose=purpose, values=updated, sources=sources,
        question=question, display_local_enquiry=display, lead_binding=binding,
    )
    result = collection_result(admission, text)
    if change is None:
        result.pending_intent = question or NoPendingIntent(kind="none")
        if question:
            result.state = "clarification"
        public_update = _content(admission, result.pending_intent.model_dump(mode="json"))
    else:
        public_update = None
    return CollectionPlan(result, public_update, collection_update, draft=change, selection=selection)
