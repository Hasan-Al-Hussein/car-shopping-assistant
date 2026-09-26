"""Real all-record semantic acceptance and explicitly synthetic adversarial claims."""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest
from pydantic import ValidationError

from app.inventory.claim_evidence import bind_claim, original_text
from app.inventory.extraction import (
    ExtractedCandidate,
    _structured,
    extract_reviewed,
    resolve_family,
)
from app.inventory.import_reader import SourceCell, SourceSpec, read_workbook
from app.inventory.normalization import (
    CellProvenance,
    NormalizedCandidate,
    NormalizedField,
    NormalizedListing,
    normalize_candidate,
)
from app.inventory.review_authoring import cash, claim, mileage, record, term
from app.inventory.review_catalogue import (
    EXTRACTION_VERSION,
    FAMILIES,
    ClaimAnnotation,
)
from app.inventory.source_catalogue import provided_source_catalogue
from app.inventory.text_normalization import normalize_text
from tests.support.harness import PROJECT


@pytest.fixture(scope="module")
def normalized() -> NormalizedCandidate:
    facts = json.loads((PROJECT / "fixtures/shared/source-facts.json").read_text(encoding="utf-8"))
    path = PROJECT / facts["source_relative_path"]
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    source = read_workbook(path, SourceSpec(expected_sha256=facts["workbook_sha256"]))
    result = normalize_candidate(source)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before == facts["workbook_sha256"]
    return result


@pytest.fixture(scope="module")
def extracted(normalized: NormalizedCandidate) -> ExtractedCandidate:
    catalogue = provided_source_catalogue()
    assert catalogue.review_state == "approved", (
        "Full source semantic review must close before acceptance tests."
    )
    return extract_reviewed(normalized, catalogue)


def index(result: ExtractedCandidate) -> dict[str, Any]:
    return {item.normalized.ref.source_id: item for item in result.records}


def test_every_record_family_and_span_is_accounted_for(extracted: ExtractedCandidate) -> None:
    report = extracted.coverage_report()
    review_version = extracted.catalogue.review_version
    assert len(extracted.records) == len(report["records"]) == 100
    assert report["audit_only_count"] == 100 and report["published"] is False
    assert extracted.manifest.snapshot_id != extracted.normalized_source.manifest.snapshot_id
    assert set(report["families"]) == set(FAMILIES)
    assert all(sum(counts.values()) == 100 for counts in report["families"].values())
    for item in extracted.records:
        assert len(item.resolutions) == 20 and item.review.review_complete
        assert item.normalized.ref == extracted.manifest.reference(item.review.source_id)
        original = next(
            row
            for row in extracted.normalized_source.records
            if row.ref.source_id == item.review.source_id
        )
        assert item.normalized.source is original.source
        assert item.normalized.photo is original.photo
        for accepted in item.claims:
            assert accepted.ref == item.normalized.ref
            assert accepted.evidence_review_version == review_version
            for evidence in (accepted.evidence, *accepted.condition_evidence):
                text, basis = original_text(evidence.source)
                locator = evidence.locator
                assert basis == evidence.span_basis
                assert locator.raw_text == text[locator.span_start : locator.span_end]
                assert locator.span_end - locator.span_start == len(locator.raw_text)
                assert locator.workbook_sha256 == extracted.manifest.workbook_sha256
                assert locator.cell == evidence.source.coordinate
                assert evidence.source_row == item.normalized.source.row
                assert locator.verification == "source_claim"
                assert locator.review_status == "reviewed_extraction"
        for fact in item.resolutions:
            if fact.family in FAMILIES[:12]:
                fact.public_fact()


