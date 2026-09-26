"""Real P9 persistence across caller departure; existing approved disposable Store harness."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import PresentationProof
from app.api.schemas.sessions import (
    ClarificationIntent,
    MessageRequest,
    MessageResult,
    NoPendingIntent,
)
from app.assistant.budget import TurnBudget
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import TurnIntent
from app.assistant.service_adapters import BoundedServiceWorker, SessionServiceAdapter
from app.core.config import Settings
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.sessions.service import TurnAdmission, TurnTicket
from app.sessions.state import SessionContent
from tests.platform.session_cases import answer

from .conversation_fakes import FakeInventory, adapter, budget, request, state
from .test_p9c_composition import pending_session, reply
from .test_service_worker import until


def test_cancelled_begin_can_commit_only_the_original_pending_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness, current, pending = pending_session()
    context, value = harness.context(), reply(current, pending)
    worker, started, release = BoundedServiceWorker(), Event(), Event()
    original = harness.service.begin

    def blocked(ctx: AuthorizedOwnerContext, sid: str, body: MessageRequest) -> TurnAdmission:
        started.set()
        assert release.wait(5)
        return original(ctx, sid, body)

    monkeypatch.setattr(harness.service, "begin", blocked)

    async def exercise() -> None:
        task = asyncio.create_task(
            SessionServiceAdapter(harness.service, worker, budget()).begin(
                context, current.session_id, value
            )
        )
        try:
            await until(started.is_set)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert worker.pending
            with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
                await SessionServiceAdapter(harness.service, worker, budget()).begin(
                    context, current.session_id, value
                )
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            await until(lambda: not worker.pending)
        monkeypatch.setattr(harness.service, "begin", original)
        facade = SessionServiceAdapter(harness.service, worker, budget())
        observed = await facade.get(context, current.session_id)
        assert observed.revision == current.revision + 1 and observed.pending_intent == pending
        replay = await facade.begin(context, current.session_id, value)
        assert replay.status == "pending" and replay.ticket is None
        model, transport = adapter(TurnIntent(operation="search"))
        inventory = FakeInventory()
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            await ReadCoordinator(facade, model, inventory).run(
                context, current.session_id, value, request_state=state(), budget=budget()
            )
        assert transport.requests == [] and inventory.calls == []
        assert (await facade.get(context, current.session_id)).revision == observed.revision

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        assert worker.close()


@pytest.mark.parametrize("newer_question", [False, True])
def test_late_complete_replays_original_result_and_cannot_replace_newer_question(
    monkeypatch: pytest.MonkeyPatch, newer_question: bool
) -> None:
    harness, current, pending = pending_session()
    context, value = harness.context(), reply(current, pending)
    admission = harness.service.begin(context, current.session_id, value)
    assert admission.ticket is not None
    result = answer(admission, "Original grounded answer").model_copy(
        update={"pending_intent": NoPendingIntent(kind="none")}
    )
    result = MessageResult.model_validate(result.model_dump(mode="json"))
    worker, started, release = BoundedServiceWorker(), Event(), Event()
    original = harness.service.complete
    calls: list[TurnTicket] = []

    def blocked(
        ctx: AuthorizedOwnerContext,
        ticket: TurnTicket,
        supplied: MessageResult,
        *,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
    ) -> MessageResult:
        calls.append(ticket)
        started.set()
        assert release.wait(5)
        return original(
            ctx, ticket, supplied, update=update, presentation=presentation, selection=selection
        )

    monkeypatch.setattr(harness.service, "complete", blocked)

    async def exercise() -> None:
        ledger = TurnBudget(Settings().timeouts, asyncio.get_running_loop().time() + 0.1)
        assert admission.ticket is not None
        task = asyncio.create_task(
            SessionServiceAdapter(harness.service, worker, ledger).complete(
                context, admission.ticket, result, update=SessionContent()
            )
        )
        replacement = None
        try:
            await until(started.is_set)
            with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
                await task
            assert worker.pending and len(calls) == 1
            if newer_question:

                def competing_write() -> ClarificationIntent:
                    observed = harness.service.get(context, current.session_id)
                    newer = harness.service.begin(
                        context, current.session_id, request(observed, "Clarify budget")
                    )
                    assert newer.ticket is not None
                    question = ClarificationIntent(
                        kind="clarification",
                        intent_id=str(uuid4()),
                        created_revision=newer.session.revision,
                        purpose="search_criteria",
                        targets=["budget"],
                        question="Which cash budget should apply?",
                    )
                    newer_result = answer(newer).model_copy(
                        update={
                            "state": "clarification",
                            "text": question.question,
                            "pending_intent": question,
                        }
                    )
                    original(
                        context,
                        newer.ticket,
                        newer_result,
                        update=SessionContent(pending_intent=question),
                    )
                    return question

                # Explicit external competitor, not a replacement Assistant worker.
                with ThreadPoolExecutor(max_workers=1) as competitor:
                    replacement = await asyncio.get_running_loop().run_in_executor(
                        competitor, competing_write
                    )
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            await until(lambda: not worker.pending)
        replay = await SessionServiceAdapter(harness.service, worker, budget()).begin(
            context, current.session_id, value
        )
        assert replay.status == "completed" and replay.ticket is None and replay.result is not None
        assert (
            replay.result.text == result.text
            and replay.result.client_message_id == value.client_message_id
        )
        assert replay.result.state == ("superseded" if newer_question else "answered")
        assert len(calls) == 1
        observed = await SessionServiceAdapter(harness.service, worker, budget()).get(
            context, current.session_id
        )
        if newer_question:
            assert observed.pending_intent == replacement
        else:
            assert observed.pending_intent.kind == "none"

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        assert worker.close()
