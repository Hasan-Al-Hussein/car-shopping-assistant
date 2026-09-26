"""A8 boundary tests: require real P14 imports; doubles prove forwarding, not atomicity.

Authored source only. No fallback module or skipped missing dependency is installed.
"""

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.api.schemas.memory import PreferenceRecord, ShortlistResult
from app.api.schemas.sessions import MessageResult
from app.assistant.action_bridge import (
    ActionBridge, ActionClarification, RequestedActions, requested_actions,
)
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.core.errors import ApiFailure
from app.memory.service import PreferenceService
from app.sessions.service import SessionService, TurnAdmission, TurnTicket
from app.shortlist.service import ShortlistService
from app.viewings.confirmation import ConfirmationParticipant

from .conversation_fakes import CONTEXT, ref, request, session


def admission(text: str, **changes: Any) -> TurnAdmission:
    current = session(
        revision=8,
        criteria={"filters": {"budget": {"maximum": 6_000_000, "currency": "AED"},
                              "makes": ["Honda"]}, "soft_preferences": ["family use"]},
        recalled_preferences={"revision": 4, "entries": [], "collection_mode": "explicit_save"},
        **changes,
    )
    return TurnAdmission(
        "accepted", str(uuid4()), current, request(current, text, expected_revision=7),
        ticket=object.__new__(TurnTicket),
    )


def neutral(turn: TurnAdmission) -> MessageResult:
    return MessageResult(
        client_message_id=turn.request.client_message_id, session_id=turn.session.session_id,
        turn_revision=turn.session.revision, current_revision=turn.session.revision,
        state="answered", text="Awaiting completion.", pending_intent=turn.session.pending_intent,
        persistence="not_saved", provider_state="available",
    )


class CompletionSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.result: MessageResult | None = None
        self.failure: ApiFailure | None = None

    def complete_action(self, *args: Any, **kwargs: Any) -> MessageResult:
        self.calls.append((*args, kwargs))
        if self.failure is not None:
            raise self.failure
        assert self.result is not None
        return self.result

    def confirm_turn(self, *args: Any, **kwargs: Any) -> MessageResult:
        return self.complete_action(*args, **kwargs)


class ShortlistSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def get(self, context: Any, *, page_size: int) -> ShortlistResult:
        self.calls.append((context, page_size))
        return ShortlistResult(revision=17, items=[], total=0, next_cursor=None)


def bridge(spy: CompletionSpy, shortlist: ShortlistSpy | None = None) -> ActionBridge:
    return ActionBridge(
        cast(SessionService, spy), preferences=cast(PreferenceService, object()),
        shortlist=None if shortlist is None else cast(ShortlistService, shortlist),
        confirmation=cast(ConfirmationParticipant, object()),
    )


def test_search_is_not_permission_and_completed_admission_cannot_prepare() -> None:
    turn = admission("Show cars within my budget")
    assert requested_actions(turn, TurnIntent(operation="search")) is None
    with pytest.raises(ApiFailure):
        bridge(CompletionSpy()).prepare(
            CONTEXT, replace(turn, status="completed", ticket=None),
            # A trusted parser result from a separate explicit message cannot revive a ticket.
            required(admission("Remember my budget")), None,
        )


def required(turn: TurnAdmission, intent: TurnIntent | None = None) -> RequestedActions:
    parsed = requested_actions(
        turn, intent or TurnIntent(operation="smalltalk", scope="durable", deferred=["preferences"])
    )
    assert parsed is not None
    return parsed


@pytest.mark.parametrize("extra", [
    {"scope": "hypothetical"}, {"deferred": ["preferences", "viewing"]},
    {"patches": [{"kind": "text", "field": "makes", "operation": "replace",
                  "values": ["Honda"], "quote": "Remember my makes"}]},
])
def test_model_cannot_mix_new_criteria_or_other_effects_into_save(extra: dict[str, Any]) -> None:
    turn = admission("Remember my makes")
    intent = TurnIntent.model_validate({"operation": "smalltalk", "scope": "durable",
                                       "deferred": ["preferences"], **extra})
    with pytest.raises(ActionClarification):
        required(turn, intent)


@pytest.mark.parametrize("text", [
    "Do not remember my budget", "Remember my saved budget", "Save my saved makes",
    "Correct my preferences", "Remember my requirements", "Remember my budget and book a viewing",
    "Remember my budget of AED 90,000", "Remember my budget and remember my makes",
])
def test_unsupported_or_ambiguous_command_has_no_plan(text: str) -> None:
    with pytest.raises(ActionClarification):
        required(admission(text))


