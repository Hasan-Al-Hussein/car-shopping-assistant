"""Full reviewed corpus oracle and exact cross-listing evidence/qualifier/photo checks."""

import json
from dataclasses import replace

import pytest

from app.inventory.compact_reader import CompactReference
from app.inventory.extraction import ExtractedCandidate
from app.inventory.public_projection import (
    ListingEligibility,
    map_listing_detail,
    map_listing_summary,
)
from app.inventory.review_catalogue import PUBLIC_FAMILIES
from app.inventory.snapshot_codec import PreparedCandidate, canonical_json


def test_all_100_public_facts_equal_accepted_resolutions_and_original_photos(
    prepared_snapshot: PreparedCandidate, snapshot_candidate: ExtractedCandidate
) -> None:
    accepted = {record.normalized.ref: record for record in snapshot_candidate.records}
    assert len(prepared_snapshot.listings) == len(accepted) == 100
    for row in prepared_snapshot.listings:
        source = accepted[row.ref]
        summary = map_listing_summary(row)
        detail = map_listing_detail(CompactReference(row.ref, "current", row))
        assert detail.listing == summary
        data = {**detail.model_dump(mode="json"), **summary.model_dump(mode="json")}
        for family in PUBLIC_FAMILIES:
            assert data[family] == source.fact(family).public_fact()
        assert summary.photo.model_dump() == source.normalized.photo.model_dump()
        assert detail.description == (source.normalized.text("description").display or "")
        assert summary.title == (
            source.normalized.text("title").display or f"Listing {row.ref.source_id}"
        )
        assert detail.eligibility == "configuration_missing"
        assert all(
            locator["verification"] == "source_claim"
            for fact in (data[family] for family in PUBLIC_FAMILIES)
            for group in ([fact] if fact["status"] == "known" else fact.get("claims", []))
            for locator in group["evidence"]
        )


def test_foreign_claim_and_changed_raw_span_are_rejected(
    prepared_snapshot: PreparedCandidate,
) -> None:
    original = next(row for row in prepared_snapshot.listings if row.ref.source_id == "12")
    for defect in ("parent", "span"):
        data = json.loads(original.normalized_json)
        claim = data["claims"][0]
        if defect == "parent":
            claim["ref"]["source_id"] = "13"
        else:
            claim["evidence"][0]["raw_text"] = "changed"
        forged = replace(original, normalized_json=canonical_json(data))
        with pytest.raises(ValueError):
            map_listing_summary(forged)


def test_money_and_conflict_are_not_repaired_by_projection(
    prepared_snapshot: PreparedCandidate,
) -> None:
    rows = {row.ref.source_id: row for row in prepared_snapshot.listings}
    price = map_listing_summary(rows["3"]).cash_price
    assert price.status == "known" and price.value.minor_units == 11975000
    assert price.value.currency == "AED" and price.value.basis == "cash"
    assert all(locator.semantic_role == "cash_price" for locator in price.evidence)
    assert map_listing_summary(rows["6"]).cash_price.status == "unknown"
    trim = map_listing_summary(rows["4"]).trim
    assert trim.status == "conflicting" and {claim.value for claim in trim.claims} == {
        "e 400",
        "e 450",
    }
    historical = map_listing_detail(
        CompactReference(rows["12"].ref, "historical", rows["12"]),
        eligibility=ListingEligibility("simulated_eligible", "test config"),
    )
    assert historical.eligibility == "unavailable"


def test_withheld_display_is_not_replaced_by_raw_markup(
    prepared_snapshot: PreparedCandidate,
) -> None:
    original = prepared_snapshot.listings[0]
    data = json.loads(original.normalized_json)
    # Synthetic accepted representation seam; raw source is never re-parsed by the mapper.
    data["fields"]["title"]["text"].update(state="withheld", display=None, search=None)
    data["fields"]["description"]["text"].update(state="withheld", display=None, search=None)
    row = replace(original, normalized_json=canonical_json(data))
    detail = map_listing_detail(CompactReference(row.ref, "current", row))
    assert detail.listing.title == f"Listing {row.ref.source_id}" and detail.description == ""
    assert any("source text" in warning for warning in detail.listing.evidence_warnings)