@pytest.mark.parametrize(
    "source_id,family,expected",
    [
        ("4", "trim", {"e 400", "e 450"}),
        ("19", "trim", {"xdrive20i", "xdrive20d"}),
        ("52", "year", {2015, 2014}),
        ("27", "service_history", {"partial service history", "full service history"}),
        ("17", "engine", {"W12", "V8"}),
        ("96", "trim", {"t5 momentum", "B5 FWD Momentum"}),
        ("95", "model", {"rav 4", "Wildlander"}),
        ("31", "trim", {"r-sport", "F sport"}),
        ("39", "trim", {"s", "SQ4"}),
    ],
)
def test_real_conflicts_preserve_both_claims(
    extracted: ExtractedCandidate, source_id: str, family: Any, expected: set[Any]
) -> None:
    fact = index(extracted)[source_id].fact(family)
    assert fact.status == "conflicting" and not fact.strict_match_eligible
    assert {group.value.value for group in fact.groups} == expected
    assert (
        len({claim.evidence.locator.evidence_id for group in fact.groups for claim in group.claims})
        >= 2
    )


def test_real_money_roles_and_currency_are_not_interchanged(extracted: ExtractedCandidate) -> None:
    cars = index(extracted)
    assert cars["3"].fact("cash_price").public_fact()["value"] == {
        "minor_units": 11975000,
        "currency": "AED",
        "basis": "cash",
    }
    monthly = cars["3"].fact("money").claims
    assert {item.annotation.value.value for item in monthly} == {211100, 187600}
    assert {
        tuple((term.kind, term.value.value) for term in item.annotation.conditions)
        for item in monthly
    } == {
        (("down_payment", 10), ("finance_term", 5)),
        (("down_payment", 20), ("finance_term", 5)),
    }
    assert cars["12"].fact("cash_price").groups[0].value.value == 3500000
    salary = next(item for item in cars["12"].claims if item.annotation.role == "salary")
    assert salary.annotation.value.value == 300000 and salary.annotation.qualifier == "at_least"
    assert any(item.value.value == "WPS" for item in salary.annotation.conditions)
    assert cars["13"].fact("cash_price").groups[0].value.value == 5450000
    assert {
        item.annotation.value.value for item in cars["13"].claims if item.annotation.role == "fee"
    } == {100000, 120000}
    for source_id in ("6", "29", "78", "79", "92"):
        assert cars[source_id].fact("cash_price").status == "unknown"
    historical = next(
        item for item in cars["79"].claims if item.annotation.role == "historical_service_cost"
    )
    assert (
        historical.annotation.value.value == 85000 and historical.annotation.value.currency is None
    )
    assert historical.evidence.locator.semantic_role == "service_cost"


def test_real_distance_year_warranty_and_scope(extracted: ExtractedCandidate) -> None:
    cars = index(extracted)
    assert cars["22"].fact("mileage_km").status == "unknown"
    interval = next(
        item for item in cars["22"].claims if item.annotation.role == "service_interval"
    )
    assert interval.annotation.value.value == 16000 and interval.annotation.conditions
    assert cars["47"].fact("mileage_km").groups[0].value.value == 122090
    assert {item.annotation.value.value for item in cars["47"].fact("distance").claims} == {
        104700,
        114700,
    }
    assert cars["68"].fact("mileage_km").groups[0].value.value == 34927
    assert cars["91"].fact("year").groups[0].value.value == 2009
    assert cars["91"].fact("facelift_year").groups[0].value.value == 2025
    assert cars["28"].fact("mileage_km").groups[0].value.value == 0
    for source_id in ("10", "29", "46", "73", "80", "92", "100"):
        assert cars[source_id].fact("warranty").status == "unknown"
    assert cars["71"].fact("warranty").public_fact()["value"].find("unverified") >= 0
    assert cars["83"].fact("trim").status == "unknown"
    for source_id in ("2", "7", "10", "26", "58", "98"):
        assert cars[source_id].fact("location").status == "unknown"
    assert cars["57"].fact("location").status == "known"
    assert cars["49"].fact("transmission").status == "unknown"
    assert cars["19"].fact("fuel_type").status == "unknown"


