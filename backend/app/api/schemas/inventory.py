"""Exact inventory identity, evidence, deterministic search and presentation contracts."""

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import Field, StrictBool, StrictInt, StringConstraints, model_validator

from app.api.schemas.common import DTO, Digest, Id, InventoryRef, OpaqueKey, ShortText, UtcInstant


class SourceLocator(DTO):
    evidence_id: Id
    workbook_sha256: Digest
    sheet: ShortText
    cell: Annotated[str, StringConstraints(strict=True, max_length=32)]
    raw_text: Annotated[str, StringConstraints(strict=True, max_length=16000)]
    span_start: Annotated[int, Field(strict=True, ge=0)]
    span_end: Annotated[int, Field(strict=True, ge=0)]
    extraction_version: ShortText
    category: Literal["structured_source", "seller_description", "reviewed_correction"]
    review_status: Literal["not_reviewed", "reviewed_extraction", "reviewed_correction"]
    verification: Literal["source_claim"] = "source_claim"
    original_unit: ShortText | None = None
    semantic_role: (
        Literal[
            "vehicle_mileage",
            "warranty_limit",
            "service_interval",
            "cash_price",
            "finance_instalment",
            "salary",
            "fee",
            "service_cost",
            "other",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def ordered_span(self) -> "SourceLocator":
        if self.span_end < self.span_start:
            raise ValueError("Evidence span end must not precede start.")
        if self.span_end - self.span_start != len(self.raw_text):
            raise ValueError("Public evidence is the exact source span, not the whole source cell.")
        return self


class KnownFact[V](DTO):
    status: Literal["known"]
    value: V
    evidence: Annotated[list[SourceLocator], Field(min_length=1, max_length=20)]
    qualifier: Literal["exact", "approximate", "at_least", "at_most"] = "exact"


class UnknownFact(DTO):
    status: Literal["unknown"]
    reason: Literal["not_stated", "unparseable", "unsupported", "not_applicable"]


class FactClaim[V](DTO):
    value: V
    evidence: Annotated[list[SourceLocator], Field(min_length=1, max_length=20)]
    qualifier: Literal["exact", "approximate", "at_least", "at_most"] = "exact"


class ConflictingFact[V](DTO):
    status: Literal["conflicting"]
    claims: Annotated[list[FactClaim[V]], Field(min_length=2, max_length=20)]


TextFact = Annotated[
    KnownFact[ShortText] | UnknownFact | ConflictingFact[ShortText], Field(discriminator="status")
]
IntegerFact = Annotated[
    KnownFact[StrictInt] | UnknownFact | ConflictingFact[StrictInt], Field(discriminator="status")
]


class Money(DTO):
    minor_units: Annotated[int, Field(strict=True, ge=0, le=10**12)]
    currency: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")]
    basis: Literal["cash", "monthly_finance", "salary", "service_cost"]


MoneyFact = Annotated[
    KnownFact[Money] | UnknownFact | ConflictingFact[Money], Field(discriminator="status")
]


class CashMoney(Money):
    basis: Literal["cash"] = "cash"


CashPriceFact = Annotated[
    KnownFact[CashMoney] | UnknownFact | ConflictingFact[CashMoney], Field(discriminator="status")
]


class ListingPhoto(DTO):
    state: Literal["source_present", "missing", "blocked", "unverified"]
    url: Annotated[str, StringConstraints(strict=True, max_length=2048)] | None
    alt: Annotated[str, StringConstraints(strict=True, max_length=300)]
    source: Literal["supplied_listing"] = "supplied_listing"

    @model_validator(mode="after")
    def exact_approved_source(self) -> "ListingPhoto":
        if self.state != "source_present":
            if self.url is not None:
                raise ValueError("Unavailable photo cannot expose a renderable URL.")
            return self
        if self.url is None or any(ord(char) < 33 for char in self.url):
            raise ValueError("Source photo requires a valid supplied URL.")
        parsed = urlsplit(self.url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "dbz-images.dubizzle.com"
            or parsed.fragment
            or not parsed.path.startswith("/images/")
            or "\\" in parsed.path
            or "%" in parsed.path
            or "/../" in parsed.path
        ):
            raise ValueError("Photo is outside the approved source policy.")
        if parse_qsl(parsed.query, keep_blank_values=True) not in (
            [("impolicy", "dpv")],
            [("impolicy", "dpc")],
            [("imwidth", "800")],
        ):
            raise ValueError("Photo query is outside the reviewed source patterns.")
        return self


class ListingSummary(DTO):
    ref: InventoryRef
    title: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=1000)]
    make: TextFact
    model: TextFact
    trim: TextFact
    year: IntegerFact
    cash_price: CashPriceFact
    mileage_km: IntegerFact
    photo: ListingPhoto
    evidence_warnings: Annotated[list[ShortText], Field(max_length=24)] = []


