"""Synthetic durable booking rows for future I11 real-Store capacity observations.

These fixtures prove query behavior, not valid confirmation/receipt production.
Inventory/configuration uses the existing accepted I8 fixture unchanged.
"""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.models import Booking, BookingReview, OperationOutcome, Owner
from app.identity.service import utc_text
from app.inventory.references import ImmutableInventoryRef
from tests.inventory.test_viewing_adapter import NOW, Case


def occupy(
    case: Case, start: datetime, end: datetime, *,
    resource_id: str | None = None, ref: ImmutableInventoryRef | None = None,
) -> None:
    """New foreign owner per row, expired replay retention, no buyer identity input."""
    selected = ref or case.ref
    if resource_id is None:
        item = case.reader.read_refs((case.ref,)).items[0]
        assert item.mapping is not None
        resource_id = item.mapping.resource_id
    owner, review, operation, booking = (str(uuid4()) for _ in range(4))
    issued = utc_text(NOW - timedelta(days=2))
    expired = utc_text(NOW - timedelta(days=1))
    opaque = "S" * 43
    payload_hash = "a" * 64

    def seed(db: Session) -> None:
        db.add(Owner(id=owner, created_at=issued, display_name="Synthetic foreign owner",
                     shortlist_revision=0, preference_revision=0))
        db.flush()
        db.add(BookingReview(
            id=review, owner_id=owner, draft_id=None, draft_revision=0,
            operation_key=opaque, payload_hash=payload_hash,
            immutable_payload_json={"synthetic_capacity_fixture": True},
            store_generation=case.store.generation, issued_at=issued,
            expires_at=expired, state="consumed",
        ))
        db.flush()
        db.add(OperationOutcome(
            id=operation, owner_id=owner, operation_key=opaque, review_id=review,
            payload_hash=payload_hash, store_generation=case.store.generation,
            terminal_state="SUCCEEDED", terminal_at=issued, replay_valid_until=expired,
            terminal_result_json={"synthetic_capacity_fixture": True},
        ))
        db.flush()
        db.add(Booking(
            id=booking, owner_id=owner, review_id=review, operation_id=operation,
            operation_state="SUCCEEDED", resource_id=resource_id,
            **selected.model_dump(), starts_at_utc=utc_text(start), ends_at_utc=utc_text(end),
            timezone="Asia/Dubai", confirmed_at=issued, expires_at=expired,
            immutable_receipt_json={"synthetic_capacity_fixture": True},
        ))

    case.store.write(seed)


def business_image(case: Case) -> tuple[tuple[tuple[object, ...], ...], ...]:
    """Exact synthetic business rows, including immutable JSON; no count-only proof."""
    tables = (
        "owners", "owner_credentials", "conversation_sessions", "messages", "bookings",
        "booking_drafts", "booking_reviews", "operation_outcomes", "leads", "export_intents",
        "rule_versions", "active_rules", "active_inventory", "operational_events",
    )

    def observe(db: Session) -> tuple[tuple[tuple[object, ...], ...], ...]:
        return tuple(
            tuple(tuple(row) for row in db.connection().exec_driver_sql(
                f'SELECT * FROM "{table}" ORDER BY 1'
            ).all())
            for table in tables
        )

    return case.store.read(observe)
