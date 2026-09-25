"""Pure field validation over existing calendar/privacy contracts.

These helpers confer no collection, save, draft or booking authority. Their caller must
validate the complete original utterance, question binding and current owned collection.
No provider, session storage or proposed participant interface is used here.
"""

import re
from datetime import datetime

from app.api.schemas.viewings import AppointmentSelection
from app.viewings.scheduling import SchedulingError, ViewingRules

from .packet import minimize_text

_MONTHS = {
    name: number
    for number, name in enumerate(
        ("january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"),
        start=1,
    )
}
_NAMED_DATE = re.compile(
    r"(?P<day>[0-9]{1,2}) (?P<month>[a-z]+) (?P<year>[0-9]{4})"
    r"|(?P<month_first>[a-z]+) (?P<day_second>[0-9]{1,2}),? (?P<year_last>[0-9]{4})"
)
_CLOCK_24 = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]")
_CLOCK_12 = re.compile(r"(?P<hour>0?[1-9]|1[0-2])(?::(?P<minute>[0-5][0-9]))?\s*(?P<period>am|pm)")
_PRIVATE_FIELD = re.compile(
    r"\b(?:my|our)\s+(?:e-?mail(?:\s+address)?|"
    r"(?:phone|telephone|mobile)\s+(?:number|no\.?)|contact\s+(?:number|details))"
    r"\s*(?:is\b|:|=)"
    r"|\b(?:e-?mail|phone|telephone|mobile|contact number)\s*[:=]"
    r"|\b(?:contact|call|text|e-?mail|whatsapp)\s+me\b",
    re.I,
)
_SPOKEN_CONTACT = re.compile(
    r"\b(?:my|our)\s+(?:phone|telephone|mobile)\s+is\s+"
    r"(?:(?:zero|oh|one|two|three|four|five|six|seven|eight|nine|double|triple)"
    r"(?:[\s,-]+|(?=[.!?](?:\s|$))|$)){7,}",
    re.I,
)


class CollectionFieldError(ValueError):
    """Closed code only; never include rejected buyer/private field text."""


def _span(value: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= 80:
        raise CollectionFieldError("FIELD_CLARIFICATION_REQUIRED")
    return value.strip().casefold()


def needs_local_private_reply(text: str, private_values: tuple[str, ...] = ()) -> bool:
    """Keep private/contact-bearing turns out of the provider and collection extractor.

    The existing minimizer supplies conservative private/document detection, including
    its calendar and currency exemptions. This additionally intercepts labelled contact
    expressions even when their body uses prose rather than a recognized address format.
    True means local form/privacy guidance only, never contact capture or a saved result.
    It is defense in depth, not a claim to recognize every possible PII encoding.
    """
    return (
        bool(_PRIVATE_FIELD.search(text) or _SPOKEN_CONTACT.search(text))
        or minimize_text(text, private_values) != text
    )


def viewing_date(span: str, *, rules: ViewingRules, now: datetime) -> str:
    """Resolve an exact cited date once, returning a concrete Dubai calendar date.

    Relative values must be resolved at their source turn, before retaining the result;
    carrying 'tomorrow' into a later turn would silently move the requested day.
    The midnight value is used only to resolve the date and is never an appointment.
    """
    value = _span(span)
    named = _NAMED_DATE.fullmatch(value)
    if named is not None:
        month = _MONTHS.get(named.group("month") or named.group("month_first"))
        if month is None:
            raise CollectionFieldError("DATE_CLARIFICATION_REQUIRED")
        day = int(named.group("day") or named.group("day_second"))
        year = int(named.group("year") or named.group("year_last"))
        value = f"{year:04d}-{month:02d}-{day:02d}"
    try:
        resolved = rules.resolve_local_start(value, "00:00", now=now)
    except SchedulingError:
        raise CollectionFieldError("DATE_CLARIFICATION_REQUIRED") from None
    return datetime.fromisoformat(resolved.local_start).date().isoformat()


def viewing_time(span: str) -> str:
    """Accept exact 24-hour time or an explicitly qualified 12-hour time only."""
    value = _span(span)
    if _CLOCK_24.fullmatch(value):
        return value
    clock = _CLOCK_12.fullmatch(value)
    if clock is None:
        raise CollectionFieldError("TIME_CLARIFICATION_REQUIRED")
    hour = int(clock.group("hour")) % 12 + (12 if clock.group("period") == "pm" else 0)
    minute = int(clock.group("minute") or "0")
    return f"{hour:02d}:{minute:02d}"


def appointment_selection(
    date_value: str, time_value: str, *, rules: ViewingRules, now: datetime,
) -> AppointmentSelection:
    """Build the existing proposal DTO; shared draft/confirmation still validate rules.

    This conversion neither reads capacity nor validates operating-hour eligibility.
    Never describe the returned proposal as available, held, reviewed or confirmed.
    """
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date_value):
        raise CollectionFieldError("CONCRETE_DATE_REQUIRED")
    if not _CLOCK_24.fullmatch(time_value):
        raise CollectionFieldError("CONCRETE_TIME_REQUIRED")
    try:
        resolved = rules.resolve_local_start(date_value, time_value, now=now)
    except SchedulingError:
        raise CollectionFieldError("APPOINTMENT_CLARIFICATION_REQUIRED") from None
    return AppointmentSelection(
        starts_at_utc=resolved.starts_at_utc.isoformat().replace("+00:00", "Z"),
        timezone=resolved.timezone,
        appointment_type="viewing",
    )
