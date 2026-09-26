"""Authored coordinator/P9C composition; requires a separate real test-store grant.

The existing Platform harness supplies real ownership, tickets and SQLite. Provider and
Inventory remain synthetic. The inline thread facade is test scaffolding, not a production
worker/deadline implementation. Nothing initializes a store at module import.
"""

import asyncio
from uuid import uuid4

import pytest

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    ListingDetail,
    PresentationProof,
    SearchCriteria,
    SearchRequest,
    SearchResult,
)
from app.api.schemas.sessions import (
    ClarificationIntent,
    MessageRequest,
    MessageResult,
    SessionState,
    TranscriptTurn,
)
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import TurnIntent
from app.assistant.provider import ProviderFault, TransportResponse
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.sessions.service import SessionService, TurnAdmission, TurnTicket
from app.sessions.state import SessionContent
from tests.platform.session_cases import SessionHarness, answer, make_harness

from .conversation_fakes import (
    FakeInventory,
    ScriptedTransport,
    adapter,
    budget,
    listing,
    provider,
    request,
    state,
)


class ActualSessions:
    def __init__(self, service: SessionService) -> None:
        self.service = service

    async def begin(
        self, context: AuthorizedOwnerContext, session_id: str, value: MessageRequest
    ) -> TurnAdmission:
        return await asyncio.to_thread(self.service.begin, context, session_id, value)

    async def get(self, context: AuthorizedOwnerContext, session_id: str) -> SessionState:
        return await asyncio.to_thread(self.service.get, context, session_id)

    async def recent_context(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        *,
        before_revision: int,
    ) -> tuple[TranscriptTurn, ...]:
        return await asyncio.to_thread(
            self.service.recent_context,
            context,
            session_id,
            before_revision=before_revision,
        )

    async def ordinal(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str, ordinal: int
    ) -> InventoryRef:
        return await asyncio.to_thread(
            self.service.ordinal, context, session_id, presentation_id, ordinal
        )

    async def original_refs(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str
    ) -> tuple[InventoryRef, ...]:
        owned = await asyncio.to_thread(
            self.service.presentation_refs, context, session_id, presentation_id
        )
        return tuple(
            InventoryRef.model_validate(item.model_dump(mode="json")) for item in owned.refs
        )

    async def complete(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
        result: MessageResult,
        *,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
    ) -> MessageResult:
        return await asyncio.to_thread(
            self.service.complete,
            context,
            ticket,
            result,
            update=update,
            presentation=presentation,
            selection=selection,
        )


def pending_session() -> tuple[SessionHarness, SessionState, ClarificationIntent]:
    harness = make_harness()  # Executed only inside separately authorized test functions.
    current = harness.create()
    first = harness.service.begin(
        harness.context(), current.session_id, request(current, "Help choose a make")
    )
    assert first.ticket is not None
    pending = ClarificationIntent(
        kind="clarification",
        intent_id=str(uuid4()),
        created_revision=first.session.revision,
        purpose="search_criteria",
        targets=["makes"],
        question="Which make should be required?",
    )
    result = answer(first).model_copy(
        update={"state": "clarification", "text": pending.question, "pending_intent": pending}
    )
    harness.service.complete(
        harness.context(), first.ticket, result, update=SessionContent(pending_intent=pending)
    )
    return harness, harness.service.get(harness.context(), current.session_id), pending


def test_recent_context_is_owned_completed_bounded_and_chronological() -> None:
    harness = make_harness()
    current = harness.create()
    for index in range(8):
        admitted = harness.service.begin(
            harness.context(), current.session_id, request(current, f"Shopping question {index}")
        )
        harness.service.complete(harness.context(), admitted.ticket, answer(admitted))
        current = harness.service.get(harness.context(), current.session_id)
    admission = harness.service.begin(
        harness.context(), current.session_id, request(current, "Current unfinished question")
    )
    turns = harness.service.recent_context(
        harness.context(), current.session_id, before_revision=admission.session.revision
    )
    assert [turn.user_text for turn in turns] == [f"Shopping question {i}" for i in range(2, 8)]
    assert all(turn.state == "completed" for turn in turns)
    with pytest.raises(ApiFailure):
        harness.service.recent_context(
            harness.context(1), current.session_id, before_revision=admission.session.revision
        )


def reply(
    current: SessionState, pending: ClarificationIntent, text: str = "Honda"
) -> MessageRequest:
    return request(
        current,
        text,
        clarification_reply={
            "intent_id": pending.intent_id,
            "created_revision": pending.created_revision,
        },
    )


def honda_intent() -> TurnIntent:
    return TurnIntent.model_validate(
        {
            "operation": "search",
            "patches": [
                {
                    "kind": "text",
                    "field": "makes",
                    "operation": "add",
                    "values": ["Honda"],
                    "quote": "Honda",
                }
            ],
        }
    )


class SignedReadFixture(FakeInventory):
    """One synthetic result using the Platform fixture's actually verified proof."""

    def __init__(self, harness: SessionHarness) -> None:
        self.proof = harness.proof(("12",))
        item = listing("12").model_dump(mode="json")
        item["listing"]["ref"] = self.proof.ordered_refs[0].model_dump(mode="json")
        super().__init__(ListingDetail.model_validate(item))

    async def search(self, value: SearchRequest, *, deadline_at: float) -> SearchResult:
        self.calls.append("search")
        criteria = SearchCriteria.model_validate(
            value.model_dump(
                mode="json",
                exclude={"snapshot_id", "page_size", "cursor", "client_request_id"},
            )
        )
        return SearchResult(
            client_request_id=value.client_request_id,
            state="matches",
            items=[self.items[0].listing],
            supported_total=1,
            next_cursor=None,
            presentation=self.proof,
            applied_criteria=criteria,
            evidence_coverage=[],
        )