def test_correction_copies_current_values_and_retains_original_identity() -> None:
    turn = admission("Update my saved preferences to my current search")
    spy = CompletionSpy()
    actual = bridge(spy)
    plan = actual.prepare(CONTEXT, turn, required(turn), None)
    replay = actual.prepare(CONTEXT, turn, required(turn), None)
    assert plan.preference is not None and replay.preference is not None
    assert plan.preference.expected_revision == 4 != turn.session.revision
    assert plan.preference.intent == "correct"
    assert plan.preference.session_id == turn.session.session_id
    assert plan.message_id == turn.message_id
    assert plan.preference.client_action_id == replay.preference.client_action_id
    assert {value.key for value in plan.preference.changes} == {"budget", "makes", "requirements"}
    turn.session.criteria.filters.makes.append("Toyota")
    assert plan.preference.changes[1].value == ["Honda"]
    assert spy.calls == []


def test_save_all_cannot_silently_omit_unsupported_current_filters() -> None:
    turn = admission("Remember my preferences")
    turn.session.criteria.filters.models.append("Civic")
    with pytest.raises(ActionClarification):
        bridge(CompletionSpy()).prepare(CONTEXT, turn, required(turn), None)


@pytest.mark.parametrize("text,desired", [
    ("Add the selected car to my shortlist", True),
    ("Remove the selected car from my shortlist", False),
])
def test_membership_uses_exact_reference_and_independent_observed_revision(
    text: str, desired: bool,
) -> None:
    turn, observed = admission(text), ShortlistSpy()
    intent = TurnIntent(operation="detail", deferred=["shortlist"], references=[
        ReferenceRequest(source="selected", quote="the selected car")
    ])
    plan = bridge(CompletionSpy(), observed).prepare(CONTEXT, turn, required(turn, intent), ref("one"))
    assert plan.membership is not None
    assert plan.membership.ref == ref("one") and plan.membership.desired is desired
    assert plan.membership.command.expected_revision == 17
    assert observed.calls == [(CONTEXT, 1)]


def test_compound_domains_have_distinct_ids_and_reject_short_reference_quote() -> None:
    turn = admission("Remember my budget and add the selected car to my shortlist")
    intent = TurnIntent(operation="detail", scope="durable", deferred=["preferences", "shortlist"],
                        references=[ReferenceRequest(source="selected", quote="the selected car")])
    actual = bridge(CompletionSpy(), ShortlistSpy())
    plan = actual.prepare(CONTEXT, turn, required(turn, intent), ref("one"))
    assert plan.preference is not None and plan.membership is not None
    assert plan.preference.client_action_id != plan.membership.command.client_action_id
    incomplete = intent.model_copy(update={"references": [ReferenceRequest(source="selected", quote="car")]})
    with pytest.raises(ActionClarification):
        required(turn, incomplete)


@pytest.mark.parametrize("outcome", ["succeeded", "rejected", "unresolved"])
def test_actual_typed_outcome_and_ack_are_returned_without_rewriting(outcome: str) -> None:
    turn, spy = admission("Remember my budget"), CompletionSpy()
    actual = bridge(spy)
    plan = actual.prepare(CONTEXT, turn, required(turn), None)
    assert plan.preference is not None
    action: dict[str, Any] = {"state": outcome, "client_action_id": plan.preference.client_action_id}
    if outcome == "succeeded":
        action["result"] = {"entries": [], "revision": 5, "collection_mode": "explicit_save"}
    elif outcome == "rejected":
        action["code"] = "REVISION_CONFLICT"
    else:
        action.update(submitted_store_generation=str(uuid4()), recovery="read_current_state")
    result = neutral(turn)
    spy.result = MessageResult.model_validate({
        **result.model_dump(mode="json"), "text": "Actual shared-service acknowledgement: " + outcome,
        "actions": {"preferences": action}, "persistence": "saved",
    })
    returned = actual.complete(CONTEXT, turn, plan, result)
    assert returned is spy.result
    context, ticket, submitted, commands = spy.calls[0]
    assert context is CONTEXT and ticket is turn.ticket
    assert submitted.actions.preferences.state == "not_requested"
    assert commands["preference"] == plan.preference
    assert commands["preference_service"] is actual.preferences


def test_unknown_commit_failure_and_supersession_are_not_rewritten() -> None:
    turn, spy = admission("Remember my budget"), CompletionSpy()
    actual = bridge(spy)
    plan = actual.prepare(CONTEXT, turn, required(turn), None)
    spy.failure = ApiFailure("OPERATION_UNRESOLVED")
    with pytest.raises(ApiFailure) as error:
        actual.complete(CONTEXT, turn, plan, neutral(turn))
    assert error.value is spy.failure
    spy.failure = None
    spy.result = MessageResult.model_validate({
        **neutral(turn).model_dump(mode="json"), "state": "superseded", "current_revision": 9,
        "text": "This turn was superseded; no actions were applied.", "persistence": "saved",
    })
    assert actual.complete(CONTEXT, turn, plan, neutral(turn)) is spy.result
    # This checks delegation only; P14's actual no-effects proof belongs to its runtime tests.


