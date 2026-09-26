"""Actual A1/A2 adapter + scripted JSON + narrow A3 port fakes, never live services."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import ListingResult, SearchRequest, SearchResult
from app.api.schemas.sessions import ClarificationIntent, MessageRequest, MessageResult
from app.assistant.budget import TurnBudget
from app.assistant.collection_bridge import CollectionPort
from app.assistant.collection_planner import CollectionObservation
from app.assistant.coordinator import ReadCoordinator
from app.assistant.grounded_conversation import GroundedConversationDraft
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.assistant.provider import ProviderFault, TransportResponse
from app.core.errors import ApiFailure
from app.sessions.collection import CollectionSnapshot

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    ScriptedTransport,
    adapter,
    budget,
    listing,
    provider,
    ref,
    request,
    response,
    session,
    state,
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


def test_broad_browse_uses_actual_structured_adapter_and_atomic_completion() -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        model, transport = adapter(TurnIntent(operation="search"))
        value, ledger = request(sessions.current, "Help me browse cars"), budget()
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value, ledger)
        assert result.state == "answered" and result.persistence == "saved"
        assert result.search is not None and result.search.items
        assert result.turn_revision == 1 and result.current_revision == 2
        assert sessions.completions == [(result.search.presentation, None)]
        assert sessions.current.active_presentation_id == result.search.presentation.presentation_id
        assert inventory.calls == ["search"] and ledger.tool_invocations == 1
        assert ledger.provider_attempts == 1 and len(transport.requests) == 1
        assert 0 < inventory.deadlines[0] <= ledger.deadline_at
        assert result.actions.model_dump() == {
            "preferences": {"state": "not_requested"},
            "shortlist": {"state": "not_requested"},
            "lead": {"state": "not_requested"},
        }

    asyncio.run(exercise())


def test_exact_completed_replay_has_no_provider_or_inventory_rerun() -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        model, transport = adapter(TurnIntent(operation="search"))
        coordinator = ReadCoordinator(sessions, model, inventory)
        value = request(sessions.current, "Browse cars")
        first = await run(coordinator, sessions, value)
        replay_budget = budget()
        second = await run(coordinator, sessions, value, replay_budget)
        assert first == second and len(transport.requests) == 1 and inventory.calls == ["search"]
        assert replay_budget.provider_attempts == replay_budget.tool_invocations == 0
        with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
            await run(coordinator, sessions, value.model_copy(update={"text": "Changed payload"}))

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "interrupted,code", [(False, "OPERATION_UNRESOLVED"), (True, "UNSUPPORTED_STATE")]
)
def test_pending_and_interrupted_admission_do_not_authorize_rerun(
    interrupted: bool, code: str
) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        value = request(sessions.current, "Browse cars")
        await sessions.begin(CONTEXT, sessions.current.session_id, value)
        if interrupted:
            sessions.turns[value.client_message_id].status = "interrupted"
        model, transport = adapter(TurnIntent(operation="search"))
        with pytest.raises(ApiFailure, match=code):
            await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert transport.requests == [] and inventory.calls == [] and sessions.completions == []

    asyncio.run(exercise())


def test_delayed_a_after_b_keeps_original_turn_identity_without_old_search() -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        started, release = asyncio.Event(), asyncio.Event()

        async def delayed() -> TransportResponse:
            started.set()
            await release.wait()
            return response(TurnIntent(operation="search"))

        slow = ReadCoordinator(sessions, provider(ScriptedTransport(delayed)), inventory)
        original = request(sessions.current, "Browse cars")
        task = asyncio.create_task(run(slow, sessions, original))
        try:
            await asyncio.wait_for(started.wait(), 2)
            fast_model, _ = adapter(TurnIntent(operation="smalltalk"))
            newer = await run(
                ReadCoordinator(sessions, fast_model, inventory),
                sessions,
                request(sessions.current, "Hello"),
            )
            release.set()
            older = await asyncio.wait_for(task, 2)
            assert (
                older.state == "superseded"
                and older.client_message_id == original.client_message_id
            )
            assert (
                older.turn_revision == 1 and older.current_revision == newer.current_revision == 2
            )
            assert inventory.calls == [] and sessions.current.criteria == session().criteria
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def pending_budget() -> ClarificationIntent:
    return ClarificationIntent(
        kind="clarification",
        intent_id=str(uuid4()),
        created_revision=0,
        purpose="search_criteria",
        targets=["budget"],
        question="Which currency and total cash amount should the budget use?",
    )


@pytest.mark.parametrize("reply", [False, True])
def test_skipped_or_incomplete_budget_question_never_becomes_unconstrained_search(
    reply: bool,
) -> None:
    async def exercise() -> None:
        pending = pending_budget()
        sessions = FakeSessions(session(pending_intent=pending.model_dump(mode="json")))
        inventory = FakeInventory()
        model, transport = adapter(TurnIntent(operation="search"))
        extra: dict[str, Any] = {}
        if reply:
            extra["clarification_reply"] = {"intent_id": pending.intent_id, "created_revision": 0}
        result = await run(
            ReadCoordinator(sessions, model, inventory),
            sessions,
            request(sessions.current, "AED" if reply else "Just show cars", **extra),
        )
        assert result.state == "clarification" and inventory.calls == []
        assert result.pending_intent.kind == "clarification"
        assert result.pending_intent.targets == ["budget"]
        assert result.pending_intent == pending
        assert pending.question in transport.requests[0].contents
        assert result.search is None and sessions.current.criteria.filters.budget is None

    asyncio.run(exercise())


def test_complete_matched_budget_reply_can_resume_search() -> None:
    async def exercise() -> None:
        pending = pending_budget()
        sessions = FakeSessions(session(pending_intent=pending.model_dump(mode="json")))
        inventory = FakeInventory()
        text = "cash up to AED 60k"
        intent = TurnIntent.model_validate(
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
                        "quote": text,
                    }
                ],
            }
        )
        model, _ = adapter(intent)
        value = request(
            sessions.current,
            text,
            clarification_reply={"intent_id": pending.intent_id, "created_revision": 0},
        )
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert result.search is not None and result.pending_intent.kind == "none"
        assert sessions.current.criteria.filters.budget is not None
        assert sessions.current.criteria.filters.budget.maximum == 6_000_000
        admitted = sessions.turns[value.client_message_id].admission
        assert admitted.session.pending_intent == pending
        assert sessions.lifecycle == ["begin", "get", "complete"]
        replay_model, replay_transport = adapter()
        replay = await run(ReadCoordinator(sessions, replay_model, inventory), sessions, value)
        assert replay == result and replay_transport.requests == []
        assert sessions.lifecycle[-1] == "begin"  # No pre-get after the question is resolved.

    asyncio.run(exercise())


def test_first_honda_uses_original_mixed_order_then_selected_followup() -> None:
    async def exercise() -> None:
        page = str(uuid4())
        sessions = FakeSessions(session(active_presentation_id=page))
        toyota, honda, later = listing("toyota", "Toyota"), listing("honda"), listing("later")
        sessions.presentations[page] = (toyota.listing.ref, honda.listing.ref, later.listing.ref)
        inventory = FakeInventory(later, toyota, honda)  # Fresh order deliberately differs.
        model, _ = adapter(
            TurnIntent(
                operation="detail",
                references=[
                    ReferenceRequest(
                        source="ordinal", position=0, make="Honda", quote="first Honda"
                    )
                ],
            ),
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="selected", quote="that car")],
            ),
        )
        coordinator = ReadCoordinator(sessions, model, inventory)
        ledger = budget()
        first = await run(
            coordinator, sessions, request(sessions.current, "Show the first Honda"), ledger
        )
        assert (
            first.handoff_summary is not None
            and first.handoff_summary.selected_ref == honda.listing.ref
        )
        assert sessions.current.selected_ref == honda.listing.ref and ledger.tool_invocations == 3
        assert inventory.calls == ["original_batch", "detail"]
        second = await run(
            coordinator, sessions, request(sessions.current, "Tell me about that car")
        )
        assert (
            second.handoff_summary is not None
            and second.handoff_summary.selected_ref == honda.listing.ref
        )
        assert "search" not in inventory.calls

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "case",
    [
        "unknown_preceding",
        "omitted_make",
        "selected_bypass",
        "embedded_model_number",
        "short_quote",
        "arabic_qualifier",
        "extra_model_number",
    ],
)
def test_ambiguous_original_reference_never_guesses(case: str) -> None:
    async def exercise() -> None:
        page = str(uuid4())
        first, second = (
            listing("one", None if case == "unknown_preceding" else "Toyota"),
            listing("two"),
        )
        sessions = FakeSessions(
            session(active_presentation_id=page, selected_ref=first.listing.ref.model_dump())
        )
        sessions.presentations[page] = (first.listing.ref, second.listing.ref)
        inventory = FakeInventory(first, second)
        reference = ReferenceRequest(
            source="ordinal", position=0, make="Honda", quote="first Honda"
        )
        if case == "omitted_make":
            reference = reference.model_copy(update={"make": None})
        elif case == "selected_bypass":
            reference = ReferenceRequest(source="selected", quote="first Honda")
        elif case == "embedded_model_number":
            reference = ReferenceRequest(source="ordinal", position=2, quote="Model 3")
        elif case == "short_quote":
            reference = ReferenceRequest(source="ordinal", position=0, quote="first")
        elif case == "arabic_qualifier":
            reference = ReferenceRequest(source="ordinal", position=0, quote="first هوندا")
        elif case == "extra_model_number":
            reference = ReferenceRequest(
                source="ordinal", position=0, make="Honda", quote="first Honda 3"
            )
        model, _ = adapter(TurnIntent(operation="detail", references=[reference]))
        text = "Show first Honda" if case == "short_quote" else reference.quote
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions, request(sessions.current, text)
        )
        assert result.state == "clarification" and result.handoff_summary is None
        assert (
            "detail" not in inventory.calls and sessions.current.selected_ref == first.listing.ref
        )

    asyncio.run(exercise())


def test_provider_failure_preserves_exact_admitted_question_without_replacement() -> None:
    async def exercise() -> None:
        pending = pending_budget()
        sessions = FakeSessions(session(pending_intent=pending.model_dump(mode="json")))
        inventory = FakeInventory()
        failed = provider(ScriptedTransport(ProviderFault("quota")))
        value = request(
            sessions.current,
            "AED",
            clarification_reply={"intent_id": pending.intent_id, "created_revision": 0},
        )
        result = await run(ReadCoordinator(sessions, failed, inventory), sessions, value)
        assert (
            result.state == "provider_unavailable" and result.pending_intent.kind == "clarification"
        )
        assert result.pending_intent.targets == ["budget"] and inventory.calls == []
        assert sessions.current.pending_intent == result.pending_intent == pending
        assert result.current_revision == result.turn_revision == 1
        assert sessions.lifecycle == ["begin", "get", "complete"]
        model, _ = adapter(TurnIntent(operation="search"))
        skipped = await run(
            ReadCoordinator(sessions, model, inventory),
            sessions,
            request(sessions.current, "Browse cars"),
        )
        assert skipped.state == "clarification" and inventory.calls == []

    asyncio.run(exercise())


@pytest.mark.parametrize("collection_available", [False, True], ids=["unconfigured", "configured"])
def test_three_original_ordinals_plus_comparison_is_four_reads_and_defers_actions(
    collection_available: bool,
) -> None:
    async def exercise() -> None:
        page = str(uuid4())
        inventory = FakeInventory(listing("one"), listing("two"), listing("three"))
        sessions = FakeSessions(session(active_presentation_id=page))
        sessions.presentations[page] = tuple(item.listing.ref for item in inventory.items)
        intent = TurnIntent(
            operation="compare",
            references=[
                ReferenceRequest(source="ordinal", position=index, quote=word)
                for index, word in enumerate(("first", "second", "third"))
            ],
            deferred=["viewing", "lead"],
        )
        model, _ = adapter(intent)
        ledger = budget()
        collection = AsyncMock(spec=CollectionPort) if collection_available else None
        if collection is not None:
            collection.observe_collection.return_value = CollectionObservation(
                snapshot=CollectionSnapshot(
                    collection=None,
                    digest=None,
                    expired=False,
                    now="2026-09-24T04:00:00Z",
                    unresolved=None,
                ),
                lead=None,
                draft=None,
            )
        result = await run(
            ReadCoordinator(sessions, model, inventory, collection=collection),
            sessions,
            request(sessions.current, "Compare first, second and third; arrange viewing"),
            ledger,
        )
        assert result.comparison is not None and len(result.comparison.items) == 3
        assert result.comparison.items == list(inventory.items)
        assert ledger.tool_invocations == 4 and inventory.calls == ["compare"]
        assert sessions.reads == ["ordinal", "ordinal", "ordinal"]
        assert result.state == "clarification" and result.operation is None
        assert result.actions.lead.state == "not_requested"
        assert "No preference, shortlist, enquiry or viewing action was executed" in result.text
        if collection is not None:
            collection.observe_collection.assert_awaited_once()
            collection.prepare_collection.assert_not_awaited()
            collection.complete_collection.assert_not_awaited()

    asyncio.run(exercise())


def test_preused_shared_tool_budget_never_fans_out_a_fifth_read() -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        model, _ = adapter(TurnIntent(operation="search"))
        ledger = budget()
        for _ in range(4):
            ledger.begin_tool()
        result = await run(
            ReadCoordinator(sessions, model, inventory),
            sessions,
            request(sessions.current, "Browse"),
            ledger,
        )
        assert result.search is None and inventory.calls == [] and ledger.tool_invocations == 4
        assert "read limit" in result.text

    asyncio.run(exercise())


def test_provider_and_unconfigured_inventory_failures_do_not_claim_empty_results() -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        unavailable = provider(ScriptedTransport(ProviderFault("quota")))
        result = await run(
            ReadCoordinator(sessions, unavailable, inventory),
            sessions,
            request(sessions.current, "Browse"),
        )
        assert (
            result.state == "provider_unavailable"
            and result.search is None
            and inventory.calls == []
        )
        model, _ = adapter(TurnIntent(operation="search"))
        absent = await run(
            ReadCoordinator(sessions, model), sessions, request(sessions.current, "Browse")
        )
        assert absent.state == "answered" and absent.search is None
        assert "does not mean there are no matching cars" in absent.text

    asyncio.run(exercise())


def test_read_criteria_or_exact_ref_mismatch_is_rejected() -> None:
    class WrongSearch(FakeInventory):
        async def search(self, value: SearchRequest, *, deadline_at: float) -> SearchResult:
            result = await super().search(value, deadline_at=deadline_at)
            return result.model_copy(update={"client_request_id": str(uuid4())})

    class WrongDetail(FakeInventory):
        async def detail(self, value: InventoryRef, *, deadline_at: float) -> ListingResult:
            return listing("a-different-car")

    async def exercise() -> None:
        sessions = FakeSessions(session(selected_ref=ref("one").model_dump()))
        for inventory, intent, text in (
            (WrongSearch(), TurnIntent(operation="search"), "Browse"),
            (
                WrongDetail(),
                TurnIntent(
                    operation="detail",
                    references=[ReferenceRequest(source="selected", quote="that car")],
                ),
                "that car",
            ),
        ):
            model, _ = adapter(intent)
            result = await run(
                ReadCoordinator(sessions, model, inventory),
                sessions,
                request(sessions.current, text),
            )
            assert result.search is None and result.handoff_summary is None
            assert "unavailable" in result.text

    asyncio.run(exercise())


def test_cancellation_after_admission_leaves_original_pending_without_domain_work() -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        started = asyncio.Event()

        async def waiting() -> TransportResponse:
            started.set()
            await asyncio.Future[None]()
            raise AssertionError("unreachable")

        coordinator = ReadCoordinator(sessions, provider(ScriptedTransport(waiting)), inventory)
        value = request(sessions.current, "Browse cars")
        task = asyncio.create_task(run(coordinator, sessions, value))
        try:
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert inventory.calls == [] and sessions.completions == []
            replay = await sessions.begin(CONTEXT, sessions.current.session_id, value)
            assert replay.status == "pending" and replay.ticket is None
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_read_cannot_replace_retained_viewing_review_car_or_pending_authority() -> None:
    async def exercise() -> None:
        draft, page = str(uuid4()), str(uuid4())
        pending = {
            "kind": "viewing_review",
            "draft_id": draft,
            "review_id": str(uuid4()),
            "operation_key": "k" * 43,
        }
        sessions = FakeSessions(
            session(
                current_draft_id=draft,
                pending_intent=pending,
                selected_ref=ref("original").model_dump(),
                active_presentation_id=page,
            )
        )
        inventory = FakeInventory(listing("original"), listing("other"))
        sessions.presentations[page] = (ref("original"), ref("other"))
        model, _ = adapter(
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="ordinal", position=1, quote="second")],
            )
        )
        result = await run(
            ReadCoordinator(sessions, model, inventory),
            sessions,
            request(sessions.current, "Show second"),
        )
        assert result.handoff_summary is not None and result.handoff_summary.selected_ref == ref(
            "other"
        )
        assert sessions.current.selected_ref == ref("original")
        assert sessions.current.current_draft_id == draft
        assert sessions.current.pending_intent.model_dump() == pending
        assert sessions.completions[-1][1] is None and result.operation is None

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "operation,text",
    [("return", "Back again"), ("smalltalk", "Hello"), ("unsupported", "Tell me the weather")],
)
def test_non_read_turns_do_not_touch_inventory(operation: str, text: str) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory()
        before = sessions.current
        model, transport = adapter(TurnIntent.model_validate({"operation": operation}))
        greeting = "Hi! I can help you explore the supplied car inventory."
        if operation == "smalltalk":
            answer = GroundedConversationDraft.model_validate({
                "status": "answered",
                "paragraphs": [{
                    "text": greeting,
                    "citations": [{
                        "source_id": "application", "quote": "searches the supplied car inventory",
                    }],
                }],
            })
            transport.steps.append(TransportResponse(answer.model_dump_json()))
        result = await run(
            ReadCoordinator(sessions, model, inventory), sessions, request(sessions.current, text)
        )
        assert result.state == "answered" and result.persistence == "saved"
        assert inventory.calls == [] and sessions.current.criteria == before.criteria
        assert result.operation is None and result.pending_intent == before.pending_intent
        assert all(
            action["state"] == "not_requested" for action in result.actions.model_dump().values()
        )
        if operation == "smalltalk":
            assert result.text == greeting and result.evidence == []
            assert [call.schema["title"] for call in transport.requests] == [
                "TurnIntent", "GroundedConversationDraft",
            ]

    asyncio.run(exercise())
