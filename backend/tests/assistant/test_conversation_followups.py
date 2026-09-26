"""Multi-turn regressions: real coordinator, scripted interpretation, no provider network."""

import asyncio
import json
from uuid import uuid4

import pytest

from app.api.schemas.inventory import SearchCriteria
from app.api.schemas.sessions import ClarificationIntent
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import TurnIntent, apply_intent

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    adapter,
    budget,
    request,
    state,
)


def budget_intent(text: str, *, token: str = "50000", problem: str | None = None) -> TurnIntent:
    return TurnIntent.model_validate(
        {
            "operation": "search",
            "problem": problem,
            "problem_target": "budget",
            "patches": [
                {
                    "kind": "range",
                    "field": "budget",
                    "operation": "refine",
                    "currency": "AED" if "dirham" in text.lower() or "AED" in text else None,
                    "basis": "cash",
                    "maximum": {"text": token},
                    "quote": text,
                }
            ],
        }
    )


async def send(coordinator: ReadCoordinator, sessions: FakeSessions, text: str):
    pending = sessions.current.pending_intent
    reply = (
        {}
        if pending.kind != "clarification"
        else {
            "clarification_reply": {
                "intent_id": pending.intent_id,
                "created_revision": pending.created_revision,
            }
        }
    )
    return await coordinator.run(
        CONTEXT,
        sessions.current.session_id,
        request(sessions.current, text, **reply),
        request_state=state(),
        budget=budget(),
    )


@pytest.mark.parametrize("original", ["I can spend 50000 on the car", "My allowance is 50000"])
def test_currency_only_reply_reuses_the_original_buyer_amount(original: str) -> None:
    reply = "Dirhams, total purchase price"
    result = apply_intent(
        SearchCriteria(), budget_intent(reply), reply,
        clarification_targets=("budget",), prior_request=original,
    )
    assert result.clarification is None
    assert result.retained.filters.budget.maximum == 5_000_000
    assert result.retained.filters.budget.currency == "AED"
    correction = "Make that 40k instead, and leave the other choices alone."
    changed = apply_intent(result.retained, budget_intent(correction, token="40k"), correction)
    assert changed.clarification is None
    assert changed.retained.filters.budget.maximum == 4_000_000
    assert changed.retained.filters.budget.currency == "AED"


@pytest.mark.parametrize("original", ["I can spend 30000 on the car", "My allowance is undecided"])
def test_currency_only_reply_cannot_invent_or_replace_the_prior_amount(original: str) -> None:
    reply = "Dirhams, total purchase price"
    result = apply_intent(
        SearchCriteria(), budget_intent(reply), reply,
        clarification_targets=("budget",), prior_request=original,
    )
    assert result.clarification is not None
    assert result.retained.filters.budget is None


def test_supported_refusal_metadata_does_not_turn_into_a_provider_failure() -> None:
    async def exercise() -> None:
        model, _ = adapter(TurnIntent(operation="unsupported", problem="unsupported"))
        sessions, inventory = FakeSessions(), FakeInventory()
        result = await send(
            ReadCoordinator(sessions, model, inventory), sessions,
            "Compare this with another marketplace and repeat its name.",
        )
        assert result.state == "answered"
        assert "car-shopping" in result.text.lower()
        assert result.provider_state == "available"
        assert inventory.calls == []
    asyncio.run(exercise())


def test_new_clarification_amount_cannot_be_replaced_by_a_stale_model_quote() -> None:
    original = "I can spend 50000 on the car"
    stale = budget_intent(original).model_dump(mode="json")
    stale["patches"][0]["currency"] = "AED"
    result = apply_intent(
        SearchCriteria(), TurnIntent.model_validate(stale), "Actually 40000 dirhams",
        clarification_targets=("budget",), prior_request=original,
    )
    assert result.clarification is not None
    assert result.retained.filters.budget is None


