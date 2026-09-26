"""Request policies preserve state and route through actual coordinator guards."""

import asyncio
from uuid import uuid4

import pytest

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import ListingResult
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.assistant.provider import ProviderFault, TransportResponse
from app.assistant.request_policy import external_source_search
from app.assistant.scope import compose_scope
from app.core.errors import ApiFailure

from .conversation_fakes import (
    FakeInventory,
    FakeSessions,
    ScriptedTransport,
    adapter,
    listing,
    provider,
    request,
    response,
    session,
)
from .test_coordinator import pending_budget, run


@pytest.mark.parametrize("operation", [
    "search", "detail", "compare", "return", "smalltalk", "unsupported",
])
@pytest.mark.parametrize("problem", [
    None, "currency", "basis", "conflict", "unsupported_attribute",
    "reference", "persistence", "meaning",
])
@pytest.mark.parametrize("patches", [False, True])
def test_external_source_boundary_precedes_proposed_local_criteria(
    operation: str, problem: str | None, patches: bool,
) -> None:
    async def exercise() -> None:
        selected = listing("prior").listing.ref
        sessions = FakeSessions(session(
            criteria={"filters": {"makes": ["Mazda"]}, "soft_preferences": ["easy parking"]},
            selected_ref=selected.model_dump(),
        ))
        before = sessions.current.model_copy(deep=True)
        inventory = FakeInventory()
        proposed = [{
            "kind": "text", "field": "makes", "operation": "add",
            "values": ["Honda"], "quote": "Honda",
        }] if patches else []
        model, transport = adapter(TurnIntent.model_validate({
            "operation": operation, "problem": problem, "patches": proposed,
        }))
        value = request(sessions.current, "Find Honda cars on DubiCars.")
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert result.state == "answered" and result.provider_state == "available"
        assert result.text == compose_scope(topics=("unrelated",)).text
        assert result.evidence == [] and result.search is None and result.handoff_summary is None
        assert inventory.calls == [] and len(transport.requests) == 1
        assert sessions.current.criteria == before.criteria
        assert sessions.current.selected_ref == selected
        assert sessions.current.pending_intent == before.pending_intent
        assert sessions.completions == [(None, None)]
        assert sessions.turns[value.client_message_id].admission.request.text == value.text
        assert result.operation is None
        assert all(x["state"] == "not_requested" for x in result.actions.model_dump().values())

    asyncio.run(exercise())


@pytest.mark.parametrize("text", [
    "Find Honda cars on DubiCars.",
    "find honda cars on dUbICars",
    "SHOW used Honda CARS VIA yallamotor!",
    "Find electric cars on AutoTrader", "Find diesel cars on Cars24",
    "Find hybrid cars on marketplace SampleHub",
    "List vehicles on website opaque-place",
    "Search for used cars on the external marketplace something",
    "Find listings via another platform source7",
])
def test_reviewed_bare_sources_and_explicit_opaque_labels(text: str) -> None:
    current = session()
    assert external_source_search(
        TurnIntent(operation="smalltalk"), request(current, text), current, collection_active=False,
    )


@pytest.mark.parametrize("text", [
    "Find Honda cars on sale", "Find cars on finance", "Find cars on credit",
    "Find cars on lease", "Find cars on a budget of AED 50000", "Find cars on budget",
    "Find cars on time", "Find cars on Monday", "Find cars on the weekend",
    "Find cars on weekends", "Find cars on LPG", "Find cars on CNG", "Find cars on Dubai",
    "Find cars on Sheikh Zayed Road", "Find cars on Airport Road", "Find cars on the Palm",
    "Find cars in Dubai", "Find cars near Abu Dhabi", "Find cars on page 2",
    "Find cars on page", "Find cars on display", "Find cars on the road",
    "Find cars on map", "Find cars via local inventory", "Find cars on inventory",
    "Find cars on dubizzle", "Find cars on marketplace dubizzle", "Find cars on SampleHub",
    'Find "DubiCars" cars', 'Find cars on "DubiCars"', 'Find model "on Monday"',
    'Find cars on "sale"', "Find cars on another website", "Find cars on other marketplaces",
    "Do not find cars on source7", "Find no Honda cars on source7",
    "Find cars on source7 and save them", "Find cars on source7 or source8",
    "Find cars on source7; book one", "If possible find cars on source7",
    "Find not Honda cars on source7", "Find cars on source7 tomorrow",
    "Find no Honda cars on DubiCars", "Find not Honda cars on website SampleHub",
    "Find Honda and Mazda cars on DubiCars", "Find Honda or Mazda cars on website SampleHub",
    "Find Honda then Mazda cars on cars24", "Find save Honda cars on DubiCars",
    "Find not-red cars on DubiCars", "Find no-diesel cars on marketplace SampleHub",
    "Find cars on website " + "s" * 65,
    "Find one two three four five cars on DubiCars",
    "Find cars on source7\nand write a poem", "Find cars on source7\t",
    "Find cars on source7\x85", "Find cars on source7\u2028", "Find cars on source7\u2029",
    "Find cars on source7 " + "extra " * 80,
    "FİND Honda cars on source7", "Find cars on söurce7",
])
def test_uncovered_or_ordinary_modifiers_keep_existing_guarded_handling(text: str) -> None:
    current = session()
    assert not external_source_search(
        TurnIntent(operation="search"), request(current, text), current, collection_active=False,
    )


