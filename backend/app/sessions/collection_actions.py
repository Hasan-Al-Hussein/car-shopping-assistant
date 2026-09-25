"""Concrete lead/draft completion on the existing authorized caller transaction."""

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import PresentationProof
from app.api.schemas.leads import LeadSaveRequest, LeadUpdateRequest
from app.api.schemas.sessions import (
    ClarificationIntent, LeadActionSucceeded, MessageActionResults, MessageResult, NoPendingIntent,
)
from app.api.schemas.viewings import BookingDraftCreate, BookingDraftUpdate
from app.core.errors import ApiFailure
from app.database.models import ConversationSession, Message
from app.database.store import StoreError
from app.identity.authorization import AuthorizedOwnerContext, OwnerUnit
from app.inventory.references import ImmutableInventoryRef
from app.leads.changes import PreparedLeadChange
from app.leads.service import LeadService
from app.sessions import repository as repo
from app.sessions.collection import (
    CollectionEnvelope, CollectionUpdate, LeadBinding, RetainedCollectionCommand,
    _DraftReplyMaterial, _draft_reply_material, _issue_draft_reply, collection_values_digest,
)
from app.sessions.collection_state import apply_update, owned_collection, unresolved_command
from app.sessions.inventory import check_admission
from app.sessions.state import SessionContent, StoredMessage, canonical, copied, fingerprint
from app.viewings.drafts import DraftService

if TYPE_CHECKING:
    from app.sessions.service import DraftChange, LeadChange, SessionService, TurnTicket


def _lead_authority(
    unit: OwnerUnit, row: ConversationSession, message: Message, collection: CollectionEnvelope,
    command: LeadSaveRequest | LeadUpdateRequest, lead_id: str | None,
) -> None:
    question = repo.content(row).pending_intent
    request = repo.message_content(message).request
    reply = request.clarification_reply
    if (
        command.session_id != row.id or not isinstance(question, ClarificationIntent)
        or question.purpose != "action_intent" or question.targets != ["confirmation"]
        or collection.question != question or reply is None
        or (reply.intent_id, reply.created_revision) != (question.intent_id, question.created_revision)
        or collection.displayed_values_digest != collection_values_digest(collection.values, collection.lead_binding)
        or command.values.budget != collection.values.budget
        or command.values.requirements != collection.values.requirements
        or command.values.selected_refs != ([] if collection.values.ref is None else [collection.values.ref])
    ):
        raise ApiFailure("UNSUPPORTED_STATE")
    binding = collection.lead_binding
    current = unit.lead_for_journey(row.journey_id)
    if isinstance(command, LeadSaveRequest):
        if binding is not None or current is not None or lead_id is not None:
            raise ApiFailure("LEAD_EXISTS")
        if command.values.email.state != "missing" or command.values.phone.state != "missing":
            raise ApiFailure("VALIDATION_ERROR")
    else:
        if binding is None or current is None or (
            lead_id, command.expected_revision, current.id, current.revision
        ) != (binding.lead_id, binding.revision, binding.lead_id, binding.revision):
            raise ApiFailure("REVISION_CONFLICT")
        from app.leads import repository as leads

        previous = leads.values(current)
        if len(previous.selected_refs) > 1:
            raise ApiFailure("UNSUPPORTED_STATE")
        fields = {source.field for source in collection.provenance}
        if (
            previous.budget != command.values.budget and "budget" not in fields
            or previous.requirements != command.values.requirements and "requirements" not in fields
            or previous.selected_refs != command.values.selected_refs and "ref" not in fields
            or previous.email != command.values.email or previous.phone != command.values.phone
        ):
            raise ApiFailure("VALIDATION_ERROR")


