"""Coordinator contract checks, not evidence of live model understanding.

Scripted proposals deliberately normalize language. The separate bounded live UI
run verifies whether the real provider produces useful interpretations itself.
The fixture inventory filters only makes; production retrieval is tested live.
"""

import asyncio
import json
from uuid import uuid4

import pytest

from app.api.schemas.inventory import SearchResult
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import (
    CollectionProposal,
    NumberToken,
    QuestionRequest,
    RangePatch,
    ReferenceRequest,
    TextPatch,
    TurnIntent,
)
from app.assistant.provider import TransportResponse

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
from .test_grounded_conversation import car, draft


class ExactMakeFixtureInventory(FakeInventory):
    """Small source fixture; never silently broadens a requested make."""

    async def search(self, value, *, deadline_at):
        result = await super().search(value, deadline_at=deadline_at)
        makes = {make.casefold() for make in value.filters.makes}
        rows = [
            row for row in result.items
            if not makes or row.make.value.casefold() in makes
        ]
        data = result.model_dump(mode="json")
        data.update(
            state="matches" if rows else "no_supported_matches",
            items=[row.model_dump(mode="json") for row in rows],
            supported_total=len(rows),
        )
        data["presentation"]["ordered_refs"] = [row.ref.model_dump(mode="json") for row in rows]
        return SearchResult.model_validate(data)


def shopping_session(*, make=None):
    return session(criteria={"filters": {
        "makes": [] if make is None else [make],
        "budget": {"currency": "AED", "maximum": 5_000_000},
        "years": {"minimum": 2015},
        "mileage_km": {"maximum": 100_000},
    }})


async def run(coordinator, sessions, text):
    return await coordinator.run(
        CONTEXT, sessions.current.session_id, request(sessions.current, text),
        request_state=state(), budget=budget(),
    )


@pytest.mark.parametrize(("old_make", "text", "canonical"), [
    (None, "what toyata cars do u offer?", "Toyota"),
    ("toyata", "i meant toyota", "Toyota"),
    ("lancia", "Toyota's the badge I had in mind.", "Toyota"),
    (None, "Could I see the Mercdes selection?", "Mercedes"),
])
def test_model_normalized_make_reaches_search_without_rewriting_other_filters(
    old_make, text, canonical,
):
    async def check():
        sessions = FakeSessions(shopping_session(make=old_make))
        original = sessions.current.criteria.model_dump(mode="json")
        proposal = TurnIntent(operation="search", patches=[TextPatch(
            kind="text", field="makes", operation="replace",
            values=[canonical], quote=text,
        )])
        model, transport = adapter(proposal)
        inventory = ExactMakeFixtureInventory(car(1, make=canonical, price=3_600_000))
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, text)
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert len(inventory.searches) == 1
        assert inventory.searches[0].filters.makes == [canonical.casefold()]
        after = sessions.current.criteria.model_dump(mode="json")
        after["filters"]["makes"] = original["filters"]["makes"]
        assert after == original
        assert result.search.supported_total == 1
        packet = json.loads(transport.requests[0].contents)
        assert packet["message"] == text
        assert json.loads(packet["accepted_criteria"])["filters"]["budget"]["maximum"] == 5_000_000

    asyncio.run(check())


def test_correction_recovers_zero_result_and_provider_receives_actual_previous_turn():
    async def check():
        first = "show the Toyata cars"
        second = "Toyota's the one I was talking about"
        model, transport = adapter(*[
            TurnIntent(operation="search", patches=[TextPatch(
                kind="text", field="makes", operation="replace",
                values=[make], quote=text,
            )]) for text, make in [(first, "toyata"), (second, "Toyota")]
        ])
        sessions = FakeSessions(shopping_session())
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota", price=3_699_900))
        coordinator = ReadCoordinator(sessions, model, inventory)
        empty = await run(coordinator, sessions, first)
        assert empty.search.supported_total == 0
        repaired = await run(coordinator, sessions, second)
        assert repaired.state == "answered" and repaired.pending_intent.kind == "none"
        assert repaired.search.supported_total == 1
        assert [make.casefold() for make in sessions.current.criteria.filters.makes] == ["toyota"]
        assert sessions.current.criteria.filters.budget.maximum == 5_000_000
        followup = json.loads(transport.requests[1].contents)
        assert followup["conversation"][0]["text"] == first
        assert "Displayed search: 0 matches" in followup["conversation"][1]["text"]
        assert json.loads(followup["accepted_criteria"])["filters"]["makes"] == ["toyata"]

    asyncio.run(check())


