"""Actual resolver/coordinator regressions; fake ports do not prove live inference or ownership."""

import asyncio
from typing import Literal
from uuid import uuid4

import pytest

from app.api.schemas.common import InventoryRef
from app.assistant.bounded_calls import CallGate
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.assistant.references import AmbiguousReference, ReferenceResolver
from app.identity.authorization import AuthorizedOwnerContext

from .a4_cases import detail
from .conversation_fakes import (
    CONTEXT,
    FakeInventory,
    FakeSessions,
    adapter,
    budget,
    request,
    session,
)
from .test_coordinator import run
from .test_warranty_references import assert_grounded_warranty

DEMO_TEXT = "What is the mileage on the first car you just showed me?"


class RecordingSessions(FakeSessions):
    def __init__(self) -> None:
        super().__init__(session(active_presentation_id=str(uuid4())))
        self.ordinal_arguments: list[tuple[AuthorizedOwnerContext, str, str, int]] = []

    async def ordinal(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str, ordinal: int
    ) -> InventoryRef:
        self.ordinal_arguments.append((context, session_id, presentation_id, ordinal))
        return await super().ordinal(context, session_id, presentation_id, ordinal)


@pytest.mark.parametrize("suffix", ["you just showed me", "you showed me"])
@pytest.mark.parametrize("quote_style", ["full", "car", "ordinal"])
def test_natural_mileage_then_warranty_retains_the_original_first_car(
    suffix: str, quote_style: str
) -> None:
    async def exercise() -> None:
        item, other = detail("3"), detail("27")
        sessions = RecordingSessions()
        page = sessions.current.active_presentation_id
        assert page is not None
        sessions.presentations[page] = (item.listing.ref, other.listing.ref)
        inventory = FakeInventory(other, item)
        quotes = {"full": f"first car {suffix}", "car": "first car", "ordinal": "first"}
        model, transport = adapter(
            TurnIntent(
                operation="detail",
                references=[
                    ReferenceRequest(source="ordinal", position=0, quote=quotes[quote_style])
                ],
            ),
            TurnIntent(
                operation="detail", references=[ReferenceRequest(source="selected", quote="it")]
            ),
        )
        coordinator = ReadCoordinator(sessions, model, inventory)
        text = DEMO_TEXT if suffix == "you just showed me" else DEMO_TEXT.replace("just ", "")
        first_request = request(sessions.current, text)
        assert first_request.selected_ref is None and first_request.presentation_id is None
        first = await run(coordinator, sessions, first_request)
        assert first.state == "answered" and "68,000 km" in first.text
        assert first.handoff_summary is not None
        assert first.handoff_summary.selected_ref == item.listing.ref
        assert sessions.ordinal_arguments == [(CONTEXT, sessions.current.session_id, page, 0)]
        assert first.evidence and all(item_.ref == item.listing.ref for item_ in first.evidence)
        second_request = request(sessions.current, "Is there a warranty on it?")
        second = await run(coordinator, sessions, second_request)
        assert_grounded_warranty(second, item, "Warranty:")
        assert sessions.current.selected_ref == item.listing.ref
        assert sessions.current.active_presentation_id == page
        assert inventory.calls == ["detail", "detail"]
        assert sessions.reads == ["ordinal", "original_refs"]
        assert len(transport.requests) == 2
        for value in (first_request, second_request):
            assert sessions.turns[value.client_message_id].admission.request == value

    asyncio.run(exercise())


