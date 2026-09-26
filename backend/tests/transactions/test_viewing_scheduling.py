"""Controlled server-clock calendar boundaries; no store, capacity or user clock."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import VIEWING_VENUE, DemoPolicy
from app.viewings.scheduling import SchedulingError, ViewingRules
from tests.transactions.viewing_fixtures import NOW


@pytest.fixture
def rules() -> ViewingRules:
    return ViewingRules(DemoPolicy())


def test_policy_is_adopted_version_with_optional_contacts_and_simulated_venue(
    rules: ViewingRules,
) -> None:
    assert rules.version == "DEMO-POLICY-1:viewing-calendar-1"
    assert rules.policy.capacity == 1
    assert rules.policy.contact_required is False
    assert rules.policy.booking_mode == "simulated"
    assert rules.venue_label == VIEWING_VENUE


@pytest.mark.parametrize(
    "change", [{"slot_minutes": 60}, {"version": "DEMO-POLICY-2"}, {"open_weekdays": (0,)}]
)
def test_unadopted_policy_or_validation_bypass_cannot_reuse_rules(
    change: dict[str, object],
) -> None:
    with pytest.raises(SchedulingError, match="RULES_UNAVAILABLE"):
        ViewingRules(DemoPolicy().model_copy(update=change))


def test_missing_policy_is_named_unavailable() -> None:
    with pytest.raises(SchedulingError, match="RULES_UNAVAILABLE"):
        ViewingRules(None)


@pytest.mark.parametrize(
    "date_text",
    ["04/05", "31 April", "2026-04-31", "09-21", "20260921", "next Saturday", "2026-W39-1"],
)
def test_ambiguous_or_impossible_dates_need_clarification(
    rules: ViewingRules, date_text: str
) -> None:
    with pytest.raises(SchedulingError):
        rules.resolve_local_start(date_text, "08:00", now=NOW)


@pytest.mark.parametrize(
    "time_text", ["7", "7:00", "24:00", "08:60", "08:00Z", "evening", "08:00:00"]
)
def test_inexact_or_impossible_local_times_are_rejected(
    rules: ViewingRules, time_text: str
) -> None:
    with pytest.raises(SchedulingError):
        rules.resolve_local_start("2026-09-21", time_text, now=NOW)


def test_relative_dates_use_dubai_midnight_and_year_boundary(rules: ViewingRules) -> None:
    before_midnight = datetime(2026, 12, 31, 19, 59, tzinfo=UTC)
    today = rules.resolve_local_start("today", "08:00", now=before_midnight)
    tomorrow = rules.resolve_local_start("tomorrow", "08:00", now=before_midnight)
    after_midnight = rules.resolve_local_start(
        "today", "08:00", now=before_midnight + timedelta(minutes=1)
    )
    assert today.local_start == "2026-12-31T08:00:00+04:00"
    assert tomorrow.local_start == after_midnight.local_start == "2027-01-01T08:00:00+04:00"
    assert tomorrow.starts_at_utc == datetime(2027, 1, 1, 4, tzinfo=UTC)
    assert tomorrow.requires_review is True


def test_naive_server_clock_is_not_assumed_to_be_dubai_or_utc(rules: ViewingRules) -> None:
    with pytest.raises(SchedulingError, match="AWARE_INSTANT_REQUIRED"):
        rules.resolve_local_start("today", "08:00", now=NOW.replace(tzinfo=None))


def test_extreme_dates_and_clock_remain_named_failures(rules: ViewingRules) -> None:
    with pytest.raises(SchedulingError, match="DATE_OUT_OF_RANGE"):
        rules.resolve_local_start("0001-01-01", "00:00", now=NOW)
    with pytest.raises(SchedulingError, match="DATE_OUT_OF_RANGE"):
        rules.resolve_local_start("today", "08:00", now=datetime.max.replace(tzinfo=UTC))


def test_exact_offset_must_match_declared_zone(rules: ViewingRules) -> None:
    assert rules.parse_local_timestamp(
        "2026-09-21T08:00:00+04:00", timezone="Asia/Dubai"
    ) == datetime(2026, 9, 21, 4, tzinfo=UTC)
    with pytest.raises(SchedulingError, match="LOCAL_OFFSET_MISMATCH"):
        rules.parse_local_timestamp("2026-09-21T08:00:00+03:00", timezone="Asia/Dubai")
    with pytest.raises(SchedulingError, match="TIMEZONE_MISMATCH"):
        rules.parse_local_timestamp("2026-09-21T08:00:00+04:00", timezone="Europe/London")
    with pytest.raises(SchedulingError, match="TIMEZONE_MISMATCH"):
        rules.resolve_local_start("today", "08:00", now=NOW, timezone="UTC")


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-21T08:00:00",
        "2026-09-21T04:00:00Z",
        "2026-02-30T08:00:00+04:00",
        "2026-09-21 08:00:00+04:00",
        "2026-09-21T08:00:00+25:00",
        "2026-09-21T08:00:00+03:60",
    ],
)
def test_local_timestamp_requires_complete_possible_local_date_and_offset(
    rules: ViewingRules, value: str
) -> None:
    with pytest.raises(SchedulingError):
        rules.parse_local_timestamp(value, timezone="Asia/Dubai")


@pytest.mark.parametrize("local_start", ["2026-09-21T08:00:00+04:00", "2026-09-26T19:30:00+04:00"])
def test_monday_opening_and_saturday_last_full_interval_are_valid(
    rules: ViewingRules, local_start: str
) -> None:
    start = datetime.fromisoformat(local_start)
    interval = rules.validate_interval(start, start + timedelta(minutes=30), now=NOW)
    assert interval.local_start == local_start
    assert interval.ends_at_utc - interval.starts_at_utc == timedelta(minutes=30)
    assert interval.timezone == "Asia/Dubai" and interval.rules_version == rules.version
    if start.weekday() == 5:
        assert interval.local_end == "2026-09-26T20:00:00+04:00"


@pytest.mark.parametrize(
    ("local_start", "code"),
    [
        ("2026-09-26T20:00:00+04:00", "OUTSIDE_OPEN_HOURS"),
        ("2026-09-27T08:00:00+04:00", "CLOSED_DAY"),
        ("2026-09-22T07:59:00+04:00", "OUTSIDE_OPEN_HOURS"),
        ("2026-09-22T19:45:00+04:00", "OUTSIDE_OPEN_HOURS"),
        ("2026-09-22T08:15:00+04:00", "OFF_GRID"),
        ("2026-09-22T08:00:00.000001+04:00", "OFF_GRID"),
        ("2026-09-22T23:45:00+04:00", "OUTSIDE_OPEN_HOURS"),
        ("2026-09-19T08:00:00+04:00", "PAST_SLOT"),
    ],
)
def test_rejected_calendar_boundaries(rules: ViewingRules, local_start: str, code: str) -> None:
    start = datetime.fromisoformat(local_start)
    with pytest.raises(SchedulingError, match=code):
        rules.validate_interval(start, start + timedelta(minutes=30), now=NOW)


@pytest.mark.parametrize("minutes", [-30, 0, 29, 31, 60])
def test_requested_end_cannot_bypass_exact_full_duration(rules: ViewingRules, minutes: int) -> None:
    start = datetime(2026, 9, 21, 4, tzinfo=UTC)
    with pytest.raises(SchedulingError, match="INVALID_FULL_INTERVAL"):
        rules.validate_interval(start, start + timedelta(minutes=minutes), now=NOW)


def test_minimum_lead_is_inclusive_to_the_microsecond(rules: ViewingRules) -> None:
    start = datetime(2026, 9, 21, 4, tzinfo=UTC)
    assert rules.validate_interval(start, start + timedelta(minutes=30), now=NOW)
    with pytest.raises(SchedulingError, match="MINIMUM_LEAD_NOT_MET"):
        rules.validate_interval(
            start, start + timedelta(minutes=30), now=NOW + timedelta(microseconds=1)
        )


def test_horizon_uses_inclusive_dubai_date_not_rolling_hours(rules: ViewingRules) -> None:
    last = datetime.fromisoformat("2026-10-21T19:30:00+04:00")
    assert last.astimezone(UTC) > NOW + timedelta(days=30)
    assert rules.validate_interval(last, last + timedelta(minutes=30), now=NOW)
    next_day = datetime.fromisoformat("2026-10-22T08:00:00+04:00")
    with pytest.raises(SchedulingError, match="HORIZON_EXCEEDED"):
        rules.validate_interval(next_day, next_day + timedelta(minutes=30), now=NOW)


def test_year_boundary_is_a_real_exact_local_proposal(rules: ViewingRules) -> None:
    now = datetime(2026, 12, 31, 19, 59, tzinfo=UTC)
    proposed = rules.resolve_local_start("tomorrow", "08:00", now=now)
    interval = rules.validate_interval(
        proposed.starts_at_utc,
        proposed.starts_at_utc + timedelta(minutes=30),
        now=now,
        local_start=proposed.local_start,
    )
    assert interval.local_start == "2027-01-01T08:00:00+04:00"


def test_changed_rule_version_and_mismatched_local_presentation_reject(rules: ViewingRules) -> None:
    start = datetime(2026, 9, 21, 4, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    with pytest.raises(SchedulingError, match="RULES_CHANGED"):
        rules.validate_interval(start, end, now=NOW, expected_rules_version="prior-rules")
    with pytest.raises(SchedulingError, match="LOCAL_INSTANT_MISMATCH"):
        rules.validate_interval(start, end, now=NOW, local_start="2026-09-21T08:30:00+04:00")
    with pytest.raises(SchedulingError, match="LOCAL_OFFSET_MISMATCH"):
        rules.validate_interval(start, end, now=NOW, local_start="2026-09-21T08:00:00+03:00")
    with pytest.raises(SchedulingError, match="TIMEZONE_MISMATCH"):
        rules.validate_interval(start, end, now=NOW, timezone="UTC")


def test_candidate_output_is_bounded_sorted_and_uses_the_same_rules(rules: ViewingRules) -> None:
    slots = rules.candidate_slots("2026-09-21", days=7, now=NOW)
    assert len(slots) == 24
    assert slots[0].local_start == "2026-09-21T08:00:00+04:00"
    assert slots[-1].local_end == "2026-09-21T20:00:00+04:00"
    assert all(
        left.ends_at_utc == right.starts_at_utc
        for left, right in zip(slots, slots[1:], strict=False)
    )
    for slot in slots:
        assert rules.validate_interval(slot.starts_at_utc, slot.ends_at_utc, now=NOW) == slot


def test_candidates_skip_closed_sunday_without_extending_requested_window(
    rules: ViewingRules,
) -> None:
    saturday = datetime(2026, 9, 26, 15, tzinfo=UTC)
    slots = rules.candidate_slots("2026-09-26", days=3, now=saturday, limit=3)
    assert [slot.local_start for slot in slots] == [
        "2026-09-26T19:30:00+04:00",
        "2026-09-28T08:00:00+04:00",
        "2026-09-28T08:30:00+04:00",
    ]
    assert rules.candidate_slots("2026-09-27", days=1, now=saturday) == ()


def test_candidates_exclude_past_and_after_horizon_dates(rules: ViewingRules) -> None:
    assert rules.candidate_slots("2026-09-19", days=1, now=NOW) == ()
    assert rules.candidate_slots("2026-10-22", days=7, now=NOW) == ()
    assert len(rules.candidate_slots("2026-10-21", days=1, now=NOW)) == 24


@pytest.mark.parametrize("days", [0, 8, True])
def test_candidate_window_is_strictly_bounded(rules: ViewingRules, days: int) -> None:
    with pytest.raises(SchedulingError, match="INVALID_DAY_WINDOW"):
        rules.candidate_slots("2026-09-21", days=days, now=NOW)


@pytest.mark.parametrize("limit", [0, 25, True])
def test_candidate_limit_cannot_expand_public_maximum(rules: ViewingRules, limit: int) -> None:
    with pytest.raises(SchedulingError, match="INVALID_CANDIDATE_LIMIT"):
        rules.candidate_slots("2026-09-21", days=1, now=NOW, limit=limit)


def test_candidate_window_cannot_overflow_date_range(rules: ViewingRules) -> None:
    with pytest.raises(SchedulingError, match="DATE_OUT_OF_RANGE"):
        rules.candidate_slots("9999-12-31", days=7, now=NOW)
