"""Race the real UI HTTP confirmation against the real typed chat confirmation.

The existing route fixture supplies isolated SQLite/CSV services and synthetic
Inventory only. This is not browser, live-provider or production-data evidence.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import select

from app.api.schemas.operations import OperationSucceeded
from app.api.schemas.sessions import ExplicitConfirmation, MessageRequest, MessageResult
from app.assistant.action_bridge import ActionBridge
from app.core.errors import ApiFailure
from app.database.models import Booking, Lead, OperationOutcome
from tests.integration.test_transaction_routes import RoutesHarness
from tests.integration.test_transaction_routes import h as h
from tests.transactions.draft_fixtures import confirmation


def test_ui_http_and_chat_confirmation_race_keeps_one_original_operation(h: RoutesHarness) -> None:
    draft = h.create()
    base = h.flow.drafts.base
    context = base.context()
    before = base.service.get(context, draft.session_id)
    command = confirmation(draft)
    request = MessageRequest(
        client_message_id=str(uuid4()),
        expected_revision=before.revision,
        text="Confirm this simulated viewing.",
        explicit_confirmation=ExplicitConfirmation.model_validate(
            {**command.model_dump(mode="json"), "draft_id": draft.draft_id}
        ),
    )
    bridge = ActionBridge(
        base.service, preferences=None, shortlist=None, confirmation=h.flow.participant
    )
    assert draft.review is not None
    assert request.explicit_confirmation is not None
    assert request.explicit_confirmation.operation_key == draft.review.operation_key
    assert h.flow.counts() == (0, 0, 0, 0, 0)

    prepared = Barrier(2, timeout=5)
    previous_prepares = h.flow.drafts.inventory.prepares

    def overlap_before_writes() -> None:
        # The fixture calls this after its Inventory read has closed. Both real
        # entrypoints must observe the same uncommitted review before proceeding.
        prepared.wait()

    def chat_confirm() -> MessageResult | ApiFailure:
        try:
            return bridge.confirm(context, draft.session_id, request)
        except ApiFailure as error:
            # UI-first advances R before a new chat receipt can be accepted.
            # Any other failure remains a test failure, not a permitted outcome.
            if error.code != "REVISION_CONFLICT":
                raise
            return error

    h.flow.drafts.inventory.after_prepare = overlap_before_writes
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            ui_future = pool.submit(h.confirm, draft)
            chat_future = pool.submit(chat_confirm)
            ui_response = ui_future.result(timeout=20)
            chat_result = chat_future.result(timeout=20)
    finally:
        h.flow.drafts.inventory.after_prepare = None

    assert h.flow.drafts.inventory.prepares == previous_prepares + 2
    assert ui_response.status_code == 200
    ui_result = OperationSucceeded.model_validate(ui_response.json()["data"])
    terminal = h.terminal()
    assert ui_result.operation_key == command.operation_key
    assert ui_result.review_id == command.review_id
    assert ui_result.original_store_generation == base.store.generation
    assert ui_result.model_dump(mode="json", exclude={"csv"}) == {
        key: value for key, value in terminal.items() if key != "csv"
    }
    assert h.flow.counts() == (1, 1, 1, 1, 1)
    assert base.store.read(lambda db: list(db.scalars(select(OperationOutcome.operation_key)))) == [
        command.operation_key
    ]
    assert base.store.read(lambda db: list(db.scalars(select(Booking.id)))) == [
        ui_result.booking.booking_id
    ]
    assert base.store.read(lambda db: list(db.scalars(select(Lead.id)))) == [ui_result.lead.lead_id]

    current = base.service.get(context, draft.session_id)
    assert current.revision == before.revision + 1
    assert current.pending_intent.kind == "none" and current.current_draft_id is None
    transcript = base.service.transcript(context, draft.session_id)
    if isinstance(chat_result, ApiFailure):
        assert chat_result.code == "REVISION_CONFLICT"
        assert transcript.items == []
    else:
        assert isinstance(chat_result.operation, OperationSucceeded)
        assert chat_result.provider_state == "not_used" and chat_result.persistence == "saved"
        assert chat_result.turn_revision == chat_result.current_revision == current.revision
        assert chat_result.operation.operation_key == command.operation_key
        assert chat_result.operation.booking == ui_result.booking
        assert chat_result.operation.lead == ui_result.lead
        assert len(transcript.items) == 1
        assert transcript.items[0].client_message_id == request.client_message_id
        assert transcript.items[0].assistant_result == chat_result
        assert bridge.confirm(context, draft.session_id, request) == chat_result

    # Both schedules recover the identical original terminal; neither may issue a
    # replacement review/key to conceal a stale chat revision or duplicate a lead.
    observed = h.application.status(context, command.operation_key, base.store.generation)
    assert isinstance(observed, OperationSucceeded)
    assert observed.operation_key == command.operation_key
    assert observed.booking == ui_result.booking and observed.lead == ui_result.lead
    replay = h.confirm(draft)
    assert replay.status_code == 200
    replay_result = OperationSucceeded.model_validate(replay.json()["data"])
    assert replay_result.operation_key == command.operation_key
    assert replay_result.booking == ui_result.booking and replay_result.lead == ui_result.lead
    assert h.terminal() == terminal and h.flow.counts() == (1, 1, 1, 1, 1)
    assert base.service.get(context, draft.session_id).revision == current.revision
