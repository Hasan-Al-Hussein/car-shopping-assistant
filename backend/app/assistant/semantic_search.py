"""Apply model-interpreted shopping filters without a second phrase-based intent parser.

The model decides what a read-only request means. This boundary validates cited input,
numeric representation and state consistency; it never authorizes a business action.
"""

import re
from typing import Any

from pydantic import ValidationError

from app.api.schemas.inventory import BudgetRange, IntegerRange, SearchCriteria

from .intent import (
    _NUMBER,
    CriteriaTransition,
    RangePatch,
    ResetPatch,
    Target,
    TextPatch,
    TurnIntent,
    _contains,
    _number,
    issue,
)


def _unique(values: list[str]) -> list[str]:
    result: dict[str, str] = {}
    for value in values:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("EMPTY_VALUE")
        result.setdefault(normalized.casefold(), normalized)
    return list(result.values())


def _text(values: dict[str, Any], patch: TextPatch) -> None:
    container = values if patch.field in {"query", "soft_preferences"} else values["filters"]
    old = container[patch.field]
    if patch.operation == "clear":
        if patch.values:
            raise ValueError("INVALID_CLEAR")
        container[patch.field] = "" if patch.field == "query" else []
        return
    proposed = _unique(patch.values)
    if not proposed:
        raise ValueError("EMPTY_VALUE")
    if patch.field == "query":
        if len(proposed) != 1:
            raise ValueError("INVALID_QUERY")
        if patch.operation == "remove":
            if proposed[0].casefold() != old.casefold():
                raise ValueError("UNKNOWN_REMOVAL")
            container[patch.field] = ""
        else:
            container[patch.field] = proposed[0]
        return
    old_keys = {value.casefold() for value in old}
    new_keys = {value.casefold() for value in proposed}
    if patch.operation == "remove":
        if not new_keys <= old_keys:
            raise ValueError("UNKNOWN_REMOVAL")
        container[patch.field] = [value for value in old if value.casefold() not in new_keys]
    elif patch.operation == "replace":
        container[patch.field] = proposed
    else:
        container[patch.field] = _unique([*old, *proposed])


def _range(
    values: dict[str, Any],
    patch: RangePatch,
    message: str,
    *,
    clarified: bool,
    prior_request: str,
) -> None:
    filters = values["filters"]
    old = filters[patch.field]
    endpoints = (
        ("minimum", patch.minimum, patch.clear_minimum),
        ("maximum", patch.maximum, patch.clear_maximum),
    )
    clearing_endpoint = any(clear for _, _, clear in endpoints)
    if clearing_endpoint and patch.operation != "correct":
        raise ValueError("INVALID_ENDPOINT_CLEAR")
    if any(clear and token is not None for _, token, clear in endpoints):
        raise ValueError("CONTRADICTORY_ENDPOINT")
    if patch.operation == "clear":
        if (
            patch.minimum is not None
            or patch.maximum is not None
            or patch.currency is not None
            or patch.basis != "unknown"
        ):
            raise ValueError("INVALID_CLEAR")
        filters[patch.field] = None
        return
    if patch.minimum is None and patch.maximum is None and not clearing_endpoint:
        raise ValueError("NO_BOUND")
    if patch.field != "budget" and (patch.currency is not None or patch.basis != "unknown"):
        raise ValueError("INVALID_RANGE_METADATA")

    result = dict(old) if old is not None else {}
    for name, _, clear in endpoints:
        if clear:
            result[name] = None
    if patch.field == "budget":
        # Ordinary purchase searches use the app's UAE cash-price defaults. An
        # explicit ambiguity is handled before applying patches; absent optional
        # metadata alone must not turn a understood amount into a buyer question.
        if patch.basis == "monthly_finance":
            raise ValueError("BUDGET_BASIS")
        currency = patch.currency or result.get("currency") or "AED"
        if old and currency != old["currency"]:
            # A currency change must restate every surviving bound. Never carry an
            # old number into a different currency or perform implicit conversion.
            if patch.operation != "correct" or any(
                result.get(name) is not None and token is None
                for name, token in (("minimum", patch.minimum), ("maximum", patch.maximum))
            ):
                raise ValueError("BUDGET_CURRENCY")
            result = {}
        result.update(currency=currency, basis="cash")
    elif patch.field == "mileage_km":
        if re.search(r"\b(?:miles?|mi)\b", patch.quote, re.I):
            raise ValueError("MILEAGE_UNIT")
        if old is None and not re.search(r"\b(?:km|kilomet\w*)\b", patch.quote, re.I):
            raise ValueError("MILEAGE_UNIT")

    for name, token in (("minimum", patch.minimum), ("maximum", patch.maximum)):
        if token is None:
            continue
        numeric_quote = patch.quote
        if clarified:
            if _NUMBER.search(message):
                # A new amount supersedes the earlier clarification request.
                numeric_quote = message
            elif not _contains(token.text, numeric_quote):
                numeric_quote = prior_request
        if patch.field == "years" and not re.fullmatch(r"\d{4}", token.text):
            raise ValueError("YEAR_TOKEN")
        if not any(
            match.group().strip().casefold() == token.text.strip().casefold()
            for match in _NUMBER.finditer(numeric_quote)
        ):
            # Word boundaries alone allow 20 inside 20,000 or 40 inside 40.001.
            # Bind the entire numeric lexeme before converting it to integer units.
            raise ValueError("UNSUPPORTED_NUMBER")
        number = _number(
            token, numeric_quote, cash=patch.field == "budget", lower=name == "minimum"
        )
        previous = result.get(name)
        if patch.operation == "refine" and previous is not None:
            number = max(previous, number) if name == "minimum" else min(previous, number)
        result[name] = number
    schema = BudgetRange if patch.field == "budget" else IntegerRange
    filters[patch.field] = schema.model_validate(result).model_dump(mode="json")


