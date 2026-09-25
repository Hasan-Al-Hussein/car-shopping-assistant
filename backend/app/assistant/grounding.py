"""Pure source-claim rendering. No provider prose, retrieval, actions or executable tools."""

import json
from dataclasses import dataclass
from typing import Literal

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    CashMoney,
    CashPriceFact,
    ConflictingFact,
    IntegerFact,
    KnownFact,
    ListingDetail,
    ListingSummary,
    SourceLocator,
    TextFact,
    UnknownFact,
)

Fact = TextFact | IntegerFact | CashPriceFact
RefKey = tuple[str, str, str]
LABELS: dict[str, str] = {
    "make": "make",
    "model": "model",
    "trim": "trim",
    "year": "model year",
    "cash_price": "cash asking price",
    "mileage_km": "odometer mileage",
    "fuel_type": "fuel type",
    "body_type": "body style",
    "transmission": "transmission",
    "location": "location",
    "warranty": "warranty",
    "service_history": "service history",
}
QUALIFIERS = {
    "exact": "",
    "approximate": "approximately ",
    "at_least": "at least ",
    "at_most": "at most ",
}
DISPLAY_LABELS = {"year": "Year", "cash_price": "Price", "mileage_km": "Mileage"}


class GroundingError(ValueError):
    """Closed internal reason only; never echo rejected source or model text."""


def key(ref: InventoryRef) -> RefKey:
    return ref.namespace, ref.snapshot_id, ref.source_id


def fact_for(item: ListingSummary | ListingDetail, attribute: str) -> Fact:
    if attribute not in LABELS:
        raise GroundingError("UNSUPPORTED_ATTRIBUTE")
    summary = item.listing if isinstance(item, ListingDetail) else item
    facts: dict[str, Fact] = {
        "make": summary.make,
        "model": summary.model,
        "trim": summary.trim,
        "year": summary.year,
        "cash_price": summary.cash_price,
        "mileage_km": summary.mileage_km,
    }
    if isinstance(item, ListingDetail):
        facts.update(
            fuel_type=item.fuel_type,
            body_type=item.body_type,
            transmission=item.transmission,
            location=item.location,
            warranty=item.warranty,
            service_history=item.service_history,
        )
    return facts.get(attribute, UnknownFact(status="unknown", reason="unsupported"))


def locators(fact: Fact) -> tuple[SourceLocator, ...]:
    if isinstance(fact, UnknownFact):
        return ()
    if isinstance(fact, KnownFact):
        return tuple(fact.evidence)
    return tuple(evidence for claim in fact.claims for evidence in claim.evidence)


@dataclass(frozen=True)
class FactualClaimReference:
    """Internal trace for one rendered sentence, not a new public DTO or model schema."""

    ref: RefKey
    attribute: str
    evidence_ids: tuple[str, ...]
    state: Literal["known", "unknown", "conflicting", "fit", "unresolved"]
    text: str


class EvidenceBindings:
    """Detect collisions within an answer, not authentication of a first locator binding.

    The caller supplies unmodified results from the trusted inventory read service.
    A model-created DTO or evidence ID is not an authoritative inventory response.
    """

    def __init__(self) -> None:
        self._ids: dict[str, tuple[RefKey, dict[str, object]]] = {}

    def bind(self, ref: InventoryRef, attribute: str, fact: Fact) -> tuple[str, ...]:
        ids = []
        for locator in locators(fact):
            association = (key(ref), locator.model_dump(mode="json"))
            old = self._ids.get(locator.evidence_id)
            if old is not None and old != association:
                raise GroundingError("EVIDENCE_IDENTITY_CONFLICT")
            self._ids[locator.evidence_id] = association
            if locator.evidence_id not in ids:
                ids.append(locator.evidence_id)
        claims = (
            fact.claims
            if isinstance(fact, ConflictingFact)
            else (fact,)
            if isinstance(fact, KnownFact)
            else ()
        )
        for claim in claims:
            if attribute in {"year", "mileage_km"} and (
                type(claim.value) is not int or claim.value < 0
            ):
                raise GroundingError("INVALID_NUMERIC_FACT")
            if attribute == "cash_price":
                if not isinstance(claim.value, CashMoney) or claim.value.basis != "cash":
                    raise GroundingError("NOT_CASH_PRICE")
                price_sources = [
                    source for source in claim.evidence if source.semantic_role == "cash_price"
                ]
                if not price_sources or any(
                    source.original_unit not in {None, claim.value.currency}
                    for source in price_sources
                ):
                    raise GroundingError("CASH_EVIDENCE_ROLE")
            if attribute == "mileage_km" and not any(
                source.semantic_role == "vehicle_mileage" for source in claim.evidence
            ):
                raise GroundingError("MILEAGE_EVIDENCE_ROLE")
        return tuple(ids)


def value_text(value: object, attribute: str) -> str:
    if isinstance(value, CashMoney):
        if value.currency != "AED":
            # Only the supplied AED price scale is established by the reviewed inventory.
            return f"{value.currency} {value.minor_units:,} minor units cash"
        major, minor = divmod(value.minor_units, 100)
        return f"{value.currency} {major:,}.{minor:02d} cash"
    if type(value) is int:
        return f"{value:,} km" if attribute == "mileage_km" else str(value)
    if isinstance(value, str):
        # A quoted value remains data; callers render this plain text, never HTML/Markdown.
        return json.dumps(value, ensure_ascii=False)
    raise GroundingError("UNSUPPORTED_FACT_VALUE")


def render_fact(
    ref: InventoryRef,
    attribute: str,
    fact: Fact,
    bindings: EvidenceBindings,
) -> FactualClaimReference:
    if attribute not in LABELS:
        raise GroundingError("UNSUPPORTED_ATTRIBUTE")
    label = DISPLAY_LABELS.get(attribute, LABELS[attribute].capitalize())
    ids = bindings.bind(ref, attribute, fact)
    if isinstance(fact, UnknownFact):
        reasons = {
            "not_stated": "not stated",
            "unparseable": "cannot be resolved from the listing wording",
            "unsupported": "no supported value in these listings",
            "not_applicable": "marked not applicable in the listing",
        }
        text = f"{label}: {reasons[fact.reason]}."
    elif isinstance(fact, KnownFact):
        attribution = (
            " (seller claim)"
            if any(source.category == "seller_description" for source in fact.evidence)
            else ""
        )
        text = (
            f"{label}: {QUALIFIERS[fact.qualifier]}{value_text(fact.value, attribute)}"
            f"{attribution}."
        )
    else:
        alternatives = [
            QUALIFIERS[claim.qualifier] + value_text(claim.value, attribute)
            for claim in fact.claims
        ]
        text = (
            f"{label}: conflicting listing values — "
            + " versus ".join(alternatives)
            + ". No value is resolved."
        )
    if len(text) > 330:
        text = (
            f"{label}: {len(fact.claims)} conflicting source claims; "
            "no value is resolved. See the attached evidence."
            if isinstance(fact, ConflictingFact)
            else f"{label}: listing statement too long to summarize; "
            "see the full value and qualifiers in the listing evidence."
        )
    if attribute == "warranty" and not isinstance(fact, UnknownFact):
        text += " Current warranty validity is not independently verified."
    return FactualClaimReference(key(ref), attribute, ids, fact.status, text)
