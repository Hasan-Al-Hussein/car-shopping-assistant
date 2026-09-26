"""Trusted routing context and deterministic reads; mocks do not prove model semantics."""

import asyncio
import json
import socket
from collections.abc import Callable
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.assistant.budget import TurnBudget
from app.assistant.collection_language import CollectionLanguageError, parse_collection_request
from app.assistant.collection_planner import plan_collection
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import (
    CollectionFieldProposal,
    CollectionProposal,
    ReferenceRequest,
    TurnIntent,
    apply_intent,
)
from app.assistant.interpretation import interpret
from app.assistant.packet import MAX_INPUT_TOKENS, output_system_instruction
from app.assistant.provider import GeminiAdapter
from app.assistant.scope import compose_scope
from app.assistant.transport import GoogleGenAITransport
from app.core.config import FrozenSettings, Settings

from .a4_cases import UNTRUSTED, detail
from .conversation_fakes import (
    FakeInventory,
    FakeSessions,
    adapter,
    listing,
    request,
    session,
    state,
)
from .test_action_bridge import admission
from .test_collection_planner import RULES, observed
from .test_coordinator import pending_budget, run
from .test_transport import FAKE_KEY, body


@pytest.mark.parametrize(
    "prompt,reference,has_selection,collection",
    [
        ("Does it have a warranty?", ReferenceRequest(source="selected", quote="it"), True, None),
        ("What is its mileage?", ReferenceRequest(source="selected", quote="its"), True, None),
        (
            "What is the price of that car?",
            ReferenceRequest(source="selected", quote="that car"),
            True,
            None,
        ),
        (
            "What is the price of the first car?",
            ReferenceRequest(source="ordinal", position=0, quote="first car"),
            True,
            None,
        ),
        ("Show details", ReferenceRequest(source="request", quote="details"), True, None),
        ("Show this car", ReferenceRequest(source="request", quote="this car"), True, None),
        (
            "Show the fourth car",
            ReferenceRequest(source="ordinal", position=3, quote="fourth car"),
            True,
            None,
        ),
        ("Does it have a warranty?", ReferenceRequest(source="selected", quote="it"), False, None),
        ("Explain vehicle warranty", None, False, None),
        ("Explain odometer mileage", None, True, None),
        (
            'Prepare a local enquiry; My cash budget is AED 38000; '
            'My needs are "low running costs"',
            None,
            True,
            CollectionProposal(
                command="start_enquiry",
                fields=[
                    CollectionFieldProposal(field="budget", quote="My cash budget is AED 38000"),
                    CollectionFieldProposal(
                        field="requirements", quote='My needs are "low running costs"'
                    ),
                ],
            ),
        ),
        ("Save this local enquiry", None, True, CollectionProposal(command="save_enquiry")),
    ],
)
def test_listing_guidance_and_reference_context_cross_actual_sdk_wire(
    monkeypatch: pytest.MonkeyPatch,
    prompt: str,
    reference: ReferenceRequest | None,
    has_selection: bool,
    collection: CollectionProposal | None,
    record_property: Callable[[str, object], None],
) -> None:
    """The scripted proposal exercises wire construction, not natural-language inference."""
    calls: list[httpx.Request] = []
    expected = TurnIntent(
        operation="detail" if reference else "smalltalk",
        references=[reference] if reference else [],
        problem="reference" if reference and not has_selection else None,
        problem_target="selected_ref" if reference else "query",
        collection=collection,
    )
    selected, explicit = detail("3").listing.ref, detail("4").listing.ref
    pending = pending_budget().model_copy(
        update={"question": "Pending question " + "word " * 36 + "end"}
    )
    if collection is not None and collection.command == "save_enquiry":
        pending = pending.model_copy(
            update={
                "purpose": "action_intent",
                "targets": ["confirmation"],
                "question": "Explicitly save or correct the local enquiry values "
                "shown in this answer?",
            }
        )
    current = session(
        revision=1,
        selected_ref=selected.model_dump() if has_selection else None,
        active_presentation_id=str(uuid4()),
        pending_intent=pending.model_dump(),
        criteria={
            "filters": {
                "budget": {
                    "minimum": 1000000,
                    "maximum": 20000000,
                    "currency": "AED",
                    "basis": "cash",
                }
            }
        },
    )
    message = request(
        current,
        prompt,
        expected_revision=0,
        selected_ref=explicit.model_dump() if reference and reference.source == "request" else None,
    )

    def deny_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("OFFLINE_ROUTING_TEST_NETWORK_FORBIDDEN")

    def handler(outgoing: httpx.Request) -> httpx.Response:
        calls.append(outgoing)
        return httpx.Response(
            200,
            json=body(
                candidates=[
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": expected.model_dump_json()}]},
                    }
                ]
            ),
            request=outgoing,
        )

    async def exercise() -> None:
        monkeypatch.setattr(socket, "getaddrinfo", deny_network)
        monkeypatch.setattr(socket.socket, "connect", deny_network)
        monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
        settings = Settings(gemini_api_key=SecretStr(FAKE_KEY))
        model = GeminiAdapter(
            settings,
            GoogleGenAITransport(settings, transport_factory=lambda: httpx.MockTransport(handler)),
        )
        budget = TurnBudget(settings.timeouts, asyncio.get_running_loop().time() + 30)
        try:
            result = await interpret(
                model,
                message,
                current,
                state(),
                budget,
                (),
                collection_summary="Active collection: local_enquiry; date missing; time missing."
                if collection is not None
                else None,
            )
            record_property("provider_diagnostic", result.diagnostic.code)
            assert result.state == "available" and result.proposal == expected, result.diagnostic
            assert len(calls) == budget.provider_attempts == 1
            assert budget.tool_invocations == 0
        finally:
            assert await model.close(timeout_seconds=1)

    asyncio.run(exercise())
    outgoing = calls[0]
    record_property("actual_wire_bytes", len(outgoing.content))
    assert len(outgoing.content) <= MAX_INPUT_TOKENS and FAKE_KEY not in outgoing.content.decode()
    sent = json.loads(outgoing.content)
    instruction = sent["systemInstruction"]["parts"][0]["text"]
    contract = json.loads(instruction.split("Canonical output JSON Schema:\n", 1)[1])
    admission_bytes = (
        len(json.dumps(sent["contents"][0]["parts"][0]["text"], ensure_ascii=True).encode())
        + len(
            json.dumps(output_system_instruction(contract, repair=True), ensure_ascii=True).encode()
        )
        + 1024
    )
    record_property("repair_admission_bytes", admission_bytes)
    assert admission_bytes <= MAX_INPUT_TOKENS
    assert contract == TurnIntent.model_json_schema()
    operation = contract["properties"]["operation"]["description"]
    assert "unknown/conflicting facts" in operation
    assert "no patches or deferred writes" in operation
    assert "problem=reference" in operation and "unsupported hard search requirements" in operation
    assert "question: DEFAULT for natural questions" in operation
    assert "even with a selected car" in operation
    assert "Prefer question/shown for conversational ordinal or comparative follow-ups" in operation
    values = contract["$defs"]["TextPatch"]["properties"]["values"]["description"]
    assert "model 7 => models=['7']" in values
    assert "model 'Model 7' => models=['Model 7']" in values
    assert "trim 2.5 => trims=['2.5']" in values and "infer no make" in values
    assert "patches=[]" in contract["properties"]["collection"]["description"]
    assert "not search or saved preferences" in contract["properties"]["collection"]["description"]
    command = contract["$defs"]["CollectionProposal"]["properties"]["command"]
    command_guidance = command["description"]
    assert "'Save this local enquiry' is save_enquiry" in command_guidance
    assert "never preferences or viewing confirmation" in command_guidance
    for example in contract["examples"]:
        TurnIntent.model_validate(example, strict=True)
    assert all(
        TurnIntent.model_config[key] == value for key, value in FrozenSettings.model_config.items()
    )
    reference_schema = contract["$defs"]["ReferenceRequest"]["properties"]
    assert "session selected_ref" in reference_schema["source"]["description"]
    assert "original results" in reference_schema["source"]["description"]
    assert (
        "explicit UI choice in presented_refs => detail/request"
        in (reference_schema["source"]["description"])
    )
    assert "'fourth car' => detail/ordinal, position=3" in reference_schema["source"]["description"]
    assert "Exact buyer reference phrase" in reference_schema["quote"]["description"]
    # A canonical command can equal buyer text; the trusted channel must still be static.
    assert instruction == output_system_instruction(TurnIntent.model_json_schema())
    assert pending.question not in instruction
    packet = json.loads(sent["contents"][0]["parts"][0]["text"])
    assert packet["message"] == prompt
    assert packet["selected_ref"] == (selected.model_dump() if has_selection else None)
    assert packet["presented_refs"] == (
        [explicit.model_dump()] if reference and reference.source == "request" else []
    )
    assert packet["facts"] == []  # Fact absence here must not be treated as unsupported scope.
    assert len(packet["history_summaries"]) == 4
    assert pending.question in packet["history_summaries"][-1]
    assert pending.purpose in packet["history_summaries"][-1]
    assert "Established budget currency: AED; basis: cash." in packet["history_summaries"]
    assert "soft_preferences TextPatch" in packet["history_summaries"][0]
    assert all(len(summary) <= 400 for summary in packet["history_summaries"])
    assert "cite a car only when the buyer does" in packet["history_summaries"][1]


