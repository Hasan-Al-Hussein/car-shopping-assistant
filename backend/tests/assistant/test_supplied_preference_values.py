"""Source-only A8 amendment tests; require its unapplied patch and real P14 imports.

Quality's exact live-demo prompts are reproduced as source fixtures. Scripted passing
checks, when authorized, still cannot stand in for that actual HTTP/provider demo.
"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest

from app.api.schemas.memory import PreferenceRecord
from app.assistant.action_bridge import ActionClarification, requested_actions
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import TextPatch, TurnIntent
from app.assistant.interpretation import interpret
from app.assistant.recalled_values import is_recall_question

from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    adapter,
    budget,
    ref,
    request,
    session,
    state,
)
from .test_action_bridge import CompletionSpy, admission, bridge
from .test_action_routing import ActionPortSpy, run
from .test_recalled_values import saved_record

VALUES = ["quiet cabin", "space for a folding bicycle"]
SAVE_TEXT = (
    "Please explicitly remember these two soft requirements for future conversations: "
    '"quiet cabin" and "space for a folding bicycle". Save these preferences now.'
)
RECALL_TEXT = (
    "What requirements did I ask you to remember in my earlier conversation? "
    "Tell me the saved values."
)


def proposal(**changes: Any) -> TurnIntent:
    return TurnIntent.model_validate(
        {
            "operation": "smalltalk",
            "scope": "durable",
            "deferred": ["preferences"],
            "patches": [
                TextPatch(
                    kind="text",
                    field="soft_preferences",
                    operation="add",
                    values=VALUES,
                    quote='"quiet cabin" and "space for a folding bicycle"',
                ).model_dump()
            ],
            **changes,
        }
    )


def test_exact_demo_saves_new_values_and_not_the_unrelated_current_criteria() -> None:
    turn = admission(SAVE_TEXT)
    before = turn.session.criteria.model_dump(mode="json")
    requested = requested_actions(turn, proposal())
    assert requested is not None
    spy = CompletionSpy()
    actual = bridge(spy)
    plan = actual.prepare(CONTEXT, turn, requested, None)
    assert plan.preference is not None
    assert plan.preference.changes[0].model_dump(mode="json") == {
        "key": "requirements",
        "value": VALUES,
        "strength": "soft",
    }
    assert len(plan.preference.changes) == 1
    assert plan.preference.expected_revision == 4
    assert plan.message_id == turn.message_id
    assert turn.session.criteria.model_dump(mode="json") == before
    assert requested.supplied_requirements == tuple(VALUES)
    # Same input builds the same original per-domain action identity, with no new action on replay.
    again = actual.prepare(CONTEXT, turn, requested, None)
    assert again.preference == plan.preference and spy.calls == []


@pytest.mark.parametrize(
    "changes",
    [
        {"patches": []},
        {
            "patches": [
                TextPatch(
                    kind="text",
                    field="soft_preferences",
                    operation="add",
                    values=["quiet cabin"],
                    quote='"quiet cabin"',
                ).model_dump()
            ]
        },
        {
            "patches": [
                TextPatch(
                    kind="text",
                    field="soft_preferences",
                    operation="add",
                    values=VALUES + ["low mileage"],
                    quote=SAVE_TEXT,
                ).model_dump()
            ]
        },
        {
            "patches": [
                TextPatch(
                    kind="text",
                    field="soft_preferences",
                    operation="clear",
                    values=[],
                    quote=SAVE_TEXT,
                ).model_dump()
            ]
        },
        {"scope": "hypothetical"},
        {"scope": "unclear"},
        {"deferred": ["preferences", "shortlist"]},
        {"problem": "meaning"},
    ],
)
def test_missing_extra_or_ambiguous_model_values_never_authorize_partial_save(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(ActionClarification):
        requested_actions(admission(SAVE_TEXT), proposal(**changes))


@pytest.mark.parametrize(
    "text",
    [
        "Do not " + SAVE_TEXT,
        SAVE_TEXT + " Also book a viewing.",
        SAVE_TEXT.replace("two", "three"),
        SAVE_TEXT.replace("soft requirements", "hard requirements"),
    ],
)
def test_full_buyer_command_must_agree_with_count_scope_and_complete_effect(text: str) -> None:
    with pytest.raises(ActionClarification):
        requested_actions(admission(text), proposal())


def test_other_new_values_work_without_demo_specific_content() -> None:
    text = 'Remember my soft preferences: "easy parking" and "comfortable front seats".'
    intent = TurnIntent(
        operation="smalltalk",
        scope="durable",
        deferred=["preferences"],
        patches=[
            TextPatch(
                kind="text",
                field="soft_preferences",
                operation="replace",
                values=["easy parking", "comfortable front seats"],
                quote=text,
            )
        ],
    )
    requested = requested_actions(admission(text), intent)
    assert requested is not None
    assert requested.supplied_requirements == ("easy parking", "comfortable front seats")


@pytest.mark.parametrize("strength,correcting", [("hard", False), ("soft", False), ("hard", True)])
def test_new_values_do_not_silently_replace_existing_saved_requirements(
    strength: str,
    correcting: bool,
) -> None:
    turn = admission(SAVE_TEXT.replace("remember", "correct") if correcting else SAVE_TEXT)
    payload = saved_record().model_dump(mode="json")
    payload["entries"] = [payload["entries"][0]]
    payload["entries"][0]["preference"] = {
        "key": "requirements",
        "value": ["seven seats"],
        "strength": strength,
    }
    turn.session.recalled_preferences = PreferenceRecord.model_validate(payload)
    with pytest.raises(ActionClarification):
        requested_actions(turn, proposal())


def test_explicit_correction_can_replace_a_saved_soft_list() -> None:
    text = 'Correct my saved soft requirements: "quiet cabin" and "space for a folding bicycle".'
    turn = admission(text)
    payload = saved_record().model_dump(mode="json")
    payload["entries"] = [payload["entries"][0]]
    payload["entries"][0]["preference"] = {
        "key": "requirements",
        "value": ["easy parking"],
        "strength": "soft",
    }
    turn.session.recalled_preferences = PreferenceRecord.model_validate(payload)
    requested = requested_actions(turn, proposal())
    assert requested is not None and requested.preference_intent == "correct"
    assert requested.supplied_requirements == tuple(VALUES)


def test_identical_saved_soft_values_are_not_silently_merged_or_changed() -> None:
    turn = admission(SAVE_TEXT)
    payload = saved_record().model_dump(mode="json")
    payload["entries"] = [payload["entries"][0]]
    payload["entries"][0]["preference"] = {
        "key": "requirements",
        "value": VALUES,
        "strength": "soft",
    }
    turn.session.recalled_preferences = PreferenceRecord.model_validate(payload)
    requested = requested_actions(turn, proposal())
    assert requested is not None and requested.supplied_requirements == tuple(VALUES)


def test_exact_demo_coordinator_routes_supplied_values_without_inventory_or_search_edits() -> None:
    async def exercise() -> None:
        sessions = FakeSessions(
            session(
                selected_ref=ref("selected"),
                criteria={
                    "filters": {
                        "makes": ["Honda"],
                        "budget": {"maximum": 6_000_000, "currency": "AED"},
                    },
                    "soft_preferences": ["family use"],
                },
            )
        )
        before = sessions.current.criteria.model_dump(mode="json")
        inventory, actions = FakeInventory(), ActionPortSpy(sessions)
        model, _ = adapter(proposal())
        result = await run(
            ReadCoordinator(sessions, model, inventory, actions=actions),
            sessions,
            request(sessions.current, SAVE_TEXT),
        )
        assert result.state == "answered" and actions.calls == ["prepare", "complete"]
        assert actions.prepared[0][1].supplied_requirements == tuple(VALUES)
        assert actions.prepared[0][0].request.text == SAVE_TEXT
        assert sessions.current.criteria.model_dump(mode="json") == before
        assert sessions.current.selected_ref == ref("selected") and inventory.calls == []

    asyncio.run(exercise())


@pytest.mark.parametrize("matched", [False, True])
def test_new_values_cannot_skip_or_modify_unresolved_hard_question(matched: bool) -> None:
    async def exercise() -> None:
        pending = {
            "kind": "clarification",
            "intent_id": str(uuid4()),
            "created_revision": 1,
            "purpose": "search_criteria",
            "targets": ["budget"],
            "question": "Which currency is your budget?",
        }
        sessions = FakeSessions(session(revision=2, pending_intent=pending))
        actions = ActionPortSpy(sessions)
        model, _ = adapter(proposal())
        changes: dict[str, Any] = {}
        if matched:
            changes["clarification_reply"] = {
                "intent_id": pending["intent_id"],
                "created_revision": 1,
            }
        before = sessions.current.criteria.model_dump(mode="json")
        result = await run(
            ReadCoordinator(sessions, model, actions=actions),
            sessions,
            request(sessions.current, SAVE_TEXT, **changes),
        )
        assert result.text == pending["question"] and actions.calls == []
        assert result.pending_intent.model_dump(mode="json") == pending
        assert sessions.current.criteria.model_dump(mode="json") == before

    asyncio.run(exercise())


def test_exact_demo_recall_is_read_only_and_surfaces_both_actual_values() -> None:
    async def exercise() -> None:
        payload = saved_record().model_dump(mode="json")
        payload["entries"] = [payload["entries"][0]]
        payload["entries"][0]["preference"] = {
            "key": "requirements",
            "value": VALUES,
            "strength": "soft",
        }
        sessions = FakeSessions(session(recalled_preferences=payload))
        actions = ActionPortSpy(sessions)
        model, _ = adapter(TurnIntent(operation="return"))
        before = sessions.current.recalled_preferences.model_dump(mode="json")
        result = await run(
            ReadCoordinator(sessions, model, actions=actions),
            sessions,
            request(sessions.current, RECALL_TEXT),
        )
        assert is_recall_question(RECALL_TEXT)
        assert not is_recall_question(RECALL_TEXT + " Save new values now.")
        assert all(value in result.text for value in VALUES)
        assert actions.calls == ["recall"]
        assert sessions.current.recalled_preferences.model_dump(mode="json") == before

    asyncio.run(exercise())


def test_interpretation_packet_fits_with_both_budget_and_retained_question() -> None:
    async def exercise() -> None:
        pending = {
            "kind": "clarification",
            "intent_id": str(uuid4()),
            "created_revision": 0,
            "purpose": "search_criteria",
            "targets": ["makes"],
            "question": "Which makes?",
        }
        current = session(
            pending_intent=pending,
            criteria={"filters": {"budget": {"maximum": 6_000_000, "currency": "AED"}}},
        )
        model, transport = adapter(proposal())
        result = await interpret(model, request(current, SAVE_TEXT), current, state(), budget(), ())
        assert result.state == "available" and len(transport.requests) == 1
        packet = json.loads(transport.requests[0].contents)
        summaries = packet["history_summaries"]
        assert len(summaries) == 4 and all(len(item) <= 400 for item in summaries)
        assert "soft_preferences TextPatch" in summaries[0]
        assert "return/session" in summaries[1]
        assert "AED" in summaries[2] and pending["question"] in summaries[3]
        assert "search_criteria" in summaries[3]

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "text,values",
    [
        (
            "Please remember Nissan as a soft make preference for future conversations, "
            "not a required filter.",
            ["Nissan"],
        ),
        ("Save Mazda as a preference for next time.", ["Mazda"]),
        (
            "Remember that I prefer easy parking and comfortable front seats.",
            ["easy parking", "comfortable front seats"],
        ),
        ("Remember that I prefer cars without sunroofs.", ["cars without sunroofs"]),
        ("Remember that I prefer not to have a sunroof.", ["not to have a sunroof"]),
        (
            "Remember that I prefer cars that don't have sunroofs.",
            ["cars that don't have sunroofs"],
        ),
    ],
)
def test_natural_explicit_preference_save_uses_current_buyer_values(text, values) -> None:
    intent = TurnIntent(
        operation="question",
        scope="session",
        deferred=["preferences"],
        patches=[
            TextPatch(
                kind="text", field="soft_preferences", operation="add", values=values, quote=text
            ),
        ],
    )
    turn = admission(text)
    before = turn.session.criteria.model_dump(mode="json")
    requested = requested_actions(turn, intent)
    assert requested is not None and requested.supplied_requirements == tuple(values)
    plan = bridge(CompletionSpy()).prepare(CONTEXT, turn, requested, None)
    assert plan.preference is not None
    assert plan.preference.changes[0].value == values
    assert plan.preference.changes[0].strength == "soft"
    assert turn.session.criteria.model_dump(mode="json") == before


@pytest.mark.parametrize(
    "text",
    [
        "I prefer Nissan.",
        "Do not remember Nissan as a soft preference.",
        "Could I remember Nissan as a soft preference?",
        "Remember Nissan as a soft preference if I decide later.",
        "Remember Nissan as a soft preference, but do not save it.",
        "Remember Nissan as a soft preference without saving it.",
        "Remember Nissan as a soft preference, but not to store it.",
        "Remember Nissan as a soft preference, but never permanently save it.",
        "Remember Nissan as a soft preference. Also book a viewing.",
        "Remember what I said about Nissan preferences earlier?",
        "Remember Nissan as a required filter.",
    ],
)
def test_natural_preference_path_does_not_turn_mentions_or_qualified_requests_into_writes(
    text,
) -> None:
    intent = TurnIntent(
        operation="question",
        deferred=["preferences"],
        patches=[
            TextPatch(
                kind="text",
                field="soft_preferences",
                operation="add",
                values=["Nissan"],
                quote=text,
            ),
        ],
    )
    with pytest.raises(ActionClarification):
        requested_actions(admission(text), intent)


@pytest.mark.parametrize(
    "values,quote",
    [
        (["Toyota"], "Remember Nissan as a soft preference."),
        (["Nissan"], "Earlier I preferred Nissan."),
        (["van"], "Remember caravan comfort as a soft preference."),
    ],
)
def test_natural_preference_values_need_exact_current_message_spans(values, quote) -> None:
    text = "Remember Nissan as a soft preference."
    intent = TurnIntent(
        operation="question",
        deferred=["preferences"],
        patches=[
            TextPatch(
                kind="text", field="soft_preferences", operation="add", values=values, quote=quote
            ),
        ],
    )
    with pytest.raises(ActionClarification):
        requested_actions(admission(text), intent)
