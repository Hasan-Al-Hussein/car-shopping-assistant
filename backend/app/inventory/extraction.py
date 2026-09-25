"""Pure reviewed extraction, conservative resolution and complete family accounting."""

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal

from pydantic import TypeAdapter

from app.api.schemas.inventory import CashPriceFact, IntegerFact, TextFact
from app.inventory.claim_evidence import ReviewedClaim, bind_claim, original_text
from app.inventory.import_reader import WorkbookReadResult
from app.inventory.normalization import NormalizedCandidate, NormalizedListing, normalize_candidate
from app.inventory.references import SnapshotManifest, normalization_manifest
from app.inventory.review_catalogue import (
    EXTRACTION_VERSION,
    FAMILIES,
    PUBLIC_FAMILIES,
    ClaimAnnotation,
    Family,
    RecordReview,
    ReviewCatalogue,
    SourceField,
    SpanSelection,
    TypedValue,
)

SINGLE_VALUE_FAMILIES = frozenset(
    {
        "make",
        "model",
        "trim",
        "year",
        "cash_price",
        "mileage_km",
        "fuel_type",
        "body_type",
        "transmission",
        "location",
        "regional_specs",
        "facelift_year",
    }
)
TEXT_ADAPTER: TypeAdapter[Any] = TypeAdapter(TextFact)
INTEGER_ADAPTER: TypeAdapter[Any] = TypeAdapter(IntegerFact)
CASH_ADAPTER: TypeAdapter[Any] = TypeAdapter(CashPriceFact)


@dataclass(frozen=True)
class ClaimGroup:
    value: TypedValue
    qualifier: str
    claims: tuple[ReviewedClaim, ...]


@dataclass(frozen=True)
class FamilyResolution:
    family: Family
    status: Literal["known", "unknown", "conflicting"]
    disposition: str
    reason: str
    groups: tuple[ClaimGroup, ...]
    claims: tuple[ReviewedClaim, ...]
    strict_match_eligible: bool
    partial_coverage: bool

    def public_fact(self) -> dict[str, Any]:
        if self.family not in PUBLIC_FAMILIES:
            raise ValueError("INTERNAL_FAMILY_HAS_NO_PUBLIC_FACT")
        if self.status == "unknown":
            result: dict[str, Any] = {"status": "unknown", "reason": self.reason}
        else:
            values = []
            for group in self.groups:
                value: Any = group.value.value
                if self.family == "cash_price":
                    value = {
                        "minor_units": value,
                        "currency": group.value.currency,
                        "basis": "cash",
                    }
                locators = [
                    locator.model_dump(mode="json")
                    for claim in group.claims
                    for locator in claim.locators()
                ]
                values.append({"value": value, "qualifier": group.qualifier, "evidence": locators})
            result = (
                {"status": "known", **values[0]}
                if self.status == "known"
                else {"status": "conflicting", "claims": values}
            )
        adapter = (
            CASH_ADAPTER
            if self.family == "cash_price"
            else INTEGER_ADAPTER
            if self.family in {"year", "mileage_km"}
            else TEXT_ADAPTER
        )
        # Serialization validates the unchanged public DTO, never truncates evidence.
        serialized: dict[str, Any] = adapter.validate_python(result).model_dump(mode="json")
        return serialized


@dataclass(frozen=True)
class ExtractedListing:
    normalized: NormalizedListing
    review: RecordReview
    claims: tuple[ReviewedClaim, ...]
    resolutions: tuple[FamilyResolution, ...]

    def fact(self, family: Family) -> FamilyResolution:
        return next(item for item in self.resolutions if item.family == family)