@pytest.mark.parametrize("has_selection", [False, True])
@pytest.mark.parametrize(
    "prompt,topic",
    [
        ("Explain vehicle warranty", "warranty"),
        ("Explain odometer mileage", "mileage"),
    ],
)
def test_generic_explanation_does_not_require_or_read_a_listing(
    prompt: str,
    topic: str,
    has_selection: bool,
) -> None:
    async def exercise() -> None:
        item = detail("3")
        sessions = FakeSessions(
            session(
                selected_ref=item.listing.ref.model_dump() if has_selection else None,
                criteria={"soft_preferences": ["easy parking"]},
            )
        )
        before = sessions.current
        inventory = FakeInventory(item)
        model, transport = adapter(TurnIntent(operation="smalltalk"))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions, request(sessions.current, prompt)
        )
        assert result.state == "answered" and result.text == compose_scope(topics=(topic,)).text
        assert result.evidence == [] and result.handoff_summary is None
        assert result.pending_intent.kind == "none" and result.operation is None
        assert inventory.calls == [] and len(transport.requests) == 1
        assert sessions.current.selected_ref == before.selected_ref
        assert sessions.current.criteria == before.criteria
        assert all(
            action["state"] == "not_requested" for action in result.actions.model_dump().values()
        )

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "field,value,prompt",
    [
        ("models", "7", "Show model 7"),
        ("trims", "2.5", "Show trim 2.5"),
        ("models", "Model 7", 'Show model "Model 7"'),
        ("models", "Land Cruiser", 'Show model "Land Cruiser"'),
        ("models", "Civic", "Show model Civic"),
        ("makes", "Honda", "Show make Honda"),
    ],
)
def test_explicit_field_values_reach_search_with_canonical_case(
    field: str,
    value: str,
    prompt: str,
) -> None:
    """Scripted extraction tests forwarding/guards, not real-model or inventory matching."""

    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        proposal = TurnIntent.model_validate(
            {
                "operation": "search",
                "patches": [
                    {
                        "kind": "text",
                        "field": field,
                        "operation": "add",
                        "values": [value],
                        "quote": prompt,
                    }
                ],
            }
        )
        model, transport = adapter(proposal)
        result = await run(
            ReadCoordinator(sessions, model, inventory),
            sessions,
            request(sessions.current, prompt),
        )
        assert result.state == "answered" and inventory.calls == ["search"]
        assert len(transport.requests) == 1 and len(inventory.searches) == 1
        actual = inventory.searches[0].filters
        for name in ("makes", "models", "trims"):
            # Search canonicalizes case; complete names and numeric text remain values.
            assert getattr(actual, name) == ([value.casefold()] if name == field else [])
            # Session intent retains the buyer's casing before search normalization.
            assert getattr(sessions.current.criteria.filters, name) == (
                [value] if name == field else []
            )
        assert result.operation is None
        assert all(
            action["state"] == "not_requested" for action in result.actions.model_dump().values()
        )
        packet = json.loads(transport.requests[0].contents)
        assert packet["message"] == prompt

    asyncio.run(exercise())


