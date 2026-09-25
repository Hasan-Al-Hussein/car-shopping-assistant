"""Deterministic Dubai calendar rules, independent of capacity and persistence."""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from app.core.config import VIEWING_VENUE, DemoPolicy

RULES_VERSION = "viewing-calendar-1"
MAX_WINDOW_DAYS = 7
MAX_CANDIDATES = 24
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_LOCAL_TIME = re.compile(r"[0-9]{2}:[0-9]{2}\Z")
_LOCAL_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]\Z"
)


class SchedulingError(ValueError):
    """Closed reason code only; no rejected date/contact text in the exception."""


def utc_instant(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SchedulingError("AWARE_INSTANT_REQUIRED")
    try:
        return value.astimezone(UTC)
    except (ValueError, OverflowError):
        raise SchedulingError("DATE_OUT_OF_RANGE") from None


def exact_date(value: str) -> date:
    if not _DATE.fullmatch(value):
        raise SchedulingError("EXACT_DATE_REQUIRED")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise SchedulingError("IMPOSSIBLE_DATE") from None


@dataclass(frozen=True)
class ZonedInterval:
    starts_at_utc: datetime
    ends_at_utc: datetime
    local_start: str
    local_end: str
    timezone: Literal["Asia/Dubai"]
    rules_version: str


@dataclass(frozen=True)
class ProposedLocalStart:
    """Resolved exact proposal; never a booking, hold or implicit confirmation."""

    local_start: str
    starts_at_utc: datetime
    timezone: Literal["Asia/Dubai"]
    requires_review: Literal[True] = True


@dataclass(frozen=True, init=False)
class ViewingRules:
    """Only the adopted F04 policy is supported; absent/changed policies fail closed."""

    policy: DemoPolicy
    zone: ZoneInfo
    version: str
    venue_label: str

    def __init__(self, policy: DemoPolicy | None) -> None:
        if policy is None:
            raise SchedulingError("RULES_UNAVAILABLE")
        try:
            validated = DemoPolicy.model_validate(policy.model_dump(mode="python"))
            zone = ZoneInfo(validated.timezone)
        except (ValidationError, ValueError, ZoneInfoNotFoundError):
            raise SchedulingError("RULES_UNAVAILABLE") from None
        object.__setattr__(self, "policy", validated)
        object.__setattr__(self, "zone", zone)
        object.__setattr__(self, "version", f"{validated.version}:{RULES_VERSION}")
        object.__setattr__(self, "venue_label", VIEWING_VENUE)

    def resolve_local_start(
        self,
        date_expression: str,
        local_time: str,
        *,
        now: datetime,
        timezone: str = "Asia/Dubai",
    ) -> ProposedLocalStart:
        """Accept exact ISO dates, today or tomorrow; other prose needs clarification.

        Dates without a year, next-weekday/evening phrases and unnamed timezones
        have no silently chosen interpretation. Relative dates use Dubai today.
        """
        if timezone != self.policy.timezone:
            raise SchedulingError("TIMEZONE_MISMATCH")
        try:
            today = utc_instant(now).astimezone(self.zone).date()
        except OverflowError:
            raise SchedulingError("DATE_OUT_OF_RANGE") from None
        if date_expression in {"today", "tomorrow"}:
            try:
                selected = today + timedelta(days=date_expression == "tomorrow")
            except OverflowError:
                raise SchedulingError("DATE_OUT_OF_RANGE") from None
        else:
            selected = exact_date(date_expression)
        if not _LOCAL_TIME.fullmatch(local_time):
            raise SchedulingError("EXACT_LOCAL_TIME_REQUIRED")
        try:
            wall = datetime.combine(selected, time.fromisoformat(local_time))
        except ValueError:
            raise SchedulingError("IMPOSSIBLE_LOCAL_TIME") from None
        aware = wall.replace(tzinfo=self.zone)
        # Keep round-trip/ambiguity checks explicit even though Dubai has no current DST.
        try:
            resolved_utc = aware.astimezone(UTC)
            round_trip = resolved_utc.astimezone(self.zone).replace(tzinfo=None)
        except OverflowError:
            raise SchedulingError("DATE_OUT_OF_RANGE") from None
        if round_trip != wall:
            raise SchedulingError("NONEXISTENT_LOCAL_TIME")
        if aware.utcoffset() != wall.replace(tzinfo=self.zone, fold=1).utcoffset():
            raise SchedulingError("AMBIGUOUS_LOCAL_TIME")
        return ProposedLocalStart(aware.isoformat(), resolved_utc, self.policy.timezone)

    def parse_local_timestamp(self, value: str, *, timezone: str) -> datetime:
        """Require explicit date/year/offset agreeing with the declared Dubai zone."""
        if timezone != self.policy.timezone:
            raise SchedulingError("TIMEZONE_MISMATCH")
        if not _LOCAL_TIMESTAMP.fullmatch(value):
            raise SchedulingError("EXPLICIT_LOCAL_OFFSET_REQUIRED")
        try:
            supplied = datetime.fromisoformat(value)
            zoned = supplied.astimezone(self.zone)
        except (ValueError, OverflowError):
            raise SchedulingError("IMPOSSIBLE_LOCAL_TIMESTAMP") from None
        if supplied.utcoffset() != zoned.utcoffset() or supplied.replace(
            tzinfo=None
        ) != zoned.replace(tzinfo=None):
            raise SchedulingError("LOCAL_OFFSET_MISMATCH")
        return utc_instant(supplied)

    def validate_interval(
        self,
        starts_at: datetime,
        ends_at: datetime,
        *,
        now: datetime,
        timezone: str = "Asia/Dubai",
        local_start: str | None = None,
        expected_rules_version: str | None = None,
    ) -> ZonedInterval:
        """Validate the entire interval under the adopted inclusive/grid contract.

        Capacity uses [start, end) later. Passing these rules is not proof that
        capacity is free and does not authorize a reviewed action or reservation.
        """
        if expected_rules_version is not None and expected_rules_version != self.version:
            raise SchedulingError("RULES_CHANGED")
        if timezone != self.policy.timezone:
            raise SchedulingError("TIMEZONE_MISMATCH")
        start, end, current = utc_instant(starts_at), utc_instant(ends_at), utc_instant(now)
        duration = timedelta(minutes=self.policy.slot_minutes)
        if end - start != duration:
            raise SchedulingError("INVALID_FULL_INTERVAL")
        if (
            local_start is not None
            and self.parse_local_timestamp(local_start, timezone=timezone) != start
        ):
            raise SchedulingError("LOCAL_INSTANT_MISMATCH")
        try:
            local = start.astimezone(self.zone)
            local_end = end.astimezone(self.zone)
            today = current.astimezone(self.zone).date()
            latest_date = today + timedelta(days=self.policy.horizon_days)
            earliest_start = current + timedelta(minutes=self.policy.minimum_lead_minutes)
        except OverflowError:
            raise SchedulingError("DATE_OUT_OF_RANGE") from None
        if start <= current:
            raise SchedulingError("PAST_SLOT")
        if start < earliest_start:
            raise SchedulingError("MINIMUM_LEAD_NOT_MET")
        if local.date() > latest_date:
            raise SchedulingError("HORIZON_EXCEEDED")
        if local.weekday() not in self.policy.open_weekdays:
            raise SchedulingError("CLOSED_DAY")
        opens = datetime.combine(local.date(), time.fromisoformat(self.policy.open_time), self.zone)
        closes = datetime.combine(
            local.date(), time.fromisoformat(self.policy.close_time), self.zone
        )
        if local < opens or local_end > closes or local_end.date() != local.date():
            raise SchedulingError("OUTSIDE_OPEN_HOURS")
        if (local - opens) % duration != timedelta(0):
            raise SchedulingError("OFF_GRID")
        return ZonedInterval(
            start,
            end,
            local.isoformat(),
            local_end.isoformat(),
            self.policy.timezone,
            self.version,
        )

    def candidate_slots(
        self,
        from_date: str,
        *,
        days: int,
        now: datetime,
        limit: int = MAX_CANDIDATES,
    ) -> tuple[ZonedInterval, ...]:
        """At most 7 days / 168 evaluated grid positions / 24 calendar candidates."""
        if type(days) is not int or not 1 <= days <= MAX_WINDOW_DAYS:
            raise SchedulingError("INVALID_DAY_WINDOW")
        if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
            raise SchedulingError("INVALID_CANDIDATE_LIMIT")
        first = exact_date(from_date)
        current = utc_instant(now)
        duration = timedelta(minutes=self.policy.slot_minutes)
        slots: list[ZonedInterval] = []
        try:
            # Validate the whole requested date window, even if an early day fills the limit.
            if first > date.max - timedelta(days=days - 1):
                raise SchedulingError("DATE_OUT_OF_RANGE")
            for offset in range(days):
                selected = first + timedelta(days=offset)
                start = datetime.combine(
                    selected, time.fromisoformat(self.policy.open_time), self.zone
                )
                closes = datetime.combine(
                    selected, time.fromisoformat(self.policy.close_time), self.zone
                )
                while start + duration <= closes:
                    try:
                        candidate = self.validate_interval(start, start + duration, now=current)
                    except SchedulingError as error:
                        if str(error) not in {
                            "PAST_SLOT",
                            "MINIMUM_LEAD_NOT_MET",
                            "HORIZON_EXCEEDED",
                            "CLOSED_DAY",
                        }:
                            raise
                    else:
                        slots.append(candidate)
                        if len(slots) == limit:
                            return tuple(slots)
                    start += duration
        except OverflowError:
            raise SchedulingError("DATE_OUT_OF_RANGE") from None
        return tuple(slots)
