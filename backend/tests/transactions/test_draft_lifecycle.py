"""Actual session/lead services around draft recovery; synthetic terminal staging only."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.schemas.leads import ReviewedExistingLead
from app.api.schemas.operations import OperationRejected, OperationSucceeded
from app.api.schemas.sessions import ClarificationIntent, MessageRequest
from app.api.schemas.viewings import BookingCoreReceipt
from app.core.errors import ApiFailure
from app.database.models import Booking, Lead, OperationOutcome
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.leads.participant import LeadParticipant
from app.leads.service import LeadService
from app.sessions.state import SessionContent
from tests.platform.session_cases import answer
from tests.transactions.draft_fixtures import DraftHarness, confirmation, make_draft_harness, update
from tests.transactions.lead_fixtures import buyer_values, correction, save_request


@pytest.fixture
def drafts() -> DraftHarness:
    return make_draft_harness()


@pytest.mark.parametrize("has_draft", [False, True])
def test_pending_clarification_is_preserved_by_fresh_draft_commands(
    drafts: DraftHarness, has_draft: bool
) -> None:
    original = drafts.command(complete=False)
    prior = drafts.service.create(drafts.base.context(), original) if has_draft else None
    state = drafts.base.service.get(drafts.base.context(), drafts.sessions[0])
    admission = drafts.base.service.begin(
        drafts.base.context(),
        state.session_id,
        MessageRequest(
            client_message_id=str(uuid4()),
            expected_revision=state.revision,
            text="I need a family car",
        ),
    )
    question = ClarificationIntent(
        kind="clarification",
        intent_id=str(uuid4()),
        created_revision=admission.session.revision + 1,
        purpose="search_criteria",
        targets=["makes"],
        question="Which make should I use?",
    )
    content = SessionContent(
        criteria=state.criteria,
        selected_ref=state.selected_ref,
        active_presentation_id=state.active_presentation_id,
        current_draft_id=state.current_draft_id,
        pending_intent=question,
    )
    assert admission.ticket is not None
    drafts.base.service.complete(
        drafts.base.context(),
        admission.ticket,
        answer(admission).model_copy(update={"state": "clarification", "pending_intent": question}),
        update=content,
    )
    before = drafts.base.service.get(drafts.base.context(), state.session_id)
    counts, prepares = drafts.counts(), drafts.inventory.prepares
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        if prior is None:
            drafts.service.create(drafts.base.context(), drafts.command())
        else:
            drafts.service.update(
                drafts.base.context(), prior.draft_id, update(prior, "refresh_review")
            )
    assert drafts.base.service.get(drafts.base.context(), state.session_id) == before
    assert before.pending_intent == question and drafts.counts() == counts
    assert drafts.inventory.prepares == prepares
    if prior is not None:
        assert drafts.service.create(drafts.base.context(), original) == prior
        assert drafts.base.service.get(drafts.base.context(), state.session_id) == before


@pytest.mark.parametrize("change", ["correction", "expiry", "session_turn"])
def test_preserved_lead_and_session_binding_requires_current_review(
    drafts: DraftHarness, change: str
) -> None:
    leads = LeadService(drafts.base.auth)
    saved = leads.save(drafts.base.context(), save_request(drafts.sessions[0])).lead
    first = drafts.service.create(drafts.base.context(), drafts.command())
    assert first.review is not None and isinstance(first.review.lead_change, ReviewedExistingLead)
    assert (first.review.lead_change.lead_id, first.review.lead_change.expected_revision) == (
        saved.lead_id,
        1,
    )
    before = drafts.counts()
    if change == "correction":
        values = buyer_values()
        values.requirements = ["Explicit new buyer requirement"]
        leads.update(
            drafts.base.context(), saved.lead_id, correction(drafts.sessions[0], 1, values)
        )
    elif change == "expiry":

        def expire(db: Session) -> None:
            row = db.get(Lead, saved.lead_id)
            assert row is not None
            row.expires_at = utc_text(drafts.base.clock.value + timedelta(minutes=1))

        drafts.base.store.write(expire)
        drafts.base.clock.value += timedelta(minutes=1)
    else:
        current = drafts.base.service.get(drafts.base.context(), drafts.sessions[0])
        drafts.base.service.begin(
            drafts.base.context(),
            current.session_id,
            MessageRequest(
                client_message_id=str(uuid4()),
                expected_revision=current.revision,
                text="Another question",
            ),
        )
    observed = drafts.service.get(drafts.base.context(), first.draft_id)
    assert observed.state == "needs_details" and observed.review is not None
    assert observed.review.state == "invalidated"
    assert observed.review.operation_key == first.review.operation_key
    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        drafts.base.auth.write(
            drafts.base.context(),
            lambda unit: drafts.service.mark_submitted(
                unit,
                first.draft_id,
                confirmation(first),
                generation=drafts.base.store.generation,
                now=utc_text(drafts.base.clock.value),
            ),
        )
    if change == "expiry":
        with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
            drafts.service.update(
                drafts.base.context(), first.draft_id, update(first, "refresh_review")
            )
        assert drafts.counts() == before
    else:
        refreshed = drafts.service.update(
            drafts.base.context(), first.draft_id, update(first, "refresh_review")
        )
        assert refreshed.state == "reviewable" and refreshed.review is not None
        assert isinstance(refreshed.review.lead_change, ReviewedExistingLead)
        assert refreshed.review.lead_change.expected_revision == (
            2 if change == "correction" else 1
        )


@pytest.mark.parametrize("break_link", [False, True])
def test_successful_terminal_requires_owned_booking_and_lead_link(
    drafts: DraftHarness, break_link: bool
) -> None:
    LeadService(drafts.base.auth).save(drafts.base.context(), save_request(drafts.sessions[0]))
    first = drafts.service.create(drafts.base.context(), drafts.command())
    assert first.review is not None
    review_id = first.review.review_id

    def stage(unit: OwnerUnit) -> None:
        # A test caller stages a simulated terminal. This is not a capacity/BE15 implementation.
        row = unit.review(review_id)
        row.state = "consumed"
        now = utc_text(drafts.base.clock.value)
        expiry = utc_text(drafts.base.clock.value + timedelta(days=90))
        assert first.review is not None
        accepted = BookingCoreReceipt(
            state="confirmed_simulated",
            booking_id=str(uuid4()),
            review=first.review.model_copy(update={"state": "consumed"}),
            confirmed_at=now,
        )
        operation = OperationOutcome(
            id=str(uuid4()),
            owner_id=unit.owner_id,
            operation_key=row.operation_key,
            review_id=row.id,
            payload_hash=row.payload_hash,
            store_generation=row.store_generation,
            terminal_state="SUCCEEDED",
            terminal_at=now,
            replay_valid_until=expiry,
            terminal_result_json={"synthetic_staging": True},
        )
        unit.db.add(operation)
        unit.db.flush()
        unit.db.add(
            Booking(
                id=accepted.booking_id,
                owner_id=unit.owner_id,
                review_id=row.id,
                operation_id=operation.id,
                operation_state="SUCCEEDED",
                resource_id=accepted.review.resource_id,
                **accepted.review.ref.model_dump(),
                starts_at_utc=accepted.review.starts_at_utc,
                ends_at_utc=accepted.review.ends_at_utc,
                timezone=accepted.review.timezone,
                immutable_receipt_json=accepted.model_dump(mode="json"),
                confirmed_at=now,
                expires_at=expiry,
            )
        )
        unit.db.flush()
        participant = LeadParticipant().apply(
            unit,
            accepted=accepted,
            generation=drafts.base.store.generation,
            now=now,
            retention_days=90,
        )
        operation.terminal_result_json = OperationSucceeded(
            state="succeeded",
            operation_key=row.operation_key,
            review_id=row.id,
            original_store_generation=row.store_generation,
            terminal_at=now,
            replay_valid_until=expiry,
            booking=accepted,
            lead=participant.lead,
            csv=participant.csv,
        ).model_dump(mode="json")
        if break_link:
            unit.db.delete(unit.lead_booking(participant.lead.lead_id, accepted.booking_id))

    drafts.base.auth.write(drafts.base.context(), stage)
    observed = drafts.service.get(drafts.base.context(), first.draft_id)
    assert observed.state == ("unresolved" if break_link else "resolved")
    if break_link:
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            drafts.service.create(drafts.base.context(), drafts.command())
    else:
        new = drafts.service.create(drafts.base.context(), drafts.command())
        assert new.state == "reviewable" and new.draft_id != first.draft_id


@pytest.mark.parametrize("terminal", [False, True])
def test_parentless_review_retains_terminal_or_uncertain_authority(
    drafts: DraftHarness, terminal: bool
) -> None:
    first = drafts.service.create(drafts.base.context(), drafts.command())
    command = drafts.command()
    assert first.review is not None
    review_id = first.review.review_id

    def detach(unit: OwnerUnit) -> None:
        review = unit.review(review_id)
        review.state, review.draft_id = "consumed", None
        draft = unit.draft(first.draft_id)
        draft.active_review_id = None
        draft.state = "resolved"
        if terminal:
            now = utc_text(drafts.base.clock.value)
            expiry = utc_text(drafts.base.clock.value + timedelta(days=90))
            result = OperationRejected.model_validate(
                dict(
                    state="rejected",
                    operation_key=review.operation_key,
                    review_id=review.id,
                    original_store_generation=review.store_generation,
                    terminal_at=now,
                    replay_valid_until=expiry,
                    rejection_code="CAPACITY_UNAVAILABLE",
                    booking={"state": "not_created"},
                    lead={"state": "not_requested"},
                    csv={"state": "not_requested"},
                )
            )
            unit.db.add(
                OperationOutcome(
                    id=str(uuid4()),
                    owner_id=unit.owner_id,
                    operation_key=review.operation_key,
                    review_id=review.id,
                    payload_hash=review.payload_hash,
                    store_generation=review.store_generation,
                    terminal_state="REJECTED",
                    terminal_at=now,
                    replay_valid_until=expiry,
                    terminal_result_json=result.model_dump(mode="json"),
                )
            )
        # Use a separate session below; old parent context is never repaired by GET.

    drafts.base.auth.write(drafts.base.context(), detach)
    new_session = drafts.base.create()
    command.session_id, command.expected_session_revision = (
        new_session.session_id,
        new_session.revision,
    )
    if terminal:
        assert drafts.service.create(drafts.base.context(), command).state == "reviewable"
    else:
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            drafts.service.create(drafts.base.context(), command)
