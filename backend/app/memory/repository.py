"""Unit-local preference mapping and bounded retention, preserving P9's encoding."""

from pydantic import BaseModel
from sqlalchemy import select

from app.api.schemas.memory import PreferenceEntry, PreferenceRecord
from app.core.errors import ApiFailure
from app.database.models import Owner, Preference
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit

KEYS = frozenset({"budget", "makes", "use_cases", "requirements"})
MAX_REVISION = 2_147_483_647


def stored[Model: BaseModel](model: type[Model], value: object) -> Model:
    try:
        return model.model_validate(value)
    except (TypeError, ValueError):
        raise StoreError("PREFERENCE_STATE_INCOMPATIBLE") from None


def owner(unit: OwnerUnit) -> Owner:
    row = unit.db.get(Owner, unit.owner_id)
    if row is None:
        raise StoreError("PREFERENCE_OWNER_INCOMPATIBLE")
    return row


def next_revision(current: int, expected: int) -> int:
    if current != expected:
        raise ApiFailure("REVISION_CONFLICT")
    if current >= MAX_REVISION:
        raise ApiFailure("UNSUPPORTED_STATE")
    return current + 1


def entry(row: Preference) -> PreferenceEntry:
    if set(row.value_json) != {"value"}:
        raise StoreError("PREFERENCE_STATE_INCOMPATIBLE")
    return stored(
        PreferenceEntry,
        dict(
            preference={**row.value_json, "key": row.key, "strength": row.strength},
            source_session_id=row.source_session_reference,
            source_action_id=row.source_action_id,
            source_message_id=row.source_message_reference,
            confirmed_at=row.confirmed_at,
            expires_at=row.expires_at,
            applicability=row.applicability,
        ),
    )


def record(unit: OwnerUnit, now: str) -> PreferenceRecord:
    setting = unit.preference_setting()
    entries = [
        entry(row)
        for row in unit.db.scalars(
            select(Preference)
            .where(Preference.owner_id == unit.owner_id, Preference.expires_at > now)
            .order_by(Preference.key)
            .limit(5)
        )
    ]
    return stored(
        PreferenceRecord,
        dict(
            entries=[item.model_dump(mode="json") for item in entries],
            revision=owner(unit).preference_revision,
            collection_mode="explicit_save" if setting is None else setting.collection_mode,
        ),
    )


def purge_expired(unit: OwnerUnit, *, now: str) -> int:
    """Trusted operator hook inside an authorized write; never purge dependent authority.

    Only four typed preference rows are eligible. Caller owns transaction/commit.
    Session, receipt, listing, lead and unresolved operation rows are untouched.
    """
    rows = list(
        unit.db.scalars(
            select(Preference)
            .where(Preference.owner_id == unit.owner_id, Preference.expires_at <= now)
            .order_by(Preference.key)
            .limit(5)
        )
    )
    if len(rows) > 4 or any(row.key not in KEYS for row in rows):
        raise StoreError("PREFERENCE_STATE_INCOMPATIBLE")
    if rows:
        buyer = owner(unit)
        buyer.preference_revision = next_revision(
            buyer.preference_revision, buyer.preference_revision
        )
        for row in rows:
            unit.db.delete(row)
    return len(rows)
