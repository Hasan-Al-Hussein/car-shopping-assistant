"""Caller-unit collection admission and copying; no nested authorization or effects."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.api.schemas.common import InventoryRef
from app.api.schemas.sessions import ClarificationIntent, PendingIntent
from app.core.errors import ApiFailure
from app.database.models import ConversationSession, Message, StoreMetadata
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.sessions import repository as repo
from app.sessions.collection import (
    CollectionEnvelope, CollectionUpdate, CollectionValues, RetainedCollectionCommand,
    StoredFieldSource, collection_digest, collection_values_digest,
)


def unresolved_command(
    unit: OwnerUnit, session_id: str | None = None, *, exclude_message_id: str | None = None,
) -> RetainedCollectionCommand | None:
    if session_id is not None:
        unit.session(session_id)
    query = select(Message).where(
        Message.owner_id == unit.owner_id,
        Message.state.in_(("pending", "interrupted")),
        Message.result_json["collection_command"].as_string().is_not(None),
    )
    if exclude_message_id is not None:
        query = query.where(Message.id != exclude_message_id)
    rows = unit.db.scalars(query.order_by(Message.accepted_revision).limit(2)).all()
    if len(rows) > 1:
        raise StoreError("COLLECTION_MULTIPLE_UNRESOLVED_COMMANDS")
    if not rows:
        return None
    row = rows[0]
    retained = repo.message_content(row).collection_command
    if retained is None or (retained.source_message_id, retained.session_id, retained.request_hash) != (
        row.id, row.session_id, row.payload_hash,
    ):
        raise StoreError("COLLECTION_COMMAND_INCOMPATIBLE")
    return retained


def check_collection_command_fence(
    unit: OwnerUnit, *, source_message_id: str | None, command_hash: str,
) -> None:
    """Shared fresh-command guard; exact participant receipt replay stays ahead of it."""
    retained = unresolved_command(unit)
    metadata = unit.db.get(StoreMetadata, 1)
    if retained is not None and (
        source_message_id is None or retained.source_message_id != source_message_id
        or retained.command_hash != command_hash
        or metadata is None or retained.submitted_store_generation != metadata.store_generation
    ):
        raise ApiFailure("OPERATION_UNRESOLVED")


def owned_collection(
    unit: OwnerUnit, row: ConversationSession, *, generation: str, now: str,
    require_active: bool = False,
) -> CollectionEnvelope | None:
    value = repo.content(row).collection
    if value is not None:
        if (value.owner_id, value.session_id) != (unit.owner_id, row.id):
            raise StoreError("COLLECTION_OWNER_INCOMPATIBLE")
        if require_active and (datetime.fromisoformat(value.expires_at) <= datetime.fromisoformat(now)
                               or value.store_generation != generation):
            raise ApiFailure("REVISION_CONFLICT")
    elif require_active:
        raise ApiFailure("UNSUPPORTED_STATE")
    return value


def apply_update(
    unit: OwnerUnit, row: ConversationSession, message: Message, *, generation: str,
    now: str, mutation: CollectionUpdate | None, final_revision: int,
    pending: PendingIntent, selected_ref: InventoryRef | None,
) -> CollectionEnvelope | None:
    before = owned_collection(unit, row, generation=generation, now=now)
    if mutation is None:
        return before
    if unresolved_command(unit, row.id, exclude_message_id=message.id) is not None:
        raise ApiFailure("OPERATION_UNRESOLVED")
    if mutation.expected_digest != collection_digest(before):
        raise ApiFailure("REVISION_CONFLICT")
    if mutation.values is None:
        return None
    fresh = before is None or datetime.fromisoformat(before.expires_at) <= datetime.fromisoformat(now) or before.store_generation != generation
    if not fresh and before is not None and mutation.purpose != before.purpose:
        raise ApiFailure("UNSUPPORTED_STATE")
    values = mutation.values
    if values.ref is not None and values.ref != selected_ref:
        raise ApiFailure("PRESENTATION_INVALID")
    baseline = CollectionValues() if fresh or before is None else before.values
    changed = {
        name for name in ("budget", "requirements", "ref", "local_date", "local_time")
        if getattr(baseline, name) != getattr(values, name)
        or name == "requirements" and baseline.requirements_state != values.requirements_state
    }
    sources = {source.field: source for source in mutation.sources}
    if set(sources) != changed:
        raise ApiFailure("VALIDATION_ERROR")
    text = repo.message_content(message).request.text
    provenance = {} if fresh or before is None else {entry.field: entry for entry in before.provenance}
    for name, source in sources.items():
        if source.end > len(text) or not text[source.start:source.end].strip():
            raise ApiFailure("VALIDATION_ERROR")
        provenance[name] = StoredFieldSource(**source.model_dump(), message_id=message.id)
    question = mutation.question
    if question is not None and (
        question != pending or (question.created_revision != final_revision and (
            fresh or before is None or question != before.question
        ))
        or question.purpose not in {"listing_reference", "viewing_details", "action_intent"}
    ):
        raise ApiFailure("VALIDATION_ERROR")
    if mutation.lead_binding is not None:
        lead = unit.lead(mutation.lead_binding.lead_id)
        if lead.journey_id != row.journey_id or lead.revision != mutation.lead_binding.revision:
            raise ApiFailure("REVISION_CONFLICT")
    displayed = None
    if mutation.display_local_enquiry:
        if (not isinstance(question, ClarificationIntent) or question.purpose != "action_intent"
            or question.targets != ["confirmation"]):
            raise ApiFailure("VALIDATION_ERROR")
        current = unit.lead_for_journey(row.journey_id)
        if (current is None) != (mutation.lead_binding is None):
            raise ApiFailure("REVISION_CONFLICT")
        displayed = collection_values_digest(values, mutation.lead_binding)
    elif before is not None and not fresh and (
        values == before.values and question == before.question
        and mutation.lead_binding == before.lead_binding
    ):
        displayed = before.displayed_values_digest
    if not fresh and before is not None and (
        values == before.values and question == before.question
        and mutation.lead_binding == before.lead_binding and displayed == before.displayed_values_digest
    ):
        return before
    if before is not None and not fresh and before.revision >= repo.MAX_REVISION:
        raise ApiFailure("UNSUPPORTED_STATE")
    return CollectionEnvelope(
        collection_id=str(uuid4()) if fresh or before is None else before.collection_id,
        revision=1 if fresh or before is None else before.revision + 1,
        owner_id=unit.owner_id, session_id=row.id, store_generation=generation,
        created_at=now if fresh or before is None else before.created_at,
        expires_at=min(row.expires_at, utc_text(datetime.fromisoformat(now) + timedelta(minutes=30)))
        if fresh or before is None else before.expires_at,
        source_message_id=message.id if fresh or before is None else before.source_message_id,
        updated_message_id=message.id, purpose=mutation.purpose, values=values,
        provenance=list(provenance.values()), question=question,
        displayed_values_digest=displayed, lead_binding=mutation.lead_binding,
    )