@pytest.mark.parametrize("guard", [
    "pending", "draft", "collection", "durable", "hypothetical", "unclear",
    "deferred", "intent_collection", "reply", "confirmation",
])
def test_external_policy_cannot_replace_workflow_or_scope_authority(guard: str) -> None:
    current = session()
    changes: dict[str, object] = {}
    extra: dict[str, object] = {}
    if guard == "pending":
        current = session(pending_intent=pending_budget().model_dump())
    if guard == "draft":
        current = session(current_draft_id=str(uuid4()))
    if guard in {"durable", "hypothetical", "unclear"}:
        changes["scope"] = guard
    if guard == "deferred":
        changes["deferred"] = ["preferences"]
    if guard == "intent_collection":
        changes["collection"] = {"command": "start_enquiry", "fields": []}
    if guard == "reply":
        extra["clarification_reply"] = {"intent_id": str(uuid4()), "created_revision": 0}
    if guard == "confirmation":
        extra["explicit_confirmation"] = {
            "draft_id": str(uuid4()), "review_id": str(uuid4()), "expected_draft_revision": 0,
            "operation_key": "x" * 43, "rules_version": "test-v1",
            "store_generation": str(uuid4()), "confirmation": "confirm_simulated_viewing",
        }
    intent = TurnIntent.model_validate({"operation": "search", **changes})
    assert not external_source_search(
        intent, request(current, "Find cars on DubiCars", **extra), current,
        collection_active=guard == "collection",
    )


def test_external_boundary_preserves_ui_selection_legitimately_admitted_by_begin() -> None:
    async def exercise() -> None:
        old, chosen = listing("prior").listing.ref, listing("chosen").listing.ref
        sessions = FakeSessions(session(selected_ref=old.model_dump()))
        model, _ = adapter(TurnIntent(operation="unsupported", problem="unsupported_attribute"))
        result = await run(
            ReadCoordinator(sessions, model, FakeInventory()), sessions,
            request(sessions.current, "Find cars on DubiCars", selected_ref=chosen.model_dump()),
        )
        assert result.text == compose_scope(topics=("unrelated",)).text
        assert sessions.current.selected_ref == chosen
        assert sessions.completions == [(None, None)]

    asyncio.run(exercise())


@pytest.mark.parametrize("text", ["Find cars on DubiCars", "Show this car and write me a poem"])
def test_existing_pending_question_remains_authoritative(text: str) -> None:
    async def exercise() -> None:
        pending = pending_budget()
        sessions = FakeSessions(session(pending_intent=pending.model_dump()))
        model, _ = adapter(TurnIntent(operation="search"))
        inventory = FakeInventory()
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, text,
                    selected_ref=listing("chosen").listing.ref.model_dump()),
        )
        assert result.state == "clarification" and result.text == pending.question
        assert sessions.current.pending_intent == pending
        assert inventory.calls == [] and result.handoff_summary is None

    asyncio.run(exercise())


@pytest.mark.parametrize("text", ["Find cars on DubiCars", "Show this car and write me a poem"])
@pytest.mark.parametrize("failure", ["private", "unavailable", "superseded"])
def test_request_policies_do_not_preempt_prior_admission_guards(text: str, failure: str) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()

        async def supersede() -> TransportResponse:
            sessions.current = sessions.current.model_copy(
                update={"revision": sessions.current.revision + 1},
            )
            return response(TurnIntent(operation="unsupported"))

        transport = ScriptedTransport(
            ProviderFault("quota") if failure == "unavailable" else supersede,
        )
        value = request(
            sessions.current, text + (" synthetic@example.test" if failure == "private" else ""),
            selected_ref=listing("chosen").listing.ref.model_dump(),
        )
        result = await run(
            ReadCoordinator(sessions, provider(transport), inventory), sessions, value,
        )
        assert inventory.calls == [] and result.search is None and result.handoff_summary is None
        assert sessions.current.criteria == session().criteria
        if failure == "private":
            assert transport.requests == [] and result.provider_state == "not_used"
        else:
            assert len(transport.requests) == 1
            assert result.state == (
                "provider_unavailable" if failure == "unavailable" else "superseded"
            )

    asyncio.run(exercise())


@pytest.mark.parametrize("code", ["NOT_FOUND", "SNAPSHOT_STALE", "PRESENTATION_INVALID"])
def test_mixed_ui_read_still_requires_a_valid_inventory_reference(code: str) -> None:
    class RejectingInventory(FakeInventory):
        async def detail(self, value: InventoryRef, *, deadline_at: float) -> ListingResult:
            self.calls.append("detail")
            raise ApiFailure(code)

    async def exercise() -> None:
        sessions, inventory = FakeSessions(), RejectingInventory()
        model, transport = adapter(TurnIntent(operation="unsupported", problem="reference"))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, "Show this car and write me a poem",
                    selected_ref=listing("rejected").listing.ref.model_dump()),
        )
        assert result.state == "clarification" and result.pending_intent.kind == "clarification"
        assert result.pending_intent.purpose == "listing_reference"
        assert result.handoff_summary is None and result.evidence == []
        assert inventory.calls == ["detail"] and len(transport.requests) == 1
        assert sessions.completions == [(None, None)]

    asyncio.run(exercise())


@pytest.mark.parametrize("text,selected", [
    ("Show this car and write me a poem", False),
    ("Show this car or that car and write me a poem", True),
])
def test_real_missing_or_competing_reference_is_not_recovered(text: str, selected: bool) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        model, _ = adapter(TurnIntent(
            operation="detail", references=[ReferenceRequest(source="request", quote="this car")],
        ))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            request(sessions.current, text,
                    selected_ref=listing("chosen").listing.ref.model_dump() if selected else None),
        )
        assert result.state == "clarification" and result.handoff_summary is None
        assert result.evidence == [] and inventory.calls == []

    asyncio.run(exercise())
