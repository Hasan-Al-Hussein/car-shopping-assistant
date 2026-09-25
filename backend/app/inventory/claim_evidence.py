"""Bind reviewed meanings to exact original Unicode or OOXML token spans."""

import json
from dataclasses import dataclass, field
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import ConfigDict

from app.api.schemas.inventory import SourceLocator
from app.inventory.import_reader import SourceCell
from app.inventory.normalization import NormalizedListing
from app.inventory.references import ImmutableInventoryRef
from app.inventory.review_catalogue import ClaimAnnotation, SpanSelection, TypedValue


class ImmutableSourceLocator(SourceLocator):
    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class BoundEvidence:
    ref: ImmutableInventoryRef
    locator: ImmutableSourceLocator
    source_row: int
    source_field: str
    span_basis: Literal["unicode_text", "ooxml_value_token"]
    source: SourceCell = field(repr=False)


@dataclass(frozen=True)
class ReviewedClaim:
    annotation: ClaimAnnotation
    evidence: BoundEvidence
    condition_evidence: tuple[BoundEvidence, ...]
    evidence_review_version: str

    @property
    def ref(self) -> ImmutableInventoryRef:
        return self.evidence.ref

    def locators(self) -> list[SourceLocator]:
        return [self.evidence.locator, *(item.locator for item in self.condition_evidence)]


def original_text(cell: SourceCell) -> tuple[str, Literal["unicode_text", "ooxml_value_token"]]:
    if cell.data_type in {"f", "e"}:
        raise ValueError("EVIDENCE_SOURCE_TYPE_UNSUPPORTED")
    if isinstance(cell.value, str):
        return cell.value, "unicode_text"
    if (
        type(cell.value) in {int, float}
        and cell.storage is not None
        and cell.storage.value is not None
    ):
        return cell.storage.value, "ooxml_value_token"
    raise ValueError("EVIDENCE_SOURCE_TYPE_UNSUPPORTED")


def _role(role: str) -> str:
    if role == "historical_service_cost":
        return "service_cost"
    if role in {
        "vehicle_mileage",
        "warranty_limit",
        "service_interval",
        "cash_price",
        "finance_instalment",
        "salary",
        "fee",
    }:
        return role
    return "other"


def bind_span(
    listing: NormalizedListing,
    annotation: ClaimAnnotation,
    selection: SpanSelection,
    *,
    extraction_version: str,
    review_version: str,
    ordinal: int = 0,
    original_unit: str | None = None,
    semantic_role: str | None = None,
) -> BoundEvidence:
    cell = listing.source.cell(selection.source_field)
    original, basis = original_text(cell)
    starts: list[int] = []
    start = original.find(selection.quote)
    while start != -1:
        starts.append(start)
        start = original.find(selection.quote, start + 1)
    if not starts or selection.occurrence is None and len(starts) != 1:
        raise ValueError("EVIDENCE_SPAN_MISSING_OR_AMBIGUOUS")
    occurrence = selection.occurrence or 0
    if occurrence >= len(starts):
        raise ValueError("EVIDENCE_OCCURRENCE_INVALID")
    start = starts[occurrence]
    end = start + len(selection.quote)
    identity = json.dumps(
        {
            "ref": listing.ref.model_dump(),
            "cell": cell.coordinate,
            "start": start,
            "end": end,
            "meaning": annotation.model_dump(mode="json"),
            "ordinal": ordinal,
            "extraction_version": extraction_version,
            "review_version": review_version,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    locator = ImmutableSourceLocator.model_validate(
        {
            "evidence_id": str(uuid5(NAMESPACE_URL, identity)),
            "workbook_sha256": listing.identity_provenance.workbook_sha256,
            "sheet": listing.source.sheet,
            "cell": cell.coordinate,
            "raw_text": original[start:end],
            "span_start": start,
            "span_end": end,
            "extraction_version": extraction_version,
            "category": "structured_source"
            if selection.source_field in {"make", "model", "trim", "year"}
            else "seller_description",
            "review_status": "not_reviewed"
            if annotation.disposition == "unreviewed"
            else "reviewed_extraction",
            "verification": "source_claim",
            "original_unit": original_unit,
            "semantic_role": _role(semantic_role or annotation.role),
        }
    )
    return BoundEvidence(
        listing.ref, locator, listing.source.row, selection.source_field, basis, cell
    )


def _source_unit(value: TypedValue) -> str | None:
    """Source-facing unit from reviewed metadata, distinct from normalized storage."""
    if value.unit == "minor_units":
        return value.currency
    if value.unit == "currency_unknown":
        return None
    return value.unit


def bind_claim(
    listing: NormalizedListing,
    annotation: ClaimAnnotation,
    *,
    extraction_version: str,
    review_version: str,
) -> ReviewedClaim:
    main = bind_span(
        listing,
        annotation,
        annotation.source,
        extraction_version=extraction_version,
        review_version=review_version,
        original_unit=_source_unit(annotation.value),
    )
    conditions = tuple(
        bind_span(
            listing,
            annotation,
            condition.source,
            extraction_version=extraction_version,
            review_version=review_version,
            ordinal=index + 1,
            original_unit=_source_unit(condition.value),
            semantic_role="warranty_limit"
            if annotation.family == "warranty" and condition.kind == "distance_limit"
            else "other",
        )
        for index, condition in enumerate(annotation.conditions)
    )
    return ReviewedClaim(annotation, main, conditions, review_version)