def test_source_money_unit_is_not_normalized_storage_unit(extracted: ExtractedCandidate) -> None:
    assert extracted.manifest.extraction_version == "reviewed-claims-2"
    for item in extracted.records:
        for reviewed in item.claims:
            value = reviewed.annotation.value
            if value.unit == "minor_units":
                assert reviewed.evidence.locator.original_unit == value.currency == "AED"
                assert reviewed.annotation.value.unit == "minor_units"
            elif value.unit == "currency_unknown":
                assert reviewed.evidence.locator.original_unit is None
    assert index(extracted)["3"].fact("cash_price").public_fact()["value"] == {
        "minor_units": 11975000,
        "currency": "AED",
        "basis": "cash",
    }


def test_numeric_labels_and_arabic_evidence_are_exact(extracted: ExtractedCandidate) -> None:
    cars = index(extracted)
    for identifier, family, value, raw in (
        ("12", "model", "3", "3.0"),
        ("22", "trim", "707", "707.0"),
    ):
        fact = cars[identifier].fact(family)
        assert fact.groups[0].value.value == value
        evidence = fact.groups[0].claims[0].evidence
        assert evidence.span_basis == "ooxml_value_token" and evidence.source.python_type == "float"
        assert evidence.locator.raw_text == raw
    transmission = cars["19"].fact("transmission").groups[0].claims[0]
    assert transmission.evidence.locator.raw_text == "8 سرعات القير الأوتوماتيكي"


def test_snapshot_is_deterministic_and_semantic_changes_reidentify(
    normalized: NormalizedCandidate, extracted: ExtractedCandidate
) -> None:
    catalogue = extracted.catalogue
    reordered = catalogue.model_copy(update={"records": tuple(reversed(catalogue.records))})
    assert reordered.review_version == catalogue.review_version
    again = extract_reviewed(
        replace(normalized, records=tuple(reversed(normalized.records))), reordered
    )
    assert again.evidence_ledger() == extracted.evidence_ledger()
    first = catalogue.records[0]
    changed = catalogue.model_copy(
        update={
            "records": (
                first.model_copy(update={"note": first.note + " Reviewed anew."}),
                *catalogue.records[1:],
            )
        }
    )
    revised = extract_reviewed(normalized, changed)
    assert revised.manifest.snapshot_id != extracted.manifest.snapshot_id
    assert revised.normalized_source.manifest.snapshot_id == normalized.manifest.snapshot_id
    assert len(json.loads(extracted.manifest.canonical_bytes())) == 8
    with pytest.raises(FrozenInstanceError):
        extracted.manifest.extraction_version = "bad"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        extracted.records[0].normalized.ref.source_id = "bad"  # type: ignore[misc]


@pytest.mark.parametrize(
    "change,code",
    [
        ({"review_state": "draft"}, "APPROVED"),
        ({"workbook_sha256": "0" * 64}, "SOURCE_MISMATCH"),
        ({"sheet": "raw dataset"}, "SOURCE_MISMATCH"),
    ],
)
def test_unreviewed_and_wrong_source_catalogues_rejected(
    normalized: NormalizedCandidate, change: dict[str, Any], code: str
) -> None:
    catalogue = provided_source_catalogue().model_copy(update=change)
    with pytest.raises(ValueError, match=code):
        extract_reviewed(normalized, catalogue)


def synthetic_listing(normalized: NormalizedCandidate, text: str) -> NormalizedListing:
    # In-memory synthetic adversarial cell; never saved or mixed into a real ledger.
    base = normalized.records[0]
    cell = SourceCell("description", f"G{base.source.row}", text, "s", "str")
    source = replace(
        base.source,
        cells=tuple(cell if item.field == "description" else item for item in base.source.cells),
    )
    fields = tuple(
        NormalizedField(
            CellProvenance(item.provenance.workbook_sha256, source.sheet, source.row, cell),
            normalize_text(cell),
        )
        if item.provenance.source.field == "description"
        else item
        for item in base.fields
    )
    return replace(base, source=source, fields=fields)