def _draft_values(
    unit: OwnerUnit, row: ConversationSession, collection: CollectionEnvelope,
    command: BookingDraftCreate | BookingDraftUpdate, draft_id: str | None,
    mutation: CollectionUpdate | None,
) -> None:
    if collection.purpose != "viewing" or collection.displayed_values_digest is not None:
        raise ApiFailure("UNSUPPORTED_STATE")
    values = collection.values if mutation is None else mutation.values
    effective_ref = command.ref
    effective_appointment = command.appointment
    if isinstance(command, BookingDraftCreate):
        if command.session_id != row.id or command.expected_session_revision != row.revision:
            raise ApiFailure("REVISION_CONFLICT")
    else:
        if draft_id is None or repo.content(row).current_draft_id != draft_id:
            raise ApiFailure("REVISION_CONFLICT")
        current = unit.draft_for_session(row.id, draft_id)
        if current.revision != command.expected_revision:
            raise ApiFailure("REVISION_CONFLICT")
        if command.intent in {"suspend", "discard"}:
            return
        from app.viewings import draft_repository as drafts

        if effective_ref is None:
            effective_ref = InventoryRef(namespace=current.namespace, snapshot_id=current.snapshot_id,
                                         source_id=current.source_id)
        if effective_appointment is None:
            effective_appointment = drafts.appointment(current)
    if values is None or values.ref is None:
        raise ApiFailure("VALIDATION_ERROR")
    if effective_ref != values.ref:
        raise ApiFailure("VALIDATION_ERROR")
    if effective_appointment is not None:
        local = datetime.fromisoformat(effective_appointment.starts_at_utc).astimezone(ZoneInfo("Asia/Dubai"))
        if (local.date().isoformat(), local.strftime("%H:%M")) != (values.local_date, values.local_time):
            raise ApiFailure("VALIDATION_ERROR")
    elif values.local_date is not None and values.local_time is not None:
        raise ApiFailure("VALIDATION_ERROR")
    if values.budget.state != "missing" or values.requirements_state != "missing":
        from app.leads import repository as leads

        binding = collection.lead_binding if mutation is None else mutation.lead_binding
        lead = unit.lead_for_journey(row.journey_id)
        if binding is None or lead is None or (binding.lead_id, binding.revision) != (lead.id, lead.revision):
            raise ApiFailure("UNSUPPORTED_STATE")
        saved_values = leads.values(lead)
        if (saved_values.budget != values.budget or saved_values.requirements != values.requirements
            or saved_values.selected_refs != [values.ref]):
            raise ApiFailure("UNSUPPORTED_STATE")


