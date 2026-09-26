"""General semantic route, history-bound references and read-only memory regressions."""

import asyncio
import json

from app.api.schemas.sessions import AnswerEvidence
from app.assistant.answer_assembly import GroundedAnswer
from app.assistant.coordinator import ReadCoordinator
from app.assistant.grounded_conversation import _conversation
from app.assistant.intent import QuestionRequest, TurnIntent

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    adapter,
    budget,
    listing,
    request,
    state,
)


def test_question_answer_establishes_references_without_a_search_page(monkeypatch):
    async def check():
        first, second = listing("one", "Nissan"), listing("two", "Nissan")
        captured = []

        async def compose(provider, message, session, turns, rows, **kwargs):
            captured.append((message.text, turns, rows, kwargs["scope"]))
            return GroundedAnswer(
                "Two Nissan listings. The second is newer.",
                (AnswerEvidence(ref=second.listing.ref, attributes=["make"]),),
                (),
            )

        monkeypatch.setattr("app.assistant.grounded_conversation.compose_grounded_answer", compose)
        provider, transport = adapter(
            TurnIntent(
                operation="question",
                question=QuestionRequest(source="inventory", include_descriptions=False),
            ),
            TurnIntent(operation="question", question=QuestionRequest(source="shown")),
            TurnIntent(operation="question", question=QuestionRequest(source="selected")),
        )
        sessions, inventory = FakeSessions(), FakeInventory(first, second)
        coordinator = ReadCoordinator(sessions, provider, inventory)
        for text in (
            "How large is your Nissan selection?",
            "Tell me more about those.",
            "Does that one mention warranty?",
        ):
            result = await coordinator.run(
                CONTEXT,
                sessions.current.session_id,
                request(sessions.current, text),
                request_state=state(),
                budget=budget(),
            )
            assert result.state == "answered" and result.pending_intent.kind == "none"
        assert sessions.current.active_presentation_id is None
        assert len(captured[0][2]) == 2
        assert captured[1][2] == (first, second)
        assert captured[2][2] == (first, second)
        assert len(captured[2][1]) == 2
        assert "Nissan" in json.loads(transport.requests[1].contents)["conversation"][0]["text"]

    asyncio.run(check())


def test_natural_memory_read_does_not_require_a_recognized_phrase():
    async def check():
        provider, _ = adapter(TurnIntent(operation="return"))
        sessions = FakeSessions()
        result = await ReadCoordinator(sessions, provider, FakeInventory()).run(
            CONTEXT,
            sessions.current.session_id,
            request(sessions.current, "What do you remember about me?"),
            request_state=state(),
            budget=budget(),
        )
        assert result.state == "answered"
        assert result.pending_intent.kind == "none"
        assert "save" in result.text.lower()

    asyncio.run(check())


def test_synthesis_history_keeps_fifth_displayed_car_after_a_social_turn(monkeypatch):
    async def check():
        async def greeting(*args, **kwargs):
            return GroundedAnswer("You're welcome!", (), ())

        monkeypatch.setattr("app.assistant.grounded_conversation.compose_grounded_answer", greeting)
        provider, _ = adapter(
            TurnIntent(operation="search"),
            TurnIntent(operation="smalltalk"),
        )
        sessions = FakeSessions()
        inventory = FakeInventory(*(listing(str(index), "Nissan") for index in range(1, 6)))
        coordinator = ReadCoordinator(sessions, provider, inventory)
        for text in ("Show me the cars", "Thanks"):
            result = await coordinator.run(
                CONTEXT, sessions.current.session_id, request(sessions.current, text),
                request_state=state(), budget=budget(),
            )
            assert result.state == "answered"
        turns = await sessions.recent_context(
            CONTEXT, sessions.current.session_id, before_revision=100
        )
        history = _conversation(turns)
        displayed = history[1].text
        assert "5. [5] Nissan" in displayed
        assert "Displayed 5 of 5" in displayed
        assert history[-1].text == "You're welcome!"

    asyncio.run(check())


def test_question_synthesis_failure_retains_conversation_and_search(monkeypatch):
    async def check():
        async def unavailable(*args, **kwargs):
            return None

        monkeypatch.setattr(
            "app.assistant.grounded_conversation.compose_grounded_answer", unavailable
        )
        provider, _ = adapter(
            TurnIntent(
                operation="question",
                question=QuestionRequest(source="inventory", include_descriptions=False),
            )
        )
        sessions = FakeSessions()
        original = sessions.current.criteria
        result = await ReadCoordinator(sessions, provider, FakeInventory()).run(
            CONTEXT,
            sessions.current.session_id,
            request(sessions.current, "Which adverts mention a price?"),
            request_state=state(),
            budget=budget(),
        )
        assert result.state == "provider_unavailable"
        assert sessions.current.criteria == original
        assert (
            len(
                await sessions.recent_context(
                    CONTEXT, sessions.current.session_id, before_revision=100
                )
            )
            == 1
        )
        assert "no matching" not in result.text.lower()

    asyncio.run(check())
