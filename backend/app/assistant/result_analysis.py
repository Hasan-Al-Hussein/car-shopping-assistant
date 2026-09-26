"""Pure arithmetic over trusted inventory results for a model-selected question.

The coordinator chooses the field, operation and exact result scope. This module
does not infer intent from user wording or accept model-authored vehicle facts.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    CashMoney,
    KnownFact,
    ListingDetail,
    ListingResult,
    ListingSummary,
    UnknownFact,
)
from app.api.schemas.sessions import AnswerEvidence

from .answer_assembly import GroundedAnswer
from .grounding import (
    LABELS,
    EvidenceBindings,
    Fact,
    FactualClaimReference,
    GroundingError,
    fact_for,
    key,
    value_text,
)
from .output_policy import safe_assistant_text

AnalysisField = Literal["year", "cash_price", "mileage_km"]
AnalysisOperation = Literal["count_known", "minimum", "maximum"]
_ITEM: TypeAdapter[ListingResult | ListingSummary] = TypeAdapter(ListingResult | ListingSummary)
_MAX_ITEMS = 200
_PUBLIC_EVIDENCE_LIMIT = 10
_DISPLAY_WINNERS = 5
_DESCRIPTIONS = {
    "year": "an exact, unambiguous model year",
    "cash_price": "a clearly stated cash price",
    "mileage_km": "an exact, unambiguous mileage",
}
_EXTREMES = {
    ("year", "minimum"): "oldest stated model year",
    ("year", "maximum"): "newest stated model year",
    ("cash_price", "minimum"): "lowest stated cash price",
    ("cash_price", "maximum"): "highest stated cash price",
    ("mileage_km", "minimum"): "lowest stated mileage",
    ("mileage_km", "maximum"): "highest stated mileage",
}


@dataclass(frozen=True)
class AnalysisResult:
    answer: GroundedAnswer
    selected_refs: tuple[InventoryRef, ...]
    examined_count: int
    eligible_count: int


@dataclass(frozen=True)
class _Operand:
    ref: InventoryRef
    summary: ListingSummary | None
    fact: Fact
    evidence_ids: tuple[str, ...]

    @property
    def number(self) -> int | None:
        if not isinstance(self.fact, KnownFact) or self.fact.qualifier != "exact":
            return None
        value = self.fact.value
        if isinstance(value, CashMoney):
            return value.minor_units
        if type(value) is int:
            return value
        raise GroundingError("INVALID_NUMERIC_FACT")


def _checked(
    items: tuple[ListingResult | ListingSummary, ...],
    expected_refs: tuple[InventoryRef, ...],
    field: AnalysisField,
) -> tuple[list[_Operand], EvidenceBindings, bool]:
    if len(items) > _MAX_ITEMS:
        raise GroundingError("ANALYSIS_SCOPE_LIMIT")
    try:
        wanted = tuple(InventoryRef.model_validate(ref.model_dump()) for ref in expected_refs)
        copies = [_ITEM.validate_python(item.model_dump(mode="json")) for item in items]
    except (AttributeError, ValidationError):
        raise GroundingError("INVALID_TYPED_RESPONSE") from None
    expected_keys = [key(ref) for ref in wanted]
    if len(set(expected_keys)) != len(expected_keys):
        raise GroundingError("DUPLICATE_ANALYSIS_REFERENCE")
    refs = [item.listing.ref if isinstance(item, ListingDetail) else item.ref for item in copies]
    if [key(ref) for ref in refs] != expected_keys:
        raise GroundingError("WRONG_ANALYSIS_ORDER")
    if len({(ref.namespace, ref.snapshot_id) for ref in refs}) > 1:
        raise GroundingError("MIXED_ANALYSIS_SNAPSHOTS")
    bindings = EvidenceBindings()
    operands: list[_Operand] = []
    historical = False
    for item, ref in zip(copies, refs, strict=True):
        if isinstance(item, ListingSummary | ListingDetail):
            for attribute in LABELS:
                bindings.bind(ref, attribute, fact_for(item, attribute))
            fact = fact_for(item, field)
            summary = item.listing if isinstance(item, ListingDetail) else item
            historical |= isinstance(item, ListingDetail) and item.state == "historical"
        else:
            fact = UnknownFact(status="unknown", reason="unsupported")
            summary = None
        operands.append(_Operand(ref, summary, fact, bindings.bind(ref, field, fact)))
    return operands, bindings, historical


def _name(operand: _Operand) -> tuple[str, tuple[str, ...]]:
    summary = operand.summary
    if summary is not None and all(
        isinstance(fact, KnownFact) and fact.qualifier == "exact"
        for fact in (summary.make, summary.model)
    ):
        assert isinstance(summary.make, KnownFact) and isinstance(summary.model, KnownFact)
        name = safe_assistant_text(" ".join(f"{summary.make.value} {summary.model.value}".split()))
        if len(name) <= 100:
            return name.title(), ("make", "model")
    return f"Listing {operand.ref.source_id}", ()


def analyze_results(
    items: tuple[ListingResult | ListingSummary, ...],
    *,
    expected_refs: tuple[InventoryRef, ...],
    field: AnalysisField,
    operation: AnalysisOperation,
    scope_label: str,
    complete_scope: bool,
) -> AnalysisResult:
    """Analyze the exact supplied scope without relaxing evidence or converting currencies.

    Counts select all eligible rows. Extrema select all tied winners, grouped by
    currency for prices. Missing/error rows remain examined but are not eligible.
    Evidence is capped for the public DTO; internal claims retain every operand.
    """
    if field not in _DESCRIPTIONS or operation not in {"count_known", "minimum", "maximum"}:
        raise GroundingError("UNSUPPORTED_ANALYSIS")
    if (
        not isinstance(scope_label, str)
        or not scope_label.strip()
        or len(scope_label) > 200
        or any(ord(char) < 32 for char in scope_label)
        or type(complete_scope) is not bool
    ):
        raise GroundingError("INVALID_ANALYSIS_SCOPE")
    operands, bindings, historical = _checked(items, expected_refs, field)
    eligible = [row for row in operands if row.number is not None]
    count, known = len(operands), len(eligible)
    scope = safe_assistant_text(scope_label.strip())
    noun = "car" if count == 1 else "cars"
    scope_text = f"the {count} {noun} {'in' if complete_scope else 'checked from'} {scope}"
    lines: list[str] = []
    names: list[tuple[_Operand, tuple[str, ...], str]] = []
    selected: list[_Operand] = []
    if operation == "count_known":
        lines.append(
            f"{known} of {scope_text} {'has' if known == 1 else 'have'} {_DESCRIPTIONS[field]}."
        )
        selected = eligible
    elif not eligible:
        lines.append(f"None of {scope_text} have {_DESCRIPTIONS[field]} to compare.")
    else:
        groups: dict[str, list[_Operand]] = {}
        for row in eligible:
            assert isinstance(row.fact, KnownFact)
            currency = row.fact.value.currency if isinstance(row.fact.value, CashMoney) else ""
            groups.setdefault(currency, []).append(row)
        lines.append(f"Among {scope_text}:")
        if len(groups) > 1:
            lines.append(
                "Prices use different currencies, so there is no single cross-currency ranking. "
                "Here are the results within each currency:"
            )
        selected_keys: set[tuple[str, str, str]] = set()
        displayed = 0
        for group in groups.values():
            numbers = [row.number for row in group]
            exact_numbers = [value for value in numbers if value is not None]
            extreme = min(exact_numbers) if operation == "minimum" else max(exact_numbers)
            winners = [row for row in group if row.number == extreme]
            selected_keys.update(key(row.ref) for row in winners)
            shown = winners[: max(0, _DISPLAY_WINNERS - displayed)]
            displayed += len(shown)
            for row in shown:
                assert isinstance(row.fact, KnownFact)
                name, attributes = _name(row)
                text = (
                    f"{name} {'ties for' if len(winners) > 1 else 'has'} the "
                    f"{_EXTREMES[field, operation]}: {value_text(row.fact.value, field)}."
                )
                lines.append(text)
                names.append((row, attributes, text))
        selected = [row for row in eligible if key(row.ref) in selected_keys]
        if len(selected) > displayed:
            lines.append(
                f"{len(selected) - displayed} additional cars also qualify "
                "within their currency group."
                if field == "cash_price" and len(groups) > 1
                else f"{len(selected) - displayed} additional cars share this value."
            )
    if count > known:
        lines.append(
            f"{count - known} {'car was' if count - known == 1 else 'cars were'} excluded "
            "because the value is missing, conflicting, approximate or could not be read."
        )
    if not complete_scope:
        lines.append("This covers only the records checked, not the full selection.")
    if historical:
        lines.append("Some results are historical source records.")
    lines.append("These are listing facts; current availability is not verified.")
    text = "\n\n".join(lines)
    # Each operand contributes to this derived statement, including excluded facts.
    claims = [
        FactualClaimReference(key(row.ref), field, row.evidence_ids, row.fact.status, text)
        for row in operands
    ]
    for row, attributes, sentence in names:
        assert row.summary is not None
        for attribute in attributes:
            fact = fact_for(row.summary, attribute)
            claims.append(
                FactualClaimReference(
                    key(row.ref), attribute, bindings.bind(row.ref, attribute, fact),
                    fact.status, sentence,
                )
            )
    prioritized = list(dict.fromkeys([key(row.ref) for row in (*selected, *operands)]))
    evidence = tuple(
        AnswerEvidence(
            ref=InventoryRef(namespace=ref[0], snapshot_id=ref[1], source_id=ref[2]),
            attributes=list(dict.fromkeys(claim.attribute for claim in claims if claim.ref == ref)),
        )
        for ref in prioritized[:_PUBLIC_EVIDENCE_LIMIT]
    )
    if len(text) > 11000:
        raise GroundingError("ANSWER_LIMIT")
    return AnalysisResult(
        GroundedAnswer(text, evidence, tuple(claims)),
        tuple(row.ref for row in selected),
        count,
        known,
    )