def test_unqualified_purchase_budget_defaults_survive_a_followup_make_correction():
    async def check():
        first = "Find Lancia cars for no more than 50k"
        second = "Sorry, Toyota's the one I had in mind."
        model, transport = adapter(
            TurnIntent(operation="search", patches=[
                TextPatch(
                    kind="text", field="makes", operation="add",
                    values=["Lancia"], quote="Lancia",
                ),
                RangePatch(
                    kind="range", field="budget", operation="refine",
                    maximum=NumberToken(text="50k"), quote="no more than 50k",
                ),
            ]),
            TurnIntent(operation="search", patches=[TextPatch(
                kind="text", field="makes", operation="replace",
                values=["Toyota"], quote="Toyota's the one I had in mind",
            )]),
        )
        sessions = FakeSessions(session(criteria={"filters": {
            "years": {"minimum": 2015}, "mileage_km": {"maximum": 100_000},
        }}))
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota", price=3_699_900))
        coordinator = ReadCoordinator(sessions, model, inventory)
        empty = await run(coordinator, sessions, first)
        assert empty.state == "answered" and empty.pending_intent.kind == "none"
        assert empty.search.supported_total == 0
        assert inventory.searches[0].filters.makes == ["lancia"]
        accepted = sessions.current.criteria.filters.budget
        assert accepted is not None
        assert accepted.currency == "AED" and accepted.basis == "cash"
        assert accepted.maximum == 5_000_000 and accepted.minimum is None
        repaired = await run(coordinator, sessions, second)
        assert repaired.state == "answered" and repaired.pending_intent.kind == "none"
        assert repaired.search.supported_total == 1
        assert inventory.searches[1].filters.makes == ["toyota"]
        assert inventory.searches[1].filters.budget == accepted
        assert sessions.current.criteria.filters.budget == accepted
        assert sessions.current.criteria.filters.years.minimum == 2015
        assert sessions.current.criteria.filters.mileage_km.maximum == 100_000
        followup = json.loads(transport.requests[1].contents)
        assert followup["conversation"][0]["text"] == first
        assert "Displayed search: 0 matches" in followup["conversation"][1]["text"]
        prior = json.loads(followup["accepted_criteria"])["filters"]
        assert prior["budget"] == accepted.model_dump(mode="json")
        assert prior["makes"] == ["Lancia"]
        assert sessions.current.selected_ref is None and repaired.operation is None
        assert repaired.actions.lead.state == "not_requested"

    asyncio.run(check())


