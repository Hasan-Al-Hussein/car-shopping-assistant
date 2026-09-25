"""Unit-local canonical lead, receipt and global projection bookkeeping."""

from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from sqlalchemy import select

from app.api.schemas.common import DTO, Id
from app.api.schemas.leads import (
    ExportCurrent,
    ExportPending,
    LeadRecord,
    LeadValues,
    RequestedExportOutcome,
)
from app.core.errors import ApiFailure
from app.database.models import (
    CommandReceipt,
    ExportIntent,
    ExportState,
    Journey,
    Lead,
    LeadBooking,
)
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text

KIND = "lead.command"
MAX_REVISION = 2_147_483_647


class CaptureReceipt(DTO):
    version: Literal["lead-command-1"] = "lead-command-1"
    store_generation: Id
    # Original applied facts; callers read current separately after a replay.
    lead: LeadRecord
    # Internal provenance only; old direct UI receipts decode as None.
    source_message_id: Id | None = None


def require_write(unit: OwnerUnit) -> None:
    connection = unit.db.connection()
    if (
        not connection.in_transaction()
        or connection.get_execution_options().get("store_write") is not True
    ):
        raise StoreError("LEAD_REQUIRES_CALLER_WRITE_UNIT")


def expires(now: str, retention_days: int) -> str:
    if type(retention_days) is not int or retention_days != 90:
        raise StoreError("LEAD_RETENTION_POLICY_INCOMPATIBLE")
    return utc_text(datetime.fromisoformat(now) + timedelta(days=retention_days))


def current(unit: OwnerUnit) -> Lead | None:
    journey = unit.db.scalar(select(Journey).where(Journey.owner_id == unit.owner_id))
    return None if journey is None else unit.lead_for_journey(journey.id)


def visible(row: Lead, now: str) -> None:
    if row.expires_at <= now:
        # Retained expired state is not permission to recreate the logical lead.
        raise ApiFailure("NOT_FOUND")
    if row.created_at > row.updated_at or row.updated_at > now:
        raise StoreError("LEAD_TIME_INCOMPATIBLE")


def values(row: Lead) -> LeadValues:
    try:
        return LeadValues.model_validate(row.values_json)
    except (TypeError, ValueError):
        raise StoreError("LEAD_VALUES_INCOMPATIBLE") from None


def projection(
    unit: OwnerUnit,
    generation: str,
    now: str,
    *,
    allow_empty: bool = False,
) -> RequestedExportOutcome:
    state = unit.db.get(ExportState, 1)
    if state is None or state.store_generation != generation:
        raise StoreError("LEAD_PROJECTION_GENERATION_UNAVAILABLE")
    if (
        state.state not in {"current", "pending", "failed"}
        or not (0 if allow_empty else 1) <= state.canonical_version <= MAX_REVISION
        or state.exported_version is not None
        and not 0 <= state.exported_version <= state.canonical_version
        or state.updated_at > now
    ):
        raise StoreError("LEAD_PROJECTION_INCOMPATIBLE")
    if state.state == "current":
        if state.exported_version != state.canonical_version:
            raise StoreError("LEAD_PROJECTION_INCOMPATIBLE")
        return ExportCurrent(
            state="current",
            store_generation=generation,
            observed_at=now,
            canonical_version=state.canonical_version,
            exported_version=state.canonical_version,
        )
    return ExportPending(
        state="failed" if state.state == "failed" else "pending",
        store_generation=generation,
        observed_at=now,
        canonical_version=state.canonical_version,
        exported_version=state.exported_version,
        code="CSV_EXPORT_FAILED" if state.state == "failed" else None,
    )


def record(unit: OwnerUnit, row: Lead, generation: str, now: str) -> LeadRecord:
    visible(row, now)
    links = list(
        unit.db.scalars(
            select(LeadBooking)
            .where(
                LeadBooking.owner_id == unit.owner_id,
                LeadBooking.lead_id == row.id,
            )
            .order_by(LeadBooking.booking_id)
            .limit(101)
        )
    )
    if len(links) > 100 or (row.stage == "viewing_confirmed") != bool(links):
        raise StoreError("LEAD_BOOKINGS_INCOMPATIBLE")
    for link in links:
        unit.booking(link.booking_id)  # Requires an owned SUCCEEDED relational outcome.
    try:
        return LeadRecord.model_validate(
            dict(
                lead_id=row.id,
                journey_id=row.journey_id,
                revision=row.revision,
                stage=row.stage,
                values=values(row).model_dump(mode="json"),
                booking_ids=[link.booking_id for link in links],
                updated_at=row.updated_at,
                expires_at=row.expires_at,
                delivery="local_only",
                csv=projection(unit, generation, now).model_dump(mode="json"),
            )
        )
    except (TypeError, ValueError):
        raise StoreError("LEAD_RECORD_INCOMPATIBLE") from None