def resolve_synthetic(
    normalized: NormalizedCandidate, text: str, family: Any, *annotations: ClaimAnnotation
) -> Any:
    listing = synthetic_listing(normalized, text)
    review = record(
        listing.ref.source_id,
        listing.source.row,
        "Explicitly synthetic review fixture.",
        *annotations,
    )
    bound = tuple(
        bind_claim(listing, item, extraction_version=EXTRACTION_VERSION, review_version="test")
        for item in annotations
    )
    return resolve_family(family, bound, review)


@pytest.mark.parametrize(
    "disposition,subject",
    [
        ("conditional", "vehicle"),
        ("ambiguous", "vehicle"),
        ("unreviewed", "vehicle"),
        ("dealer_wide", "dealer"),
    ],
)
def test_synthetic_nonfacts_never_become_known(
    normalized: NormalizedCandidate, disposition: Any, subject: str
) -> None:
    item = claim(
        "warranty",
        "No warranty included; warranty can be arranged",
        disposition=disposition,
        subject=subject,
    )
    fact = resolve_synthetic(normalized, item.source.quote, "warranty", item)
    assert fact.status == "unknown" and not fact.strict_match_eligible


def test_synthetic_negation_and_unrelated_dealer_text_are_not_positive(
    normalized: NormalizedCandidate,
) -> None:
    text = "No petrol engine. Dealer has petrol cars. No warranty."
    negative = claim("fuel_type", "No petrol engine", "petrol", polarity="negative")
    dealer = claim(
        "fuel_type", "Dealer has petrol cars", "petrol", subject="dealer", disposition="dealer_wide"
    )
    fact = resolve_synthetic(normalized, text, "fuel_type", negative, dealer)
    assert fact.status == "unknown"


def test_synthetic_positive_does_not_erase_negative_claim(normalized: NormalizedCandidate) -> None:
    text = "Petrol engine. No petrol engine."
    positive = claim("fuel_type", "Petrol engine", "petrol")
    negative = claim("fuel_type", "No petrol engine", "petrol", polarity="negative")
    fact = resolve_synthetic(normalized, text, "fuel_type", positive, negative)
    assert fact.status == "unknown" and not fact.strict_match_eligible
    assert len(fact.claims) == 2 and fact.public_fact()["reason"] == "unsupported"


@pytest.mark.parametrize("field_name", ["identity_provenance", "photo_provenance"])
def test_tampered_nontext_provenance_rejected(
    normalized: NormalizedCandidate, field_name: str
) -> None:
    first = normalized.records[0]
    provenance = getattr(first, field_name)
    modified = replace(first, **{field_name: replace(provenance, workbook_sha256="0" * 64)})
    candidate = replace(normalized, records=(modified, *normalized.records[1:]))
    with pytest.raises(ValueError, match="PROVENANCE_MISMATCH"):
        extract_reviewed(candidate, provided_source_catalogue())


def test_matching_reduced_populations_cannot_bypass_reader_accounting(
    normalized: NormalizedCandidate,
) -> None:
    removed = normalized.records[0].ref.source_id
    reduced = replace(normalized, records=normalized.records[1:])
    catalogue = provided_source_catalogue()
    reduced_catalogue = catalogue.model_copy(
        update={"records": tuple(item for item in catalogue.records if item.source_id != removed)}
    )
    with pytest.raises(ValueError, match="NORMALIZATION_REQUIRES_ACCEPTED_SOURCE"):
        extract_reviewed(reduced, reduced_catalogue)


def test_missing_field_or_changed_id_cannot_enter_extraction(
    normalized: NormalizedCandidate,
) -> None:
    first = normalized.records[0]
    with pytest.raises(ValueError, match="PROVENANCE_MISMATCH"):
        extract_reviewed(
            replace(
                normalized,
                records=(replace(first, fields=first.fields[1:]), *normalized.records[1:]),
            ),
            provided_source_catalogue(),
        )
    id_cell = first.source.cell("Listing_ID")
    source = replace(
        first.source,
        cells=tuple(
            replace(cell, value="different") if cell is id_cell else cell
            for cell in first.source.cells
        ),
    )
    with pytest.raises(ValueError, match="SOURCE_INCONSISTENT"):
        extract_reviewed(
            replace(normalized, records=(replace(first, source=source), *normalized.records[1:])),
            provided_source_catalogue(),
        )