def test_natural_followup_is_synthesized_from_previous_result_set_and_cited_facts():
    async def check():
        initial = "Show the Toyata listings"
        followup = "From that lot, which one has the latest model year?"
        transport = ScriptedTransport(
            response(TurnIntent(operation="search", patches=[TextPatch(
                kind="text", field="makes", operation="replace", values=["Toyota"],
                quote=initial,
            )])),
            response(TurnIntent(operation="question", question=QuestionRequest(source="shown"))),
            TransportResponse(draft(
                "The Toyota Corolla has the newest listed model year: 2023.",
                ("car2.make", "Toyota"), ("car2.model", "Corolla"),
                ("car2.year", "2023"), ("stats.year", '"maximum":2023'),
            ).model_dump_json()),
        )
        sessions = FakeSessions()
        inventory = ExactMakeFixtureInventory(
            car(1, make="Toyota", model="Camry", year=2018),
            car(2, make="Toyota", model="Corolla", year=2023),
        )
        coordinator = ReadCoordinator(sessions, provider(transport), inventory)
        assert (await run(coordinator, sessions, initial)).search.supported_total == 2
        result = await run(coordinator, sessions, followup)
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert "2023" in result.text and "Corolla" in result.text
        assert any(
            item.ref.source_id == "2" and "year" in item.attributes for item in result.evidence
        )
        planner = json.loads(transport.requests[1].contents)
        synthesizer = json.loads(transport.requests[2].contents)
        assert planner["conversation"][0]["text"] == initial
        assert initial in synthesizer["conversation"][0]["text"]
        source = json.loads(synthesizer["source_context"])
        assert source["scope"]["rows"] == 2 and source["scope"]["complete"]
        assert source["statistics"]["stats.year"]["maximum"] == 2023
        assert len(inventory.searches) == 1, "A shown-set follow-up must not run a new broad search"

    asyncio.run(check())


@pytest.mark.parametrize("proposal", [
    TurnIntent(operation="question", question=QuestionRequest(source="selected")),
    TurnIntent(operation="detail", references=[ReferenceRequest(
        source="selected", quote="that one",
    )]),
    TurnIntent(operation="question", question=QuestionRequest(source="selected"),
               problem="reference", problem_target="selected_ref"),
])
def test_read_only_followup_uses_previous_results_without_requiring_ui_selection(proposal):
    async def check():
        initial = "Show Toyota cars"
        followup = "What model year is that one and how much does it cost?"
        transport = ScriptedTransport(
            response(TurnIntent(operation="search", patches=[TextPatch(
                kind="text", field="makes", operation="replace", values=["Toyota"],
                quote=initial,
            )])),
            response(proposal),
            TransportResponse(draft(
                "The Toyota Camry is a 2018 model with a stated cash price of AED 36,999.",
                ("car1.make", "Toyota"), ("car1.model", "Camry"),
                ("car1.year", "2018"), ("car1.cash_price", "36,999.00"),
            ).model_dump_json()),
        )
        sessions = FakeSessions(shopping_session())
        inventory = ExactMakeFixtureInventory(
            car(1, make="Toyota", model="Camry", year=2018, price=3_699_900),
        )
        coordinator = ReadCoordinator(sessions, provider(transport), inventory)
        assert (await run(coordinator, sessions, initial)).search.supported_total == 1
        assert sessions.current.selected_ref is None
        before = sessions.current.criteria.model_copy(deep=True)
        result = await run(coordinator, sessions, followup)
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert "2018" in result.text and "36,999" in result.text
        assert any(
            item.ref.source_id == "1" and {"year", "cash_price"} <= set(item.attributes)
            for item in result.evidence
        )
        assert sessions.current.criteria == before
        assert sessions.current.selected_ref is None, "A read must not create action selection"
        assert result.operation is None and result.actions.lead.state == "not_requested"
        assert len(inventory.searches) == 1
        synthesis = json.loads(transport.requests[2].contents)
        corpus = json.loads(synthesis["source_context"])
        assert corpus["scope"]["scope"] == "shown" and corpus["scope"]["rows"] == 1
        assert initial in synthesis["conversation"][0]["text"]

    asyncio.run(check())


@pytest.mark.parametrize("proposal", [
    TurnIntent(operation="question", question=QuestionRequest(source="selected")),
    TurnIntent(operation="detail", references=[ReferenceRequest(
        source="selected", quote="that one",
    )]),
])
def test_read_only_followup_without_previous_results_retains_clarification(proposal):
    async def check():
        sessions = FakeSessions(shopping_session())
        model, transport = adapter(proposal)
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota"))
        before = sessions.current.criteria.model_copy(deep=True)
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions,
            "What model year is that one and how much does it cost?",
        )
        assert result.state == "clarification"
        assert result.pending_intent.purpose == "listing_reference"
        assert sessions.current.criteria == before and sessions.current.selected_ref is None
        assert not result.evidence and inventory.calls == [] and len(transport.requests) == 1

    asyncio.run(check())


