"""Whole-message collection grammar; model spans propose, local rules decide.

No IDs, contact values, normalized calendar values or action results come from the model.
Unsupported clauses clarify rather than being stripped from a positive cited substring.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.api.schemas.inventory import BudgetRange
from app.api.schemas.leads import BudgetValue
from app.api.schemas.sessions import ClarificationIntent
from app.sessions.collection import FieldSource

from .intent import ReferenceRequest, TurnIntent

Command = Literal[
    "start_enquiry", "start_viewing", "fields", "review_enquiry", "save_enquiry",
    "correct_enquiry", "prepare_viewing", "refresh_viewing", "stop_enquiry",
    "stop_viewing", "discard_draft",
]
FieldName = Literal["budget", "requirements", "ref", "local_date", "local_time"]


class CollectionLanguageError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedField:
    name: FieldName
    value: str | BudgetValue | tuple[str, ...] | None
    source: FieldSource


@dataclass(frozen=True)
class CollectionRequest:
    command: Command
    fields: tuple[ParsedField, ...] = ()
    reference: ReferenceRequest | None = None


_COMMANDS: tuple[tuple[Command, str], ...] = (
    ("start_enquiry", r"(?:I (?:would like|want) to (?:leave|prepare)|help me prepare|prepare) (?:a |an )?(?:local )?enquiry"),
    ("start_viewing", r"(?:I (?:would like|want) to (?:arrange|book|prepare)|help me (?:arrange|book|prepare)|prepare|arrange) (?:a )?viewing"),
    ("review_enquiry", r"(?:review|show) (?:my|this) local enquiry"),
    ("save_enquiry", r"save (?:this|my) local enquiry"),
    ("correct_enquiry", r"(?:update|correct) my saved local enquiry"),
    ("prepare_viewing", r"prepare (?:the|my) viewing review"),
    ("refresh_viewing", r"refresh (?:the|my) viewing review"),
    ("stop_enquiry", r"stop (?:this|my) enquiry preparation"),
    ("stop_viewing", r"stop (?:this|my) viewing preparation"),
    ("discard_draft", r"discard (?:this|my) unsubmitted viewing draft"),
)
_AMOUNT = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?[kK]?"
_BUDGET = re.compile(
    r"(?:my )?cash budget(?: is|:)\s*(?P<currency>[A-Z]{3})\s+"
    rf"(?P<first>{_AMOUNT})(?:\s+(?:to|-)\s+(?P<last>{_AMOUNT}))?",
    re.I,
)
_REQUIREMENTS = re.compile(r'(?:my )?(?:requirements|needs)(?: are|:)\s*(?P<values>.+)', re.I)
_QUOTED_LIST = re.compile(r'"[^"\r\n]{1,200}"(?:\s*(?:,\s*(?:and\s+)?|and\s+)"[^"\r\n]{1,200}")*')


def _clauses(text: str) -> list[tuple[str, int, int]]:
    """Split only explicit semicolons outside quoted requirement values."""
    result: list[tuple[str, int, int]] = []
    quoted, start = False, 0
    for index, character in enumerate(text + ";"):
        if character == '"':
            quoted = not quoted
        if character == ";" and not quoted:
            left, right = start, index
            while left < right and text[left].isspace():
                left += 1
            while right > left and (text[right - 1].isspace() or text[right - 1] in ".!"):
                right -= 1
            if left == right:
                raise CollectionLanguageError("State one complete collection request.")
            result.append((text[left:right], left, right))
            start = index + 1
    if quoted or not 1 <= len(result) <= 5:
        raise CollectionLanguageError("State complete fields without conflicting clauses.")
    return result


def _minor_units(value: str) -> int:
    normalized = value.replace(",", "").casefold()
    amount = Decimal(normalized.removesuffix("k")) * (1000 if normalized.endswith("k") else 1) * 100
    if amount != amount.to_integral_value():
        raise CollectionLanguageError("Use a supported cash amount with at most two decimals.")
    return int(amount)


def _field(clause: str, start: int, end: int) -> ParsedField | None:
    def parsed(name: FieldName, value: str | BudgetValue | tuple[str, ...] | None) -> ParsedField:
        return ParsedField(name, value, FieldSource(field=name, start=start, end=end))

    budget = _BUDGET.fullmatch(clause)
    if budget:
        if budget.group("currency").upper() != "AED":
            raise CollectionLanguageError("Conversational enquiry budgets currently support explicit AED cash amounts; use the local form for other currencies.")
        first, last = budget.group("first"), budget.group("last")
        return parsed("budget", BudgetValue(state="provided", value=BudgetRange(
            currency=budget.group("currency").upper(),
            minimum=_minor_units(first) if last is not None else None,
            maximum=_minor_units(last or first), basis="cash",
        )))
    for field, label in (("budget", "budget"), ("requirements", "requirements")):
        if re.fullmatch(rf"I decline to (?:provide|state) my {label}", clause, re.I):
            return parsed(field, None)  # type: ignore[arg-type]
        if re.fullmatch(rf"clear my {label}", clause, re.I):
            return parsed(field, "clear")  # type: ignore[arg-type]
    requirements = _REQUIREMENTS.fullmatch(clause)
    if requirements and _QUOTED_LIST.fullmatch(requirements.group("values")):
        values = tuple(re.findall(r'"([^"\r\n]+)"', requirements.group("values")))
        if not 1 <= len(values) <= 24 or any(not value.strip() for value in values):
            raise CollectionLanguageError("State at most 24 nonempty quoted requirements.")
        return parsed("requirements", values)
    for field, label in (("local_date", "date"), ("local_time", "time")):
        match = re.fullmatch(rf"(?:my )?viewing {label}(?: is|:)\s*(.+)", clause, re.I)
        if match:
            return parsed(field, match.group(1))  # type: ignore[arg-type]
    return None


def parse_collection_request(
    text: str, intent: TurnIntent, *, matched_question: ClarificationIntent | None,
) -> CollectionRequest:
    proposal = intent.collection
    if (
        proposal is None or intent.patches or intent.problem is not None
        or intent.scope != "session" or set(intent.deferred) - {"viewing", "lead"}
        or len(intent.references) > 1
    ):
        raise CollectionLanguageError("Settle the other instruction before changing this collection.")
    references = intent.references
    command: Command = "fields"
    fields: list[ParsedField] = []
    reference = None
    cited: list[tuple[str, str]] = []
    clauses = _clauses(text)
    for index, (clause, start, end) in enumerate(clauses):
        plain = re.sub(r"^please\s+", "", clause, flags=re.I)
        found = False
        if index == 0:
            for candidate, pattern in _COMMANDS:
                match = re.fullmatch(pattern + r"(?P<reference> (?:of|for|about) .+)?", plain, re.I)
                if not match:
                    continue
                extra = match.group("reference")
                if extra and candidate not in {"start_viewing", "start_enquiry"}:
                    continue
                command, found = candidate, True
                if extra:
                    phrase = re.sub(r"^ (?:of|for|about) ", "", extra)
                    if len(references) != 1 or references[0].quote != phrase:
                        raise CollectionLanguageError("Name the exact car using its original result order.")
                    reference = references[0]
                    fields.append(ParsedField("ref", None, FieldSource(field="ref", start=start, end=end)))
                break
        if found:
            continue
        item = _field(clause, start, end)
        if item is None and references:
            phrase = re.sub(r"^(?:please\s+)?use\s+", "", clause, flags=re.I)
            bare_allowed = matched_question is not None and matched_question.purpose == "listing_reference"
            if (phrase != clause or bare_allowed) and references[0].quote == phrase:
                reference = references[0]
                item = ParsedField("ref", None, FieldSource(field="ref", start=start, end=end))
        if item is None and matched_question is not None and matched_question.purpose == "viewing_details":
            candidates = [value for value in proposal.fields if value.quote == clause and value.field in {"local_date", "local_time"}]
            if len(candidates) == 1:
                name = candidates[0].field
                item = ParsedField(name, clause, FieldSource(field=name, start=start, end=end))
        if item is None:
            raise CollectionLanguageError("State an explicit car, viewing date/time, cash budget or quoted requirements; separate other instructions.")
        if item.name != "ref":
            cited.append((item.name, clause))
        fields.append(item)
    if len({field.name for field in fields}) != len(fields):
        raise CollectionLanguageError("Give one unambiguous value for each field.")
    if command not in {"fields", "start_enquiry", "start_viewing"} and len(clauses) != 1:
        raise CollectionLanguageError("Review changed values before a separate explicit action.")
    if command == "fields" and not fields:
        raise CollectionLanguageError("Name the field to change.")
    if proposal.command != command or sorted(cited) != sorted((item.field, item.quote) for item in proposal.fields):
        raise CollectionLanguageError("The cited fields do not match the whole request; please state them explicitly.")
    if bool(references) != (reference is not None):
        raise CollectionLanguageError("The complete request must name the same exact car.")
    return CollectionRequest(command, tuple(fields), reference)
