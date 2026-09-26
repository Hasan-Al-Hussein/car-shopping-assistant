"""Synthetic Store/BE09/P11 composition; Inventory and booking acceptance are test ports."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.leads import LeadSaveRequest, LeadUpdateRequest, LeadValues, ReviewedLeadChange
from app.api.schemas.viewings import BookingCoreReceipt, BookingReview
from app.database.models import (
    Booking,
    CommandReceipt,
    ExportIntent,
    Lead,
    LeadBooking,
    OperationOutcome,
    VehicleResource,
)
from app.database.models import (
    BookingReview as ReviewRow,
)
from app.database.store import assert_outside_write_transaction
from app.identity.authorization import OwnerUnit
from app.identity.credentials import encode_token
from app.identity.service import utc_text
from app.inventory.references import ImmutableInventoryRef
from app.leads.participant import LeadParticipant
from app.leads.service import LeadService
from app.sessions.state import fingerprint
from app.shortlist.inventory import ReferenceBatch
from tests.platform.memory_shortlist_cases import SyntheticShortlistInventory
from tests.platform.session_cases import SessionHarness, make_harness, ref


def buyer_values() -> LeadValues:
    return LeadValues.model_validate(
        dict(
            budget={"state": "missing"},
            requirements=["Family car — سيارة عائلية"],
            selected_refs=[],
            email={"state": "missing"},
            phone={"state": "declined"},
        )
    )


def save_request(session_id: str, supplied: LeadValues | None = None) -> LeadSaveRequest:
    return LeadSaveRequest(
        client_action_id=str(uuid4()),
        session_id=session_id,
        intent="save_local_enquiry",
        values=buyer_values() if supplied is None else supplied,
    )


def correction(session_id: str, revision: int, supplied: LeadValues) -> LeadUpdateRequest:
    return LeadUpdateRequest(
        client_action_id=str(uuid4()),
        expected_revision=revision,
        session_id=session_id,
        intent="correct_local_enquiry",
        values=supplied,
    )


class LeadInventoryFake(SyntheticShortlistInventory):
    """Existing compact synthetic identity check; still not a real BE07 adapter."""

    def __init__(self, sessions: SessionHarness) -> None:
        super().__init__(sessions)
        self.checks = 0

    @property
    def reads(self) -> int:
        return len(self.batches)

    def read(self, refs: tuple[ImmutableInventoryRef, ...]) -> ReferenceBatch:
        assert_outside_write_transaction()
        return super().read(refs)

    def recheck(self, db: Session, prepared: ReferenceBatch) -> None:
        assert db.connection().get_execution_options()["store_write"] is True
        super().recheck(db, prepared)
        self.checks += 1


@dataclass
class LeadHarness:
    sessions: SessionHarness
    service: LeadService
    participant: LeadParticipant
    inventory: LeadInventoryFake
    session_ids: tuple[str, str]

    def counts(self) -> tuple[int, int, int, int, int]:
        def read(db: Session) -> tuple[int, int, int, int, int]:
            return (
                db.scalar(select(func.count()).select_from(Lead)) or 0,
                db.scalar(select(func.count()).select_from(ExportIntent)) or 0,
                db.scalar(select(func.count()).select_from(LeadBooking)) or 0,
                db.scalar(select(func.count()).select_from(Booking)) or 0,
                db.scalar(
                    select(func.count())
                    .select_from(CommandReceipt)
                    .where(
                        CommandReceipt.command_kind == "lead.command",
                    )
                )
                or 0,
            )

        return self.sessions.store.read(read)


def make_lead_harness() -> LeadHarness:
    sessions = make_harness()
    first, second = sessions.create(0), sessions.create(1)
    inventory = LeadInventoryFake(sessions)
    return LeadHarness(
        sessions,
        LeadService(sessions.auth, inventory=inventory),
        LeadParticipant(inventory=inventory),
        inventory,
        (first.session_id, second.session_id),
    )


def staged_booking(
    harness: LeadHarness,
    unit: OwnerUnit,
    change: ReviewedLeadChange,
    *,
    session_id: str | None = None,
) -> BookingCoreReceipt:
    """Stage only synthetic accepted relational context; this does not test BE14/15 acceptance."""
    now = harness.sessions.clock.value
    stamp = utc_text(now)
    start = now + timedelta(days=1)
    resource_id = str(uuid4())
    review = BookingReview(
        review_id=str(uuid4()),
        draft_id=str(uuid4()),
        session_id=session_id or harness.session_ids[0],
        draft_revision=1,
        ref=ref(),
        resource_id=resource_id,
        starts_at_utc=utc_text(start),
        ends_at_utc=utc_text(start + timedelta(minutes=30)),
        local_start=(start + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S+04:00"),
        venue_label="Simulated local viewing — no real venue or reservation.",
        rules_version="TEST_RULES",
        eligibility_version="TEST_ELIGIBILITY",
        store_generation=harness.sessions.store.generation,
        operation_key=encode_token(uuid4().bytes + uuid4().bytes),
        issued_at=stamp,
        expires_at=utc_text(now + timedelta(minutes=5)),
        lead_change=change,
        state="consumed",
    )
    accepted = BookingCoreReceipt(
        state="confirmed_simulated",
        booking_id=str(uuid4()),
        review=review,
        confirmed_at=stamp,
    )
    unit.db.add(VehicleResource(id=resource_id, mapping_version="TEST", created_at=stamp))
    unit.db.flush()
    payload = review.model_dump(mode="json", exclude={"state"})
    digest = fingerprint(dict(owner=unit.owner_id, review=payload))
    unit.db.add(
        ReviewRow(
            id=review.review_id,
            owner_id=unit.owner_id,
            draft_id=None,
            draft_revision=1,
            operation_key=review.operation_key,
            payload_hash=digest,
            immutable_payload_json=payload,
            store_generation=review.store_generation,
            issued_at=stamp,
            expires_at=review.expires_at,
            state="consumed",
        )
    )
    unit.db.flush()
    operation_id = str(uuid4())
    end = utc_text(now + timedelta(days=90))
    unit.db.add(
        OperationOutcome(
            id=operation_id,
            owner_id=unit.owner_id,
            operation_key=review.operation_key,
            review_id=review.review_id,
            payload_hash=digest,
            store_generation=review.store_generation,
            terminal_state="SUCCEEDED",
            terminal_result_json={"test_staging_only": True},
            terminal_at=stamp,
            replay_valid_until=end,
        )
    )
    unit.db.flush()
    unit.db.add(
        Booking(
            id=accepted.booking_id,
            owner_id=unit.owner_id,
            review_id=review.review_id,
            operation_id=operation_id,
            operation_state="SUCCEEDED",
            resource_id=resource_id,
            **ref().model_dump(),
            starts_at_utc=review.starts_at_utc,
            ends_at_utc=review.ends_at_utc,
            timezone="Asia/Dubai",
            immutable_receipt_json=accepted.model_dump(mode="json"),
            confirmed_at=stamp,
            expires_at=end,
        )
    )
    unit.db.flush()
    return accepted
