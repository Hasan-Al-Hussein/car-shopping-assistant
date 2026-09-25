"""BE15 participant: provisional facts in the caller's authorized write unit.

The caller owns accepted-review/capacity validation, terminal outcome construction,
commit and replay. It must discard this return if any part of its transaction fails.
No Store open, commit, file, CSV, provider or network work happens here.
"""

from dataclasses import dataclass

from sqlalchemy import select

from app.api.schemas.leads import LeadSaved, RequestedExportOutcome, ReviewedLeadCreation
from app.api.schemas.viewings import BookingCoreReceipt
from app.core.errors import ApiFailure
from app.database.models import LeadBooking, StoreMetadata
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.leads import repository as repo
from app.sessions.repository import live_session
from app.sessions.state import copied
from app.shortlist.inventory import ReferenceBatch, ShortlistInventory, key, recheck


@dataclass(frozen=True)
class ParticipatingLead:
    lead: LeadSaved
    csv: RequestedExportOutcome


class LeadParticipant:
    def __init__(self, *, inventory: ShortlistInventory | None = None) -> None:
        self.inventory = inventory

    def apply(
        self,
        unit: OwnerUnit,
        *,
        accepted: BookingCoreReceipt,
        generation: str,
        now: str,
        retention_days: int,
        prepared: ReferenceBatch | None = None,
    ) -> ParticipatingLead:
        repo.require_write(unit)
        metadata = unit.db.get(StoreMetadata, 1)
        if metadata is None or metadata.store_generation != generation:
            raise ApiFailure("STORE_GENERATION_CHANGED")
        try:
            accepted = copied(BookingCoreReceipt, accepted)
        except (AttributeError, TypeError, ValueError):
            raise ApiFailure("VALIDATION_ERROR") from None
        review = accepted.review
        if review.store_generation != generation:
            raise ApiFailure("STORE_GENERATION_CHANGED")
        # Caller stages its actual successful booking/outcome before invoking this participant.
        booking = unit.booking(accepted.booking_id)
        authority = unit.operation(review.operation_key)
        if (
            booking.immutable_receipt_json != accepted.model_dump(mode="json")
            or booking.review_id != review.review_id
            or booking.confirmed_at != accepted.confirmed_at
            or (booking.namespace, booking.snapshot_id, booking.source_id) != key(review.ref)
            or booking.resource_id != review.resource_id
            or booking.starts_at_utc != review.starts_at_utc
            or booking.ends_at_utc != review.ends_at_utc
            or booking.timezone != review.timezone
            or authority.review.id != review.review_id
            or authority.review.state != "consumed"
            or authority.review.store_generation != generation
            or authority.outcome is None
            or authority.outcome.id != booking.operation_id
            or authority.outcome.terminal_at != accepted.confirmed_at
            or accepted.confirmed_at != now
        ):
            raise StoreError("LEAD_ACCEPTED_BOOKING_INCOMPATIBLE")
        if (
            unit.db.scalar(
                select(LeadBooking.booking_id).where(
                    LeadBooking.booking_id == booking.id,
                )
            )
            is not None
        ):
            # Operation replay belongs to BE15 and must not reapply this participant.
            raise ApiFailure("UNSUPPORTED_STATE")
        session = live_session(unit, review.session_id, now)
        unit.journey(session.journey_id)
        row = unit.lead_for_journey(session.journey_id)
        change = review.lead_change
        if isinstance(change, ReviewedLeadCreation):
            if row is not None or session.revision != change.source_session_revision:
                raise ApiFailure("REVIEW_STALE")
            refs = tuple(key(ref) for ref in change.values.selected_refs)
            if refs:
                if prepared is None or tuple(key(item.ref) for item in prepared.items) != refs:
                    raise ApiFailure("STORE_UNAVAILABLE")
                if any(item.state == "missing" for item in prepared.items):
                    raise ApiFailure("NOT_FOUND")
                recheck(unit, prepared, generation, self.inventory)
            row = repo.create(
                unit,
                journey_id=session.journey_id,
                session_id=session.id,
                supplied=change.values,
                now=now,
                retention_days=retention_days,
            )
        else:
            if row is None or row.id != change.lead_id:
                raise ApiFailure("REVIEW_STALE")
            existing = repo.record(unit, row, generation, now)
            if len(existing.booking_ids) >= 100 or row.revision != change.expected_revision:
                raise ApiFailure("REVIEW_STALE")
            repo.advance(row, change.expected_revision, now, retention_days)
        row.stage = "viewing_confirmed"
        unit.db.add(LeadBooking(owner_id=unit.owner_id, lead_id=row.id, booking_id=booking.id))
        repo.enqueue(unit, row, generation, now)
        unit.db.flush()
        result = repo.record(unit, row, generation, now)
        return ParticipatingLead(
            lead=LeadSaved(state="saved", lead_id=row.id, revision=row.revision),
            csv=result.csv,
        )