class ListingDetail(DTO):
    state: Literal["current", "historical"]
    listing: ListingSummary
    description: Annotated[str, StringConstraints(strict=True, max_length=32000)]
    fuel_type: TextFact
    body_type: TextFact
    transmission: TextFact
    location: TextFact
    warranty: TextFact
    service_history: TextFact
    eligibility: Literal["simulated_eligible", "unavailable", "configuration_missing"]
    eligibility_reason: ShortText


class MissingListing(DTO):
    state: Literal["missing"]
    ref: InventoryRef


class ListingReadError(DTO):
    state: Literal["error"]
    ref: InventoryRef
    code: Literal["STORE_UNAVAILABLE", "SNAPSHOT_STALE", "INTERNAL_ERROR"]
    retryable: StrictBool


ListingResult = Annotated[
    ListingDetail | MissingListing | ListingReadError, Field(discriminator="state")
]


class IntegerRange(DTO):
    minimum: Annotated[int, Field(strict=True, ge=0, le=10**12)] | None = None
    maximum: Annotated[int, Field(strict=True, ge=0, le=10**12)] | None = None

    @model_validator(mode="after")
    def ordered(self) -> "IntegerRange":
        if self.minimum is None and self.maximum is None:
            raise ValueError("Supply at least one range bound.")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Minimum must not exceed maximum.")
        return self


class BudgetRange(IntegerRange):
    """Inclusive minimum/maximum bounds are integer minor units, not major currency units."""

    currency: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")]
    basis: Literal["cash"] = "cash"


class SearchFilters(DTO):
    makes: Annotated[list[ShortText], Field(max_length=12)] = []
    models: Annotated[list[ShortText], Field(max_length=12)] = []
    trims: Annotated[list[ShortText], Field(max_length=12)] = []
    years: IntegerRange | None = None
    budget: BudgetRange | None = None
    mileage_km: IntegerRange | None = None
    body_types: Annotated[list[ShortText], Field(max_length=8)] = []
    fuel_types: Annotated[list[ShortText], Field(max_length=8)] = []
    transmissions: Annotated[list[ShortText], Field(max_length=8)] = []

    @model_validator(mode="after")
    def bounded_clauses(self) -> "SearchFilters":
        count = sum(
            len(value) if isinstance(value, list) else int(value is not None)
            for value in self.__dict__.values()
        )
        if count > 24:
            raise ValueError("At most 24 supported filter clauses are allowed.")
        return self


class SearchCriteria(DTO):
    query: Annotated[str, StringConstraints(strict=True, max_length=1000)] = ""
    filters: SearchFilters = Field(default_factory=SearchFilters)
    soft_preferences: Annotated[list[ShortText], Field(max_length=12)] = []


class SearchRequest(SearchCriteria):
    snapshot_id: Digest | None = None
    page_size: Annotated[int, Field(strict=True, ge=1, le=50)] = 20
    cursor: Annotated[str, StringConstraints(strict=True, max_length=2048)] | None = None
    client_request_id: Id


class PresentationProof(DTO):
    presentation_id: Id
    snapshot_id: Digest
    ordered_refs: Annotated[list[InventoryRef], Field(max_length=50)]
    criteria_hash: Digest
    issued_at: UtcInstant
    expires_at: UtcInstant
    signature: OpaqueKey

    @model_validator(mode="after")
    def coherent_presentation(self) -> "PresentationProof":
        if datetime.fromisoformat(self.expires_at) <= datetime.fromisoformat(self.issued_at):
            raise ValueError("Presentation expiry must follow issue.")
        if any(ref.snapshot_id != self.snapshot_id for ref in self.ordered_refs):
            raise ValueError("Every presented reference must belong to the named snapshot.")
        keys = {(ref.namespace, ref.snapshot_id, ref.source_id) for ref in self.ordered_refs}
        if len(keys) != len(self.ordered_refs):
            raise ValueError("A presentation cannot contain duplicate references.")
        return self