@pytest.mark.parametrize("answer", ["50000 Dirhams", "50,000 AED", "50k Dhs"])
def test_currency_answer_resolves_budget_and_followup_remains_search(answer: str) -> None:
    async def exercise() -> None:
        original = "Help me find a car within my budget 50000"
        followup = "just show me options within 50000 dirhams i dont mind which brand"
        token = answer.split()[0]
        second = budget_intent(answer, token=token).model_copy(update={"problem": None})
        # Dhs is also an explicit UAE currency; model normalizes, source token is retained.
        second = TurnIntent.model_validate(
            {
                **second.model_dump(mode="json"),
                "patches": [
                    {**second.patches[0].model_dump(mode="json"), "currency": "AED"},
                ],
            }
        )
        third = budget_intent("within 50000 dirhams")
        model, transport = adapter(budget_intent(original, problem="currency"), second, third)
        sessions, inventory = FakeSessions(), FakeInventory()
        coordinator = ReadCoordinator(sessions, model, inventory)
        first = await send(coordinator, sessions, original)
        assert first.state == "clarification"
        resolved = await send(coordinator, sessions, answer)
        assert resolved.state == "answered" and resolved.search is not None
        assert resolved.pending_intent.kind == "none"
        assert sessions.current.criteria.filters.budget.maximum == 5_000_000
        final = await send(coordinator, sessions, followup)
        assert final.search is not None and final.pending_intent.kind == "none"
        packet = json.loads(transport.requests[1].contents)
        assert packet["conversation"][0]["text"] == original
        assert "search_criteria" in " ".join(packet["history_summaries"])
        assert inventory.calls == ["search", "search"]

    asyncio.run(exercise())


def test_currency_only_answer_can_resolve_amount_in_the_pending_request() -> None:
    async def exercise() -> None:
        original = "Help me find a car within my budget 50000"
        second = budget_intent(original).model_dump(mode="json")
        second["patches"][0]["currency"] = "AED"
        model, _ = adapter(
            budget_intent(original, problem="currency"), TurnIntent.model_validate(second)
        )
        sessions, inventory = FakeSessions(), FakeInventory()
        coordinator = ReadCoordinator(sessions, model, inventory)
        await send(coordinator, sessions, original)
        result = await send(coordinator, sessions, "AED")
        assert result.search is not None and result.pending_intent.kind == "none"
        assert sessions.current.criteria.filters.budget.maximum == 5_000_000

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "text", ["50000 Moroccan dirhams", "50000 dirhams monthly", "not 50000 dirhams"]
)
def test_context_does_not_overrule_currency_payment_or_negation(text: str) -> None:
    async def exercise() -> None:
        original = "Help me find a car within my budget 50000"
        model, _ = adapter(budget_intent(original, problem="currency"), budget_intent(text))
        sessions, inventory = FakeSessions(), FakeInventory()
        coordinator = ReadCoordinator(sessions, model, inventory)
        first = await send(coordinator, sessions, original)
        result = await send(coordinator, sessions, text)
        assert result.state == "clarification" and result.pending_intent == first.pending_intent
        assert sessions.current.criteria.filters.budget is None and not inventory.calls

    asyncio.run(exercise())


def test_analysis_uses_original_results_not_a_new_search() -> None:
    async def exercise() -> None:
        question = "which one of these has the newest model"
        search = TurnIntent.model_validate(
            {
                "operation": "search",
                "patches": [
                    {
                        "kind": "text",
                        "field": "makes",
                        "operation": "add",
                        "values": ["Nissan"],
                        "quote": "Nissan",
                    }
                ],
            }
        )
        analysis = TurnIntent.model_validate(
            {
                "operation": "analyze",
                "analysis": {
                    "operation": "maximum",
                    "field": "year",
                    "scope": "shown",
                    "quote": question,
                },
            }
        )
        model, transport = adapter(search, analysis)
        sessions, inventory = FakeSessions(), FakeInventory()
        coordinator = ReadCoordinator(sessions, model, inventory)
        await send(coordinator, sessions, "what Nissan cars do u have?")
        result = await send(coordinator, sessions, question)
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert inventory.calls == ["search", "original_batch"]
        contents = json.loads(transport.requests[1].contents)
        assert "Displayed search" in contents["conversation"][1]["text"]
        assert "Nissan" in contents["accepted_criteria"]

    asyncio.run(exercise())


