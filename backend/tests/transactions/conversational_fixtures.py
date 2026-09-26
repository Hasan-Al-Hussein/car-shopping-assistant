"""Real Store/session/domain units with a test-only atomic message composition.

This exercises participant rollback; it is not Platform's unimplemented A9
completion wrapper or collection-authority implementation, and proves neither.
"""

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.leads import LeadSaveResult
from app.api.schemas.sessions import (
    LeadActionSucceeded,
    MessageActionResults,
    MessageRequest,
    MessageResult,
)
from app.database.models import (
    Booking,
    BookingDraft,
    BookingReview,
    CommandReceipt,
    ConversationSession,
    ExportIntent,
    ExportState,
    Lead,
    LeadBooking,
    Message,
    OperationOutcome,
)
from app.identity.authorization import OwnerUnit
from app.sessions import repository as sessions
from app.sessions.service import TurnAdmission
from app.sessions.state import StoredMessage, fingerprint
from tests.platform.session_cases import SessionHarness


def begin(base: SessionHarness, session_id: str, *, who: int = 0) -> TurnAdmission:
    state = base.service.get(base.context(who), session_id)
    return base.service.begin(
        base.context(who), session_id,
        MessageRequest(
            client_message_id=str(uuid4()), expected_revision=state.revision,
            text="Explicit synthetic local enquiry or viewing request",
        ),
    )


def finish_in_unit(
    unit: OwnerUnit, admission: TurnAdmission, *,
    lead: LeadSaveResult | None = None, action_id: str | None = None,
) -> MessageResult:
    row = unit.session(admission.session.session_id)
    message = unit.message(row.id, admission.message_id)
    saved = sessions.message_content(message)
    assert message.state == "pending" and saved.assistant_result is None
    actions = MessageActionResults()
    if lead is not None:
        assert action_id is not None
        actions.lead = LeadActionSucceeded(
            state="succeeded", client_action_id=action_id, result=lead,
        )
    result = MessageResult(
        client_message_id=message.client_message_id, session_id=row.id,
        turn_revision=message.accepted_revision, current_revision=row.revision,
        state="answered", text="Synthetic acknowledgement of actual participant result",
        pending_intent=sessions.content(row).pending_intent,
        actions=actions, persistence="saved", provider_state="not_used",
    )
    message.result_json = StoredMessage(
        request=saved.request, worker_epoch=saved.worker_epoch, assistant_result=result,
        completion_hash=fingerprint({"synthetic_participant_composition": result.model_dump(mode="json")}),
    ).model_dump(mode="json")
    message.state = "completed"
    return result


def facts(base: SessionHarness) -> tuple[tuple[dict[str, Any], ...], ...]:
    def read(db: Session) -> tuple[tuple[dict[str, Any], ...], ...]:
        return tuple(
            tuple(dict(row) for row in db.execute(
                select(model.__table__).order_by(*model.__table__.primary_key.columns)
            ).mappings())
            for model in (
                Lead, LeadBooking, ExportIntent, ExportState, CommandReceipt, Booking, OperationOutcome,
                BookingDraft, BookingReview, Message, ConversationSession,
            )
        )

    return base.store.read(read)
