"""Repair internally contradictory interpretations without guessing the buyer's meaning."""

import asyncio

import pytest
from pydantic import ValidationError

from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import NumberToken, RangePatch, TurnIntent
from app.assistant.interpretation import CoherentTurnIntent

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    adapter,
    budget,
    request,
    state,
)


def contradictory(problem="currency"):
    return TurnIntent(operation="search", problem=problem, problem_target="budget", patches=[
        RangePatch(kind="range", field="budget", operation="refine",
                   maximum=NumberToken(text="50000"), currency="MAD", basis="cash",
                   quote="up to 50000 Moroccan dirhams"),
    ])


@pytest.mark.parametrize("problem", ["currency", "basis"])
def test_same_field_cannot_be_resolved_and_unresolved(problem):
    with pytest.raises(ValidationError, match="supplied and unresolved"):
        CoherentTurnIntent.model_validate(contradictory(problem).model_dump())


def test_genuine_ambiguity_with_no_selected_currency_remains_a_clarification():
    value = contradictory().model_dump()
    value["patches"][0]["currency"] = None
    assert CoherentTurnIntent.model_validate(value).problem == "currency"


def test_existing_bounded_model_repair_resolves_contradiction_before_search():
    async def check():
        first = contradictory()
        model, transport = adapter(first, first.model_copy(update={"problem": None}))
        sessions, inventory = FakeSessions(), FakeInventory()
        ledger = budget()
        result = await ReadCoordinator(sessions, model, inventory).run(
            CONTEXT, sessions.current.session_id,
            request(sessions.current, "up to 50000 Moroccan dirhams"),
            request_state=state(), budget=ledger,
        )
        assert ledger.provider_attempts == len(transport.requests) == 2
        assert transport.requests[1].repair is True
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert inventory.searches[0].filters.budget.currency == "MAD"
        assert inventory.searches[0].filters.budget.maximum == 5_000_000

    asyncio.run(check())


def test_repair_can_preserve_real_ambiguity_without_search_or_repeated_attempts():
    async def check():
        model, transport = adapter(
            contradictory(), TurnIntent(operation="search", problem="currency",
                                        problem_target="budget"),
        )
        sessions, inventory = FakeSessions(), FakeInventory()
        result = await ReadCoordinator(sessions, model, inventory).run(
            CONTEXT, sessions.current.session_id,
            request(sessions.current, "up to 50000 Moroccan dirhams"),
            request_state=state(), budget=budget(),
        )
        assert len(transport.requests) == 2 and inventory.searches == []
        assert result.state == "clarification"

    asyncio.run(check())
