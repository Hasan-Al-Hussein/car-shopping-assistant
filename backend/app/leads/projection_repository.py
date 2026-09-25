"""Bounded canonical CSV snapshots and projection-only acknowledgement writes."""

from dataclasses import dataclass

from sqlalchemy import LargeBinary, cast, func, select, update
from sqlalchemy.orm import Session

from app.api.schemas.leads import LeadValues
from app.database.models import Booking, ExportIntent, ExportState, Lead, LeadBooking, OperationOutcome
from app.database.store import StoreError
from app.leads.csv_serialization import LeadExportRow

MAX_ROWS = 1000
MAX_INTENTS = 10000
MAX_ROW_JSON = 65536
MAX_TOTAL_JSON = 4 * 1024 * 1024
MAX_REVISION = 2_147_483_647


class ProjectionError(ValueError):
    """Closed implementation-owned code; no buyer values or filesystem details."""


class StaleProjection(ProjectionError):
    pass


@dataclass(frozen=True)
class ProjectionSnapshot:
    generation: str
    version: int
    captured_at: str
    rows: tuple[LeadExportRow, ...]
    valid_until: str | None


def state(db: Session, generation: str) -> ExportState | None:
    value = db.get(ExportState, 1)
    if value is None:
        if db.scalar(select(Lead.id).limit(1)) is not None:
            raise ProjectionError("CSV_METADATA_MISSING")
        return None
    if value.store_generation != generation:
        raise ProjectionError("CSV_GENERATION_RECONCILIATION_REQUIRED")
    if (
        value.state not in {"current", "pending", "failed"}
        or not 0 <= value.canonical_version <= MAX_REVISION
        or value.exported_version is not None
        and not 0 <= value.exported_version <= value.canonical_version
        or value.state == "current" and value.exported_version != value.canonical_version
    ):
        raise ProjectionError("CSV_METADATA_INCOMPATIBLE")
    return value


def capture(db: Session, generation: str, now: str) -> ProjectionSnapshot | None:
    current = state(db, generation)
    if current is None:
        return None
    size = func.length(cast(Lead.values_json, LargeBinary))
    count, largest, total = db.execute(
        select(func.count(Lead.id), func.max(size), func.sum(size))
    ).one()
    if count > MAX_ROWS or (largest or 0) > MAX_ROW_JSON or (total or 0) > MAX_TOTAL_JSON:
        raise ProjectionError("CSV_CANONICAL_SNAPSHOT_LIMIT")
    intent_count = db.scalar(select(func.count()).select_from(ExportIntent)) or 0
    if intent_count > MAX_INTENTS:
        raise ProjectionError("CSV_INTENT_LIMIT")
    bad_intent = db.scalar(
        select(ExportIntent.id)
        .where(
            (ExportIntent.store_generation != generation)
            | (ExportIntent.projection_version > current.canonical_version)
            | (ExportIntent.state.not_in(("pending", "failed", "current")))
        )
        .limit(1)
    )
    if bad_intent is not None:
        raise ProjectionError("CSV_INTENT_INCOMPATIBLE")
    try:
        leads = list(db.scalars(select(Lead).order_by(Lead.id).limit(MAX_ROWS + 1)))
    except (TypeError, ValueError):
        raise ProjectionError("CSV_LEAD_INCOMPATIBLE") from None
    if current.canonical_version == 0 and leads:
        raise ProjectionError("CSV_METADATA_INCOMPATIBLE")
    links = list(
        db.execute(
            select(LeadBooking.lead_id, LeadBooking.booking_id, LeadBooking.owner_id)
            .order_by(LeadBooking.lead_id, LeadBooking.booking_id)
            .limit(MAX_ROWS * 100 + 1)
        )
    )
    if len(links) > MAX_ROWS * 100:
        raise ProjectionError("CSV_BOOKING_LINK_LIMIT")
    proven = set(
        db.scalars(
            select(LeadBooking.booking_id)
            .join(Booking, (Booking.id == LeadBooking.booking_id)
                  & (Booking.owner_id == LeadBooking.owner_id))
            .join(OperationOutcome, (OperationOutcome.id == Booking.operation_id)
                  & (OperationOutcome.owner_id == Booking.owner_id)
                  & (OperationOutcome.review_id == Booking.review_id)
                  & (OperationOutcome.terminal_state == "SUCCEEDED"))
            .limit(MAX_ROWS * 100 + 1)
        )
    )
    by_lead: dict[str, list[str]] = {lead.id: [] for lead in leads}
    owners = {lead.id: lead.owner_id for lead in leads}
    for lead_id, booking_id, owner_id in links:
        if lead_id not in by_lead or owners[lead_id] != owner_id or booking_id not in proven:
            raise ProjectionError("CSV_BOOKING_LINK_INCOMPATIBLE")
        by_lead[lead_id].append(booking_id)
    rows = []
    for lead in leads:
        if lead.expires_at <= now:
            # Retention must remove/reconcile canonical rows with a versioned intent.
            # A repair never exports expired values or silently renews their lifetime.
            raise ProjectionError("CSV_RETENTION_RECONCILIATION_REQUIRED")
        if (
            lead.updated_at > now
            or not 1 <= lead.revision <= MAX_REVISION
            or (lead.stage == "viewing_confirmed") != bool(by_lead[lead.id])
        ):
            raise ProjectionError("CSV_LEAD_INCOMPATIBLE")
        try:
            rows.append(LeadExportRow.model_validate(dict(
                lead_id=lead.id, lead_revision=lead.revision, owner_reference=lead.owner_id,
                journey_reference=lead.journey_id,
                source_session_reference=lead.source_session_reference,
                created_at_utc=lead.created_at, updated_at_utc=lead.updated_at,
                stage=lead.stage, values=LeadValues.model_validate(lead.values_json),
                booking_ids=by_lead[lead.id],
            )))
        except (TypeError, ValueError):
            raise ProjectionError("CSV_LEAD_INCOMPATIBLE") from None
    return ProjectionSnapshot(
        generation, current.canonical_version, now, tuple(rows),
        min((lead.expires_at for lead in leads), default=None),
    )


