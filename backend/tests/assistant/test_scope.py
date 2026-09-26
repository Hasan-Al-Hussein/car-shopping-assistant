"""Scope composition tests; these do not assert natural-language intent accuracy."""

import pytest

from app.assistant.answer_assembly import assemble_listing
from app.assistant.grounding import GroundingError
from app.assistant.scope import compose_scope
from tests.assistant.a4_cases import UNTRUSTED, detail


def test_greeting_and_help_are_bounded_product_text() -> None:
    answer = compose_scope(topics=("greeting", "help"))
    assert answer.text.startswith("Hello.")
    assert "compare up to three listings" in answer.text
    assert answer.claims == () and answer.evidence == ()
    assert answer.handoff_summary is None


@pytest.mark.parametrize("unsupported", ["unrelated", "competitor", "unverified_vehicle_claim"])
def test_mixed_request_keeps_supported_car_facts(unsupported: str) -> None:
    item = detail()
    factual = assemble_listing(item, expected_ref=item.listing.ref)
    combined = compose_scope(factual, topics=(unsupported,))
    assert combined.text.startswith(factual.text + "\n")
    assert "AED 119,750.00 cash" in combined.text
    assert combined.claims == factual.claims and combined.evidence == factual.evidence
    assert "negative" not in combined.text and UNTRUSTED not in combined.text


def test_competitor_policy_is_respectful_and_has_no_invented_comparison() -> None:
    answer = compose_scope(topics=("competitor",))
    assert "can't recommend or assess competing shopping services" in answer.text
    assert "supplied inventory" in answer.text
    assert answer.claims == ()
    assert not any(word in answer.text for word in ("worse", "safer", "cheaper", "unreliable"))


@pytest.mark.parametrize("topic", [UNTRUSTED, "engine_horsepower", "reliability", "دبي"])
def test_arbitrary_topics_cannot_inject_prose_or_model_specific_knowledge(topic: str) -> None:
    answer = compose_scope(topics=(topic,))
    assert topic not in answer.text
    assert "unrelated part" in answer.text
    assert answer.claims == () and answer.evidence == ()


@pytest.mark.parametrize(
    ("topic", "required"),
    [
        ("cash_price", "monthly finance instalment is not the total cash price"),
        ("mileage", "warranty mileage limit or service interval is a different claim"),
        ("evidence", "not an independently verified vehicle fact"),
        ("warranty", "does not independently establish current coverage"),
        ("historical", "does not establish current stock"),
        ("simulated_viewing", "not a booking confirmation or a real dealer appointment"),
    ],
)
def test_vocabulary_is_contract_bounded(topic: str, required: str) -> None:
    answer = compose_scope(topics=(topic,))
    assert required in answer.text
    assert answer.claims == ()


def test_unknown_topic_does_not_erase_supported_answer() -> None:
    item = detail("22")
    factual = assemble_listing(item, expected_ref=item.listing.ref, attributes=("warranty",))
    combined = compose_scope(factual, topics=(UNTRUSTED,))
    assert combined.text.startswith(factual.text)
    assert combined.claims == factual.claims
    assert UNTRUSTED not in combined.text


def test_scope_deduplicates_and_bounds_requested_fragments() -> None:
    assert compose_scope(topics=("help", "help")).text == compose_scope().text
    with pytest.raises(GroundingError, match="^SCOPE_LIMIT$"):
        compose_scope(topics=("help",) * 13)
