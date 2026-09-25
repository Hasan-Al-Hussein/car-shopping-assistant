"""Small unit-local mappings; all callers enter through BE09 authorization."""

from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import select

from app.api.schemas.common import Id, InventoryRef
from app.api.schemas.inventory import PresentationProof
from app.api.schemas.memory import PreferenceEntry, PreferenceRecord
from app.api.schemas.sessions import (
    ClarificationIntent,
    SessionState,
    UnresolvedOperationIntent,
    ViewingReviewIntent,
)
from app.core.errors import ApiFailure
from app.database.models import (
    CommandReceipt,
    ConversationSession,
    Journey,
    Message,
    Owner,
    Preference,
    PresentationItem,
    ResultPresentation,
)
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.sessions.state import SessionContent, StoredMessage, fingerprint

MAX_REVISION = 2_147_483_647
ID = TypeAdapter(Id)


def valid_id(value: str) -> str:
    try:
        return ID.validate_python(value)
    except ValidationError:
        raise ApiFailure("VALIDATION_ERROR") from None


def stored[Model: BaseModel](model: type[Model], value: object) -> Model:
    try:
        return model.model_validate(value)
    except (TypeError, ValueError):
        raise StoreError("SESSION_STATE_INCOMPATIBLE") from None


def live_session(unit: OwnerUnit, session_id: str, now: str) -> ConversationSession:
    row = unit.session(session_id)
    if row.expires_at <= now:
        raise ApiFailure("NOT_FOUND")
    return row


def content(row: ConversationSession) -> SessionContent:
    return stored(SessionContent, row.state_json)


def message_content(row: Message) -> StoredMessage:
    value = stored(StoredMessage, row.result_json)
    if (
        value.request.client_message_id != row.client_message_id
        or value.request.expected_revision != row.expected_revision
        or fingerprint(value.request.model_dump(mode="json")) != row.payload_hash
        or row.accepted_revision != row.expected_revision + 1
        or row.state not in {"pending", "completed", "interrupted"}
        or (row.state == "completed") != (value.assistant_result is not None)
        or (row.state == "completed") != (value.completion_hash is not None)
        or (value.applied_public_proof is None) != (value.applied_presentation_id is None)
        or (
            row.state != "completed"
            and (value.applied_selection is not None or value.applied_public_proof is not None)
        )
    ):
        raise StoreError("SESSION_MESSAGE_INCOMPATIBLE")
    if value.assistant_result is not None and (
        value.assistant_result.session_id != row.session_id
        or value.assistant_result.client_message_id != row.client_message_id
        or value.assistant_result.turn_revision != row.accepted_revision
    ):
        raise StoreError("SESSION_MESSAGE_INCOMPATIBLE")
    return value


def recalled(unit: OwnerUnit, now: str) -> PreferenceRecord:
    """Read only existing typed memory; no preference command or renewal here."""
    owner = unit.db.get(Owner, unit.owner_id)
    if owner is None:
        raise StoreError("SESSION_OWNER_INCOMPATIBLE")
    setting = unit.preference_setting()
    entries = []
    for row in unit.db.scalars(
        select(Preference)
        .where(Preference.owner_id == unit.owner_id, Preference.expires_at > now)
        .order_by(Preference.key)
        .limit(5)
    ):
        entries.append(
            stored(
                PreferenceEntry,
                {
                    "preference": {**row.value_json, "key": row.key, "strength": row.strength},
                    "source_session_id": row.source_session_reference,
                    "source_action_id": row.source_action_id,
                    "source_message_id": row.source_message_reference,
                    "confirmed_at": row.confirmed_at,
                    "expires_at": row.expires_at,
                    "applicability": row.applicability,
                },
            )
        )
    return stored(
        PreferenceRecord,
        {
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "revision": owner.preference_revision,
            "collection_mode": "explicit_save" if setting is None else setting.collection_mode,
        },
    )


def state(unit: OwnerUnit, row: ConversationSession, now: str) -> SessionState:
    value = content(row)
    validate_context(unit, row, value)
    return stored(
        SessionState,
        {
            **value.model_dump(mode="json", include={
                "criteria", "selected_ref", "active_presentation_id", "current_draft_id",
                "pending_intent",
            }),
            "session_id": row.id,
            "journey_id": row.journey_id,
            "revision": row.revision,
            "recalled_preferences": recalled(unit, now).model_dump(mode="json"),
        },
    )


def revision(row: ConversationSession, expected: int) -> None:
    if row.revision != expected:
        raise ApiFailure("REVISION_CONFLICT")
    if row.revision == MAX_REVISION:
        raise ApiFailure("UNSUPPORTED_STATE")