def fence(db: Session, snapshot: ProjectionSnapshot, now: str) -> None:
    current = state(db, snapshot.generation)
    if current is None or current.canonical_version != snapshot.version:
        raise StaleProjection("CSV_CANONICAL_VERSION_ADVANCED")
    require_unexpired(snapshot, now)


def require_unexpired(snapshot: ProjectionSnapshot, now: str) -> None:
    if snapshot.valid_until is not None and now >= snapshot.valid_until:
        raise ProjectionError("CSV_RETENTION_RECONCILIATION_REQUIRED")


def attempting(db: Session, snapshot: ProjectionSnapshot, now: str) -> None:
    fence(db, snapshot, now)
    current = db.get(ExportState, 1)
    assert current is not None
    current.state, current.updated_at = "pending", now
    db.execute(
        update(ExportIntent)
        .where(
            ExportIntent.store_generation == snapshot.generation,
            ExportIntent.projection_version <= snapshot.version,
            ExportIntent.state.in_(("pending", "failed")),
        )
        .values(
            state="pending", attempts=func.min(ExportIntent.attempts + 1, MAX_REVISION),
            last_error_code=None,
        )
    )


def acknowledge(db: Session, snapshot: ProjectionSnapshot, now: str) -> int:
    require_unexpired(snapshot, now)
    current = state(db, snapshot.generation)
    if current is None or current.canonical_version < snapshot.version:
        raise StoreError("CSV_ACKNOWLEDGEMENT_INCOMPATIBLE")
    if current.exported_version is not None and current.exported_version > snapshot.version:
        raise StoreError("CSV_ACKNOWLEDGEMENT_REGRESSION")
    current.exported_version = snapshot.version
    current.state = "current" if current.canonical_version == snapshot.version else "pending"
    current.updated_at = now
    db.execute(
        update(ExportIntent)
        .where(
            ExportIntent.store_generation == snapshot.generation,
            ExportIntent.projection_version <= snapshot.version,
        )
        .values(state="current", last_error_code=None)
    )
    return current.canonical_version


def failed(db: Session, generation: str, version: int | None, now: str) -> bool:
    current = state(db, generation)
    if current is None or version is not None and current.canonical_version != version:
        return False
    current.state, current.updated_at = "failed", now
    db.execute(
        update(ExportIntent)
        .where(
            ExportIntent.store_generation == generation,
            ExportIntent.projection_version <= current.canonical_version,
            ExportIntent.state != "current",
        )
        .values(state="failed", last_error_code="CSV_EXPORT_FAILED")
    )
    return True