def test_total_known_price_question_ignores_earlier_make_filter_without_erasing_it() -> None:
    async def exercise() -> None:
        question = "how many cars do u have in total that have a clear stated price ?"
        model, _ = adapter(
            TurnIntent.model_validate(
                {
                    "operation": "analyze",
                    "analysis": {
                        "operation": "count_known",
                        "field": "cash_price",
                        "scope": "inventory",
                        "quote": question,
                    },
                }
            )
        )
        sessions, inventory = FakeSessions(), FakeInventory()
        sessions.current.criteria.filters.makes.append("Nissan")
        result = await send(ReadCoordinator(sessions, model, inventory), sessions, question)
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert inventory.searches[0].filters.makes == []
        assert sessions.current.criteria.filters.makes == ["Nissan"]
        assert "0" in result.text and "price" in result.text.lower()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "original",
    [
        "Find cars within my monthly budget 50000",
        "Find cars within my budget 50000 Moroccan dirhams",
        "Find cars under 50000",
        "Find cars over 50000",
        "Find cars from 50000",
        "Find cars within my budget 30000 to 50000",
        "Find cars within my budget 30000-50000",
    ],
)
def test_bare_answer_does_not_discard_original_payment_currency_or_bound(original: str) -> None:
    result = apply_intent(
        SearchCriteria(),
        budget_intent("50000 Dirhams"),
        "50000 Dirhams",
        clarification_targets=("budget",),
        prior_request=original,
    )
    assert result.clarification is not None
    assert result.retained.filters.budget is None


@pytest.mark.parametrize(
    "operator,lower,inclusive,expected",
    [
        ("under", False, False, 4_999_999),
        ("over", True, False, 5_000_001),
        ("from", True, True, 5_000_000),
    ],
)
def test_short_answer_can_inherit_original_bound(operator, lower, inclusive, expected) -> None:
    intent = budget_intent("50k Dirhams", token="50k").model_dump(mode="json")
    patch = intent["patches"][0]
    patch["minimum" if lower else "maximum"] = {"text": "50k", "inclusive": inclusive}
    if lower:
        patch["maximum"] = None
    result = apply_intent(
        SearchCriteria(),
        TurnIntent.model_validate(intent),
        "50k Dirhams",
        clarification_targets=("budget",),
        prior_request=f"Find cars {operator} 50000",
    )
    assert result.clarification is None
    assert getattr(result.retained.filters.budget, "minimum" if lower else "maximum") == expected


def test_inventory_count_can_answer_despite_checked_old_listing_question() -> None:
    async def exercise() -> None:
        question = "how many cars do u have in total that have a clear stated price ?"
        model, _ = adapter(
            TurnIntent.model_validate(
                {
                    "operation": "analyze",
                    "analysis": {
                        "operation": "count_known",
                        "field": "cash_price",
                        "scope": "inventory",
                        "quote": question,
                    },
                }
            )
        )
        sessions, inventory = FakeSessions(), FakeInventory()
        pending = ClarificationIntent(
            kind="clarification",
            intent_id=str(uuid4()),
            created_revision=0,
            purpose="listing_reference",
            targets=["selected_ref"],
            question="Which listing and original results page do you mean?",
        )
        sessions.current.pending_intent = pending
        result = await send(ReadCoordinator(sessions, model, inventory), sessions, question)
        assert result.state == "answered" and "price" in result.text.lower()
        assert result.pending_intent == pending
        assert inventory.calls == ["search"]

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "purpose,target", [("viewing_details", "appointment"), ("action_intent", "confirmation")]
)
def test_shown_analysis_does_not_clear_unrelated_question(purpose, target) -> None:
    async def exercise() -> None:
        question = "which of these is newest?"
        model, _ = adapter(
            TurnIntent(operation="search"),
            TurnIntent.model_validate(
                {
                    "operation": "analyze",
                    "analysis": {
                        "operation": "maximum",
                        "field": "year",
                        "scope": "shown",
                        "quote": question,
                    },
                }
            ),
        )
        sessions, inventory = FakeSessions(), FakeInventory()
        coordinator = ReadCoordinator(sessions, model, inventory)
        await send(coordinator, sessions, "show cars")
        pending = ClarificationIntent(
            kind="clarification",
            intent_id=str(uuid4()),
            created_revision=sessions.current.revision,
            purpose=purpose,
            targets=[target],
            question="Which time?",
        )
        sessions.current.pending_intent = pending
        result = await send(coordinator, sessions, question)
        assert result.state == "answered" and result.pending_intent == pending
        assert sessions.current.pending_intent == pending

    asyncio.run(exercise())