def test_unsupported_normalized_year_stays_unknown(normalized: NormalizedCandidate) -> None:
    first = normalized.records[0]
    original = first.source.cell("year")
    cell = replace(original, value=999)
    source = replace(
        first.source,
        cells=tuple(cell if item.field == "year" else item for item in first.source.cells),
    )
    fields = tuple(
        NormalizedField(replace(item.provenance, source=cell), normalize_text(cell))
        if item.provenance.source.field == "year"
        else item
        for item in first.fields
    )
    assert not any(
        item.family == "year" for item in _structured(replace(first, source=source, fields=fields))
    )


def test_synthetic_quote_ambiguity_and_unicode_offsets(normalized: NormalizedCandidate) -> None:
    listing = synthetic_listing(normalized, "🚙 لا يوجد ضمان؛ 20,000 km. 20,000 km")
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        bind_claim(
            listing,
            mileage("20,000 km", 20000),
            extraction_version=EXTRACTION_VERSION,
            review_version="test",
        )
    item = claim("mileage_km", "20,000 km", 20000, unit="km", role="vehicle_mileage", occurrence=1)
    bound = bind_claim(listing, item, extraction_version=EXTRACTION_VERSION, review_version="test")
    original = listing.source.cell("description").value
    assert isinstance(original, str)
    assert bound.evidence.locator.span_start == original.rfind("20,000 km")
    assert bound.evidence.locator.raw_text == "20,000 km"


@pytest.mark.parametrize(
    "item",
    [
        claim("cash_price", "price3000", 3000, role="cash_price", unit="minor_units", basis="cash"),
        claim(
            "cash_price",
            "price3000",
            3000,
            role="salary",
            unit="minor_units",
            basis="salary",
            currency="AED",
        ),
        claim(
            "cash_price",
            "price3000",
            -3000,
            role="cash_price",
            unit="minor_units",
            basis="cash",
            currency="AED",
        ),
    ],
)
def test_synthetic_invalid_cash_semantics_are_withheld(
    normalized: NormalizedCandidate, item: ClaimAnnotation
) -> None:
    assert resolve_synthetic(normalized, "price3000", "cash_price", item).status == "unknown"


def test_synthetic_approximate_and_conditional_prices_not_strict(
    normalized: NormalizedCandidate,
) -> None:
    approximate = claim(
        "cash_price",
        "about AED100",
        10000,
        role="cash_price",
        unit="minor_units",
        currency="AED",
        basis="cash",
        qualifier="approximate",
    )
    fact = resolve_synthetic(normalized, "about AED100", "cash_price", approximate)
    assert (
        fact.status == "known"
        and fact.public_fact()["qualifier"] == "approximate"
        and not fact.strict_match_eligible
    )
    conditional = claim(
        "cash_price",
        "AED100 if eligible",
        10000,
        role="cash_price",
        unit="minor_units",
        currency="AED",
        basis="cash",
        conditions=(term("scope", "if eligible", "eligibility required"),),
    )
    limited = resolve_synthetic(normalized, "AED100 if eligible", "cash_price", conditional)
    assert not limited.strict_match_eligible and limited.public_fact()["status"] == "unknown"


def test_synthetic_contradictory_clauses_preserve_both_prices(
    normalized: NormalizedCandidate,
) -> None:
    fact = resolve_synthetic(
        normalized,
        "AED100 cash; AED200 cash",
        "cash_price",
        cash("AED100 cash", 10000),
        cash("AED200 cash", 20000),
    )
    assert fact.status == "conflicting" and len(fact.public_fact()["claims"]) == 2