@pytest.mark.parametrize("unavailable", [False, True])
def test_actual_p9c_preserves_question_for_incomplete_or_failed_interpretation(
    unavailable: bool,
) -> None:
    harness, current, pending = pending_session()
    context = harness.context()

    async def exercise() -> None:
        sessions, inventory = ActualSessions(harness.service), FakeInventory()
        model = (
            provider(ScriptedTransport(ProviderFault("quota")))
            if unavailable
            else adapter(TurnIntent(operation="search"))[0]
        )
        coordinator = ReadCoordinator(sessions, model, inventory)
        value = reply(current, pending, "Maybe")
        result = await coordinator.run(
            context, current.session_id, value, request_state=state(), budget=budget()
        )
        persisted = await sessions.get(context, current.session_id)
        assert result.state == ("provider_unavailable" if unavailable else "clarification")
        assert result.pending_intent == persisted.pending_intent == pending
        assert (
            persisted.revision
            == result.turn_revision
            == result.current_revision
            == current.revision + 1
        )
        assert inventory.calls == [] and persisted.criteria == current.criteria

    asyncio.run(exercise())


def test_actual_p9c_current_resolution_and_exact_replay_use_one_ticket_completion() -> None:
    harness, current, pending = pending_session()
    context, inventory = harness.context(), SignedReadFixture(harness)

    async def exercise() -> None:
        sessions = ActualSessions(harness.service)
        model, transport = adapter(honda_intent())
        coordinator = ReadCoordinator(sessions, model, inventory)
        value = reply(current, pending)
        result = await coordinator.run(
            context, current.session_id, value, request_state=state(), budget=budget()
        )
        persisted = await sessions.get(context, current.session_id)
        assert result.pending_intent.kind == persisted.pending_intent.kind == "none"
        assert persisted.criteria.filters.makes == ["Honda"]
        assert result.turn_revision == 3 and result.current_revision == persisted.revision == 4
        assert result.search is not None and persisted.active_presentation_id is not None
        assert persisted.active_presentation_id != result.search.presentation.presentation_id
        replay = await coordinator.run(
            context, current.session_id, value, request_state=state(), budget=budget()
        )
        assert replay == result and len(transport.requests) == 1 and inventory.calls == ["search"]

    asyncio.run(exercise())


def test_actual_p9c_retains_question_when_coordinator_is_cancelled_after_admission() -> None:
    harness, current, pending = pending_session()
    context = harness.context()

    async def exercise() -> None:
        sessions, inventory = ActualSessions(harness.service), FakeInventory()
        started = asyncio.Event()

        async def waiting() -> TransportResponse:
            started.set()
            await asyncio.Future[None]()
            raise AssertionError("unreachable")

        transport = ScriptedTransport(waiting)
        coordinator = ReadCoordinator(sessions, provider(transport), inventory)
        value = reply(current, pending)
        task = asyncio.create_task(
            coordinator.run(
                context, current.session_id, value, request_state=state(), budget=budget()
            )
        )
        try:
            await asyncio.wait_for(started.wait(), 5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            persisted = await sessions.get(context, current.session_id)
            assert persisted.pending_intent == pending and persisted.criteria == current.criteria
            with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
                await coordinator.run(
                    context, current.session_id, value, request_state=state(), budget=budget()
                )
            model, _ = adapter(TurnIntent(operation="search"))
            later = await ReadCoordinator(sessions, model, inventory).run(
                context,
                current.session_id,
                request(persisted, "Browse cars"),
                request_state=state(),
                budget=budget(),
            )
            assert later.state == "clarification" and later.pending_intent == pending
            assert len(transport.requests) == 1 and inventory.calls == []
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_actual_p9c_fences_old_resolution_when_new_question_arrives_during_read() -> None:
    harness, current, pending = pending_session()
    context = harness.context()

    async def exercise() -> None:
        started, release = asyncio.Event(), asyncio.Event()

        class PausedRead(SignedReadFixture):
            async def search(self, value: SearchRequest, *, deadline_at: float) -> SearchResult:
                started.set()
                await release.wait()
                return await super().search(value, deadline_at=deadline_at)

        sessions, inventory = ActualSessions(harness.service), PausedRead(harness)
        model, _ = adapter(honda_intent())
        coordinator = ReadCoordinator(sessions, model, inventory)
        value = reply(current, pending)
        task = asyncio.create_task(
            coordinator.run(
                context, current.session_id, value, request_state=state(), budget=budget()
            )
        )
        try:
            await asyncio.wait_for(started.wait(), 5)
            observed = await sessions.get(context, current.session_id)
            newer = await sessions.begin(
                context, current.session_id, request(observed, "Clarify budget")
            )
            assert newer.ticket is not None
            replacement = ClarificationIntent(
                kind="clarification",
                intent_id=str(uuid4()),
                created_revision=newer.session.revision,
                purpose="search_criteria",
                targets=["budget"],
                question="Which cash budget should apply?",
            )
            newer_result = answer(newer).model_copy(
                update={
                    "state": "clarification",
                    "text": replacement.question,
                    "pending_intent": replacement,
                }
            )
            await sessions.complete(
                context,
                newer.ticket,
                newer_result,
                update=SessionContent(pending_intent=replacement),
            )
            release.set()
            older = await asyncio.wait_for(task, 5)
            persisted = await sessions.get(context, current.session_id)
            assert older.state == "superseded" and older.turn_revision == 3
            assert (
                persisted.pending_intent == replacement and persisted.criteria == current.criteria
            )
            assert (
                persisted.active_presentation_id is None
                and persisted.revision == older.current_revision == 5
            )
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
