"""A3C scheduling tests with narrow fakes; not actual P9 durability evidence."""

import asyncio
from uuid import uuid4

import pytest

from app.api.schemas.sessions import ClarificationIntent, MessageRequest, MessageResult
from app.assistant.budget import TurnBudget
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import TurnIntent
from app.assistant.provider import TransportResponse
from app.core.config import Settings
from app.core.errors import ApiFailure
from app.sessions.state import SessionContent

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    ScriptedTransport,
    adapter,
    budget,
    provider,
    request,
    response,
    session,
    state,
)


def setup_reply() -> tuple[FakeSessions, ClarificationIntent, MessageRequest]:
    pending = ClarificationIntent(
        kind="clarification",
        intent_id=str(uuid4()),
        created_revision=0,
        purpose="search_criteria",
        targets=["budget"],
        question="Which currency and total cash amount should the budget use?",
    )
    sessions = FakeSessions(session(pending_intent=pending.model_dump(mode="json")))
    value = request(
        sessions.current,
        "cash up to AED 60k",
        clarification_reply={
            "intent_id": pending.intent_id,
            "created_revision": pending.created_revision,
        },
    )
    return sessions, pending, value


def complete_intent() -> TurnIntent:
    return TurnIntent.model_validate(
        {
            "operation": "search",
            "patches": [
                {
                    "kind": "range",
                    "field": "budget",
                    "operation": "refine",
                    "currency": "AED",
                    "basis": "cash",
                    "maximum": {"text": "60k"},
                    "quote": "cash up to AED 60k",
                }
            ],
        }
    )


async def run(
    coordinator: ReadCoordinator,
    sessions: FakeSessions,
    value: MessageRequest,
    ledger: TurnBudget | None = None,
) -> MessageResult:
    return await coordinator.run(
        CONTEXT,
        sessions.current.session_id,
        value,
        request_state=state(),
        budget=ledger or budget(),
    )


@pytest.mark.parametrize("interrupted", [False, True])
def test_cancelled_matched_reply_retains_question_and_retry_has_no_new_work(
    interrupted: bool,
) -> None:
    async def exercise() -> None:
        sessions, pending, value = setup_reply()
        started = asyncio.Event()
        inventory = FakeInventory()

        async def waiting() -> TransportResponse:
            started.set()
            await asyncio.Future[None]()
            raise AssertionError("unreachable")

        transport = ScriptedTransport(waiting)
        coordinator = ReadCoordinator(sessions, provider(transport), inventory)
        task = asyncio.create_task(run(coordinator, sessions, value))
        try:
            await asyncio.wait_for(started.wait(), 2)
            assert sessions.current.pending_intent == pending
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert sessions.completions == [] and inventory.calls == []
            if interrupted:
                sessions.turns[value.client_message_id].status = "interrupted"
            with pytest.raises(
                ApiFailure, match="UNSUPPORTED_STATE" if interrupted else "OPERATION_UNRESOLVED"
            ):
                await run(coordinator, sessions, value)
            assert len(transport.requests) == 1 and sessions.current.pending_intent == pending
            model, _ = adapter(TurnIntent(operation="search"))
            later = await run(
                ReadCoordinator(sessions, model, inventory),
                sessions,
                request(sessions.current, "Browse cars"),
            )
            assert later.state == "clarification" and later.pending_intent == pending
            assert inventory.calls == [] and sessions.current.criteria.filters.budget is None
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_deadline_exhaustion_after_admission_cannot_remove_question() -> None:
    async def exercise() -> None:
        sessions, pending, value = setup_reply()
        now = [0.0]
        ledger = TurnBudget(Settings().timeouts, 30.0, clock=lambda: now[0])

        async def late() -> TransportResponse:
            now[0] = 30.0
            return response(complete_intent())

        inventory = FakeInventory()
        coordinator = ReadCoordinator(sessions, provider(ScriptedTransport(late)), inventory)
        with pytest.raises(ApiFailure, match="PROVIDER_TIMEOUT"):
            await run(coordinator, sessions, value, ledger)
        assert sessions.current.pending_intent == pending and sessions.completions == []
        assert inventory.calls == [] and sessions.current.criteria.filters.budget is None

    asyncio.run(exercise())


def test_late_matched_reply_cannot_resolve_a_newer_question() -> None:
    async def exercise() -> None:
        sessions, pending, value = setup_reply()
        started, release = asyncio.Event(), asyncio.Event()

        async def delayed() -> TransportResponse:
            started.set()
            await release.wait()
            return response(complete_intent())

        inventory = FakeInventory()
        coordinator = ReadCoordinator(sessions, provider(ScriptedTransport(delayed)), inventory)
        task = asyncio.create_task(run(coordinator, sessions, value))
        try:
            await asyncio.wait_for(started.wait(), 2)
            newer = await sessions.begin(
                CONTEXT, sessions.current.session_id, request(sessions.current, "Clarify make")
            )
            assert newer.ticket is not None
            replacement = ClarificationIntent(
                kind="clarification",
                intent_id=str(uuid4()),
                created_revision=newer.session.revision,
                purpose="search_criteria",
                targets=["makes"],
                question="Which make should be required?",
            )
            result = MessageResult(
                client_message_id=newer.request.client_message_id,
                session_id=newer.session.session_id,
                turn_revision=newer.session.revision,
                current_revision=newer.session.revision,
                state="clarification",
                text=replacement.question,
                pending_intent=replacement,
                persistence="not_saved",
                provider_state="not_used",
            )
            await sessions.complete(
                CONTEXT, newer.ticket, result, update=SessionContent(pending_intent=replacement)
            )
            release.set()
            older = await asyncio.wait_for(task, 2)
            assert older.state == "superseded" and older.turn_revision == 1
            assert sessions.current.pending_intent == replacement != pending
            assert sessions.current.criteria.filters.budget is None and inventory.calls == []
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_hypothetical_answer_does_not_resolve_the_session_question() -> None:
    async def exercise() -> None:
        sessions, pending, value = setup_reply()
        model, _ = adapter(complete_intent().model_copy(update={"scope": "hypothetical"}))
        inventory = FakeInventory()
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert result.search is not None and result.pending_intent == pending
        assert sessions.current.criteria.filters.budget is None

    asyncio.run(exercise())