class SearchResult(DTO):
    client_request_id: Id
    state: Literal["matches", "no_supported_matches"]
    items: Annotated[list[ListingSummary], Field(max_length=50)]
    supported_total: Annotated[int, Field(strict=True, ge=0)]
    next_cursor: Annotated[str, StringConstraints(strict=True, max_length=2048)] | None
    presentation: PresentationProof
    applied_criteria: SearchCriteria
    evidence_coverage: Annotated[list["ConstraintCoverage"], Field(max_length=24)]
    unsupported_constraints: Annotated[list[ShortText], Field(max_length=24)] = []
    constraints_relaxed: Literal[False] = False

    @model_validator(mode="after")
    def coherent_results(self) -> "SearchResult":
        if self.presentation.ordered_refs != [item.ref for item in self.items]:
            raise ValueError("Presentation must preserve exactly the returned item order.")
        if self.state == "no_supported_matches":
            if self.items or self.supported_total or self.next_cursor:
                raise ValueError("No supported matches requires an empty result without cursor.")
        elif not self.items or self.supported_total < len(self.items):
            raise ValueError("Matches require items and a sufficient supported total.")
        if self.unsupported_constraints and self.state != "no_supported_matches":
            raise ValueError("Unsupported hard constraints cannot yield supported matches.")
        attributes = [coverage.attribute for coverage in self.evidence_coverage]
        if len(set(attributes)) != len(attributes):
            raise ValueError("Coverage must have one entry per attribute.")
        return self


class ConstraintCoverage(DTO):
    attribute: Literal[
        "make",
        "model",
        "trim",
        "year",
        "cash_price",
        "mileage_km",
        "body_type",
        "fuel_type",
        "transmission",
    ]
    source_total: Annotated[int, Field(strict=True, ge=0)]
    supported: Annotated[int, Field(strict=True, ge=0)]
    excluded_unknown: Annotated[int, Field(strict=True, ge=0)]
    excluded_conflicting: Annotated[int, Field(strict=True, ge=0)]
    excluded_unsupported_qualifier: Annotated[int, Field(strict=True, ge=0)]

    @model_validator(mode="after")
    def disjoint_coverage(self) -> "ConstraintCoverage":
        if (
            sum(
                (
                    self.supported,
                    self.excluded_unknown,
                    self.excluded_conflicting,
                    self.excluded_unsupported_qualifier,
                )
            )
            != self.source_total
        ):
            raise ValueError("Disjoint evidence categories must cover the source population.")
        return self


class ComparisonRequest(DTO):
    refs: Annotated[list[InventoryRef], Field(min_length=2, max_length=3)]

    @model_validator(mode="after")
    def unique_refs(self) -> "ComparisonRequest":
        keys = {(ref.namespace, ref.snapshot_id, ref.source_id) for ref in self.refs}
        if len(keys) != len(self.refs):
            raise ValueError("Comparison references must be distinct.")
        return self


class ComparisonResult(DTO):
    items: Annotated[list[ListingResult], Field(min_length=2, max_length=3)]


class FitReason(DTO):
    criterion: ShortText
    attribute: ShortText
    evidence_ids: Annotated[list[Id], Field(min_length=1, max_length=12)]
    text: Annotated[str, StringConstraints(strict=True, max_length=1000)]


class UnresolvedQuestion(DTO):
    criterion: ShortText
    attribute: ShortText
    reason: Literal["unknown", "conflicting", "unverified", "unmet"]
    question: Annotated[str, StringConstraints(strict=True, max_length=1000)]


class HandoffSummary(DTO):
    selected_ref: InventoryRef
    listing: ListingResult
    expressed_criteria: SearchCriteria
    fit_reasons: Annotated[list[FitReason], Field(max_length=12)]
    unresolved_questions: Annotated[list[UnresolvedQuestion], Field(max_length=12)]

    @model_validator(mode="after")
    def exact_selected_listing(self) -> "HandoffSummary":
        actual = (
            self.listing.listing.ref
            if isinstance(self.listing, ListingDetail)
            else self.listing.ref
        )
        if actual != self.selected_ref:
            raise ValueError("Handoff must describe the exact selected listing.")
        return self