def receipt(
    unit: OwnerUnit,
    action_id: str,
    digest: str,
    generation: str,
    now: str,
) -> LeadRecord | None:
    row = unit.db.scalar(
        select(CommandReceipt).where(
            CommandReceipt.owner_id == unit.owner_id,
            CommandReceipt.command_kind == KIND,
            CommandReceipt.client_action_id == action_id,
        )
    )
    if row is None:
        return None
    if row.payload_hash != digest:
        raise ApiFailure("IDEMPOTENCY_CONFLICT")
    if row.expires_at <= now:
        raise ApiFailure("REPLAY_EXPIRED")
    try:
        saved = CaptureReceipt.model_validate(row.result_json)
    except (TypeError, ValueError):
        raise StoreError("LEAD_RECEIPT_INCOMPATIBLE") from None
    if saved.store_generation != generation:
        raise ApiFailure("STORE_GENERATION_CHANGED")
    lead = unit.lead(saved.lead.lead_id)
    if (
        saved.lead.revision != row.applied_revision
        or lead.revision < row.applied_revision
        or saved.lead.journey_id != lead.journey_id
        or saved.lead.csv.store_generation != generation
    ):
        raise StoreError("LEAD_RECEIPT_INCOMPATIBLE")
    # Preserve applied lead facts, while labelling the separately observed global CSV state.
    return saved.lead.model_copy(update={"csv": projection(unit, generation, now)}, deep=True)


def remember(
    unit: OwnerUnit,
    *,
    action_id: str,
    digest: str,
    generation: str,
    lead: LeadRecord,
    now: str,
    retention_days: int,
    source_message_id: str | None = None,
) -> None:
    require_write(unit)
    unit.db.add(
        CommandReceipt(
            id=str(uuid4()),
            owner_id=unit.owner_id,
            command_kind=KIND,
            client_action_id=action_id,
            payload_hash=digest,
            applied_revision=lead.revision,
            result_json=CaptureReceipt(
                store_generation=generation, lead=lead, source_message_id=source_message_id,
            ).model_dump(
                mode="json"
            ),
            created_at=now,
            expires_at=expires(now, retention_days),
        )
    )


def enqueue(unit: OwnerUnit, row: Lead, generation: str, now: str) -> None:
    require_write(unit)
    state = unit.db.get(ExportState, 1)
    if state is None:
        # A missing singleton is valid only at first capture. Never silently repair lost metadata.
        other = unit.db.scalar(select(Lead.id).where(Lead.id != row.id).limit(1))
        if other is not None or row.revision != 1:
            raise StoreError("LEAD_PROJECTION_UNAVAILABLE")
        state = ExportState(
            id=1,
            store_generation=generation,
            canonical_version=0,
            exported_version=None,
            state="pending",
            updated_at=now,
        )
        unit.db.add(state)
    else:
        projection(unit, generation, now, allow_empty=True)
        if state.canonical_version == 0 and (
            row.revision != 1
            or unit.db.scalar(select(Lead.id).where(Lead.id != row.id).limit(1)) is not None
        ):
            raise StoreError("LEAD_EMPTY_PROJECTION_INCOMPATIBLE")
    if state.canonical_version >= MAX_REVISION:
        raise ApiFailure("UNSUPPORTED_STATE")
    state.canonical_version += 1
    state.state, state.updated_at = "pending", now
    unit.db.add(
        ExportIntent(
            id=str(uuid4()),
            lead_id=row.id,
            lead_revision=row.revision,
            store_generation=generation,
            projection_version=state.canonical_version,
            state="pending",
            attempts=0,
            last_error_code=None,
            created_at=now,
        )
    )


def create(
    unit: OwnerUnit,
    *,
    journey_id: str,
    session_id: str,
    supplied: LeadValues,
    now: str,
    retention_days: int,
) -> Lead:
    require_write(unit)
    row = Lead(
        id=str(uuid4()),
        owner_id=unit.owner_id,
        journey_id=journey_id,
        source_session_reference=session_id,
        revision=1,
        stage="interested",
        values_json=supplied.model_dump(mode="json"),
        created_at=now,
        updated_at=now,
        expires_at=expires(now, retention_days),
    )
    unit.db.add(row)
    unit.db.flush()
    return row


def advance(row: Lead, expected: int, now: str, retention_days: int) -> None:
    visible(row, now)
    if row.revision != expected:
        raise ApiFailure("LEAD_REVISION_CONFLICT")
    if row.revision >= MAX_REVISION:
        raise ApiFailure("UNSUPPORTED_STATE")
    row.revision += 1
    row.updated_at, row.expires_at = now, expires(now, retention_days)
