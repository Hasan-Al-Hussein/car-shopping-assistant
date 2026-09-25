"""Deterministic DTO-to-answer assembly; internal traces, existing public contracts."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    BudgetRange,
    CashMoney,
    ComparisonRequest,
    ComparisonResult,
    FitReason,
    HandoffSummary,
    IntegerRange,
    KnownFact,
    ListingDetail,
    ListingResult,
    ListingSummary,
    SearchCriteria,
    SearchRequest,
    SearchResult,
    UnresolvedQuestion,
)
from app.api.schemas.sessions import AnswerEvidence

from .grounding import (
    LABELS,
    EvidenceBindings,
    FactualClaimReference,
    GroundingError,
    fact_for,
    key,
    locators,
    render_fact,
)

_LISTING: TypeAdapter[ListingResult] = TypeAdapter(ListingResult)
DEFAULT_ATTRIBUTES = ("make", "model", "year", "cash_price", "mileage_km", "warranty")
SEARCH_SUMMARY_LIMIT = 5
_FILTERS = {
    "makes": "make",
    "models": "model",
    "trims": "trim",
    "years": "year",
    "budget": "cash_price",
    "mileage_km": "mileage_km",
    "body_types": "body_type",
    "fuel_types": "fuel_type",
    "transmissions": "transmission",
}


@dataclass(frozen=True)
class GroundedAnswer:
    """Internal assembly result; copy text/evidence into the existing MessageResult later."""

    text: str
    evidence: tuple[AnswerEvidence, ...]
    claims: tuple[FactualClaimReference, ...]
    handoff_summary: HandoffSummary | None = None


def _copy[T: BaseModel](model: type[T], value: T) -> T:
    try:
        return model.model_validate(value.model_dump(mode="json"))
    except ValidationError:
        raise GroundingError("INVALID_TYPED_RESPONSE") from None


def _listing(value: ListingResult) -> ListingResult:
    try:
        return _LISTING.validate_python(value.model_dump(mode="json"))
    except ValidationError:
        raise GroundingError("INVALID_TYPED_RESPONSE") from None


def _ref(value: ListingResult) -> InventoryRef:
    return value.listing.ref if isinstance(value, ListingDetail) else value.ref


def _attributes(attributes: tuple[str, ...], *, maximum: int = 12) -> tuple[str, ...]:
    if (
        not attributes
        or len(attributes) > maximum
        or len(set(attributes)) != len(attributes)
        or any(attribute not in LABELS for attribute in attributes)
    ):
        raise GroundingError("UNSUPPORTED_ATTRIBUTE_SET")
    return attributes


def _finish(
    lines: list[str],
    claims: list[FactualClaimReference],
    handoff: HandoffSummary | None = None,
) -> GroundedAnswer:
    text = "\n".join(lines)
    if len(text) > 11000:
        raise GroundingError("ANSWER_LIMIT")
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for claim in claims:
        if claim.text not in text:
            raise GroundingError("CLAIM_TEXT_NOT_RENDERED")
        attributes = grouped.setdefault(claim.ref, [])
        if claim.attribute not in attributes:
            attributes.append(claim.attribute)
    evidence = tuple(
        AnswerEvidence(
            ref=InventoryRef(namespace=ref[0], snapshot_id=ref[1], source_id=ref[2]),
            attributes=attributes,
        )
        for ref, attributes in grouped.items()
    )
    return GroundedAnswer(text, evidence, tuple(claims), handoff)


def _facts(
    item: ListingSummary | ListingDetail,
    attributes: tuple[str, ...],
    bindings: EvidenceBindings,
) -> list[FactualClaimReference]:
    ref = item.listing.ref if isinstance(item, ListingDetail) else item.ref
    # Validate all supplied public evidence in this rendered car, not model-selected IDs.
    for attribute in LABELS:
        bindings.bind(ref, attribute, fact_for(item, attribute))
    return [
        render_fact(ref, attribute, fact_for(item, attribute), bindings) for attribute in attributes
    ]


def _car(
    result: ListingResult,
    number: int,
    attributes: tuple[str, ...],
    bindings: EvidenceBindings,
) -> tuple[list[str], list[FactualClaimReference]]:
    if not isinstance(result, ListingDetail):
        status = (
            "The exact requested listing is missing; no substitute is selected."
            if result.state == "missing"
            else "The exact requested listing could not be read; no vehicle facts are asserted."
        )
        return [f"Car {number}: {status}"], []
    context = (
        "historical source record; this is not a current listing check"
        if result.state == "historical"
        else "supplied listing claims; live stock and vehicle condition "
        "are not independently verified"
    )
    claims = _facts(result, attributes, bindings)
    return [f"Car {number}: {context}.", "", *(claim.text for claim in claims)], claims


def assemble_listing(
    result: ListingResult,
    *,
    expected_ref: InventoryRef,
    attributes: tuple[str, ...] = DEFAULT_ATTRIBUTES,
) -> GroundedAnswer:
    item, expected = _listing(result), _copy(InventoryRef, expected_ref)
    if key(_ref(item)) != key(expected):
        raise GroundingError("WRONG_LISTING")
    lines, claims = _car(item, 1, _attributes(attributes), EvidenceBindings())
    return _finish(lines, claims)


def assemble_comparison(
    result: ComparisonResult,
    *,
    request: ComparisonRequest,
    attributes: tuple[str, ...] = DEFAULT_ATTRIBUTES,
) -> GroundedAnswer:
    checked, wanted = _copy(ComparisonResult, result), _copy(ComparisonRequest, request)
    if [key(_ref(item)) for item in checked.items] != [key(ref) for ref in wanted.refs]:
        raise GroundingError("WRONG_COMPARISON_ORDER")
    attributes = _attributes(attributes, maximum=6)
    bindings = EvidenceBindings()
    lines: list[str] = []
    claims: list[FactualClaimReference] = []
    for number, item in enumerate(checked.items, 1):
        car_lines, car_claims = _car(item, number, attributes, bindings)
        if lines:
            lines.append("")
        lines.extend(car_lines)
        claims.extend(car_claims)
    return _finish(lines, claims)


def assemble_search(result: SearchResult, *, request: SearchRequest) -> GroundedAnswer:
    checked, wanted = _copy(SearchResult, result), _copy(SearchRequest, request)
    criteria = SearchCriteria.model_validate(
        wanted.model_dump(
            mode="json",
            exclude={"snapshot_id", "page_size", "cursor", "client_request_id"},
        )
    )
    if (
        checked.client_request_id != wanted.client_request_id
        or checked.applied_criteria != criteria
    ):
        raise GroundingError("WRONG_SEARCH_CONTEXT")
    if wanted.snapshot_id is not None and checked.presentation.snapshot_id != wanted.snapshot_id:
        raise GroundingError("WRONG_SEARCH_SNAPSHOT")
    if checked.state == "no_supported_matches":
        reason = (
            "Some requested conditions cannot be checked from these listings, "
            "so I cannot confirm any matches."
            if checked.unsupported_constraints
            else "No matching cars found in the supplied listings."
        )
        return _finish([reason, "Your search conditions have not been changed."], [])
    noun = "car" if checked.supported_total == 1 else "cars"
    lines = [f"Found {checked.supported_total} matching {noun} in the supplied listings."]
    if checked.supported_total != len(checked.items):
        lines.append(f"This result page contains {len(checked.items)}.")
    bindings = EvidenceBindings()
    claims: list[FactualClaimReference] = []
    for number, item in enumerate(checked.items[:SEARCH_SUMMARY_LIMIT], 1):
        rendered = _facts(item, ("make", "model", "year", "cash_price"), bindings)
        lines.extend(
            [
                "",
                f"{number}. " + " ".join(claim.text for claim in rendered[:3]),
                f"   {rendered[3].text}",
            ]
        )
        claims.extend(rendered)
    if len(checked.items) > SEARCH_SUMMARY_LIMIT:
        lines.append(
            f"\nThe first {SEARCH_SUMMARY_LIMIT} cars are summarized here; "
            "the attached results include the rest of this page."
        )
    if checked.next_cursor is not None:
        lines.append("More matches are available on the next result page.")
    lines.extend(["", "Confirm current availability and condition with the seller."])
    return _finish(lines, claims)


def _fits(fact: object, condition: object) -> Literal["fit", "unmet", "unverified"]:
    if not isinstance(fact, KnownFact) or fact.qualifier != "exact":
        return "unverified"
    value = fact.value
    if isinstance(condition, list) and isinstance(value, str):
        return (
            "fit"
            if value.casefold().strip() in {item.casefold().strip() for item in condition}
            else "unmet"
        )
    if isinstance(condition, BudgetRange):
        if not isinstance(value, CashMoney) or value.currency != condition.currency:
            return "unverified"
        value = value.minor_units
    if isinstance(condition, IntegerRange) and type(value) is int:
        within = (condition.minimum is None or value >= condition.minimum) and (
            condition.maximum is None or value <= condition.maximum
        )
        return "fit" if within else "unmet"
    return "unverified"


def assemble_handoff(
    source: HandoffSummary,
    *,
    expected_ref: InventoryRef,
    criteria: SearchCriteria,
) -> GroundedAnswer:
    """Recompute explanations; never trust incoming fit/unresolved free-text narratives."""
    checked = _copy(HandoffSummary, source)
    if key(checked.selected_ref) != key(_copy(InventoryRef, expected_ref)):
        raise GroundingError("WRONG_HANDOFF_LISTING")
    if checked.expressed_criteria != _copy(SearchCriteria, criteria):
        raise GroundingError("WRONG_HANDOFF_CRITERIA")
    item, criteria = checked.listing, checked.expressed_criteria
    conditions = [
        (field, attribute, getattr(criteria.filters, field))
        for field, attribute in _FILTERS.items()
        if getattr(criteria.filters, field)
    ]
    attributes = tuple(
        dict.fromkeys(
            (
                *DEFAULT_ATTRIBUTES,
                *(attribute for _, attribute, _ in conditions),
            )
        )
    )
    lines, claims = _car(item, 1, _attributes(attributes), EvidenceBindings())
    fits: list[FitReason] = []
    unresolved: list[UnresolvedQuestion] = []
    for field, attribute, condition in conditions:
        fact = fact_for(item, attribute) if isinstance(item, ListingDetail) else None
        state = (
            _fits(fact, condition)
            if isinstance(item, ListingDetail) and item.state == "current"
            else "unverified"
        )
        ids = (
            tuple(dict.fromkeys(locator.evidence_id for locator in locators(fact)))
            if fact is not None
            else ()
        )
        if state == "fit" and len(ids) <= 12:
            text = (
                f"The source-stated {LABELS[attribute]} satisfies "
                f"your stated {LABELS[attribute]} condition."
            )
            fits.append(
                FitReason(
                    criterion=field,
                    attribute=attribute,
                    evidence_ids=list(ids),
                    text=text,
                )
            )
            trace_state: Literal["fit", "unresolved"] = "fit"
        else:
            reason: Literal["unknown", "conflicting", "unverified", "unmet"] = "unverified"
            if state == "unmet":
                reason = "unmet"
            elif fact is not None and fact.status == "conflicting":
                reason = "conflicting"
            elif fact is not None and fact.status == "unknown":
                reason = "unknown"
            text = (
                f"The {LABELS[attribute]} condition is {reason}. "
                "Confirm the exact source value before treating it as a fit."
            )
            unresolved.append(
                UnresolvedQuestion(
                    criterion=field,
                    attribute=attribute,
                    reason=reason,
                    question=text,
                )
            )
            trace_state = "unresolved"
        lines.append(text)
        claims.append(
            FactualClaimReference(
                key(checked.selected_ref),
                attribute,
                ids,
                trace_state,
                text,
            )
        )
    for present, field, text in (
        (
            bool(criteria.query),
            "query",
            "The free-text request is not itself verified vehicle evidence; "
            "identify the listing attribute that matters.",
        ),
        (
            bool(criteria.soft_preferences),
            "soft_preferences",
            "Soft preferences are not verified vehicle qualities; "
            "confirm which measurable attributes matter.",
        ),
        (
            True,
            "warranty",
            "Confirm current warranty terms and validity with the seller before relying on them.",
        ),
    ):
        if present:
            unresolved.append(
                UnresolvedQuestion(
                    criterion=field,
                    attribute=field,
                    reason="unverified",
                    question=text,
                )
            )
            lines.append(text)
    handoff = HandoffSummary(
        selected_ref=checked.selected_ref,
        listing=item,
        expressed_criteria=criteria,
        fit_reasons=fits,
        unresolved_questions=unresolved,
    )
    return _finish(lines, claims, handoff)
