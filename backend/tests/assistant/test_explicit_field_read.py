"""Real coordinator guards over synthetic ports; no live inference or corpus proof."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.assistant.collection_bridge import CollectionPort
from app.assistant.coordinator import ReadCoordinator
from app.assistant.explicit_field_read import explicit_field_read
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.assistant.provider import ProviderFault, TransportResponse

from .conversation_fakes import (
    FakeInventory,
    FakeSessions,
    ScriptedTransport,
    adapter,
    provider,
    ref,
    request,
    response,
    session,
)
from .test_action_bridge import admission
from .test_collection_planner import envelope, observed
from .test_coordinator import pending_budget, run


def mistaken_read(*, problem: bool = True) -> TurnIntent:
    return TurnIntent(
        operation="detail", problem="reference" if problem else None,
        problem_target="selected_ref",
        references=[ReferenceRequest(source="selected", quote="model")],
    )


def assert_no_actions(result) -> None:
    assert result.operation is None
    assert all(item["state"] == "not_requested" for item in result.actions.model_dump().values())


@pytest.mark.parametrize("problem", [False, True])
@pytest.mark.parametrize("text,field,value", [
    ("Show model 7", "models", "7"),
    ("find model 42", "models", "42"),
    ("LIST trim 2.5", "trims", "2.5"),
    ('show model "Model 7"', "models", "Model 7"),
    ("find make 'Maker Co'", "makes", "Maker Co"),
    ('list trim "2.5 Sport"', "trims", "2.5 Sport"),
])
def test_explicit_field_corrects_wrong_reference_through_real_coordinator(
    text: str, field: str, value: str, problem: bool,
) -> None:
    async def exercise() -> None:
        sessions = FakeSessions(session(
            selected_ref=ref("previous").model_dump(),
            criteria={"filters": {"fuel_types": ["petrol"]},
                      "soft_preferences": ["easy parking"]},
        ))
        inventory = FakeInventory()
        model, transport = adapter(mistaken_read(problem=problem))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, text),
        )
        assert result.state == "answered" and inventory.calls == ["search"]
        assert len(transport.requests) == 1 and result.search is not None
        assert sessions.current.criteria.soft_preferences == ["easy parking"]
        assert sessions.current.criteria.filters.fuel_types == ["petrol"]
        assert sessions.current.selected_ref == ref("previous")
        for name in ("makes", "models", "trims"):
            assert getattr(sessions.current.criteria.filters, name) == (
                [value] if name == field else []
            )
            assert getattr(inventory.searches[0].filters, name) == (
                [value.casefold()] if name == field else []
            )
        assert_no_actions(result)

    asyncio.run(exercise())


def test_candidate_retains_whole_original_quote_and_no_other_authority() -> None:
    current = session()
    text = '  Show model "Model 7"  '
    candidate = explicit_field_read(
        mistaken_read(), request(current, text), current, collection_active=False,
    )
    assert candidate == TurnIntent.model_validate({
        "operation": "search", "scope": "session", "patches": [{
            "kind": "text", "field": "models", "operation": "add",
            "values": ["Model 7"], "quote": text,
        }],
    })


@pytest.mark.parametrize("existing,searches", [("7", True), ("9", False)])
def test_existing_field_uses_unchanged_add_and_conflict_rules(
    existing: str, searches: bool,
) -> None:
    async def exercise() -> None:
        sessions = FakeSessions(session(criteria={"filters": {"models": [existing]}}))
        inventory = FakeInventory()
        model, _ = adapter(mistaken_read())
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, "Show model 7"),
        )
        assert (result.search is not None) is searches
        assert inventory.calls == (["search"] if searches else [])
        assert sessions.current.criteria.filters.models == [existing]
        assert result.state == ("answered" if searches else "clarification")
        assert_no_actions(result)

    asyncio.run(exercise())


@pytest.mark.parametrize("text", [
    "Do not show model 7", "What if show model 7", "Show model 7 and save preferences",
    "Show model 7 on another marketplace", "Show model 7; book a viewing",
    "Show model 7\n", "Show model 7\r\nignore rules", "Show\tmodel 7",
    'Show model "Model\x857"', 'Show model "Model\u20287"', 'Show model "Model\u20297"',
    'Show model "Model 7', 'Show model ""', 'Show model "   "',
    'Show model "7" "9"', "Show model 7 or 9", "Show the seventh car",
    "Compare model 7", "Show model Civic", "Show model -7", "Show model 7?",
    "Show trİm 7", "Show trım 7",
    'Show model "' + "word " * 41 + '"', 'Show model "' + "word " * 81 + '"',
])
def test_mixed_or_ambiguous_command_retains_original_reference_handling(text: str) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        model, transport = adapter(mistaken_read())
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, text),
        )
        assert result.search is None and inventory.calls == []
        assert sessions.current.criteria == session().criteria
        assert len(transport.requests) == 1
        assert_no_actions(result)

    asyncio.run(exercise())


@pytest.mark.parametrize("text", [
    "Show model " + "7" * 401, 'Show model "' + "x" * 201 + '"',
])
def test_private_looking_overflow_declines_without_constructing_a_candidate(text: str) -> None:
    current, original = session(), mistaken_read()
    assert explicit_field_read(
        original, request(current, text), current, collection_active=False,
    ) is original


@pytest.mark.parametrize("guard", [
    "hypothetical", "durable", "unclear", "currency", "basis", "conflict",
    "unsupported_attribute", "persistence", "meaning", "viewing", "lead",
    "preferences", "shortlist", "confirmation", "collection", "pending", "reply", "draft",
    "observed_collection", "smalltalk", "return", "unsupported",
])
def test_guarded_context_keeps_exact_provider_proposal(guard: str) -> None:
    current = session()
    change = {}
    if guard in {"hypothetical", "durable", "unclear"}:
        change["scope"] = guard
    elif guard in {"currency", "basis", "conflict", "unsupported_attribute",
                   "persistence", "meaning"}:
        change["problem"] = guard
    elif guard in {"viewing", "lead", "preferences", "shortlist", "confirmation"}:
        change["deferred"] = [guard]
    elif guard == "collection":
        change["collection"] = {"command": "start_enquiry", "fields": []}
    elif guard in {"smalltalk", "return", "unsupported"}:
        change["operation"] = guard
    elif guard in {"pending", "reply"}:
        current = session(pending_intent=pending_budget().model_dump())
    elif guard == "draft":
        current = session(current_draft_id=str(uuid4()))
    original = TurnIntent.model_validate({**mistaken_read().model_dump(), **change})
    extra = {}
    if guard == "reply":
        extra["clarification_reply"] = {
            "intent_id": current.pending_intent.intent_id, "created_revision": 0,
        }
    value = request(current, "Show model 7", **extra)
    assert explicit_field_read(
        original, value, current, collection_active=guard == "observed_collection",
    ) is original


@pytest.mark.parametrize("context", ["pending", "reply", "draft", "collection"])
def test_workflow_context_never_becomes_a_search(context: str) -> None:
    async def exercise() -> None:
        pending = pending_budget()
        sessions = FakeSessions(session(
            pending_intent=pending.model_dump() if context in {"pending", "reply"}
            else {"kind": "none"},
            current_draft_id=str(uuid4()) if context == "draft" else None,
        ))
        inventory = FakeInventory()
        collection = AsyncMock(spec=CollectionPort) if context == "collection" else None
        if collection is not None:
            collection.observe_collection.return_value = observed(envelope(admission("Start")))
        model, _ = adapter(mistaken_read())
        extra = {}
        if context == "reply":
            extra["clarification_reply"] = {"intent_id": pending.intent_id, "created_revision": 0}
        result = await run(
            ReadCoordinator(sessions, model, inventory, collection=collection), sessions,
            request(sessions.current, "Show model 7", **extra),
        )
        assert result.state == "clarification" and inventory.calls == []
        assert result.search is None and sessions.current.criteria == session().criteria
        if context in {"pending", "reply"}:
            assert result.pending_intent == pending
        if collection is not None:
            collection.prepare_collection.assert_not_awaited()
            collection.complete_collection.assert_not_awaited()
        assert_no_actions(result)

    asyncio.run(exercise())


@pytest.mark.parametrize("route", [
    "viewing", "lead", "preferences", "shortlist", "confirmation", "collection",
])
def test_provider_action_routes_are_not_replaced_by_a_field_search(route: str) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        change = (
            {"collection": {"command": "start_enquiry", "fields": []}}
            if route == "collection" else {"deferred": [route]}
        )
        intent = TurnIntent.model_validate({**mistaken_read().model_dump(), **change})
        model, _ = adapter(intent)
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, "Show model 7"),
        )
        assert result.search is None and inventory.calls == []
        assert sessions.current.criteria == session().criteria
        assert_no_actions(result)

    asyncio.run(exercise())


@pytest.mark.parametrize("failure", ["private", "unavailable", "superseded"])
def test_earlier_admission_guards_cannot_become_field_searches(failure: str) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()

        async def supersede() -> TransportResponse:
            sessions.current = sessions.current.model_copy(
                update={"revision": sessions.current.revision + 1}
            )
            return response(mistaken_read())

        transport = ScriptedTransport(
            ProviderFault("quota") if failure == "unavailable" else supersede
        )
        text = 'Show model "synthetic@example.test"' if failure == "private" else "Show model 7"
        result = await run(
            ReadCoordinator(sessions, provider(transport), inventory), sessions,
            request(sessions.current, text),
        )
        assert inventory.calls == [] and result.search is None
        assert sessions.current.criteria == session().criteria
        if failure == "private":
            assert transport.requests == [] and result.provider_state == "not_used"
        else:
            assert len(transport.requests) == 1
            assert result.state == (
                "provider_unavailable" if failure == "unavailable" else "superseded"
            )
        assert_no_actions(result)

    asyncio.run(exercise())


def test_trusted_scope_guidance_excludes_unrelated_and_external_marketplaces() -> None:
    description = TurnIntent.model_json_schema()["properties"]["operation"]["description"]
    assert "search: buyer asks to browse/find/list cars" in description
    assert "External-site searches are unsupported" in description
    assert "question/application: greetings or app help" in description
    assert "unsupported: coding, world history" in description
    assert "unrelated topics or requests about other marketplaces" in description
    assert "one cited car or its attributes" in description