def activity(row: ConversationSession, now: str, retention_days: int) -> None:
    row.last_activity_at = now
    row.expires_at = utc_text(datetime.fromisoformat(now) + timedelta(days=retention_days))


def journey(unit: OwnerUnit, now: str) -> Journey:
    row = unit.db.scalar(select(Journey).where(Journey.owner_id == unit.owner_id))
    if row is None:
        row = Journey(id=str(uuid4()), owner_id=unit.owner_id, created_at=now)
        unit.db.add(row)
        unit.db.flush()
    return row


def receipt(
    unit: OwnerUnit, kind: str, action_id: str, payload_hash: str, now: str
) -> CommandReceipt | None:
    row = unit.db.scalar(
        select(CommandReceipt).where(
            CommandReceipt.owner_id == unit.owner_id,
            CommandReceipt.command_kind == kind,
            CommandReceipt.client_action_id == action_id,
        )
    )
    if row is None:
        return None
    if row.payload_hash != payload_hash:
        raise ApiFailure("IDEMPOTENCY_CONFLICT")
    if row.expires_at <= now:
        raise ApiFailure("REPLAY_EXPIRED")
    return row


def record_receipt(
    unit: OwnerUnit,
    row: ConversationSession,
    *,
    kind: str,
    action_id: str,
    payload_hash: str,
    result: dict[str, object],
    now: str,
    retention_days: int,
) -> None:
    unit.db.add(
        CommandReceipt(
            id=str(uuid4()),
            owner_id=unit.owner_id,
            command_kind=kind,
            client_action_id=action_id,
            payload_hash=payload_hash,
            applied_revision=row.revision,
            result_json=result,
            created_at=now,
            expires_at=utc_text(datetime.fromisoformat(now) + timedelta(days=retention_days)),
        )
    )


def presentation_member(
    unit: OwnerUnit, session_id: str, presentation_id: str, ref: InventoryRef
) -> None:
    unit.presentation(session_id, presentation_id)
    items = unit.db.scalars(
        select(PresentationItem)
        .where(PresentationItem.presentation_id == presentation_id)
        .order_by(PresentationItem.ordinal)
        .limit(51)
    ).all()
    if len(items) > 50 or not any(
        (item.namespace, item.snapshot_id, item.source_id)
        == (ref.namespace, ref.snapshot_id, ref.source_id)
        for item in items
    ):
        raise ApiFailure("PRESENTATION_INVALID")


def validate_context(unit: OwnerUnit, row: ConversationSession, value: SessionContent) -> None:
    if value.active_presentation_id is not None:
        unit.presentation(row.id, value.active_presentation_id)
    if value.current_draft_id is not None:
        unit.draft_for_session(row.id, value.current_draft_id)
    pending = value.pending_intent
    if isinstance(pending, ClarificationIntent) and pending.created_revision > row.revision:
        raise ApiFailure("REVISION_CONFLICT")
    if isinstance(pending, ViewingReviewIntent | UnresolvedOperationIntent):
        if pending.draft_id != value.current_draft_id:
            raise ApiFailure("UNSUPPORTED_STATE")
        if isinstance(pending, ViewingReviewIntent):
            review = unit.review_for_draft(pending.draft_id, pending.review_id)
            if review.operation_key != pending.operation_key:
                raise ApiFailure("UNSUPPORTED_STATE")
        else:
            authority = unit.operation(pending.operation_key)
            if (
                authority.review.draft_id != pending.draft_id
                or authority.review.store_generation != pending.submitted_store_generation
            ):
                raise ApiFailure("UNSUPPORTED_STATE")


def protect_operation(before: SessionContent, after: SessionContent) -> None:
    if isinstance(before.pending_intent, ViewingReviewIntent | UnresolvedOperationIntent) and (
        before.current_draft_id != after.current_draft_id
        or before.selected_ref != after.selected_ref
        or before.pending_intent != after.pending_intent
    ):
        # Transactions owns reviewed-state transitions; this seam cannot clear them.
        raise ApiFailure("UNSUPPORTED_STATE")


def add_presentation(
    unit: OwnerUnit, row: ConversationSession, proof: PresentationProof, now: str
) -> str:
    owned_id = str(uuid4())
    unit.db.add(
        ResultPresentation(
            id=owned_id,
            owner_id=unit.owner_id,
            session_id=row.id,
            snapshot_id=proof.snapshot_id,
            criteria_hash=proof.criteria_hash,
            created_revision=row.revision,
            created_at=now,
        )
    )
    unit.db.flush()
    for ordinal, ref in enumerate(proof.ordered_refs):
        unit.db.add(
            PresentationItem(
                presentation_id=owned_id,
                ordinal=ordinal,
                namespace=ref.namespace,
                snapshot_id=ref.snapshot_id,
                source_id=ref.source_id,
            )
        )
    return owned_id