def test_current_make_patch_constrains_a_question_even_if_planner_chooses_inventory():
    async def check():
        question = "How many Toyota listings have a stated price?"
        transport = ScriptedTransport(
            response(TurnIntent(
                operation="question", question=QuestionRequest(source="inventory"),
                patches=[TextPatch(
                    kind="text", field="makes", operation="add", values=["Toyota"],
                    quote="Toyota",
                )],
            )),
            TransportResponse(draft(
                "There are 2 Toyota listings, and 1 has a stated cash price.",
                ("car1.make", "Toyota"), ("car2.make", "Toyota"),
                ("scope", '"rows":2'), ("stats.cash_price", '"exact":1'),
            ).model_dump_json()),
        )
        sessions = FakeSessions()
        inventory = ExactMakeFixtureInventory(
            car(1, make="Toyota", price=3_600_000), car(2, make="Toyota"),
            car(3, make="Nissan", price=2_000_000),
        )
        result = await run(
            ReadCoordinator(sessions, provider(transport), inventory), sessions, question,
        )
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert len(inventory.searches) == 1
        assert inventory.searches[0].filters.makes == ["toyota"]
        corpus = json.loads(json.loads(transport.requests[1].contents)["source_context"])
        assert corpus["scope"]["scope"] == "matching"
        assert corpus["scope"]["rows"] == 2 and corpus["scope"]["complete"]
        assert corpus["statistics"]["stats.cash_price"]["exact"] == 1
        assert {item.ref.source_id for item in result.evidence} == {"1", "2"}
        assert sessions.current.criteria.filters.makes == ["Toyota"]
        assert sessions.current.selected_ref is None and result.operation is None

    asyncio.run(check())


def test_clear_correction_resolves_old_make_clarification_without_resetting_budget():
    async def check():
        question_id = str(uuid4())
        current = shopping_session(make="toyata").model_dump(mode="json")
        current.update(revision=2, pending_intent={
            "kind": "clarification", "intent_id": question_id, "created_revision": 2,
            "purpose": "search_criteria", "targets": ["makes"],
            "question": "Which makes condition should I change?",
        })
        sessions = FakeSessions(session(**current))
        model, _ = adapter(TurnIntent(operation="search", patches=[TextPatch(
            kind="text", field="makes", operation="replace", values=["Toyota"],
            quote="i meant toyota",
        )]))
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota", price=3_699_900))
        result = await ReadCoordinator(sessions, model, inventory).run(
            CONTEXT, sessions.current.session_id,
            request(sessions.current, "i meant toyota", clarification_reply={
                "intent_id": question_id, "created_revision": 2,
            }),
            request_state=state(), budget=budget(),
        )
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert result.search.supported_total == 1
        assert sessions.current.criteria.filters.budget.maximum == 5_000_000

    asyncio.run(check())


def test_ordinary_correction_resolves_pending_make_without_frontend_reply_metadata():
    async def check():
        current = shopping_session(make="toyata").model_dump(mode="json")
        current.update(revision=2, pending_intent={
            "kind": "clarification", "intent_id": str(uuid4()), "created_revision": 2,
            "purpose": "search_criteria", "targets": ["makes"],
            "question": "Which makes condition should I change?",
        })
        sessions = FakeSessions(session(**current))
        model, _ = adapter(TurnIntent(operation="search", patches=[TextPatch(
            kind="text", field="makes", operation="replace", values=["Toyota"],
            quote="I meant Toyota",
        )]))
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota", price=3_699_900))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions, "I meant Toyota",
        )
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert sessions.current.pending_intent.kind == "none"
        assert result.search.supported_total == 1
        assert sessions.current.criteria.filters.budget.maximum == 5_000_000

    asyncio.run(check())


