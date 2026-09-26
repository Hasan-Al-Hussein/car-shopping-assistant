"""Real Session/Store collection fixtures; Inventory remains explicitly synthetic."""

from typing import Literal
from uuid import uuid4

from app.api.schemas.sessions import ClarificationIntent, ClarificationReply, MessageRequest
from app.sessions.collection import CollectionUpdate, CollectionValues, FieldName, FieldSource, LeadBinding
from app.sessions.service import TurnAdmission
from app.sessions.state import SessionContent
from tests.platform.session_cases import SessionHarness, answer


def begin(base: SessionHarness, session_id: str, text: str, *, select: bool = False) -> TurnAdmission:
    from tests.platform.session_cases import ref

    current = base.service.get(base.context(), session_id)
    question = current.pending_intent
    echoed = None if not isinstance(question, ClarificationIntent) else ClarificationReply(
        intent_id=question.intent_id, created_revision=question.created_revision,
    )
    return base.service.begin(base.context(), session_id, MessageRequest(
        client_message_id=str(uuid4()), expected_revision=current.revision, text=text,
        clarification_reply=echoed, selected_ref=ref() if select else None,
    ))


def public_content(admission: TurnAdmission) -> SessionContent:
    return SessionContent.model_validate(admission.session.model_dump(mode="json", include={
        "criteria", "selected_ref", "active_presentation_id", "current_draft_id", "pending_intent",
    }))


def collect(
    base: SessionHarness, session_id: str, values: CollectionValues, *,
    purpose: Literal["local_enquiry", "viewing"] = "local_enquiry",
    ask: Literal["save", "time"] | None = None, binding: LeadBinding | None = None,
) -> TurnAdmission:
    # Platform validates source identity/bounds; interpreting these values is Assistant's separate proof.
    admission = begin(base, session_id, "My non-contact collection values: " + values.model_dump_json(), select=values.ref is not None)
    assert admission.ticket is not None
    observed = base.service.read_collection(base.context(), admission.ticket)
    prior = CollectionValues() if observed.collection is None else observed.collection.values
    names: tuple[FieldName, ...] = ("budget", "requirements", "ref", "local_date", "local_time")
    sources = [FieldSource(field=name, start=0, end=len(admission.request.text)) for name in names
    if getattr(prior, name) != getattr(values, name) or (
        name == "requirements" and prior.requirements_state != values.requirements_state
    )]
    question = None if ask is None else ClarificationIntent(
        kind="clarification", intent_id=str(uuid4()), created_revision=admission.session.revision + 1,
        purpose="action_intent" if ask == "save" else "viewing_details",
        targets=["confirmation"] if ask == "save" else ["appointment"],
        question="Save these exact needs locally with CSV projection?" if ask == "save" else "What viewing time do you want?",
    )
    update = public_content(admission).model_copy(update={"pending_intent": question}) if question is not None else public_content(admission)
    response = answer(admission).model_copy(update={"pending_intent": update.pending_intent})
    base.service.complete(base.context(), admission.ticket, response, update=update, collection_update=CollectionUpdate(
        expected_digest=observed.digest, purpose=purpose, values=values, sources=sources,
        question=question, display_local_enquiry=ask == "save", lead_binding=binding,
    ))
    return admission