@pytest.mark.parametrize("page_role", ["active", "request"])
@pytest.mark.parametrize(
    "phrase,quote",
    [
        ("second car", "second"),
        ("second car", "second car you showed me"),
        ("2nd car", "2nd car you showed me"),
        ("number 2", "number 2 you showed me"),
        ("#2", "#2 you showed me"),
    ],
)
def test_contextual_ordinal_keeps_owner_session_page_and_position_arguments(
    page_role: Literal["active", "request"], phrase: str, quote: str
) -> None:
    async def exercise() -> None:
        item, other = detail("3"), detail("27")
        sessions = RecordingSessions()
        active = sessions.current.active_presentation_id
        assert active is not None
        explicit = str(uuid4())
        sessions.presentations[active] = (item.listing.ref, other.listing.ref)
        sessions.presentations[explicit] = (other.listing.ref, item.listing.ref)
        inventory = FakeInventory(other, item)
        text = f"Show me the {phrase} you showed me"
        value = request(sessions.current, text, presentation_id=explicit)
        cited = ReferenceRequest(source="ordinal", page=page_role, position=1, quote=quote)
        resolver = ReferenceResolver(
            sessions, inventory, CallGate(), CONTEXT, sessions.current, value, budget(), [cited]
        )
        resolved = await resolver.resolve(cited)
        page = active if page_role == "active" else explicit
        assert resolved == sessions.presentations[page][1]
        assert sessions.ordinal_arguments == [(CONTEXT, sessions.current.session_id, page, 1)]
        assert inventory.calls == [] and sessions.reads == ["ordinal"]
        assert value.text == text

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "text,quote",
    [
        ("Show me the first Honda car you just showed me", "first"),
        ("Show me the first Honda car you just showed me", "first Honda car you just showed me"),
        ("Show me the first Model 3 car you showed me", "first"),
        ("Show me the first car 3 you showed me", "first"),
        ("Show me the first car 3 you showed me", "first car 3 you showed me"),
        ("Show me the first car number 3 you showed me", "first"),
        ("Show me the first car number 3 you showed me", "first car number 3 you showed me"),
        ("Show me the first car you showed me or number 3", "first"),
        ("Show me the first red car you showed me", "first"),
        ("Show me the first red car you showed me", "first red car you showed me"),
        ("Show me the first هوندا car you showed me", "first"),
        ("Show me the first هوندا car you showed me", "first هوندا car you showed me"),
        ("Show me the first car you showed me or the second", "first"),
        ("Show me the first or second car you showed me", "first or second car you showed me"),
        ("Show me the first car you showed me yesterday", "first"),
        ("Show me the first car you showed me on the previous page", "first car you showed me"),
        ("Show me the first car you just showed me or the car you showed me", "first"),
        ("Show me the first car you showed me you showed me", "first car you showed me"),
        (
            "Show me the first car you showed me you showed me",
            "first car you showed me you showed me",
        ),
        ("You showed me cars; show me the first car", "first car"),
        ("Show me the first car you never showed me", "first"),
        ("Show me the first car you showed me instead of the second", "first"),
    ],
)
def test_context_phrase_cannot_hide_omitted_qualifiers_or_ambiguous_context(
    text: str, quote: str
) -> None:
    async def exercise() -> None:
        item, other = detail("3"), detail("27")
        sessions = RecordingSessions()
        page = sessions.current.active_presentation_id
        assert page is not None
        sessions.presentations[page] = (item.listing.ref, other.listing.ref)
        inventory = FakeInventory(other, item)
        model, _ = adapter(
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="ordinal", position=0, quote=quote)],
            )
        )
        value = request(sessions.current, text)
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert result.state == "clarification" and result.handoff_summary is None
        assert result.evidence == [] and inventory.calls == []
        assert sessions.reads == [] and sessions.ordinal_arguments == []
        assert sessions.current.selected_ref is None
        assert sessions.current.active_presentation_id == page
        assert sessions.completions == [(None, None)]
        assert sessions.turns[value.client_message_id].admission.request == value

    asyncio.run(exercise())


@pytest.mark.parametrize("page_role", ["active", "request"])
def test_context_phrase_does_not_supply_a_missing_presentation(
    page_role: Literal["active", "request"],
) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory(detail("3"))
        value = request(sessions.current, DEMO_TEXT)
        cited = ReferenceRequest(
            source="ordinal", page=page_role, position=0, quote="first car you just showed me"
        )
        resolver = ReferenceResolver(
            sessions, inventory, CallGate(), CONTEXT, sessions.current, value, budget(), [cited]
        )
        with pytest.raises(AmbiguousReference):
            await resolver.resolve(cited)
        assert sessions.reads == [] and inventory.calls == []

    asyncio.run(exercise())