def test_numeric_model_does_not_authorize_an_uncited_make() -> None:
    prompt = "Show model 7"
    proposal = TurnIntent.model_validate(
        {
            "operation": "search",
            "patches": [
                {
                    "kind": "text",
                    "field": "models",
                    "operation": "add",
                    "values": ["7"],
                    "quote": prompt,
                },
                {
                    "kind": "text",
                    "field": "makes",
                    "operation": "add",
                    "values": ["UncitedMake"],
                    "quote": prompt,
                },
            ],
        }
    )
    transition = apply_intent(session().criteria, proposal, prompt)
    assert transition.clarification is not None
    assert transition.retained.filters.makes == []


@pytest.mark.parametrize("kind", ["request", "ordinal"])
@pytest.mark.parametrize("has_context", [False, True])
def test_car_pointer_reads_exact_context_without_repeating_search(
    kind: str,
    has_context: bool,
) -> None:
    """Scripted intent still needs real request/presentation authority at the resolver."""

    async def exercise() -> None:
        items = tuple(listing(name) for name in ("last", "first", "third", "target"))
        page = str(uuid4())
        sessions = FakeSessions(
            session(
                selected_ref=items[0].listing.ref.model_dump() if has_context else None,
                active_presentation_id=page if has_context else None,
                criteria={"soft_preferences": ["easy parking"]},
            )
        )
        if has_context:
            sessions.presentations[page] = tuple(item.listing.ref for item in items)
        before = sessions.current.criteria
        reference = ReferenceRequest.model_validate(
            {
                "source": kind,
                "quote": "this car" if kind == "request" else "fourth car",
                "position": 3 if kind == "ordinal" else None,
            }
        )
        model, transport = adapter(TurnIntent(operation="detail", references=[reference]))
        inventory = FakeInventory(*items)
        result = await run(
            ReadCoordinator(sessions, model, inventory),
            sessions,
            request(
                sessions.current,
                "Show this car" if kind == "request" else "Show the fourth car",
                selected_ref=items[-1].listing.ref.model_dump()
                if kind == "request" and has_context
                else None,
            ),
        )
        assert len(transport.requests) == 1 and "search" not in inventory.calls
        assert sessions.current.criteria == before and result.search is None
        assert result.operation is None
        assert all(
            action["state"] == "not_requested" for action in result.actions.model_dump().values()
        )
        if has_context:
            assert result.state == "answered" and result.handoff_summary is not None
            assert result.handoff_summary.listing.listing.ref == items[-1].listing.ref
            assert sessions.current.selected_ref == items[-1].listing.ref
            assert inventory.calls == ["detail"]
        else:
            assert result.state == "clarification" and result.handoff_summary is None
            assert inventory.calls == [] and result.pending_intent.kind == "clarification"

    asyncio.run(exercise())