def apply_search_intent(
    current: SearchCriteria,
    intent: TurnIntent,
    message: str,
    *,
    clarification_targets: tuple[str, ...] = (),
    prior_request: str = "",
) -> CriteriaTransition:
    """Apply a complete semantic read proposal atomically, retaining unrelated filters.

    Exact quotes prove which buyer input was interpreted, not that a fixed verb was
    present. Text values may be normalized aliases or spelling corrections. Whether
    a phrase is negated, hypothetical, additive or corrective belongs to interpretation.
    """
    if (
        intent.operation not in {"search", "question", "analyze"}
        or intent.scope not in {"session", "hypothetical"}
        or intent.deferred
        or intent.collection is not None
    ):
        return CriteriaTransition(current, current, issue("query", "meaning"))
    if intent.problem is not None:
        return CriteriaTransition(current, current, issue(intent.problem_target, intent.problem))

    fields = ["reset" if isinstance(patch, ResetPatch) else patch.field for patch in intent.patches]
    if len(fields) != len(set(fields)):
        return CriteriaTransition(current, current, issue("query"))
    # A reset creates the base; subsequent field changes do not depend on the JSON
    # patch ordering. Nothing is committed until every proposed field validates.
    values = (SearchCriteria() if "reset" in fields else current).model_dump(mode="json")
    target: Target = "query"
    try:
        for patch in intent.patches:
            target = "query" if isinstance(patch, ResetPatch) else patch.field
            clarified = target in clarification_targets
            if not patch.quote.strip() or (
                patch.quote not in message and not (clarified and patch.quote in prior_request)
            ):
                raise ValueError("UNCITED_CHANGE")
            if isinstance(patch, TextPatch):
                _text(values, patch)
            elif isinstance(patch, RangePatch):
                _range(values, patch, message, clarified=clarified, prior_request=prior_request)
        effective = SearchCriteria.model_validate(values)
    except (ValueError, ValidationError) as error:
        reason = {"BUDGET_CURRENCY": "currency", "BUDGET_BASIS": "basis"}.get(
            str(error), "conflict"
        )
        return CriteriaTransition(current, current, issue(target, reason))
    retained = effective if intent.scope == "session" else current
    return CriteriaTransition(effective, retained, None)
