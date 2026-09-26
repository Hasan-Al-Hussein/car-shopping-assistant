"""Collection routing/forwarding checks; doubles provide no Store atomicity proof."""

import json
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from app.api.schemas.sessions import ClarificationIntent
from app.api.schemas.viewings import BookingDraftUpdate
from app.assistant.collection_bridge import CollectionBridge
from app.assistant.collection_planner import CollectionPlan, collection_result
from app.assistant.coordinator import ReadCoordinator
from app.assistant.interpretation import interpret
from app.core.errors import ApiFailure
from app.leads.service import LeadService
from app.sessions.collection import CollectionUpdate, CollectionValues
from app.sessions.service import DraftChange, SessionService
from app.viewings.drafts import DraftService

from .conversation_fakes import CONTEXT, FakeInventory, FakeSessions, adapter, budget, ref, request, session, state
from .test_action_bridge import admission
from .test_collection_planner import RULES, intent, observed


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class CollectionPortSpy:
    def __init__(self, *, failure: ApiFailure | None = None) -> None:
        self.calls: list[str] = []
        self.failure = failure

    async def observe_collection(self, context, turn):
        self.calls.append("observe")
        return observed()

    async def prepare_collection(self, context, turn, observation, requested, resolved_ref):
        self.calls.append("prepare")
        return CollectionPlan(collection_result(turn, "Awaiting shared completion."))

    async def complete_collection(self, context, turn, plan):
        self.calls.append("complete")
        if self.failure is not None:
            raise self.failure
        return plan.result


@pytest.mark.anyio
@pytest.mark.parametrize("text", ["My email is synthetic@example.test", "My phone number is 0501234567"])
async def test_contact_guidance_precedes_provider_and_collection_reads(text: str) -> None:
    sessions, inventory, collection = FakeSessions(), FakeInventory(), CollectionPortSpy()
    model, transport = adapter()
    coordinator = ReadCoordinator(sessions, model, inventory, collection=collection)
    result = await coordinator.run(
        CONTEXT, sessions.current.session_id, request(sessions.current, text), request_state=state(), budget=budget(),
    )
    assert transport.requests == [] and collection.calls == [] and inventory.calls == []
    assert result.provider_state == "not_used" and "local enquiry form" in result.text
    assert result.actions.lead.state == "not_requested" and result.operation is None


@pytest.mark.anyio
async def test_participant_completion_failure_is_not_rewritten_or_completed_again() -> None:
    sessions, inventory = FakeSessions(), FakeInventory()
    failure = ApiFailure("STORE_UNAVAILABLE")
    collection = CollectionPortSpy(failure=failure)
    model, _ = adapter(intent("start_enquiry"))
    coordinator = ReadCoordinator(sessions, model, inventory, collection=collection)
    with pytest.raises(ApiFailure) as caught:
        await coordinator.run(
            CONTEXT, sessions.current.session_id, request(sessions.current, "Prepare a local enquiry"),
            request_state=state(), budget=budget(),
        )
    assert caught.value is failure
    assert collection.calls == ["observe", "prepare", "complete"]
    assert sessions.completions == [] and inventory.calls == []


@pytest.mark.anyio
async def test_negation_cannot_route_a_positive_model_command_to_a_participant() -> None:
    sessions, collection = FakeSessions(), CollectionPortSpy()
    model, _ = adapter(intent("start_enquiry"))
    coordinator = ReadCoordinator(sessions, model, collection=collection)
    result = await coordinator.run(
        CONTEXT, sessions.current.session_id, request(sessions.current, "Do not prepare a local enquiry"),
        request_state=state(), budget=budget(),
    )
    assert collection.calls == ["observe"]
    assert result.state == "clarification" and result.actions.lead.state == "not_requested"