def test_synthetic_compatible_history_roles_do_not_conflict(
    normalized: NormalizedCandidate,
) -> None:
    fact = resolve_synthetic(
        normalized,
        "Full service history. Recently serviced.",
        "service_history",
        claim("service_history", "Full service history"),
        claim("service_history", "Recently serviced", role="recent_service"),
    )
    assert fact.status == "known" and len(fact.public_fact()["evidence"]) == 2


def test_synthetic_complementary_history_text_is_not_inferred_conflicting(
    normalized: NormalizedCandidate,
) -> None:
    fact = resolve_synthetic(
        normalized,
        "Serviced regularly. Serviced recently.",
        "service_history",
        claim("service_history", "Serviced regularly"),
        claim("service_history", "Serviced recently"),
    )
    assert fact.status == "known"


@pytest.mark.parametrize("disposition", ["conditional", "ambiguous", "unreviewed"])
def test_synthetic_uncertain_vehicle_warranty_prevents_unqualified_known(
    normalized: NormalizedCandidate, disposition: Any
) -> None:
    text = "Warranty included. Cover subject to confirmation."
    fact = resolve_synthetic(
        normalized,
        text,
        "warranty",
        claim("warranty", "Warranty included"),
        claim("warranty", "Cover subject to confirmation", disposition=disposition),
    )
    assert fact.public_fact()["status"] == "unknown"


def test_synthetic_dealer_negative_does_not_erase_vehicle_evidence(
    normalized: NormalizedCandidate,
) -> None:
    fact = resolve_synthetic(
        normalized,
        "Petrol engine. Dealer has no petrol cars.",
        "fuel_type",
        claim("fuel_type", "Petrol engine", "petrol"),
        claim(
            "fuel_type",
            "Dealer has no petrol cars",
            "petrol",
            polarity="negative",
            subject="dealer",
            disposition="dealer_wide",
        ),
    )
    assert fact.public_fact()["value"] == "petrol" and fact.strict_match_eligible


@pytest.mark.parametrize("count", [20, 21])
def test_synthetic_public_conflict_group_boundary(
    normalized: NormalizedCandidate, count: int
) -> None:
    quotes = [f"offer{number} AED{number + 100} cash" for number in range(count)]
    fact = resolve_synthetic(
        normalized,
        "; ".join(quotes),
        "cash_price",
        *(cash(quote, (number + 100) * 100) for number, quote in enumerate(quotes)),
    )
    assert fact.public_fact()["status"] == ("conflicting" if count == 20 else "unknown")
    assert len(fact.claims) == count


@pytest.mark.parametrize("same_value", [False, True])
def test_synthetic_oversized_conflict_is_field_unknown_with_full_ledger(
    normalized: NormalizedCandidate, same_value: bool
) -> None:
    quotes = [
        f"offer{index} AED{100 if same_value and index < 21 else index + 101} cash"
        for index in range(22)
    ]
    annotations = tuple(
        cash(quote, (100 if same_value and index < 21 else index + 101) * 100)
        for index, quote in enumerate(quotes)
    )
    fact = resolve_synthetic(normalized, "; ".join(quotes), "cash_price", *annotations)
    assert fact.public_fact() == {"status": "unknown", "reason": "unsupported"}
    assert len(fact.claims) == 22 and not fact.strict_match_eligible


def test_synthetic_oversized_text_conflict_and_wrong_text_type_are_withheld(
    normalized: NormalizedCandidate,
) -> None:
    long_value = "a" * 201
    fact = resolve_synthetic(
        normalized,
        "First variant. Second variant.",
        "trim",
        claim("trim", "First variant", long_value),
        claim("trim", "Second variant", "other variant"),
    )
    assert fact.status == "unknown" and len(fact.claims) == 2
    wrong = resolve_synthetic(normalized, "Petrol", "fuel_type", claim("fuel_type", "Petrol", 123))
    assert wrong.status == "unknown"