def complete_collection_action(
    service: "SessionService", context: AuthorizedOwnerContext, ticket: "TurnTicket",
    result: MessageResult, *, lead: "LeadChange | None", draft: "DraftChange | None",
    lead_service: LeadService | None, draft_service: DraftService | None,
    update: SessionContent | None, presentation: PresentationProof | None,
    selection: InventoryRef | None, collection_update: CollectionUpdate | None,
) -> MessageResult:
    from app.sessions.service import DraftChange, LeadChange

    service._check_collection_ticket(context, ticket)
    if (lead is None) == (draft is None) or presentation is not None:
        raise ApiFailure("VALIDATION_ERROR")
    result = copied(MessageResult, result)
    if (result.operation is not None or result.search is not None or any(
        action["state"] != "not_requested" for action in result.actions.model_dump().values()
    )):
        raise ApiFailure("VALIDATION_ERROR")
    update = None if update is None else copied(SessionContent, update)
    selection = None if selection is None else copied(InventoryRef, selection)
    mutation = None if collection_update is None else copied(CollectionUpdate, collection_update)
    if lead is not None:
        if type(lead) is not LeadChange or lead_service is None or lead_service.authorization is not service.authorization:
            raise ApiFailure("UNSUPPORTED_STATE")
        lead_command, lead_id = lead_service._copied_change(lead.command, lead.lead_id)
        if mutation is not None or selection is not None:
            raise ApiFailure("VALIDATION_ERROR")
        draft_command = None
        draft_id = None
        command_hash = fingerprint(dict(lead_id=lead_id, command=lead_command.model_dump(mode="json")))
    else:
        if type(draft) is not DraftChange or draft_service is None or draft_service.authorization is not service.authorization:
            raise ApiFailure("UNSUPPORTED_STATE")
        draft_command, draft_id = draft_service._copied_change(draft.command, draft.draft_id)
        lead_command = None
        lead_id = None
        command_hash = draft_service._command_hash(draft_command, draft_id)
        if mutation is not None and (mutation.question is not None or mutation.display_local_enquiry):
            raise ApiFailure("UNSUPPORTED_STATE")
    command = lead_command if lead_command is not None else draft_command
    assert command is not None
    material = dict(
        kind="session-collection-completion-1", result=result.model_dump(mode="json"),
        update=None if update is None else update.model_dump(mode="json", exclude={"collection"}),
        selection=None if selection is None else selection.model_dump(mode="json"),
        collection_update=None if mutation is None else mutation.model_dump(mode="json"),
        lead_id=lead_id, draft_id=draft_id, command=command.model_dump(mode="json"),
    )
    completion_json = canonical(material).decode("utf-8")
    completion_hash = fingerprint(material)

    def inspect(unit: OwnerUnit, now: str) -> tuple[ConversationSession, Message, StoredMessage, MessageResult | None]:
        row = repo.live_session(unit, ticket._session_id, now)
        message = unit.message(row.id, ticket._message_id)
        saved = repo.message_content(message)
        if (result.session_id, result.client_message_id, result.turn_revision) != (
            row.id, message.client_message_id, message.accepted_revision,
        ):
            raise ApiFailure("UNSUPPORTED_STATE")
        if saved.assistant_result is not None:
            if saved.completion_hash != completion_hash:
                raise ApiFailure("IDEMPOTENCY_CONFLICT")
            return row, message, saved, MessageResult.model_validate({
                **saved.assistant_result.model_dump(mode="json"), "current_revision": row.revision,
            })
        if message.state != "pending" or saved.worker_epoch != service._epoch:
            raise ApiFailure("UNSUPPORTED_STATE")
        if row.revision != message.accepted_revision:
            raise ApiFailure("REVISION_CONFLICT")
        if saved.request.explicit_confirmation is not None:
            raise ApiFailure("VALIDATION_ERROR")
        repo.validate_context(unit, row, repo.content(row))
        if unresolved_command(unit, row.id, exclude_message_id=message.id) is not None:
            raise ApiFailure("OPERATION_UNRESOLVED")
        return row, message, saved, None

    replay = service.authorization.read(context, lambda unit: inspect(unit, service._now())[3])
    if replay is not None:
        return replay

    def retain(unit: OwnerUnit) -> tuple[MessageResult | None, _DraftReplyMaterial | None]:
        now = service._now()
        row, message, saved, replay = inspect(unit, now)
        if replay is not None:
            return replay, None
        collection = owned_collection(unit, row, generation=context.generation, now=now, require_active=True)
        assert collection is not None
        retained = RetainedCollectionCommand(
            kind="lead" if lead_command is not None else "draft", source_message_id=message.id,
            session_id=row.id, submitted_store_generation=context.generation,
            request_hash=message.payload_hash, command_hash=command_hash, command=command,
            lead_id=lead_id, draft_id=draft_id, completion_hash=completion_hash,
            completion_json=completion_json,
        )
        if saved.collection_command is not None and saved.collection_command != retained:
            raise ApiFailure("IDEMPOTENCY_CONFLICT")
        reply_material = None
        if lead_command is not None:
            _lead_authority(unit, row, message, collection, lead_command, lead_id)
        else:
            assert draft_command is not None
            _draft_values(unit, row, collection, draft_command, draft_id, mutation)
            reply_material = _draft_reply_material(
                unit, session_id=row.id, generation=context.generation, message_id=message.id,
                epoch=service._epoch, command_hash=command_hash, command=draft_command, now=now,
            )
        if saved.collection_command is None:
            message.result_json = StoredMessage.model_validate({
                **saved.model_dump(mode="json"), "collection_command": retained.model_dump(mode="json"),
            }).model_dump(mode="json")
        return None, reply_material

    replay, reply_material = service.authorization.write(context, retain)
    if replay is not None:
        return replay
    reply = _issue_draft_reply(reply_material)
    prepared_lead = None
    prepared_draft = None
    prepared_selection = None
    if lead_command is not None:
        assert lead_service is not None
        observed = lead_service.prepare_change(
            context, lead_command, lead_id=lead_id, submitted_generation=context.generation,
            source_message_id=ticket._message_id,
        )
        prepared_lead = observed if isinstance(observed, PreparedLeadChange) else None
    else:
        assert draft_command is not None and draft_service is not None
        prepared_draft = draft_service.prepare_change(
            context, draft_command, draft_id=draft_id, submitted_generation=context.generation,
            source_message_id=ticket._message_id, reply=reply,
        )
        if selection is not None:
            prepared_selection = service._prepare(
                (ImmutableInventoryRef.model_validate(selection.model_dump()),), selection.snapshot_id,
            )

    def write(unit: OwnerUnit) -> MessageResult:
        now = service._now()
        row, message, saved, replay = inspect(unit, now)
        if replay is not None:
            return replay
        retained = saved.collection_command
        if retained is None or retained.completion_hash != completion_hash or retained.command_hash != command_hash:
            raise ApiFailure("IDEMPOTENCY_CONFLICT")
        before = repo.content(row)
        collection = owned_collection(unit, row, generation=context.generation, now=now, require_active=True)
        assert collection is not None
        after = before if update is None else SessionContent.model_validate({
            **update.model_dump(mode="json"), "collection": collection.model_dump(mode="json"),
            "pending_intent": before.pending_intent.model_dump(mode="json"),
            "current_draft_id": before.current_draft_id,
        })
        if (after.selected_ref, after.active_presentation_id) != (before.selected_ref, before.active_presentation_id):
            raise ApiFailure("UNSUPPORTED_STATE")
        if selection is not None:
            if prepared_selection is None:
                raise ApiFailure("SNAPSHOT_STALE")
            check_admission(
                unit, prepared_selection, generation=context.generation, snapshot_id=selection.snapshot_id,
                refs=(ImmutableInventoryRef.model_validate(selection.model_dump()),), gateway=service.inventory,
            )
            if before.active_presentation_id is not None:
                repo.presentation_member(unit, row.id, before.active_presentation_id, selection)
            after = SessionContent.model_validate({**after.model_dump(mode="json"), "selected_ref": selection.model_dump(mode="json")})
        actions = MessageActionResults()
        if lead_command is not None:
            assert lead_service is not None
            _lead_authority(unit, row, message, collection, lead_command, lead_id)
            outcome = lead_service.change_in_unit(
                unit, lead_command, lead_id=lead_id, submitted_generation=context.generation,
                source_message_id=message.id, generation=context.generation, now=now, prepared=prepared_lead,
            )
            actions.lead = LeadActionSucceeded(state="succeeded", client_action_id=lead_command.client_action_id, result=outcome)
            revised_collection = CollectionEnvelope.model_validate({
                **collection.model_dump(mode="json"), "revision": collection.revision + 1,
                "updated_message_id": message.id, "question": None, "displayed_values_digest": None,
                "lead_binding": LeadBinding(lead_id=outcome.lead.lead_id, revision=outcome.lead.revision).model_dump(),
            })
            after = SessionContent.model_validate({
                **after.model_dump(mode="json"), "collection": revised_collection.model_dump(mode="json"),
                "pending_intent": NoPendingIntent(kind="none").model_dump(),
            })
            final_revision = message.accepted_revision + int(after != before)
            text = "Your local enquiry is saved. It has not been sent to a dealer."
            text += " The CSV export is current." if outcome.lead.csv.state == "current" else (
                " The CSV export needs repair." if outcome.lead.csv.state == "failed" else " The CSV export is pending."
            )
        else:
            assert draft_command is not None and draft_service is not None
            _draft_values(unit, row, collection, draft_command, draft_id, mutation)
            candidate = apply_update(
                unit, row, message, generation=context.generation, now=now, mutation=mutation,
                final_revision=message.accepted_revision + 1, pending=before.pending_intent,
                selected_ref=after.selected_ref,
            )
            after = SessionContent.model_validate({**after.model_dump(mode="json"), "collection": None if candidate is None else candidate.model_dump(mode="json")})
            prior = draft_service.lookup_change_in_unit(
                unit, draft_command, draft_id=draft_id, generation=context.generation,
                submitted_generation=context.generation, now=now, source_message_id=message.id,
            )
            transition_changes = False
            if prior is None:
                if isinstance(draft_command, BookingDraftCreate):
                    transition_changes = True
                else:
                    assert draft_id is not None
                    existing = unit.draft_for_session(row.id, draft_id)
                    has_review = draft_command.intent in {"edit", "refresh_review"} and (
                        draft_command.appointment is not None or existing.appointment_json is not None
                    )
                    transition_changes = has_review or not isinstance(before.pending_intent, NoPendingIntent) or (
                        draft_command.intent == "discard" and before.current_draft_id is not None
                    )
            final_revision = message.accepted_revision + int(after != before or transition_changes)
            effect = draft_service.change_in_unit(
                unit, draft_command, draft_id=draft_id, generation=context.generation,
                submitted_generation=context.generation, now=now, prepared=prepared_draft,
                final_session_revision=final_revision, source_message_id=message.id, reply=reply,
            )
            if effect.session_id != row.id:
                raise StoreError("COLLECTION_DRAFT_SESSION_INCOMPATIBLE")
            if effect.transition is not None:
                if effect.replayed or effect.transition.final_revision != final_revision:
                    raise StoreError("COLLECTION_DRAFT_TRANSITION_INCOMPATIBLE")
                draft_service.resolve_session_in_unit(unit, transition=effect.transition, reply=reply)
                transitioned = repo.content(row)
                after = SessionContent.model_validate({
                    **after.model_dump(mode="json"), "current_draft_id": transitioned.current_draft_id,
                    "pending_intent": transitioned.pending_intent.model_dump(mode="json"),
                })
            elif not effect.replayed:
                raise StoreError("COLLECTION_DRAFT_TRANSITION_MISSING")
            actual_revision = message.accepted_revision + int(after != before)
            if actual_revision != final_revision:
                raise StoreError("COLLECTION_FINAL_REVISION_MISMATCH")
            repo.revision(row, message.accepted_revision)
            row.revision = final_revision
            row.state_json = after.model_dump(mode="json")
            actual = draft_service.observe_changed_in_unit(unit, effect=effect, generation=context.generation, now=now)
            text = {
                "reviewable": "Your simulated viewing review is ready. Open the review and confirm it explicitly to book.",
                "needs_details": "Your viewing draft is saved and still needs appointment details.",
                "suspended": "Your unsubmitted viewing draft is paused and its previous review is invalid.",
                "discarded": "Your unsubmitted viewing draft is discarded. No booking was cancelled.",
                "resolved": "This viewing draft is already resolved. Check its recorded outcome.",
                "unresolved": "This viewing draft has an unresolved outcome. Keep its original operation identity.",
            }[actual.state]
            if actual.state in {"reviewable", "needs_details", "suspended"} and after.collection is not None:
                accepted_values = after.collection.values
                if accepted_values.local_date is not None or accepted_values.local_time is not None:
                    label = "Prepared" if actual.state == "reviewable" else "Temporary"
                    date = accepted_values.local_date or "date needed"
                    time = accepted_values.local_time or "time needed"
                    text += f" {label} viewing details (Dubai): {date}, {time}. This change does not book a viewing."
        if lead_command is not None:
            repo.revision(row, message.accepted_revision)
            row.revision = final_revision
            row.state_json = after.model_dump(mode="json")
        repo.validate_context(unit, row, after)
        original = MessageResult.model_validate({
            **result.model_dump(mode="json"), "text": text, "actions": actions.model_dump(mode="json"),
            "state": "answered", "current_revision": row.revision, "persistence": "saved",
            "pending_intent": after.pending_intent.model_dump(mode="json"),
        })
        message.result_json = StoredMessage(
            request=saved.request, worker_epoch=saved.worker_epoch, assistant_result=original,
            completion_hash=completion_hash, collection_command=retained, applied_selection=selection,
        ).model_dump(mode="json")
        message.state = "completed"
        return original

    return service.authorization.write(context, write)
