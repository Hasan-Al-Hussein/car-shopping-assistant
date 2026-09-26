"""Staged A9 pure-field cases; NOT_RUN and no Store/provider/integration claim."""

from datetime import UTC, datetime

import pytest

from app.assistant.collection_fields import (
    CollectionFieldError,
    appointment_selection,
    needs_local_private_reply,
    viewing_date,
    viewing_time,
)
from app.core.config import DemoPolicy
from app.viewings.scheduling import ViewingRules

NOW = datetime(2026, 9, 24, 21, 15, tzinfo=UTC)  # Already 25 September in Dubai.


@pytest.fixture
def rules() -> ViewingRules:
    return ViewingRules(DemoPolicy())


@pytest.mark.parametrize("text,expected", [
    ("today", "2026-09-25"), ("tomorrow", "2026-09-26"),
    ("2026-10-03", "2026-10-03"), ("3 October 2026", "2026-10-03"),
    ("October 3, 2026", "2026-10-03"), ("January 1 2027", "2027-01-01"),
])
def test_date_uses_existing_rules_and_one_dubai_source_instant(
    rules: ViewingRules, text: str, expected: str,
) -> None:
    assert viewing_date(text, rules=rules, now=NOW) == expected


@pytest.mark.parametrize("text", [
    "Friday", "next Friday", "03/10/2026", "October 3", "tomorrow if available",
    "2026-02-29", "31 February 2026", "2026-10-03 UTC", "2026-10-03 or 2026-10-04",
])
def test_ambiguous_impossible_or_qualified_dates_are_not_normalized_away(
    rules: ViewingRules, text: str,
) -> None:
    with pytest.raises(CollectionFieldError, match="DATE_CLARIFICATION_REQUIRED"):
        viewing_date(text, rules=rules, now=NOW)


def test_naive_clock_cannot_anchor_relative_date(rules: ViewingRules) -> None:
    with pytest.raises(CollectionFieldError, match="DATE_CLARIFICATION_REQUIRED"):
        viewing_date("tomorrow", rules=rules, now=NOW.replace(tzinfo=None))


@pytest.mark.parametrize("text,expected", [
    ("14:30", "14:30"), ("08:00", "08:00"), ("2:30 pm", "14:30"),
    ("12am", "00:00"), ("12 pm", "12:00"), ("9 AM", "09:00"),
])
def test_explicit_meridiem_conversion(text: str, expected: str) -> None:
    assert viewing_time(text) == expected


@pytest.mark.parametrize("text", [
    "12", "2:30", "9", "24:00", "14:60", "13pm", "2pm UTC", "2pm or 3pm",
    "not 14:30", "14:30 if it has warranty", "2:30 p.m.",
])
def test_time_ambiguity_and_residual_conditions_require_clarification(text: str) -> None:
    with pytest.raises(CollectionFieldError, match="TIME_CLARIFICATION_REQUIRED"):
        viewing_time(text)


def test_partial_date_is_fixed_before_later_time_reply(rules: ViewingRules) -> None:
    concrete = viewing_date("tomorrow", rules=rules, now=NOW)
    later = datetime(2026, 9, 25, 22, tzinfo=UTC)
    proposal = appointment_selection(concrete, viewing_time("2:30 pm"), rules=rules, now=later)
    assert proposal.model_dump() == {
        "starts_at_utc": "2026-09-26T10:30:00Z",
        "timezone": "Asia/Dubai", "appointment_type": "viewing",
    }


def test_relative_or_partial_fields_cannot_enter_appointment(rules: ViewingRules) -> None:
    with pytest.raises(CollectionFieldError, match="CONCRETE_DATE_REQUIRED"):
        appointment_selection("tomorrow", "14:30", rules=rules, now=NOW)
    with pytest.raises(CollectionFieldError, match="CONCRETE_TIME_REQUIRED"):
        appointment_selection("2026-10-03", "2pm", rules=rules, now=NOW)


def test_field_conversion_does_not_pretend_to_validate_capacity_or_open_hours(
    rules: ViewingRules,
) -> None:
    # Midnight can be proposed syntactically; the shared domain service must reject it.
    value = appointment_selection("2026-10-03", "00:00", rules=rules, now=NOW)
    assert value.starts_at_utc == "2026-10-02T20:00:00Z"


@pytest.mark.parametrize("text", [
    "My email is buyer@example.test", "buyer@example.test", "+971 50 123 4567",
    "My email is buyer at example dot test", "Phone: zero five zero one two three",
    "My phone is zero five zero one two three four five six seven",
    "My phone is one two three four five six seven.",
    "Please contact me at my office", "Here is my passport number ABC",
])
def test_private_inputs_require_local_handling_before_any_provider_packet(text: str) -> None:
    assert needs_local_private_reply(text)


def test_registered_private_value_also_stays_local() -> None:
    assert needs_local_private_reply("Use personal-contact-token", ("personal-contact-token",))


@pytest.mark.parametrize("text", [
    "Viewing date: 2026-10-03", "Viewing time: 14:30", "My cash budget is AED 40000 to 50000",
    "My cash budget is AED 75000", "My requirements are a quiet cabin and easy parking",
    "Prepare a viewing for the first Honda", "Save this local enquiry",
    "My phone must connect by Bluetooth", "Our mobile devices need USB charging",
    "My phone is compatible with Android Auto", "I need phone connectivity",
])
def test_dates_cash_amounts_and_noncontact_collection_are_not_contact_capture(text: str) -> None:
    assert not needs_local_private_reply(text)