@pytest.mark.anyio
async def test_collection_hint_keeps_the_existing_four_bounded_provider_summaries() -> None:
    question = ClarificationIntent(
        kind="clarification", intent_id=str(uuid4()), created_revision=3,
        purpose="viewing_details", targets=["appointment"], question="Which Dubai viewing time?",
    )
    current = session(revision=3, criteria={"filters": {"budget": {"currency": "AED", "maximum": 5000000}}}, pending_intent=question)
    model, transport = adapter(intent("fields", [("local_time", "14:30")]))
    result = await interpret(
        model, request(current, "14:30"), current, state(), budget(), (),
        collection_summary="Active collection: viewing; date set; time missing.",
    )
    assert result.proposal is not None
    packet = json.loads(transport.requests[0].contents)
    summaries = packet["history_summaries"]
    assert len(summaries) == 4 and all(len(item) <= 400 for item in summaries)
    assert "soft_preferences TextPatch" in summaries[0]
    assert "return/session" in summaries[1] and "Active collection: viewing" in summaries[1]
    assert "AED" in summaries[2] and question.question in summaries[3]
    assert "viewing_details" in summaries[3]


class CompletionSpy:
    def __init__(self) -> None:
        self.authorization = object()
        self.calls = []
        self.result = None
        self.failure = None

    def complete(self, *args, **kwargs):
        self.calls.append(("ordinary", args, kwargs))
        if self.failure is not None:
            raise self.failure
        return self.result

    def complete_action(self, *args, **kwargs):
        self.calls.append(("action", args, kwargs))
        if self.failure is not None:
            raise self.failure
        return self.result


@pytest.mark.parametrize("effect", [False, True])
def test_concrete_bridge_forwards_original_ticket_selection_and_actual_receipt(effect: bool) -> None:
    turn = admission("Prepare a local enquiry")
    sessions = CompletionSpy()
    leads = cast(LeadService, SimpleNamespace(authorization=sessions.authorization))
    drafts = cast(DraftService, SimpleNamespace(authorization=sessions.authorization))
    bridge = CollectionBridge(cast(SessionService, sessions), leads, drafts, RULES)
    change = DraftChange(
        BookingDraftUpdate(client_action_id=str(uuid4()), expected_revision=4, intent="suspend"),
        draft_id=str(uuid4()),
    ) if effect else None
    update = CollectionUpdate(expected_digest=None, purpose="viewing", values=CollectionValues())
    plan = CollectionPlan(collection_result(turn, "Awaiting completion."), collection_update=update, draft=change, selection=ref("second"))
    sessions.result = plan.result.model_copy(update={"text": "Actual wrapper receipt.", "persistence": "saved"})
    result = bridge.complete(CONTEXT, turn, plan)
    kind, args, kwargs = sessions.calls[0]
    assert kind == ("action" if effect else "ordinary")
    assert args[1] is turn.ticket and result is sessions.result
    assert kwargs["selection"] == ref("second") and kwargs["collection_update"] is update
    if effect:
        assert kwargs["draft"] is change and kwargs["lead_service"] is leads and kwargs["draft_service"] is drafts
    sessions.failure = ApiFailure("STORE_UNAVAILABLE")
    with pytest.raises(ApiFailure) as caught:
        bridge.complete(CONTEXT, turn, plan)
    assert caught.value is sessions.failure


def test_bridge_rejects_a_result_for_a_different_original_message_before_completion() -> None:
    turn = admission("Prepare a local enquiry")
    sessions = CompletionSpy()
    leads = cast(LeadService, SimpleNamespace(authorization=sessions.authorization))
    drafts = cast(DraftService, SimpleNamespace(authorization=sessions.authorization))
    bridge = CollectionBridge(cast(SessionService, sessions), leads, drafts, RULES)
    result = collection_result(turn, "Invalid caller.").model_copy(update={"client_message_id": str(uuid4())})
    with pytest.raises(ApiFailure):
        bridge.complete(CONTEXT, turn, CollectionPlan(result))
    assert sessions.calls == []
