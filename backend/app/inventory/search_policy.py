"""Explicit bounded literal lexical policy; typed filters alone express ranges."""

import re
from dataclasses import dataclass

from pydantic import ValidationError

from app.api.schemas.inventory import SearchCriteria
from app.core.errors import ApiFailure
from app.inventory.snapshot_codec import canonical_json, digest_text

RANKING_VERSION = "literal-terms-soft-count-source-id-1"
MAX_TOKENS = 24
MAX_TOKEN_LENGTH = 100
MAX_SEARCH_RECORDS = 100
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
NEGATION = frozenset(
    {"no", "not", "without", "except", "exclude", "excluding", "بدون", "غير", "لا"}
)
RANGE_WORDS = frozenset({"under", "over", "below", "above", "between", "cheaper", "budget"})
UNSUPPORTED_ATTRIBUTES = frozenset(
    {"accident", "accidents", "reliable", "reliability", "available"}
)
UNARY_EXCLUSION = re.compile(r"(?:^|[\s(\[{])[!\-−](?=\S)")


def fold(value: str) -> str:
    # Only existing whitespace/case equivalence; no automotive name substitution.
    return " ".join(value.split()).casefold()


def literal_tokens(value: str) -> tuple[str, ...]:
    tokens = tuple(sorted(set(TOKEN.findall(fold(value)))))
    if len(tokens) > MAX_TOKENS or any(len(token) > MAX_TOKEN_LENGTH for token in tokens):
        raise ApiFailure("VALIDATION_ERROR")
    return tokens


@dataclass(frozen=True, slots=True)
class SearchPolicy:
    criteria: SearchCriteria
    criteria_hash: str
    terms: tuple[str, ...]
    preferences: tuple[str, ...]
    unsupported: tuple[str, ...]


def normalize_criteria(criteria: SearchCriteria) -> SearchPolicy:
    # Validate even trusted callers; model_copy is not a validation boundary.
    try:
        data = SearchCriteria.model_validate(criteria.model_dump()).model_dump(mode="json")
    except ValidationError as exc:
        raise ApiFailure("VALIDATION_ERROR") from exc
    data["query"] = fold(data["query"])
    for name, values in data["filters"].items():
        if isinstance(values, list):
            normalized = sorted({fold(value) for value in values})
            if any(not value for value in normalized):
                raise ApiFailure("VALIDATION_ERROR")
            data["filters"][name] = normalized
    data["soft_preferences"] = sorted({fold(value) for value in data["soft_preferences"]})
    if any(not value for value in data["soft_preferences"]):
        raise ApiFailure("VALIDATION_ERROR")
    try:
        normalized_criteria = SearchCriteria.model_validate(data)
    except ValidationError as exc:
        raise ApiFailure("VALIDATION_ERROR") from exc
    terms = literal_tokens(normalized_criteria.query)
    preferences = literal_tokens(" ".join(normalized_criteria.soft_preferences))
    unsupported = []
    if set(terms) & NEGATION or UNARY_EXCLUSION.search(normalized_criteria.query):
        unsupported.append("query:negation_requires_clarification")
    if set(terms) & RANGE_WORDS or any(char in normalized_criteria.query for char in "<>=≠≤≥"):
        unsupported.append("query:use_explicit_range_filters")
    if set(terms) & UNSUPPORTED_ATTRIBUTES:
        unsupported.append("query:unverified_attribute")
    if normalized_criteria.query and not terms:
        unsupported.append("query:no_supported_literal_terms")
    # Reject unsupported preferences explicitly instead of silently ignoring their meaning.
    preference_text = " ".join(normalized_criteria.soft_preferences)
    if (
        set(preferences) & (NEGATION | RANGE_WORDS | UNSUPPORTED_ATTRIBUTES)
        or UNARY_EXCLUSION.search(preference_text)
        or any(char in preference_text for char in "<>=≠≤≥")
    ):
        raise ApiFailure("VALIDATION_ERROR")
    return SearchPolicy(
        normalized_criteria,
        digest_text(canonical_json(normalized_criteria.model_dump(mode="json"))),
        terms,
        preferences,
        tuple(unsupported),
    )