@dataclass(frozen=True)
class ExtractedCandidate:
    manifest: SnapshotManifest
    normalized_source: NormalizedCandidate = field(repr=False)
    catalogue: ReviewCatalogue = field(repr=False)
    records: tuple[ExtractedListing, ...] = field(repr=False)

    def coverage_report(self) -> dict[str, Any]:
        return {
            "status": "reviewed_candidate_unpublished",
            "snapshot_id": self.manifest.snapshot_id,
            "manifest": asdict(self.manifest),
            "normalization_snapshot_id": self.normalized_source.manifest.snapshot_id,
            "review_version": self.catalogue.review_version,
            "selected_count": len(self.records),
            "audit_only_count": len(self.normalized_source.audit_records),
            "published": False,
            "coverage_meaning": (
                "All required families reviewed per record; bounded supported claims, not "
                "exhaustive extraction or independent vehicle verification."
            ),
            "families": {
                family: {
                    status: sum(item.fact(family).status == status for item in self.records)
                    for status in ("known", "unknown", "conflicting")
                }
                for family in FAMILIES
            },
            "records": [
                {
                    "ref": item.normalized.ref.model_dump(),
                    "row": item.normalized.source.row,
                    "photo_state": item.normalized.photo.state,
                    "review_complete": item.review.review_complete,
                    "note": item.review.note,
                    "families": {
                        fact.family: {
                            "status": fact.status,
                            "disposition": fact.disposition,
                            "reason": fact.reason,
                            "strict_match_eligible": fact.strict_match_eligible,
                            "partial_coverage": fact.partial_coverage,
                            "claim_keys": [claim.annotation.key for claim in fact.claims],
                            "omissions": [
                                omission.model_dump(mode="json")
                                for omission in item.review.omissions
                                if omission.family == fact.family
                            ],
                        }
                        for fact in item.resolutions
                    },
                }
                for item in self.records
            ],
        }

    def evidence_ledger(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.manifest.snapshot_id,
            "review_version": self.catalogue.review_version,
            "verification": "source_claim",
            "published": False,
            "records": [
                {
                    "ref": item.normalized.ref.model_dump(),
                    "source_row": item.normalized.source.row,
                    "claims": [
                        {
                            "annotation": claim.annotation.model_dump(mode="json"),
                            "ref": claim.ref.model_dump(),
                            "evidence_review_version": claim.evidence_review_version,
                            "source_python_type": claim.evidence.source.python_type,
                            "source_data_type": claim.evidence.source.data_type,
                            "span_basis": claim.evidence.span_basis,
                            "evidence": [
                                locator.model_dump(mode="json") for locator in claim.locators()
                            ],
                        }
                        for claim in item.claims
                    ],
                }
                for item in self.records
            ],
        }


def _structured(listing: NormalizedListing) -> tuple[ClaimAnnotation, ...]:
    claims = []
    structured_fields: tuple[SourceField, ...] = ("make", "model", "trim", "year")
    for family in structured_fields:
        cell = listing.source.cell(family)
        text = listing.text(family)
        if text.state != "informative" or text.display is None:
            continue
        if family == "year":
            if isinstance(cell.value, bool) or not isinstance(cell.value, (int, float)):
                continue
            if isinstance(cell.value, float) and not cell.value.is_integer():
                continue
            value: str | int = int(cell.value)
        else:
            value = text.display
            if len(value) > 500:
                continue
        original, _ = original_text(cell)
        claims.append(
            ClaimAnnotation.model_validate(
                {
                    "key": f"structured.{family}",
                    "family": family,
                    "source": SpanSelection(source_field=family, quote=original).model_dump(),
                    "value": {"value": value},
                    "role": "model_year" if family == "year" else family,
                    "disposition": "accepted",
                    "reason": (
                        "Structured source label reviewed in complete record context; "
                        "contradictory narrative retained separately. Not independent vehicle "
                        "verification."
                    ),
                }
            )
        )
    return tuple(claims)


def _supported(claim: ReviewedClaim) -> bool:
    item = claim.annotation
    if item.disposition != "accepted" or item.subject != "vehicle" or item.polarity != "positive":
        return False
    value = item.value
    if item.family == "cash_price":
        return (
            item.role == "cash_price"
            and type(value.value) is int
            and 0 <= value.value <= 10**12
            and value.unit == "minor_units"
            and value.currency is not None
            and value.basis == "cash"
        )
    if item.family == "mileage_km":
        return (
            item.role == "vehicle_mileage"
            and type(value.value) is int
            and value.value >= 0
            and value.unit == "km"
        )
    if item.family == "year":
        return (
            item.role == "model_year" and type(value.value) is int and 1000 <= value.value <= 9999
        )
    if item.family in PUBLIC_FAMILIES:
        return isinstance(value.value, str)
    return True


def _value_key(item: ClaimAnnotation) -> str:
    data = item.value.model_dump()
    if isinstance(data["value"], str):
        # Only whitespace/case equivalence, never automotive aliases or correction.
        data["value"] = " ".join(data["value"].split()).casefold()
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _group(claims: tuple[ReviewedClaim, ...]) -> tuple[ClaimGroup, ...]:
    grouped: dict[tuple[str, str], list[ReviewedClaim]] = {}
    for claim in claims:
        grouped.setdefault((_value_key(claim.annotation), claim.annotation.qualifier), []).append(
            claim
        )
    return tuple(
        ClaimGroup(items[0].annotation.value, items[0].annotation.qualifier, tuple(items))
        for _, items in sorted(grouped.items())
    )


