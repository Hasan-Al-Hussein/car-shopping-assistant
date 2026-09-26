"""Mixed scope retains a real UI-selected read without creating action authority."""

import asyncio
from uuid import uuid4

import pytest

from app.assistant.coordinator import ReadCoordinator, _mixed_selected_read
from app.assistant.intent import TurnIntent

from .conversation_fakes import FakeInventory, FakeSessions, adapter, listing, request, session
from .test_coordinator import pending_budget, run


@pytest.mark.parametrize("operation", [
    "search", "detail", "compare", "return", "smalltalk", "unsupported",
])
@pytest.mark.parametrize("problem", [
    None, "currency", "basis", "conflict", "unsupported_attribute",
    "reference", "persistence", "meaning",
])
@pytest.mark.parametrize("text,notice", [
    ("Show this car and write me a poem", "unrelated part"),
    ("Show me details of this listing; assess another car-shopping website", "competing"),
    ("Show this car and guarantee its condition", "additional vehicle claim"),
])
def test_supported_ui_detail_survives_only_recognized_scope_clause(
    text: str, notice: str, operation: str, problem: str | None,
) -> None:
    async def exercise() -> None:
        item = listing("chosen")
        sessions = FakeSessions(session(criteria={"soft_preferences": ["easy parking"]}))
        inventory = FakeInventory(item)
        before = sessions.current.criteria
        model, transport = adapter(TurnIntent.model_validate({
            "operation": operation, "problem": problem,
        }))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, text, selected_ref=item.listing.ref.model_dump()),
        )
        assert result.state == "answered" and result.handoff_summary is not None
        assert result.handoff_summary.selected_ref == item.listing.ref
        assert notice in result.text and inventory.calls == ["detail"]
        assert sessions.current.criteria == before and len(transport.requests) == 1
        assert result.search is None and result.operation is None
        assert all(x["state"] == "not_requested" for x in result.actions.model_dump().values())

    asyncio.run(exercise())


@pytest.mark.parametrize("guard", [
    "no_ui", "pending", "collection", "durable", "deferred", "reference_problem",
    "unknown_clause", "extra_car", "negation", "multiline", "not_mixed",
    "draft", "patches", "intent_collection", "reply", "confirmation", "hypothetical",
    "unclear", "control", "nel", "line_separator", "paragraph_separator", "overflow",
])
def test_mixed_scope_cannot_erase_other_reference_or_workflow_guards(guard: str) -> None:
    current = (
        session(pending_intent=pending_budget().model_dump()) if guard == "pending" else session()
    )
    if guard == "draft":
        current = session(current_draft_id=str(uuid4()))
    text = {
        "unknown_clause": "Show this car and book it",
        "extra_car": "Show this car and the second car and write me a poem",
        "reference_problem": "Show this car or that car and write me a poem",
        "negation": "Do not show this car and write me a poem",
        "multiline": "Show this car\nand write me a poem",
        "not_mixed": "Show this car",
        "control": "Show this car\tand write me a poem",
        "nel": "Show this car\x85and write me a poem",
        "line_separator": "Show this car\u2028and write me a poem",
        "paragraph_separator": "Show this car\u2029and write me a poem",
        "overflow": " " * 401 + "Show this car and write me a poem",
    }.get(guard, "Show this car and write me a poem")
    change: dict[str, object] = {}
    if guard in {"durable", "hypothetical", "unclear"}:
        change["scope"] = guard
    if guard == "deferred":
        change["deferred"] = ["preferences"]
    if guard == "patches":
        change["patches"] = [{
            "kind": "text", "field": "soft_preferences", "operation": "add",
            "values": ["quiet"], "quote": "quiet",
        }]
    if guard == "intent_collection":
        change["collection"] = {"command": "start_enquiry", "fields": []}
    proposal = TurnIntent.model_validate({
        "operation": "detail",
        "problem": "reference" if guard == "reference_problem" else "unsupported_attribute",
        **change,
    })
    extra: dict[str, object] = {}
    if guard == "reply":
        extra["clarification_reply"] = {"intent_id": str(uuid4()), "created_revision": 0}
    if guard == "confirmation":
        extra["explicit_confirmation"] = {
            "draft_id": str(uuid4()), "review_id": str(uuid4()), "expected_draft_revision": 0,
            "operation_key": "x" * 43, "rules_version": "test-v1",
            "store_generation": str(uuid4()), "confirmation": "confirm_simulated_viewing",
        }
    value = request(
        current, text,
        selected_ref=None if guard == "no_ui" else listing("chosen").listing.ref.model_dump(),
        **extra,
    )
    assert _mixed_selected_read(
        proposal, value, current, collection_active=guard == "collection",
    ) is proposal