def test_unrelated_make_patch_does_not_resolve_pending_budget_question():
    async def check():
        current = shopping_session(make="nissan").model_dump(mode="json")
        current.update(revision=2, pending_intent={
            "kind": "clarification", "intent_id": str(uuid4()), "created_revision": 2,
            "purpose": "search_criteria", "targets": ["budget"],
            "question": "What purchase budget should I use?",
        })
        sessions = FakeSessions(session(**current))
        pending = sessions.current.pending_intent.model_copy(deep=True)
        model, _ = adapter(TurnIntent(operation="search", patches=[TextPatch(
            kind="text", field="makes", operation="replace", values=["Toyota"],
            quote="I meant Toyota",
        )]))
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota", price=3_699_900))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions, "I meant Toyota",
        )
        assert result.state == "clarification" and result.pending_intent == pending
        assert sessions.current.pending_intent == pending
        assert result.search is None and inventory.calls == []
        assert sessions.current.criteria.filters.budget.maximum == 5_000_000

    asyncio.run(check())


def test_model_interpreted_budget_revision_preserves_make_and_exact_numeric_value():
    async def check():
        text = "Forty is too little; 55k is the ceiling I can manage"
        model, _ = adapter(TurnIntent(operation="search", patches=[RangePatch(
            kind="range", field="budget", operation="correct",
            maximum=NumberToken(text="55k"), currency="AED", basis="cash", quote=text,
        )]))
        sessions = FakeSessions(shopping_session(make="toyota"))
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota", price=3_600_000))
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, text)
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert inventory.searches[0].filters.budget.maximum == 5_500_000
        assert sessions.current.criteria.filters.makes == ["toyota"]
        assert sessions.current.criteria.filters.years.minimum == 2015

    asyncio.run(check())


def test_model_can_remove_lower_endpoint_without_resetting_unrelated_filters():
    async def check():
        text = "I'd be happy with anything up to 40k now"
        model, _ = adapter(TurnIntent(operation="search", patches=[RangePatch(
            kind="range", field="budget", operation="correct", clear_minimum=True,
            maximum=NumberToken(text="40k"), currency="AED", basis="cash", quote=text,
        )]))
        current = shopping_session(make="toyota").model_dump(mode="json")
        current["criteria"]["filters"]["budget"].update(minimum=5_000_000, maximum=10_000_000)
        sessions = FakeSessions(session(**current))
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota", price=3_600_000))
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, text)
        assert result.state == "answered" and result.pending_intent.kind == "none"
        assert inventory.searches[0].filters.budget.minimum is None
        assert inventory.searches[0].filters.budget.maximum == 4_000_000
        assert sessions.current.criteria.filters.makes == ["toyota"]
        assert sessions.current.criteria.filters.years.minimum == 2015
        assert sessions.current.criteria.filters.mileage_km.maximum == 100_000

    asyncio.run(check())


@pytest.mark.parametrize("proposal", [
    TurnIntent(operation="search", deferred=["preferences"]),
    TurnIntent(operation="search", deferred=["shortlist"]),
    TurnIntent(operation="smalltalk", collection=CollectionProposal(command="start_viewing")),
    TurnIntent(operation="search", scope="durable", patches=[TextPatch(
        kind="text", field="makes", operation="replace", values=["Toyota"], quote="toyota",
    )]),
])
def test_non_read_proposals_never_enter_semantic_search(monkeypatch, proposal):
    async def check():
        def forbidden(*args, **kwargs):
            pytest.fail("A durable/action proposal entered the read-only semantic transition")

        monkeypatch.setattr("app.assistant.coordinator.apply_search_intent", forbidden)
        sessions = FakeSessions(shopping_session(make="nissan"))
        original = sessions.current.criteria.model_copy(deep=True)
        model, _ = adapter(proposal)
        inventory = ExactMakeFixtureInventory(car(1, make="Toyota"))
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, "toyota")
        assert result.search is None
        assert inventory.calls == []
        assert sessions.current.criteria == original
        assert result.actions.lead.state == "not_requested" and result.operation is None

    asyncio.run(check())
