"""Unit-local reviewed authority and terminal proof for shared confirmation."""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.api.schemas.operations import OperationRejected, OperationSucceeded
from app.api.schemas.viewings import BookingCoreReceipt, ConfirmRequest
from app.core.errors import ApiFailure
from app.database.models import Booking, OperationOutcome, StoreMetadata
from app.database.store import StoreError
from app.identity.authorization import OperationAuthority, OwnerUnit
from app.identity.service import utc_text
from app.sessions import repository as sessions
from app.sessions.state import copied
from app.viewings import draft_repository as drafts
from app.viewings.draft_admission import PreparedViewing

type TerminalOutcome = OperationSucceeded | OperationRejected


def same_viewing_material(first: PreparedViewing, second: PreparedViewing) -> bool:
    # A trusted adapter may mint a fresh observation token for the same material.
    # Both tokens are independently rechecked; they need not be byte-identical.
    def material(value: PreparedViewing) -> tuple[object, ...]:
        return (
            value.generation,
            value.ref.model_dump(mode="json"),
            value.active_revision,
            value.index_version,
            value.resource_id,
            value.mapping_version,
            value.eligibility_version,
            value.configuration_version,
            value.configuration_revision,
        )

    return material(first) == material(second)


def command_copy(draft_id: str, command: ConfirmRequest) -> tuple[str, ConfirmRequest]:
    try:
        return sessions.valid_id(draft_id), copied(ConfirmRequest, command)
    except (AttributeError, TypeError, ValueError):
        raise ApiFailure("VALIDATION_ERROR") from None


def generation_current(unit: OwnerUnit, generation: str) -> None:
    metadata = unit.db.get(StoreMetadata, 1)
    if metadata is None or metadata.store_generation != generation:
        raise ApiFailure("STORE_GENERATION_CHANGED")


def bound_authority(
    unit: OwnerUnit, draft_id: str, command: ConfirmRequest
) -> tuple[OperationAuthority, drafts.StoredReview]:
    # Resolve the owned review first, so replacing its fixed key never becomes a new action.
    row = unit.review(command.review_id)
    payload = drafts.stored_review(unit, row)
    review = payload.review
    if (
        draft_id,
        command.review_id,
        command.expected_draft_revision,
        command.operation_key,
        command.rules_version,
        command.store_generation,
    ) != (
        review.draft_id,
        review.review_id,
        review.draft_revision,
        review.operation_key,
        review.rules_version,
        review.store_generation,
    ):
        raise ApiFailure("IDEMPOTENCY_CONFLICT")
    return unit.operation(command.operation_key), payload


def terminal(
    unit: OwnerUnit, authority: OperationAuthority, now: str
) -> TerminalOutcome | None:
    outcome = authority.outcome
    if outcome is None:
        if authority.review.state in {"submitted", "consumed"}:
            raise ApiFailure("OPERATION_UNRESOLVED")
        return None
    try:
        result = drafts.OUTCOME.validate_python(outcome.terminal_result_json)
        if not isinstance(result, OperationSucceeded | OperationRejected):
            raise ValueError("NONTERMINAL")
        if (
            result.model_dump(mode="json") != outcome.terminal_result_json
            or authority.review.state != "consumed"
            or result.terminal_at > now
            or not drafts.terminal_proven(unit, authority.review)
        ):
            raise ValueError("INCONSISTENT")
        if isinstance(result, OperationSucceeded):
            booking = unit.booking(result.booking.booking_id)
            review = result.booking.review
            if (
                booking.resource_id,
                booking.namespace,
                booking.snapshot_id,
                booking.source_id,
                booking.starts_at_utc,
                booking.ends_at_utc,
                booking.timezone,
                booking.confirmed_at,
                booking.expires_at,
                result.csv.store_generation,
            ) != (
                review.resource_id,
                review.ref.namespace,
                review.ref.snapshot_id,
                review.ref.source_id,
                review.starts_at_utc,
                review.ends_at_utc,
                review.timezone,
                result.booking.confirmed_at,
                result.replay_valid_until,
                result.original_store_generation,
            ) or result.booking.confirmed_at != result.terminal_at:
                raise ValueError("BOOKING_INCONSISTENT")
    except (TypeError, ValueError):
        raise StoreError("CONFIRMATION_TERMINAL_INCOMPATIBLE") from None
    if result.replay_valid_until <= now:
        raise ApiFailure("REPLAY_EXPIRED")
    return result


def capacity_taken(unit: OwnerUnit, accepted: BookingCoreReceipt) -> bool:
    drafts.require_write(unit)
    review = accepted.review
    # Global resource capacity, not owner/ref/snapshot capacity. Half-open intervals.
    return unit.db.scalar(
        select(Booking.id)
        .where(
            Booking.resource_id == review.resource_id,
            Booking.starts_at_utc < review.ends_at_utc,
            Booking.ends_at_utc > review.starts_at_utc,
        )
        .limit(1)
    ) is not None


def stage_outcome(
    unit: OwnerUnit,
    authority: OperationAuthority,
    *,
    succeeded: bool,
    now: str,
    retention_days: int,
) -> OperationOutcome:
    drafts.require_write(unit)
    if authority.outcome is not None:
        raise StoreError("CONFIRMATION_ALREADY_TERMINAL")
    row = authority.review
    outcome = OperationOutcome(
        id=str(uuid4()),
        owner_id=unit.owner_id,
        operation_key=row.operation_key,
        review_id=row.id,
        payload_hash=row.payload_hash,
        store_generation=row.store_generation,
        terminal_state="SUCCEEDED" if succeeded else "REJECTED",
        # Private staging only; the caller must replace and prove this before returning.
        terminal_result_json={},
        terminal_at=now,
        replay_valid_until=utc_text(datetime.fromisoformat(now) + timedelta(days=retention_days)),
    )
    unit.db.add(outcome)
    unit.db.flush()
    return outcome


def stage_booking(
    unit: OwnerUnit, outcome: OperationOutcome, accepted: BookingCoreReceipt
) -> None:
    drafts.require_write(unit)
    review = accepted.review
    unit.db.add(
        Booking(
            id=accepted.booking_id,
            owner_id=unit.owner_id,
            review_id=review.review_id,
            operation_id=outcome.id,
            operation_state="SUCCEEDED",
            **review.ref.model_dump(),
            resource_id=review.resource_id,
            starts_at_utc=review.starts_at_utc,
            ends_at_utc=review.ends_at_utc,
            timezone=review.timezone,
            immutable_receipt_json=accepted.model_dump(mode="json"),
            confirmed_at=accepted.confirmed_at,
            expires_at=outcome.replay_valid_until,
        )
    )
    unit.db.flush()