def test_complete_enquiry_example_keeps_fields_local_and_needs_no_car() -> None:
    example = TurnIntent.model_validate(TurnIntent.model_json_schema()["examples"][0], strict=True)
    assert example.collection is not None
    text = "Prepare a local enquiry; " + "; ".join(
        field.quote for field in example.collection.fields
    )
    turn = admission(text)
    requested = parse_collection_request(text, example, matched_question=None)
    plan = plan_collection(turn, observed(), requested, resolved_ref=None, rules=RULES)
    update = plan.collection_update
    assert update is not None and update.purpose == "local_enquiry" and update.values is not None
    assert update.values.ref is None and update.values.budget.value.maximum == 4700000
    assert update.values.requirements == ["wide doors"]
    assert plan.lead is None and plan.draft is None and plan.selection is None
    assert plan.result.pending_intent.kind == "none" and plan.result.operation is None
    assert plan.update is not None and plan.update.criteria == turn.session.criteria
    assert [(source.field, text[source.start : source.end]) for source in update.sources] == [
        (field.field, field.quote) for field in example.collection.fields
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"scope": "durable"},
        {"problem": "reference"},
        {"deferred": ["preferences"]},
        {
            "patches": [
                {
                    "kind": "text",
                    "field": "soft_preferences",
                    "operation": "add",
                    "values": ["wide doors"],
                    "quote": 'My needs are "wide doors"',
                }
            ]
        },
    ],
)
def test_enquiry_example_cannot_bypass_incompatible_intent_guards(
    change: dict[str, object],
) -> None:
    example = TurnIntent.model_json_schema()["examples"][0]
    proposal = TurnIntent.model_validate({**example, **change}, strict=True)
    text = 'Prepare a local enquiry; My cash budget is AED 47000; My needs are "wide doors"'
    with pytest.raises(CollectionLanguageError, match="Settle the other instruction"):
        parse_collection_request(text, proposal, matched_question=None)


@pytest.mark.parametrize(
    "source_id,price_text",
    [("3", "AED 119,750.00 cash"), ("4", "Price: not stated")],
)
def test_price_question_reads_same_car_without_changing_criteria_or_writing(
    source_id: str,
    price_text: str,
) -> None:
    async def exercise() -> None:
        item = detail(source_id)
        page = str(uuid4())
        sessions = FakeSessions(
            session(
                selected_ref=item.listing.ref.model_dump(),
                active_presentation_id=page,
                criteria={"soft_preferences": ["easy parking"]},
            )
        )
        sessions.presentations[page] = (item.listing.ref,)
        before = sessions.current.criteria
        inventory = FakeInventory(item)
        model, transport = adapter(
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="selected", quote="it")],
            )
        )
        result = await run(
            ReadCoordinator(sessions, model, inventory),
            sessions,
            request(sessions.current, "What is the price of it?"),
        )
        assert result.state == "answered" and result.handoff_summary is not None
        assert result.handoff_summary.listing == item and price_text in result.text
        assert UNTRUSTED not in result.text
        assert result.search is None and result.operation is None
        assert len(result.evidence) == 1 and result.evidence[0].ref == item.listing.ref
        assert "cash_price" in result.evidence[0].attributes
        assert inventory.calls == ["detail"] and len(transport.requests) == 1
        assert sessions.current.selected_ref == item.listing.ref
        assert sessions.current.active_presentation_id == page
        assert sessions.current.criteria == before
        assert all(
            action["state"] == "not_requested" for action in result.actions.model_dump().values()
        )
        # Unknown detail facts must not weaken the separate hard-search guard.
        filtered = apply_intent(before, TurnIntent(operation="search"), "Only cars with warranty")
        assert filtered.clarification is not None and filtered.retained == before

    asyncio.run(exercise())
