"""Warranty follow-ups through the coordinator; scripted ports, no live-provider proof."""

import asyncio
from uuid import uuid4

import pytest

from app.api.schemas.inventory import ListingDetail
from app.api.schemas.sessions import MessageResult
from app.assistant.coordinator import ReadCoordinator
from app.assistant.intent import ReferenceRequest, TurnIntent

from .a4_cases import UNTRUSTED, detail
from .conversation_fakes import FakeInventory, FakeSessions, adapter, request, session
from .test_coordinator import run

QUESTIONS = ("Does it have a warranty?", "Is there a warranty on it?")
FACT_CASES = (
    ("3", "Warranty:", "68,000 km"),
    ("4", "Warranty: not stated.", "56,000 km"),
)


def assert_grounded_warranty(
    result: MessageResult, item: ListingDetail, expected_text: str
) -> None:
    assert result.state == "answered" and result.persistence == "saved"
    assert result.handoff_summary is not None
    assert result.handoff_summary.selected_ref == item.listing.ref
    assert result.handoff_summary.listing == item
    assert expected_text in result.text
    assert UNTRUSTED not in result.text
    assert result.operation is None and result.actions.lead.state == "not_requested"
    assert len(result.evidence) == 1
    assert result.evidence[0].ref == item.listing.ref
    assert "warranty" in result.evidence[0].attributes
    if item.listing.ref.source_id == "3":
        assert (
            "GCC warranty stated; provider, term and current validity not established"
            in result.text
        )
        assert "Current warranty validity is not independently verified." in result.text
        assert "(seller claim)" in result.text
    else:
        assert "Warranty: not stated." in result.text
        assert "Current warranty validity is not independently verified." not in result.text


@pytest.mark.parametrize("text", QUESTIONS)
@pytest.mark.parametrize("source_id,warranty_text,mileage_text", FACT_CASES)
def test_selected_car_warranty_question_preserves_evidence_and_original_wording(
    text: str, source_id: str, warranty_text: str, mileage_text: str
) -> None:
    async def exercise() -> None:
        item = detail(source_id)
        sessions = FakeSessions(session(selected_ref=item.listing.ref.model_dump(mode="json")))
        inventory = FakeInventory(item)
        model, transport = adapter(
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="selected", quote="it")],
            )
        )
        value = request(sessions.current, text)
        assert value.selected_ref is None and value.presentation_id is None
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert_grounded_warranty(result, item, warranty_text)
        assert mileage_text in result.text
        assert sessions.current.selected_ref == item.listing.ref
        assert sessions.turns[value.client_message_id].admission.request == value
        assert inventory.calls == ["detail"] and len(transport.requests) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("text", QUESTIONS)
@pytest.mark.parametrize("source_id,warranty_text,mileage_text", FACT_CASES)
def test_ordinal_mileage_then_warranty_uses_the_same_original_car(
    text: str, source_id: str, warranty_text: str, mileage_text: str
) -> None:
    async def exercise() -> None:
        item, other = detail(source_id), detail("27")
        page = str(uuid4())
        sessions = FakeSessions(session(active_presentation_id=page))
        sessions.presentations[page] = (item.listing.ref, other.listing.ref)
        inventory = FakeInventory(other, item)  # Deliberately differs from the original page.
        model, transport = adapter(
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="ordinal", position=0, quote="first car")],
            ),
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="selected", quote="it")],
            ),
        )
        coordinator = ReadCoordinator(sessions, model, inventory)
        first_request = request(sessions.current, "What is the mileage of the first car?")
        assert sessions.current.selected_ref is None and first_request.selected_ref is None
        first = await run(coordinator, sessions, first_request)
        assert first.state == "answered" and mileage_text in first.text
        assert first.handoff_summary is not None
        assert first.handoff_summary.selected_ref == item.listing.ref
        assert sessions.current.selected_ref == item.listing.ref
        second_request = request(sessions.current, text)
        assert second_request.selected_ref is None and second_request.presentation_id is None
        second = await run(coordinator, sessions, second_request)
        assert_grounded_warranty(second, item, warranty_text)
        assert sessions.current.selected_ref == item.listing.ref
        assert sessions.current.active_presentation_id == page
        assert inventory.calls == ["detail", "detail"]
        assert sessions.reads == ["ordinal", "original_refs"]
        assert len(transport.requests) == 2
        for value in (first_request, second_request):
            assert sessions.turns[value.client_message_id].admission.request == value

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "text,quote",
    [
        ("Does it have a warranty on the second car?", "it"),
        ("Is there a warranty on it or Honda?", "it"),
        ("Is there a warranty on it or Model 3?", "it"),
        ("Does it have a warranty on the red car?", "it"),
        ("Does it have a warranty on هوندا?", "it"),
        ("Is there a warranty on this one or that one?", "this one"),
        ("Does it have a warranty or does that car have one?", "it"),
        ("Is there a warranty on that car or it?", "that car"),
        ("Is there a warranty on it or this car?", "it"),
    ],
)
def test_warranty_vocabulary_does_not_hide_an_extra_car_reference(
    text: str, quote: str
) -> None:
    async def exercise() -> None:
        item = detail("3")
        sessions = FakeSessions(session(selected_ref=item.listing.ref.model_dump(mode="json")))
        inventory = FakeInventory(item)
        model, _ = adapter(
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="selected", quote=quote)],
            )
        )
        value = request(sessions.current, text)
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert result.state == "clarification" and result.handoff_summary is None
        assert result.evidence == [] and inventory.calls == []
        assert sessions.current.selected_ref == item.listing.ref
        assert sessions.completions == [(None, None)]
        assert sessions.turns[value.client_message_id].admission.request == value

    asyncio.run(exercise())


@pytest.mark.parametrize("text", QUESTIONS)
def test_warranty_pronoun_without_a_selected_car_does_not_guess(text: str) -> None:
    async def exercise() -> None:
        sessions, inventory = FakeSessions(), FakeInventory(detail("3"), detail("4"))
        model, _ = adapter(
            TurnIntent(
                operation="detail",
                references=[ReferenceRequest(source="selected", quote="it")],
            )
        )
        value = request(sessions.current, text)
        result = await run(ReadCoordinator(sessions, model, inventory), sessions, value)
        assert result.state == "clarification" and result.handoff_summary is None
        assert result.evidence == [] and inventory.calls == []
        assert sessions.current.selected_ref is None
        assert sessions.completions == [(None, None)]
        assert sessions.turns[value.client_message_id].admission.request == value

    asyncio.run(exercise())