def _conflicts(family: Family, claims: tuple[ReviewedClaim, ...]) -> bool:
    if family in SINGLE_VALUE_FAMILIES:
        # Non-exact/bounded claims cannot manufacture a contradiction with exact claims.
        comparable = [item for item in claims if item.annotation.qualifier == "exact"]
        by_basis: dict[tuple[str | None, str | None, str | None], set[str]] = {}
        for item in comparable:
            value = item.annotation.value
            by_basis.setdefault((value.unit, value.currency, value.basis), set()).add(
                _value_key(item.annotation)
            )
        return any(len(values) > 1 for values in by_basis.values())
    if family == "engine":
        return (
            len(
                {
                    _value_key(item.annotation)
                    for item in claims
                    if item.annotation.role == "configuration"
                    and item.annotation.qualifier == "exact"
                }
            )
            > 1
        )
    if family == "service_history":
        # Only explicitly reviewed mutually exclusive completeness claims conflict.
        # Different free-text history descriptions can be complementary.
        return (
            len(
                {
                    _value_key(item.annotation)
                    for item in claims
                    if item.annotation.role == "history_completeness"
                    and item.annotation.qualifier == "exact"
                }
            )
            > 1
        )
    return False


def _public_bounds_exceeded(family: Family, groups: tuple[ClaimGroup, ...]) -> bool:
    if family not in PUBLIC_FAMILIES:
        return False
    return (
        len(groups) > 20
        or any(
            isinstance(group.value.value, str) and len(group.value.value) > 200 for group in groups
        )
        or any(sum(len(claim.locators()) for claim in group.claims) > 20 for group in groups)
    )


def resolve_family(
    family: Family, claims: tuple[ReviewedClaim, ...], review: RecordReview
) -> FamilyResolution:
    all_claims = tuple(item for item in claims if item.annotation.family == family)
    accepted = tuple(item for item in all_claims if _supported(item))
    partial = any(item.family == family for item in review.omissions)
    hold = next((item for item in review.holds if item.family == family), None)

    def unknown(disposition: str, reason: str = "unsupported") -> FamilyResolution:
        return FamilyResolution(
            family, "unknown", disposition, reason, (), all_claims, False, partial
        )

    if hold is not None:
        return unknown("review_hold")
    if any(
        item.annotation.subject != "dealer" and item.annotation.polarity == "negative"
        for item in all_claims
    ):
        # The public categorical contract has no polarity member. Preserve negative
        # evidence internally and withhold rather than erase it or invent a boolean.
        return unknown("negative_or_contradictory_claim_unresolved")
    if _conflicts(family, accepted):
        # Engine conflict includes just comparable configurations, not unrelated power/size.
        conflict_claims = accepted
        if family == "engine":
            conflict_claims = tuple(
                item for item in accepted if item.annotation.role == "configuration"
            )
        if family == "service_history":
            conflict_claims = tuple(
                item for item in accepted if item.annotation.role == "history_completeness"
            )
        groups = _group(conflict_claims)
        if _public_bounds_exceeded(family, groups):
            return unknown("public_representation_bound_exceeded")
        return FamilyResolution(
            family,
            "conflicting",
            "unresolved_source_conflict",
            "source_claims_disagree",
            groups,
            all_claims,
            False,
            partial,
        )
    # A structured label never overrides unresolved contradictory/uncertain vehicle prose.
    if any(
        item.annotation.subject != "dealer"
        and item.annotation.disposition in {"ambiguous", "unreviewed"}
        for item in all_claims
    ) and family in {*SINGLE_VALUE_FAMILIES, *PUBLIC_FAMILIES}:
        return unknown("ambiguous_or_unreviewed")
    if not accepted:
        if all_claims:
            dispositions = {item.annotation.disposition for item in all_claims}
            return unknown(
                "unsupported_typed_or_negative_claim"
                if dispositions == {"accepted"}
                else "_or_".join(sorted(dispositions))
            )
        if partial:
            return unknown("reviewed_omission")
        if family in {"make", "model", "trim", "year"}:
            return unknown("unavailable_structured_label", "unparseable")
        return unknown("not_stated", "not_stated")
    groups = _group(accepted)
    if family in PUBLIC_FAMILIES and (
        any(
            item.annotation.subject != "dealer" and item.annotation.disposition == "conditional"
            for item in all_claims
        )
        or any(
            condition.kind in {"scope", "option", "temporal", "down_payment", "finance_term"}
            for claim in accepted
            for condition in claim.annotation.conditions
        )
    ):
        return unknown("conditional_value_not_strict")
    if family in SINGLE_VALUE_FAMILIES and len(groups) != 1:
        return unknown("incompatible_qualifiers_or_conditions")
    if family in PUBLIC_FAMILIES and family not in SINGLE_VALUE_FAMILIES:
        # Complementary service/warranty clauses are combined with all linked evidence;
        # no arbitrary text inequality creates a false conflict.
        combined = "; ".join(str(group.value.value) for group in groups)
        qualifiers = {group.qualifier for group in groups}
        if len(qualifiers) != 1:
            return unknown("incompatible_qualifiers_or_conditions")
        groups = (
            (ClaimGroup(TypedValue(value=combined), next(iter(qualifiers)), accepted),)
            if len(combined) <= 200
            else ()
        )
        if not groups:
            return unknown("public_text_bound_exceeded")
    if _public_bounds_exceeded(family, groups):
        return unknown("public_representation_bound_exceeded")
    strict = family in SINGLE_VALUE_FAMILIES and all(group.qualifier == "exact" for group in groups)
    # Conditional claims stay in the ledger and cannot silently qualify strict filters.
    if any(
        item.annotation.subject != "dealer" and item.annotation.disposition == "conditional"
        for item in all_claims
    ):
        strict = False
    if any(
        condition.kind in {"scope", "option", "temporal", "down_payment", "finance_term"}
        for claim in accepted
        for condition in claim.annotation.conditions
    ):
        strict = False
    return FamilyResolution(
        family,
        "known",
        "supported_partial" if partial else "supported",
        "reviewed_source_claim",
        groups,
        all_claims,
        strict,
        partial,
    )


