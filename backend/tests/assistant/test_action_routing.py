"""A8 coordinator proposal tests; require integration.patch + P14 before execution.

These port spies check scheduling/forwarding only, never Store or booking atomicity.
"""

import asyncio
from typing import Any, cast
from uuid import uuid4

import pytest

from app.api.schemas.common import InventoryRef
from app.api.schemas.sessions import MessageRequest, MessageResult, SessionState
from app.assistant.action_bridge import PreparedActions, RequestedActions
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.assistant.recalled_values import format_recalled_preferences
from app.identity.authorization import AuthorizedOwnerContext
from app.sessions.service import TurnAdmission
from app.sessions.state import SessionContent

from .conversation_fakes import (
    CONTEXT, FakeInventory, FakeSessions, ScriptedTransport, adapter, budget,
    provider, ref, request, response, session, state,
)
from .test_recalled_values import NOW, saved_record


class ActionPortSpy:
    def __init__(self, sessions: FakeSessions) -> None:
        self.sessions = sessions
        self.calls: list[str] = []
        self.prepared: list[tuple[TurnAdmission, RequestedActions, InventoryRef | None]] = []
        self.confirmed: MessageRequest | None = None
        self.result: MessageResult | None = None

    async def prepare_actions(
        self, context: AuthorizedOwnerContext, admission: TurnAdmission,
        requested: RequestedActions, resolved_ref: InventoryRef | None,
    ) -> PreparedActions:
        self.calls.append("prepare")
        self.prepared.append((admission, requested, resolved_ref))
        # Opaque port sentinel: this test does not invoke the concrete bridge or persist actions.
        return cast(PreparedActions, object())

    async def complete_actions(
        self, context: AuthorizedOwnerContext, admission: TurnAdmission,
        plan: PreparedActions, result: MessageResult, *, update: SessionContent | None = None,
    ) -> MessageResult:
        self.calls.append("complete")
        assert admission.ticket is not None
        result.text = "Shared completion result."
        self.result = await self.sessions.complete(context, admission.ticket, result, update=update)
        return self.result

    async def confirm_turn(
        self, context: AuthorizedOwnerContext, session_id: str, value: MessageRequest,
    ) -> MessageResult:
        self.calls.append("confirm")
        self.confirmed = value
        assert self.sessions.lifecycle == []
        return MessageResult(
            client_message_id=value.client_message_id, session_id=session_id,
            turn_revision=value.expected_revision + 1, current_revision=value.expected_revision + 1,
            state="answered", text="Shared confirmation receipt.",
            pending_intent={"kind": "none"}, persistence="saved", provider_state="not_used",
        )

    async def recall_preferences(
        self, context: AuthorizedOwnerContext, current: SessionState,
    ) -> str:
        self.calls.append("recall")
        return format_recalled_preferences(
            current.recalled_preferences, session_id=current.session_id, criteria=current.criteria, now=NOW
        )


async def run(coordinator: ReadCoordinator, sessions: FakeSessions, value: MessageRequest) -> MessageResult:
    return await coordinator.run(
        CONTEXT, sessions.current.session_id, value, request_state=state(), budget=budget()
    )


def test_confirmation_routes_before_begin_and_does_not_call_provider() -> None:
    async def exercise() -> None:
        sessions = FakeSessions(session(revision=4))
        actions = ActionPortSpy(sessions)
        gemini, transport = adapter()
        coordinator = ReadCoordinator(sessions, gemini, actions=actions)
        value = request(sessions.current, "Confirm this reviewed viewing", explicit_confirmation={
            "draft_id": str(uuid4()), "review_id": str(uuid4()), "expected_draft_revision": 2,
            "operation_key": "k" * 43, "rules_version": "rules-1", "store_generation": str(uuid4()),
            "confirmation": "confirm_simulated_viewing",
        })
        result = await run(coordinator, sessions, value)
        assert actions.calls == ["confirm"] and actions.confirmed == value
        assert sessions.lifecycle == [] and transport.requests == []
        assert result.current_revision == 5

    asyncio.run(exercise())


def test_plain_yes_and_model_confirmation_cannot_reconstruct_authority() -> None:
    async def exercise() -> None:
        sessions = FakeSessions()
        actions = ActionPortSpy(sessions)
        gemini, _ = adapter(TurnIntent(operation="smalltalk", deferred=["confirmation"]))
        result = await run(ReadCoordinator(sessions, gemini, actions=actions), sessions, request(sessions.current, "yes"))
        assert actions.calls == [] and result.operation is None
        assert result.state == "clarification"

    asyncio.run(exercise())


def test_search_does_not_save_and_completed_action_replay_skips_prepare() -> None:
    async def exercise() -> None:
        sessions = FakeSessions()
        actions = ActionPortSpy(sessions)
        gemini, transport = adapter(TurnIntent(operation="search"), TurnIntent(
            operation="smalltalk", scope="durable", deferred=["preferences"]
        ))
        coordinator = ReadCoordinator(sessions, gemini, FakeInventory(), actions=actions)
        await run(coordinator, sessions, request(sessions.current, "Show cars"))
        assert actions.calls == []
        value = request(sessions.current, "Remember my budget")
        first = await run(coordinator, sessions, value)
        again = await run(coordinator, sessions, value)
        assert actions.calls == ["prepare", "complete"]
        assert first == again and len(transport.requests) == 2
        assert actions.prepared[0][0].request == value

    asyncio.run(exercise())


