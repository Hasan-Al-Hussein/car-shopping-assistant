"""Bounded, source-bound review instructions; no heuristic fact approval."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    model_validator,
)

from app.api.schemas.common import Digest

EXTRACTION_VERSION = "reviewed-claims-2"
Family = Literal[
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
    "warranty",
    "service_history",
    "regional_specs",
    "features",
    "condition",
    "engine",
    "money",
    "distance",
    "facelift_year",
    "service_plan",
]
FAMILIES: tuple[Family, ...] = (
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
    "warranty",
    "service_history",
    "regional_specs",
    "features",
    "condition",
    "engine",
    "money",
    "distance",
    "facelift_year",
    "service_plan",
)
PUBLIC_FAMILIES = FAMILIES[:12]
SourceField = Literal["make", "model", "trim", "year", "title", "description"]
Qualifier = Literal["exact", "approximate", "at_least", "at_most"]
Disposition = Literal[
    "accepted", "conditional", "ambiguous", "dealer_wide", "excluded", "unreviewed"
]
Label = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
Reason = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=500)]
BoundedText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2000)]
Scalar = StrictInt | Annotated[str, StringConstraints(strict=True, min_length=1, max_length=500)]


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class SpanSelection(ReviewModel):
    source_field: SourceField
    quote: BoundedText
    occurrence: Annotated[int, Field(strict=True, ge=0, le=100)] | None = None


class TypedValue(ReviewModel):
    value: Scalar
    unit: Label | None = None
    currency: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")] | None = None
    basis: Label | None = None


class ClaimCondition(ReviewModel):
    kind: Literal[
        "duration",
        "expiry",
        "distance_limit",
        "down_payment",
        "finance_term",
        "option",
        "provider",
        "temporal",
        "scope",
        "other",
    ]
    source: SpanSelection
    value: TypedValue


class ClaimAnnotation(ReviewModel):
    key: Label
    family: Family
    source: SpanSelection
    value: TypedValue
    role: Label
    qualifier: Qualifier = "exact"
    disposition: Disposition
    subject: Literal["vehicle", "dealer", "unspecified"] = "vehicle"
    polarity: Literal["positive", "negative"] = "positive"
    conditions: Annotated[tuple[ClaimCondition, ...], Field(max_length=12)] = ()
    reason: Reason


class FamilyHold(ReviewModel):
    family: Family
    reason: Reason
    claim_keys: Annotated[tuple[Label, ...], Field(max_length=20)] = ()


class FamilyOmission(ReviewModel):
    family: Family
    source_fields: tuple[SourceField, ...]
    reason: Reason


class RecordReview(ReviewModel):
    source_id: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9._-]{1,128}$")]
    source_row: Annotated[int, Field(strict=True, ge=2, le=20000)]
    review_complete: StrictBool
    note: Reason
    claims: Annotated[tuple[ClaimAnnotation, ...], Field(max_length=100)] = ()
    holds: Annotated[tuple[FamilyHold, ...], Field(max_length=20)] = ()
    omissions: Annotated[tuple[FamilyOmission, ...], Field(max_length=20)] = ()

    @model_validator(mode="after")
    def unique_annotations(self) -> "RecordReview":
        keys = [claim.key for claim in self.claims]
        if len(keys) != len(set(keys)) or any(key.startswith("structured.") for key in keys):
            raise ValueError("REVIEW_CLAIM_KEY_INVALID")
        if len({hold.family for hold in self.holds}) != len(self.holds):
            raise ValueError("REVIEW_HOLD_DUPLICATE")
        if len({item.family for item in self.omissions}) != len(self.omissions):
            raise ValueError("REVIEW_OMISSION_DUPLICATE")
        valid_keys = {
            *keys,
            "structured.make",
            "structured.model",
            "structured.trim",
            "structured.year",
        }
        if any(key not in valid_keys for hold in self.holds for key in hold.claim_keys):
            raise ValueError("REVIEW_HOLD_REFERENCE_INVALID")
        return self


class ReviewCatalogue(ReviewModel):
    schema_version: Literal["review-catalogue-1"]
    extraction_version: Literal["reviewed-claims-2"]
    policy_version: Label
    namespace: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-z0-9_-]{1,64}$")]
    workbook_sha256: Digest
    sheet: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
    families: tuple[Family, ...]
    review_state: Literal["draft", "approved"]
    review_method: Reason
    records: Annotated[tuple[RecordReview, ...], Field(min_length=1, max_length=20000)]

    @model_validator(mode="after")
    def complete_scope(self) -> "ReviewCatalogue":
        if self.families != FAMILIES:
            raise ValueError("REVIEW_FAMILY_SCOPE_INVALID")
        if len({item.source_id for item in self.records}) != len(self.records):
            raise ValueError("REVIEW_RECORD_DUPLICATE")
        if self.review_state == "approved" and not all(
            item.review_complete for item in self.records
        ):
            raise ValueError("REVIEW_INCOMPLETE")
        return self

    def canonical_bytes(self) -> bytes:
        data = self.model_dump(mode="json")
        data["records"].sort(key=lambda item: item["source_id"])
        for record in data["records"]:
            record["claims"].sort(key=lambda item: item["key"])
            record["holds"].sort(key=lambda item: item["family"])
            record["omissions"].sort(key=lambda item: item["family"])
        return json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")

    @property
    def review_version(self) -> str:
        # Full SHA-256 is a valid bounded ASCII version label in the frozen preimage.
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