def extract_reviewed(
    candidate: NormalizedCandidate, catalogue: ReviewCatalogue
) -> ExtractedCandidate:
    # Revalidate externally supplied Pydantic instances, including model_copy updates.
    catalogue = ReviewCatalogue.model_validate(catalogue.model_dump(mode="python"))
    if catalogue.review_state != "approved" or not all(
        item.review_complete for item in catalogue.records
    ):
        raise ValueError("EXTRACTION_REQUIRES_APPROVED_REVIEW")
    if candidate.manifest != normalization_manifest(candidate.source_manifest):
        raise ValueError("EXTRACTION_REQUIRES_NORMALIZATION_CANDIDATE")
    reconstructed = normalize_candidate(
        WorkbookReadResult(
            candidate.source_manifest,
            candidate.reader_report,
            tuple(item.source for item in candidate.records),
            candidate.audit_records,
        )
    )
    expected = {item.ref.source_id: item for item in reconstructed.records}
    audit_rows = sum(
        sheet.meaningful_rows
        for sheet in candidate.reader_report.sheets
        if sheet.role == "audit_only"
    )
    if audit_rows != len(candidate.audit_records) or any(
        expected.get(item.ref.source_id) != item for item in candidate.records
    ):
        raise ValueError("REVIEW_PROVENANCE_MISMATCH")
    if (
        catalogue.namespace,
        catalogue.workbook_sha256,
        catalogue.sheet,
        catalogue.extraction_version,
    ) != (
        candidate.manifest.namespace,
        candidate.manifest.workbook_sha256,
        candidate.manifest.sheet,
        EXTRACTION_VERSION,
    ):
        raise ValueError("REVIEW_SOURCE_MISMATCH")
    by_id = {item.source_id: item for item in catalogue.records}
    if set(by_id) != {item.ref.source_id for item in candidate.records} or len(
        candidate.records
    ) != len(by_id):
        raise ValueError("REVIEW_POPULATION_MISMATCH")
    review_version = catalogue.review_version
    manifest = replace(
        candidate.manifest,
        extraction_version=EXTRACTION_VERSION,
        evidence_review_version=review_version,
    )
    listings = []
    for original in candidate.records:
        review = by_id[original.ref.source_id]
        if (
            original.ref != candidate.manifest.reference(original.source.source_id or "")
            or review.source_row != original.source.row
            or original.source.sheet != catalogue.sheet
        ):
            raise ValueError("REVIEW_RECORD_BINDING_MISMATCH")
        listing = replace(original, ref=manifest.reference(review.source_id))
        annotations = (*_structured(listing), *review.claims)
        claims = tuple(
            bind_claim(
                listing,
                annotation,
                extraction_version=EXTRACTION_VERSION,
                review_version=review_version,
            )
            for annotation in annotations
        )
        resolutions = tuple(resolve_family(family, claims, review) for family in FAMILIES)
        for resolution in resolutions:
            if resolution.family in PUBLIC_FAMILIES:
                resolution.public_fact()
        listings.append(ExtractedListing(listing, review, claims, resolutions))
    return ExtractedCandidate(
        manifest,
        candidate,
        catalogue,
        tuple(sorted(listings, key=lambda item: item.normalized.ref.source_id)),
    )
