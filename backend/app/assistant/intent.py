"""Finite language proposals and deterministic, explicit criteria transitions."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, ValidationError

from app.api.schemas.inventory import BudgetRange, IntegerRange, SearchCriteria
from app.core.config import FrozenSettings

TextField = Literal[
    "query",
    "makes",
    "models",
    "trims",
    "body_types",
    "fuel_types",
    "transmissions",
    "soft_preferences",
]
RangeField = Literal["years", "budget", "mileage_km"]
Target = Literal[
    "query",
    "makes",
    "models",
    "trims",
    "years",
    "budget",
    "mileage_km",
    "body_types",
    "fuel_types",
    "transmissions",
    "soft_preferences",
    "selected_ref",
    "preference_scope",
    "appointment",
    "confirmation",
]
Quote = Annotated[str, Field(min_length=1, max_length=400)]
ValueText = Annotated[str, Field(min_length=1, max_length=200)]


class TextPatch(FrozenSettings):
    kind: Literal["text"]
    field: TextField
    operation: Literal["add", "replace", "remove", "clear"]
    values: Annotated[list[ValueText], Field(max_length=12)] = Field(
        default_factory=list, description="Exclude explicit make/model/trim field labels. "
        "model 7 => models=['7']; model 'Model 7' => models=['Model 7']; "
        "trim 2.5 => trims=['2.5']. Keep full quoted/numeric text; infer no make."
    )
    quote: Quote = Field(description="Exact buyer-message span supporting this change.")


class NumberToken(FrozenSettings):
    text: Annotated[str, Field(min_length=1, max_length=32)] = Field(
        description="Exact number token from the buyer, e.g. 60k; never normalized invented digits."
    )
    inclusive: bool = True


class RangePatch(FrozenSettings):
    kind: Literal["range"]
    field: RangeField
    operation: Literal["refine", "correct", "clear"]
    minimum: NumberToken | None = None
    maximum: NumberToken | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    basis: Literal["cash", "monthly_finance", "unknown"] = "unknown"
    quote: Quote


class ResetPatch(FrozenSettings):
    kind: Literal["reset"]
    quote: Quote


Patch = Annotated[TextPatch | RangePatch | ResetPatch, Field(discriminator="kind")]


class ReferenceRequest(FrozenSettings):
    source: Literal["selected", "request", "ordinal"] = Field(
        description="request: 'this car' with an explicit UI choice in presented_refs => "
        "detail/request. selected: session selected_ref for it/its/that car. ordinal: "
        "'fourth car' => detail/ordinal, position=3, page=active in original results. "
        "Missing fact rows do not invalidate an ordinal. Non-ordinal: position=make=null."
    )
    page: Literal["active", "request"] = Field(
        default="active", description="For ordinal: active original results, or explicitly "
        "supplied request results page. Never infer a different page."
    )
    position: Annotated[int, Field(ge=0, le=49)] | None = Field(
        default=None, description="Zero-based position, within the ORIGINAL order or named make."
    )
    make: ValueText | None = None
    quote: Quote = Field(
        description="Exact buyer reference phrase, e.g. it or first Honda, not the whole "
        "attribute question. Preserve cited ordinal/make qualifiers and every other car reference."
    )


class CollectionFieldProposal(FrozenSettings):
    field: Literal["budget", "requirements", "local_date", "local_time"]
    quote: Annotated[str, Field(min_length=1, max_length=4000)]


class CollectionProposal(FrozenSettings):
    """Cited non-contact collection proposal; never command or permission material."""

    command: Literal[
        "start_enquiry", "start_viewing", "fields", "review_enquiry", "save_enquiry",
        "correct_enquiry", "prepare_viewing", "refresh_viewing", "stop_enquiry",
        "stop_viewing", "discard_draft",
    ] = Field(
        description="Local enquiry review/save/correct map to review_enquiry/save_enquiry/"
        "correct_enquiry, fields=[]. 'Save this local enquiry' is save_enquiry, never "
        "preferences or viewing confirmation."
    )
    fields: Annotated[list[CollectionFieldProposal], Field(max_length=4)] = Field(
        default_factory=list
    )


class TurnIntent(FrozenSettings):
    """Extract one supported shopping read and explicit buyer-cited criteria changes.

    Browse without a questionnaire. Keep unspecified criteria. Correct/replace only explicit
    corrections; refine tighter numeric bounds; clear only explicit removals. Keep numeric
    tokens verbatim and mark exclusive bounds. Currency/cash basis must be cited or established.
    Subjective wishes stay soft; unsupported hard search requirements and competing references
    need clarification. Distinguish hypothetical/session/durable intent. Enquiry/viewing uses
    collection; other writes use deferred. Never provide facts, answer prose,
    permissions or receipts.
    """

    model_config = ConfigDict(json_schema_extra={"examples": [
        {
            "operation": "smalltalk", "scope": "session", "patches": [], "references": [],
            "problem": None, "problem_target": "query", "deferred": ["lead"],
            "collection": {"command": "start_enquiry", "fields": [
                {"field": "budget", "quote": "My cash budget is AED 47000"},
                {"field": "requirements", "quote": 'My needs are "wide doors"'},
            ]},
        },
    ]})

    operation: Literal["search", "detail", "compare", "return", "smalltalk", "unsupported"] = Field(
        description="search: local inventory only. External-site searches are unsupported; "
        "no car pointers. detail: one cited car or its attributes; unknown/conflicting facts; "
        "no patches or deferred writes. "
        "Ordinal follow-ups use detail, never repeat search. compare: two/three cited cars. "
        "return: saved preferences. smalltalk: collections, greeting/app help or generic "
        "automotive explanations. These: session, no references/patches/deferred/"
        "collection, problem=null even with a selected car. unsupported: coding, world history, "
        "unrelated topics or requests about other marketplaces. problem=reference: "
        "unresolved/competing references, not absent facts. "
        "Unknown facts aren't unsupported hard search requirements."
    )
    scope: Literal["session", "hypothetical", "durable", "unclear"] = "session"
    patches: Annotated[list[Patch], Field(max_length=12)] = Field(default_factory=list)
    references: Annotated[list[ReferenceRequest], Field(max_length=3)] = Field(default_factory=list)
    problem: (
        Literal[
            "currency",
            "basis",
            "conflict",
            "unsupported_attribute",
            "reference",
            "persistence",
            "meaning",
        ]
        | None
    ) = None
    problem_target: Target = "query"
    deferred: Annotated[
        list[Literal["viewing", "lead", "preferences", "shortlist", "confirmation"]],
        Field(max_length=5),
    ] = Field(default_factory=list)
    collection: CollectionProposal | None = Field(
        default=None, description="Enquiry/viewing: smalltalk/session, patches=[], problem=null, "
        "deferred=[] or lead/viewing only; references only if cited. Budget/requirements go to "
        "fields with complete-clause quotes, not search or saved preferences. "
        "Example is a shape, not permission; "
        "quote only the current buyer."
    )


@dataclass(frozen=True)
class Clarification:
    target: Target
    question: str


@dataclass(frozen=True)
class CriteriaTransition:
    effective: SearchCriteria
    retained: SearchCriteria
    clarification: Clarification | None


_CORRECT = re.compile(r"\b(actually|instead|rather|change|replace|raise|lower|correct|now)\b", re.I)
_REMOVE = re.compile(r"\b(any|remove|drop|clear|forget|exclude|not|no)\b", re.I)
_ALTERNATIVE = re.compile(r"\b(or|either|also|include|add)\b", re.I)
_RESET = re.compile(r"\b(start over|reset (?:the )?(?:search|filters)|remove all filters)\b", re.I)
_NUMBER = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*[kK]?")
_HARD = re.compile(
    r"\b(only|must|required|require|mandatory|at least|at most|no more than|under|over)\b", re.I
)
_VETO = re.compile(
    r"\b(do not|don't|dont|never|not now|not yet|(?:not|no)\s+"
    r"(?:reset|remove|clear|drop|change|replace|forget))\b",
    re.I,
)
_HYPOTHETICAL = re.compile(r"\b(what if|suppose|hypothetical(?:ly)?|just exploring)\b", re.I)
_DURABLE = re.compile(
    r"\b(remember|next time|future searches|save (?:my |these )?preferences)\b", re.I
)
_UNSUPPORTED_HARD = re.compile(
    r"\b(accident[- ]free|safest|reliab(?:le|ility)|warranty|colour|color|perfect condition)\b",
    re.I,
)
_CUES: dict[str, tuple[str, ...]] = {
    "query": ("query", "search"),
    "makes": ("make", "brand"),
    "models": ("model",),
    "trims": ("trim",),
    "years": ("year",),
    "budget": ("budget", "price", "cash"),
    "mileage_km": ("mileage", "kilomet", "kilometre", "km"),
    "body_types": ("body", "style"),
    "fuel_types": ("fuel",),
    "transmissions": ("transmission", "gearbox"),
    "soft_preferences": ("preference", "nice to have"),
}


def issue(target: Target, reason: str = "conflict") -> Clarification:
    if reason in {"currency", "basis"}:
        return Clarification(
            "budget", "Which currency and total cash amount should the budget use?"
        )
    if reason == "reference":
        return Clarification("selected_ref", "Which listing and original results page do you mean?")
    if reason == "persistence":
        return Clarification(
            "preference_scope",
            "Should these criteria apply only to this search? No preferences have been saved.",
        )
    if reason == "unsupported_attribute":
        return Clarification(
            "soft_preferences",
            "Which supported listing attribute should express this requirement, "
            "or is it a preference?",
        )
    if reason == "meaning":
        return Clarification(
            "query", "Would you like to browse cars, refine a search, or inspect a listing?"
        )
    label = target.replace("_", " ")
    return Clarification(
        target, f"Which {label} condition should I change? The accepted criteria remain in place."
    )


def _contains(value: str, quote: str) -> bool:
    return (
        re.search(r"(?<!\w)" + re.escape(value.casefold().strip()) + r"(?!\w)", quote.casefold())
        is not None
    )


def _clear_named(field: str, quote: str, old: object) -> bool:
    if _VETO.search(quote):
        return False
    cues = any(_contains(cue, quote) for cue in _CUES[field])
    named_old = (
        isinstance(old, list) and bool(old) and all(_contains(str(value), quote) for value in old)
    )
    return bool(_REMOVE.search(quote) and (cues or named_old))


def _bound_cited(patch: RangePatch, token: NumberToken, *, lower: bool) -> bool:
    """Finite supported English operators; uncertain language asks, never guesses."""
    number = re.escape(token.text)
    quote = re.sub(r"\bno more than\b", "at most", patch.quote, flags=re.I)
    quote = re.sub(r"\bno less than\b", "at least", quote, flags=re.I)
    if re.search(r"\b(?:not|no|never|don't)\b", quote, re.I):
        return False
    amount = r"(?:[A-Za-z]{3}\s+)?" + number + r"(?!\w)"
    prefix = (
        r"(?<!\w)(?:"
        + (
            r"at least|from|minimum(?: of)?|>="
            if lower
            else r"at most|up to|maximum(?: of)?|<=|budget(?: of)?"
        )
        + r")\s*"
        + amount
    )
    suffix = (
        r"(?<!\w)"
        + number
        + r"\s*(?:"
        + (
            r"or newer|and newer|or more|and above|onwards|\+"
            if lower
            else r"or older|and older|or less|and below"
        )
        + r")(?!\w)"
    )
    exclusive = (
        r"(?<!\w)(?:"
        + (r"over|above|more than|after|>" if lower else r"under|below|less than|before|<")
        + r")\s*"
        + amount
    )
    inclusive = bool(re.search(prefix, quote, re.I) or re.search(suffix, quote, re.I))
    strict = bool(re.search(exclusive, quote, re.I))
    if patch.minimum is not None and patch.maximum is not None:
        interval = (
            r"(?<!\w)(?:[A-Za-z]{3}\s+)?"
            + re.escape(patch.minimum.text)
            + r"\s*(?:to|and|[-–])\s*(?:[A-Za-z]{3}\s+)?"
            + re.escape(patch.maximum.text)
            + r"(?!\w)"
        )
        inclusive = inclusive or bool(re.search(interval, quote, re.I))
    return (inclusive and not strict) if token.inclusive else (strict and not inclusive)


def _number(token: NumberToken, quote: str, *, cash: bool, lower: bool) -> int:
    if not _NUMBER.fullmatch(token.text) or not _contains(token.text, quote):
        raise ValueError("UNSUPPORTED_NUMBER")
    value = token.text.replace(",", "").replace(" ", "").lower()
    try:
        amount = Decimal(value.removesuffix("k")) * (1000 if value.endswith("k") else 1)
        amount *= 100 if cash else 1
        if amount != amount.to_integral_value():
            raise ValueError("UNSUPPORTED_PRECISION")
        number = int(amount)
    except InvalidOperation:
        raise ValueError("UNSUPPORTED_NUMBER") from None
    return number if token.inclusive else number + (1 if lower else -1)


def _text(values: dict[str, object], patch: TextPatch) -> None:
    if _VETO.search(patch.quote):
        raise ValueError("NEGATED_CHANGE")
    container = values if patch.field in {"query", "soft_preferences"} else values["filters"]
    assert isinstance(container, dict)
    old = container[patch.field]
    if patch.operation == "clear":
        if patch.values or not _clear_named(patch.field, patch.quote, old):
            raise ValueError("UNCONFIRMED_REMOVAL")
        container[patch.field] = "" if patch.field == "query" else []
        return
    if not patch.values or any(
        not value.strip() or not _contains(value, patch.quote) for value in patch.values
    ):
        raise ValueError("UNSUPPORTED_VALUE")
    if patch.field in {"query", "soft_preferences"} and _HARD.search(patch.quote):
        # A lexical query/soft preference cannot verify an unsupported hard attribute.
        raise ValueError("UNSUPPORTED_HARD_ATTRIBUTE")
    if patch.field == "query":
        if len(patch.values) != 1 or patch.operation not in {"add", "replace"}:
            raise ValueError("UNSUPPORTED_QUERY_EDIT")
        if old and old != patch.values[0] and not _CORRECT.search(patch.quote):
            raise ValueError("UNCONFIRMED_REPLACEMENT")
        container[patch.field] = patch.values[0]
        return
    assert isinstance(old, list)
    old_keys = {str(item).casefold() for item in old}
    new_keys = {item.casefold() for item in patch.values}
    if patch.operation == "remove":
        if not _REMOVE.search(patch.quote) or not new_keys <= old_keys:
            raise ValueError("UNSUPPORTED_NEGATIVE_FILTER")
        container[patch.field] = [item for item in old if str(item).casefold() not in new_keys]
    elif patch.operation == "replace":
        if old and new_keys != old_keys and not _CORRECT.search(patch.quote):
            raise ValueError("UNCONFIRMED_REPLACEMENT")
        container[patch.field] = list(dict.fromkeys(patch.values))
    else:
        if (
            old
            and not new_keys <= old_keys
            and patch.field != "soft_preferences"
            and not _ALTERNATIVE.search(patch.quote)
        ):
            raise ValueError("UNCLEAR_ALTERNATIVE")
        container[patch.field] = old + [
            item for item in patch.values if item.casefold() not in old_keys
        ]


def _range(values: dict[str, object], patch: RangePatch) -> None:
    if _VETO.search(patch.quote):
        raise ValueError("NEGATED_CHANGE")
    filters = values["filters"]
    assert isinstance(filters, dict)
    old = filters[patch.field]
    if patch.operation == "clear":
        if patch.minimum or patch.maximum or not _clear_named(patch.field, patch.quote, old):
            raise ValueError("UNCONFIRMED_REMOVAL")
        filters[patch.field] = None
        return
    if patch.minimum is None and patch.maximum is None:
        raise ValueError("NO_BOUND")
    if patch.operation == "correct" and old is not None and not _CORRECT.search(patch.quote):
        raise ValueError("UNCONFIRMED_CORRECTION")
    result = dict(old) if isinstance(old, dict) else {}
    if patch.field == "budget":
        if patch.basis == "monthly_finance" or re.search(
            r"\b(month|monthly|instalment|installment)\b", patch.quote, re.I
        ):
            raise ValueError("BUDGET_BASIS")
        currency = patch.currency or result.get("currency")
        if currency is None or (
            currency != result.get("currency") and not _contains(str(currency), patch.quote)
        ):
            raise ValueError("BUDGET_CURRENCY")
        if patch.basis != "cash" and result.get("basis") != "cash":
            raise ValueError("BUDGET_BASIS")
        if (
            patch.basis == "cash"
            and result.get("basis") != "cash"
            and not re.search(r"\b(cash|total|purchase price)\b", patch.quote, re.I)
        ):
            raise ValueError("BUDGET_BASIS")
        if old and currency != result.get("currency") and patch.operation != "correct":
            raise ValueError("BUDGET_CURRENCY")
        if old and currency != result.get("currency"):
            if any(
                result.get(name) is not None and token is None
                for name, token in (("minimum", patch.minimum), ("maximum", patch.maximum))
            ):
                raise ValueError("BUDGET_CURRENCY")
            result = {}
        result.update(currency=currency, basis="cash")
    elif patch.field == "mileage_km":
        if re.search(r"\b(miles?|mi)\b", patch.quote, re.I) or (
            old is None and not re.search(r"\b(km|kilomet\w*)\b", patch.quote, re.I)
        ):
            raise ValueError("MILEAGE_UNIT")
    for name, token in (("minimum", patch.minimum), ("maximum", patch.maximum)):
        if token is None:
            continue
        if not _bound_cited(patch, token, lower=name == "minimum"):
            raise ValueError("UNCLEAR_BOUND")
        if patch.field == "years" and not re.fullmatch(r"\d{4}", token.text):
            raise ValueError("YEAR_TOKEN")
        number = _number(token, patch.quote, cash=patch.field == "budget", lower=name == "minimum")
        previous = result.get(name)
        if patch.operation == "refine" and previous is not None:
            if (name == "minimum" and number < int(previous)) or (
                name == "maximum" and number > int(previous)
            ):
                raise ValueError("UNCONFIRMED_RELAXATION")
            number = max(int(previous), number) if name == "minimum" else min(int(previous), number)
        result[name] = number
    checked = (BudgetRange if patch.field == "budget" else IntegerRange).model_validate(result)
    filters[patch.field] = checked.model_dump(mode="json")


def apply_intent(current: SearchCriteria, intent: TurnIntent, message: str) -> CriteriaTransition:
    """Only supported, cited changes apply; unresolved edits cannot erase accepted criteria."""
    effective = SearchCriteria.model_validate(current.model_dump(mode="json"))
    problem = issue(intent.problem_target, intent.problem) if intent.problem else None
    if intent.patches and _VETO.search(message):
        # The model cannot omit negation by citing only the positive suffix.
        return CriteriaTransition(current, current, issue("query"))
    # Omission is also an untrusted proposal. Explicit hard markers must be accounted
    # for in cited typed changes, not silently erased by an empty/broad interpretation.
    hard = list(_HARD.finditer(message))
    for marker in hard:
        numeric = marker.group().casefold() in {
            "at least",
            "at most",
            "no more than",
            "under",
            "over",
        }
        candidates = [
            patch
            for patch in intent.patches
            if (isinstance(patch, RangePatch) if numeric else isinstance(patch, TextPatch))
        ]
        covered = any(
            patch.quote in message
            and (
                message.index(patch.quote)
                <= marker.start()
                < message.index(patch.quote) + len(patch.quote)
            )
            for patch in candidates
        )
        if not covered or _UNSUPPORTED_HARD.search(message):
            problem = problem or issue("soft_preferences", "unsupported_attribute")
    # Independently cover each quoted comparison number. One make patch cannot account
    # for an omitted price bound merely by quoting the entire sentence.
    comparisons = re.finditer(
        r"\b(?:at least|at most|no more than|no less than|up to|under|over|below|above|"
        r"before|after|less than|more than)\s+(?:(?P<currency>[A-Z]{3})\s+)?"
        r"(?P<number>(?:\d[\d,]*)(?:\.\d+)?\s*[kK]?)(?!\w)",
        message,
        re.I,
    )
    for comparison in comparisons:
        number = comparison.group("number").strip()
        suffix = message[comparison.end() : comparison.end() + 12]
        field = (
            "budget"
            if comparison.group("currency")
            else "mileage_km"
            if re.match(r"\s*(?:km|kilomet\w*)\b", suffix, re.I)
            else "years"
            if re.fullmatch(r"\d{4}", number)
            else None
        )
        covered = any(
            isinstance(patch, RangePatch)
            and (field is None or patch.field == field)
            and patch.quote in message
            and comparison.group() in patch.quote
            and any(
                token is not None
                and token.text.strip() == number
                and _bound_cited(
                    patch.model_copy(update={"quote": comparison.group()}), token, lower=lower
                )
                for lower, token in ((True, patch.minimum), (False, patch.maximum))
            )
            for patch in intent.patches
        )
        if not covered:
            problem = problem or issue("budget" if field == "budget" else "query")
    if _HYPOTHETICAL.search(message) and intent.scope != "hypothetical":
        return CriteriaTransition(current, current, issue("preference_scope", "persistence"))
    if _DURABLE.search(message) and intent.scope not in {"durable", "unclear"}:
        return CriteriaTransition(current, current, issue("preference_scope", "persistence"))
    fields = ["reset" if isinstance(patch, ResetPatch) else patch.field for patch in intent.patches]
    for patch in intent.patches:
        target: Target = "query" if isinstance(patch, ResetPatch) else patch.field
        key = "reset" if isinstance(patch, ResetPatch) else patch.field
        if patch.quote not in message or fields.count(key) > 1:
            problem = problem or issue(target)
            continue
        if (
            intent.problem in {"currency", "basis", "conflict", "unsupported_attribute"}
            and intent.problem_target == target
        ):
            continue
        values = effective.model_dump(mode="json")
        try:
            if isinstance(patch, ResetPatch):
                if not _RESET.search(patch.quote) or _VETO.search(patch.quote):
                    raise ValueError("UNCONFIRMED_RESET")
                values = SearchCriteria().model_dump(mode="json")
            elif isinstance(patch, TextPatch):
                _text(values, patch)
            else:
                _range(values, patch)
            effective = SearchCriteria.model_validate(values)
        except (ValueError, ValidationError) as error:
            reason = {
                "BUDGET_CURRENCY": "currency",
                "BUDGET_BASIS": "basis",
                "UNSUPPORTED_HARD_ATTRIBUTE": "unsupported_attribute",
            }.get(str(error), "conflict")
            problem = problem or issue(target, reason)
    if intent.scope in {"durable", "unclear"}:
        problem = problem or issue("preference_scope", "persistence")
    retained = effective if intent.scope == "session" else current
    return CriteriaTransition(effective, retained, problem)