@pytest.mark.parametrize("matched", [False, True])
def test_save_cannot_replace_unresolved_hard_criteria_question(matched: bool) -> None:
    async def exercise() -> None:
        pending = {"kind": "clarification", "intent_id": str(uuid4()), "created_revision": 1,
                   "purpose": "search_criteria", "targets": ["budget"], "question": "Which currency is your cash budget?"}
        sessions = FakeSessions(session(revision=2, pending_intent=pending))
        actions = ActionPortSpy(sessions)
        gemini, _ = adapter(TurnIntent(operation="smalltalk", scope="durable", deferred=["preferences"]))
        changes: dict[str, Any] = {}
        if matched:
            changes["clarification_reply"] = {"intent_id": pending["intent_id"], "created_revision": 1}
        result = await run(ReadCoordinator(sessions, gemini, actions=actions), sessions,
                           request(sessions.current, "Remember my budget", **changes))
        assert result.text == pending["question"]
        assert result.pending_intent.model_dump(mode="json") == pending
        assert sessions.current.pending_intent == result.pending_intent and actions.calls == []

    asyncio.run(exercise())


def test_newer_turn_prevents_action_preparation() -> None:
    async def exercise() -> None:
        sessions = FakeSessions()
        actions = ActionPortSpy(sessions)

        async def late() -> Any:
            sessions.current.revision += 1
            return response(TurnIntent(operation="smalltalk", scope="durable", deferred=["preferences"]))

        gemini = provider(ScriptedTransport(late))
        result = await run(ReadCoordinator(sessions, gemini, actions=actions), sessions,
                           request(sessions.current, "Remember my budget"))
        assert result.state == "superseded" and actions.calls == []

    asyncio.run(exercise())


@pytest.mark.parametrize("unresolved_reference", [False, True])
def test_unresolved_listing_question_survives_incomplete_action_reply(
    unresolved_reference: bool,
) -> None:
    async def exercise() -> None:
        pending = {"kind": "clarification", "intent_id": str(uuid4()), "created_revision": 1,
                   "purpose": "listing_reference", "targets": ["selected_ref"],
                   "question": "Which exact car should be saved?"}
        sessions = FakeSessions(session(revision=2, pending_intent=pending))
        actions = ActionPortSpy(sessions)
        intent = (
            TurnIntent(operation="detail", deferred=["shortlist"], references=[
                ReferenceRequest(source="selected", quote="the selected car")
            ]) if unresolved_reference else
            TurnIntent(operation="smalltalk", scope="durable", deferred=["preferences"])
        )
        gemini, _ = adapter(intent)
        text = "Add the selected car to my shortlist" if unresolved_reference else "Remember my budget"
        value = request(sessions.current, text, clarification_reply={
            "intent_id": pending["intent_id"], "created_revision": 1,
        })
        result = await run(ReadCoordinator(sessions, gemini, actions=actions), sessions, value)
        assert result.text == pending["question"] and actions.calls == []
        assert result.pending_intent.model_dump(mode="json") == pending
        assert sessions.current.pending_intent == result.pending_intent

    asyncio.run(exercise())


def test_shortlist_ordinal_keeps_original_message_and_original_order() -> None:
    async def exercise() -> None:
        page = str(uuid4())
        sessions = FakeSessions(session(active_presentation_id=page))
        sessions.presentations[page] = (ref("one"), ref("two"))
        actions = ActionPortSpy(sessions)
        gemini, _ = adapter(TurnIntent(operation="detail", deferred=["shortlist"], references=[
            ReferenceRequest(source="ordinal", quote="the second car", position=1)
        ]))
        value = request(sessions.current, "Add the second car to my shortlist")
        await run(ReadCoordinator(sessions, gemini, FakeInventory(), actions=actions), sessions, value)
        assert actions.prepared[0][2] == ref("two")
        assert actions.prepared[0][0].request.text == value.text
        assert sessions.reads == ["ordinal"]

    asyncio.run(exercise())


def test_new_session_reply_contains_two_actual_saved_values() -> None:
    async def exercise() -> None:
        remembered = saved_record()
        sessions = FakeSessions(session(recalled_preferences=remembered.model_dump(mode="json")))
        assert sessions.current.session_id != remembered.entries[0].source_session_id
        actions = ActionPortSpy(sessions)
        gemini, _ = adapter(TurnIntent(operation="return"))
        result = await run(ReadCoordinator(sessions, gemini, actions=actions), sessions,
                           request(sessions.current, "What preferences do you remember?"))
        assert "60,000.00" in result.text and '"Honda", "Toyota"' in result.text
        assert actions.calls == ["recall"] and sessions.current.criteria.filters.makes == []

    asyncio.run(exercise())
