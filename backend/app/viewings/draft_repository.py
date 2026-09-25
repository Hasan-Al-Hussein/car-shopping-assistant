"""Unit-local draft/review state and observational lifecycle projection."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import TypeAdapter
from sqlalchemy import select

from app.api.schemas.common import DTO, Id, Revision
from app.api.schemas.leads import ReviewedExistingLead
from app.api.schemas.operations import OperationRejected, OperationStatus, OperationSucceeded
from app.api.schemas.sessions import ClarificationIntent, NoPendingIntent, ViewingReviewIntent
from app.api.schemas.viewings import AppointmentSelection, BookingDraft, BookingReview
from app.core.errors import ApiFailure
from app.database.models import Booking, ConversationSession
from app.database.models import BookingDraft as DraftRow
from app.database.models import BookingReview as ReviewRow
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.sessions import repository as sessions
from app.sessions.state import SessionContent, fingerprint
from app.viewings.draft_admission import DraftInventory, PreparedViewing, recheck
from app.viewings.scheduling import SchedulingError, ViewingRules

KIND = "viewing.draft.command"
MAX_REVISION = 2_147_483_647
OUTCOME: TypeAdapter[OperationStatus] = TypeAdapter(OperationStatus)


class StoredReview(DTO):
    version: Literal["viewing-review-1"] = "viewing-review-1"
    owner_id: Id
    session_revision: Revision
    review: BookingReview  # Immutable original valid view; lifecycle is the relational state.
    admission: PreparedViewing


class DraftReceipt(DTO):
    version: Literal["viewing-draft-command-1"] = "viewing-draft-command-1"
    generation: Id
    draft_id: Id
    source_message_id: Id | None = None


def require_write(unit: OwnerUnit) -> None:
    connection = unit.db.connection()
    if (
        not connection.in_transaction()
        or connection.get_execution_options().get("store_write") is not True
    ):
        raise StoreError("DRAFT_REQUIRES_CALLER_WRITE_UNIT")


def later(now: str, *, minutes: int) -> str:
    return utc_text(datetime.fromisoformat(now) + timedelta(minutes=minutes))


def digest(payload: StoredReview) -> str:
    return fingerprint(payload.model_dump(mode="json", exclude={"review": {"state"}}))


def stored_review(unit: OwnerUnit, row: ReviewRow) -> StoredReview:
    try:
        value = StoredReview.model_validate(row.immutable_payload_json)
        review = value.review
        if (
            value.model_dump(mode="json") != row.immutable_payload_json
            or value.owner_id != unit.owner_id
            or row.owner_id != unit.owner_id
            or review.state != "valid"
            or digest(value) != row.payload_hash
            or row.draft_id is not None
            and review.draft_id != row.draft_id
            or (
                review.review_id,
                review.draft_revision,
                review.operation_key,
                review.store_generation,
                review.issued_at,
                review.expires_at,
            )
            != (
                row.id,
                row.draft_revision,
                row.operation_key,
                row.store_generation,
                row.issued_at,
                row.expires_at,
            )
            or row.state not in {"valid", "invalidated", "expired", "submitted", "consumed"}
            or review.ref.model_dump(mode="json") != value.admission.ref.model_dump(mode="json")
            or review.resource_id != value.admission.resource_id
            or review.rules_version != value.admission.configuration_version
            or review.eligibility_version != value.admission.eligibility_version
            or review.store_generation != value.admission.generation
        ):
            raise ValueError("INCOMPATIBLE")
        return value
    except (TypeError, ValueError):
        raise StoreError("DRAFT_REVIEW_INCOMPATIBLE") from None


def terminal_proven(unit: OwnerUnit, row: ReviewRow) -> bool:
    """Retained immutable terminal authority, not mere row existence or current CSV."""
    authority = unit.operation(row.operation_key)
    outcome = authority.outcome
    if outcome is None:
        return False
    payload = stored_review(unit, row)
    try:
        result = OUTCOME.validate_python(outcome.terminal_result_json)
        if not isinstance(result, OperationSucceeded | OperationRejected):
            return False
        if (
            result.operation_key != row.operation_key
            or result.review_id != row.id
            or result.original_store_generation != row.store_generation
            or result.terminal_at != outcome.terminal_at
            or result.replay_valid_until != outcome.replay_valid_until
        ):
            return False
        if isinstance(result, OperationSucceeded):
            if outcome.terminal_state != "SUCCEEDED" or (
                result.booking.review.model_dump(mode="json", exclude={"state"})
                != payload.review.model_dump(mode="json", exclude={"state"})
            ):
                return False
            booking = unit.booking(result.booking.booking_id)
            lead = unit.lead(result.lead.lead_id)
            unit.lead_booking(lead.id, booking.id)
            return (
                booking.operation_id == outcome.id
                and booking.review_id == row.id
                and lead.revision >= result.lead.revision
                and booking.immutable_receipt_json == result.booking.model_dump(mode="json")
            )
        return (
            outcome.terminal_state == "REJECTED"
            and unit.db.scalar(
                select(Booking.id).where(
                    Booking.owner_id == unit.owner_id, Booking.operation_id == outcome.id
                )
            )
            is None
        )
    except (ApiFailure, TypeError, ValueError):
        return False


def owner_uncertain(unit: OwnerUnit) -> None:
    pending = list(
        unit.db.scalars(
            select(ReviewRow)
            .where(
                ReviewRow.owner_id == unit.owner_id,
                ReviewRow.state.in_(("submitted", "consumed")),
            )
            .order_by(ReviewRow.id)
            .limit(1001)
        )
    )
    if len(pending) > 1000:
        raise StoreError("DRAFT_RECOVERY_SCAN_LIMIT")
    if any(not terminal_proven(unit, row) for row in pending):
        raise ApiFailure("OPERATION_UNRESOLVED")


def editable(unit: OwnerUnit, row: DraftRow, expected: int) -> None:
    owner_uncertain(unit)
    if row.state in {"unresolved", "resolved", "discarded"}:
        raise ApiFailure("UNSUPPORTED_STATE")
    if row.revision != expected:
        raise ApiFailure("REVISION_CONFLICT")
    if row.revision >= MAX_REVISION:
        raise ApiFailure("UNSUPPORTED_STATE")


def invalidate(unit: OwnerUnit, row: DraftRow) -> None:
    if row.active_review_id is None:
        return
    review = unit.review_for_draft(row.id, row.active_review_id)
    stored_review(unit, review)
    if review.state in {"submitted", "consumed"}:
        raise ApiFailure("OPERATION_UNRESOLVED")
    review.state = "invalidated"
    row.active_review_id = None


def appointment(row: DraftRow) -> AppointmentSelection | None:
    try:
        return (
            None
            if row.appointment_json is None
            else AppointmentSelection.model_validate(
                row.appointment_json,
            )
        )
    except (TypeError, ValueError):
        raise StoreError("DRAFT_APPOINTMENT_INCOMPATIBLE") from None


def lead_current(
    unit: OwnerUnit, review: BookingReview, session: ConversationSession, now: str
) -> bool:
    lead = unit.lead_for_journey(session.journey_id)
    change = review.lead_change
    if isinstance(change, ReviewedExistingLead):
        return (
            lead is not None
            and (lead.id, lead.revision)
            == (
                change.lead_id,
                change.expected_revision,
            )
            and lead.expires_at > now
        )
    return lead is None and session.revision == change.source_session_revision


def view(
    unit: OwnerUnit,
    row: DraftRow,
    *,
    now: str,
    generation: str,
    rules: ViewingRules,
    gateway: DraftInventory | None,
) -> BookingDraft:
    if row.session_id is None:
        raise ApiFailure("NOT_FOUND")
    if row.state not in {
        "needs_details",
        "reviewable",
        "suspended",
        "discarded",
        "resolved",
        "unresolved",
    }:
        raise StoreError("DRAFT_STATE_INCOMPATIBLE")
    if row.state in {"suspended", "discarded"} and row.active_review_id is not None:
        raise StoreError("DRAFT_STATE_INCOMPATIBLE")
    session = unit.session(row.session_id)
    selected = appointment(row)
    required: list[str] = [] if selected is not None else ["appointment"]
    state = row.state
    review: BookingReview | None = None
    if row.active_review_id is not None:
        stored = unit.review_for_draft(row.id, row.active_review_id)
        payload = stored_review(unit, stored)
        review = payload.review.model_copy(update={"state": stored.state}, deep=True)
        if stored.state in {"submitted", "consumed"}:
            state = "resolved" if terminal_proven(unit, stored) else "unresolved"
        elif row.expires_at <= now or stored.expires_at <= now:
            review.state = "expired"
            state, required = (
                "needs_details",
                ["draft_expired" if row.expires_at <= now else "review_refresh"],
            )
        elif stored.state == "valid":
            try:
                recheck(unit, payload.admission, generation, rules, gateway)
                rules.validate_interval(
                    datetime.fromisoformat(review.starts_at_utc),
                    datetime.fromisoformat(review.ends_at_utc),
                    now=datetime.fromisoformat(now),
                    local_start=review.local_start,
                )
                context = sessions.content(session)
                pending = context.pending_intent
                if (
                    session.expires_at <= now
                    or session.revision != payload.session_revision
                    or context.current_draft_id != row.id
                    or not isinstance(pending, ViewingReviewIntent)
                    or (pending.draft_id, pending.review_id, pending.operation_key)
                    != (
                        row.id,
                        review.review_id,
                        review.operation_key,
                    )
                    or not lead_current(unit, review, session, now)
                ):
                    raise ApiFailure("REVIEW_STALE")
            except (ApiFailure, SchedulingError):
                review.state = "invalidated"
                state, required = "needs_details", ["review_refresh"]
            else:
                state = "reviewable"
        else:
            state, required = "needs_details", ["review_refresh"]
    elif state not in {"suspended", "discarded", "resolved", "unresolved"}:
        state = "needs_details"
        if row.expires_at <= now:
            required = ["draft_expired"]
        elif selected is not None:
            required = ["review_refresh"]
    try:
        return BookingDraft.model_validate(
            dict(
                draft_id=row.id,
                session_id=row.session_id,
                revision=row.revision,
                ref=dict(
                    namespace=row.namespace, snapshot_id=row.snapshot_id, source_id=row.source_id
                ),
                appointment=None if selected is None else selected.model_dump(mode="json"),
                state=state,
                expires_at=row.expires_at,
                required_fields=required,
                review=None if review is None else review.model_dump(mode="json"),
            )
        )
    except (TypeError, ValueError):
        raise StoreError("DRAFT_STATE_INCOMPATIBLE") from None


def allow_transition(content: SessionContent) -> None:
    if isinstance(content.pending_intent, ClarificationIntent):
        raise ApiFailure("UNSUPPORTED_STATE")


def session_transition(
    unit: OwnerUnit,
    session: ConversationSession,
    row: DraftRow,
    *,
    now: str,
) -> None:
    before = sessions.content(session)
    allow_transition(before)
    if session.revision >= MAX_REVISION:
        raise ApiFailure("UNSUPPORTED_STATE")
    session.state_json = transition_content(unit, session, row).model_dump(mode="json")
    session.revision += 1
    sessions.activity(session, now, 7)


def transition_content(
    unit: OwnerUnit, session: ConversationSession, row: DraftRow,
) -> SessionContent:
    """Pure field projection after a caller has proved the domain transition."""
    before = sessions.content(session)
    pending = NoPendingIntent(kind="none").model_dump(mode="json")
    if row.active_review_id is not None:
        review = unit.review_for_draft(row.id, row.active_review_id)
        pending = ViewingReviewIntent(
            kind="viewing_review",
            draft_id=row.id,
            review_id=review.id,
            operation_key=review.operation_key,
        ).model_dump(mode="json")
    return SessionContent.model_validate(
        {
            **before.model_dump(mode="json"),
            "current_draft_id": None if row.state == "discarded" else row.id,
            "pending_intent": pending,
        }
    )


def receipt(
    unit: OwnerUnit, action_id: str, payload_hash: str, generation: str, now: str,
    *, source_message_id: str | None = None,
) -> DraftRow | None:
    prior = sessions.receipt(unit, KIND, action_id, payload_hash, now)
    if prior is None:
        return None
    try:
        saved = DraftReceipt.model_validate(prior.result_json)
    except (TypeError, ValueError):
        raise StoreError("DRAFT_RECEIPT_INCOMPATIBLE") from None
    if saved.generation != generation:
        raise ApiFailure("STORE_GENERATION_CHANGED")
    if source_message_id is not None and saved.source_message_id != source_message_id:
        raise ApiFailure("IDEMPOTENCY_CONFLICT")
    row = unit.draft(saved.draft_id)
    if prior.applied_revision > row.revision:
        raise StoreError("DRAFT_RECEIPT_INCOMPATIBLE")
    return row