def test_different_message_plan_or_preclaimed_success_never_reaches_completion() -> None:
    turn, spy = admission("Remember my budget"), CompletionSpy()
    actual = bridge(spy)
    plan = actual.prepare(CONTEXT, turn, required(turn), None)
    with pytest.raises(ApiFailure):
        actual.complete(CONTEXT, turn, replace(plan, message_id=str(uuid4())), neutral(turn))
    assert plan.preference is not None
    claimed = MessageResult.model_validate({
        **neutral(turn).model_dump(mode="json"), "actions": {"preferences": {
            "state": "rejected", "client_action_id": plan.preference.client_action_id,
            "code": "REVISION_CONFLICT",
        }},
    })
    with pytest.raises(ApiFailure):
        actual.complete(CONTEXT, turn, plan, claimed)
    assert spy.calls == []


def test_replayed_shortlist_current_state_is_not_relabelled_as_new_addition() -> None:
    turn, spy = admission("Add the selected car to my shortlist"), CompletionSpy()
    actual = bridge(spy, ShortlistSpy())
    intent = TurnIntent(operation="detail", deferred=["shortlist"], references=[
        ReferenceRequest(source="selected", quote="the selected car")
    ])
    plan = actual.prepare(CONTEXT, turn, required(turn, intent), ref("one"))
    assert plan.membership is not None
    action_id = plan.membership.command.client_action_id
    spy.result = MessageResult.model_validate({
        **neutral(turn).model_dump(mode="json"), "text": "Replayed action; this car is currently not saved.",
        "persistence": "saved", "actions": {"shortlist": {
            "state": "succeeded", "client_action_id": action_id, "result": {
                "ref": ref("one").model_dump(mode="json"), "client_action_id": action_id,
                "saved": False, "changed_at_apply": True, "replayed": True,
                "applied_revision": 18, "current_revision": 19, "reference_state": "current",
            },
        }},
    })
    assert actual.complete(CONTEXT, turn, plan, neutral(turn)) is spy.result


def test_confirm_preserves_typed_review_key_and_plain_yes_cannot_confirm() -> None:
    turn, spy = admission("yes"), CompletionSpy()
    actual = bridge(spy)
    with pytest.raises(ApiFailure):
        actual.confirm(CONTEXT, turn.session.session_id, turn.request)
    assert spy.calls == []
    payload = dict(draft_id=str(uuid4()), review_id=str(uuid4()), expected_draft_revision=3,
                   operation_key="k" * 43, rules_version="rules-1", store_generation=str(uuid4()),
                   confirmation="confirm_simulated_viewing")
    body = request(turn.session, "Confirm the reviewed viewing", explicit_confirmation=payload)
    spy.result = neutral(turn)
    assert actual.confirm(CONTEXT, turn.session.session_id, body) is spy.result
    assert spy.calls[0][2] == body and spy.calls[0][2] is not body
    assert spy.calls[0][3]["participant"] is actual.confirmation


def test_recall_calls_owned_service_for_all_keys_without_filtering_override_values() -> None:
    current = session()
    calls: list[tuple[Any, ...]] = []

    def recall(*args: Any, **kwargs: Any) -> PreferenceRecord:
        calls.append((*args, kwargs))
        return current.recalled_preferences

    prefs = SimpleNamespace(recall=recall, authorization=SimpleNamespace(
        identity=SimpleNamespace(now_text=lambda: "2026-09-24T00:00:00Z")
    ))
    actual = ActionBridge(cast(SessionService, CompletionSpy()), preferences=cast(PreferenceService, prefs),
                          shortlist=None, confirmation=None)
    assert "No current saved preferences" in actual.recall(CONTEXT, current)
    assert calls == [(CONTEXT, {"keys": ("budget", "makes", "use_cases", "requirements"),
                               "current_keys": ()})]


def test_partial_composition_can_present_owned_admission_memory() -> None:
    current = session()
    sessions = SimpleNamespace(authorization=SimpleNamespace(
        identity=SimpleNamespace(now_text=lambda: "2026-09-24T00:00:00Z")
    ))
    actual = ActionBridge(cast(SessionService, sessions), preferences=None,
                          shortlist=None, confirmation=cast(ConfirmationParticipant, object()))
    assert "No current saved preferences" in actual.recall(CONTEXT, current)
