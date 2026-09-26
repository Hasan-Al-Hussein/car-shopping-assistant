"""Real collection planning with scripted intents; no live inference or Store proof."""

import asyncio

import pytest

from app.api.schemas.sessions import ClarificationReply
from app.assistant.collection_language import parse_collection_request
from app.assistant.collection_planner import plan_collection
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import CollectionProposal, TurnIntent
from app.sessions.collection import CollectionValues

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    adapter,
    budget,
    request,
    state,
)
from .test_action_bridge import admission
from .test_collection_planner import RULES, envelope, intent, observed


class PlanningPort:
    """Invoke the actual planner; completion is observed, never represented as committed."""

    def __init__(self, observation):
        self.observation = observation
        self.calls = []
        self.plan = None

    async def observe_collection(self, context, turn):
        self.calls.append("observe")
        return self.observation

    async def prepare_collection(self, context, turn, observation, requested, resolved_ref):
        self.calls.append("prepare")
        self.plan = plan_collection(
            turn, observation, requested, resolved_ref=resolved_ref, rules=RULES,
        )
        return self.plan

    async def complete_collection(self, context, turn, plan):
        self.calls.append("complete")
        return plan.result


@pytest.mark.parametrize("lead_marker", [False, True])
@pytest.mark.parametrize("scenario", [
    "valid", "missing_echo", "stale_values", "negated", "bare_yes",
])
def test_reviewed_save_routes_to_real_planner_without_weakening_guards(
    lead_marker: bool, scenario: str,
) -> None:
    async def exercise() -> None:
        review = admission("Review my local enquiry")
        values = CollectionValues.model_validate({
            "budget": {"state": "provided", "value": {"maximum": 4500000, "currency": "AED"}},
            "requirements": ["quiet cabin"], "requirements_state": "provided",
        })
        observation = observed(envelope(review, purpose="local_enquiry", values=values))
        review_plan = plan_collection(
            review, observation,
            parse_collection_request(
                review.request.text, intent("review_enquiry"), matched_question=None,
            ),
            resolved_ref=None, rules=RULES,
        )
        question = review_plan.result.pending_intent
        assert question.kind == "clarification" and question.targets == ["confirmation"]
        assert review_plan.lead is None and review_plan.draft is None
        stored = envelope(
            review, purpose="local_enquiry", values=values, question=question, displayed=True,
        )
        if scenario == "stale_values":
            stored = stored.model_copy(update={
                "values": values.model_copy(update={"requirements": ["changed after review"]}),
            })
        sessions = FakeSessions(review.session.model_copy(update={
            "revision": question.created_revision, "pending_intent": question,
        }))
        before = sessions.current.criteria
        port, inventory = PlanningPort(observed(stored)), FakeInventory()
        model, transport = adapter(TurnIntent(
            operation="smalltalk", scope="session", deferred=["lead"] if lead_marker else [],
            collection=CollectionProposal(command="save_enquiry"),
        ))
        text = {
            "negated": "Do not save this local enquiry", "bare_yes": "yes",
        }.get(scenario, "Save this local enquiry")
        message = request(
            sessions.current, text,
            clarification_reply=None if scenario == "missing_echo" else ClarificationReply(
                intent_id=question.intent_id, created_revision=question.created_revision,
            ).model_dump(),
        )
        turn_budget = budget()
        result = await ReadCoordinator(sessions, model, inventory, collection=port).run(
            CONTEXT, sessions.current.session_id, message,
            request_state=state(), budget=turn_budget,
        )
        assert len(transport.requests) == 1 and inventory.calls == []
        assert sessions.current.criteria == before and message.explicit_confirmation is None
        if scenario == "valid":
            assert port.calls == ["observe", "prepare", "complete"]
            assert port.plan is not None and port.plan.lead is not None
            command = port.plan.lead.command
            assert command.intent == "save_local_enquiry"
            assert command.values.budget == values.budget
            assert command.values.requirements == values.requirements
            assert command.values.selected_refs == [] and port.plan.draft is None
            assert result.text == "Saving the reviewed local enquiry."
            assert turn_budget.tool_invocations == 1
        else:
            assert "complete" not in port.calls and port.plan is None
            assert result.state == "clarification" and question.question in result.text
            assert result.pending_intent == question
            assert result.actions.lead.state == "not_requested"
            assert turn_budget.tool_invocations == (scenario in {"missing_echo", "stale_values"})

    asyncio.run(exercise())
