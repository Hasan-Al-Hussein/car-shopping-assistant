"""Exact retained-history comparison, original batches and read-only factual handoff."""

from time import monotonic

import pytest
from pydantic import ValidationError

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import ComparisonRequest, ListingDetail, SearchCriteria
from app.core.errors import ApiFailure
from app.database.store import Store
from app.inventory.compact_reader import CompactReference
from app.inventory.details_service import InventoryDetailsService
from app.inventory.handoff import handoff
from app.inventory.public_projection import ListingEligibility, map_listing_detail
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage
from tests.inventory.compact_cases import admitted_pair
from tests.inventory.public_cases import public_harness


def test_mixed_history_missing_and_reused_id_preserve_exact_photos(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage
) -> None:
    reader, old = admitted_pair(inventory_store, snapshot_plan, second_plan)
    InventoryRepository(inventory_store).activate(
        second_plan.index.snapshot_id, expected_revision=old.active_revision
    )
    service = InventoryDetailsService(reader)
    old_ref = snapshot_plan.candidate.manifest.reference("12")
    current_ref = second_plan.candidate.manifest.reference("12")
    missing = current_ref.model_copy(update={"source_id": "absent"})
    before = inventory_store.path.read_bytes()
    result = service.compare(ComparisonRequest(refs=[current_ref, old_ref, missing]))
    assert [item.state for item in result.items] == ["current", "historical", "missing"]
    current, historical = result.items[:2]
    assert isinstance(current, ListingDetail) and isinstance(historical, ListingDetail)
    assert current.listing.ref.model_dump() == current_ref.model_dump()
    assert historical.listing.ref.model_dump() == old_ref.model_dump()
    assert current.listing.photo.url != historical.listing.photo.url
    assert current.listing.make != historical.listing.make
    assert historical.eligibility == "unavailable"
    assert inventory_store.path.read_bytes() == before


@pytest.mark.parametrize("state", ["missing", "error"])
def test_handoff_public_ref_preserves_missing_or_error_result(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    source_id = "absent" if state == "missing" else "12"
    ref = InventoryRef.model_validate(
        snapshot_plan.candidate.manifest.reference(source_id).model_dump()
    )
    if state == "error":

        def fail_mapping(
            item: CompactReference, *, eligibility: ListingEligibility | None = None
        ) -> ListingDetail:
            raise ValueError("SYNTHETIC_ITEM_PROJECTION_FAILURE")

        monkeypatch.setattr("app.inventory.details_service.map_listing_detail", fail_mapping)
    result = handoff(harness.details, ref, SearchCriteria())
    assert result.listing.state == state
    assert result.selected_ref.model_dump() == ref.model_dump()
    assert result.listing.model_dump()["ref"] == ref.model_dump()
    assert result.fit_reasons == []


def test_unadmitted_history_is_local_error_and_other_candidates_survive(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage
) -> None:
    reader, old = admitted_pair(inventory_store, snapshot_plan, second_plan)
    InventoryRepository(inventory_store).activate(
        second_plan.index.snapshot_id, expected_revision=old.active_revision
    )
    reader.invalidate()
    reader.admit(second_plan.index.snapshot_id)
    service = InventoryDetailsService(reader)
    refs = [
        second_plan.candidate.manifest.reference("12"),
        snapshot_plan.candidate.manifest.reference("12"),
        second_plan.candidate.manifest.reference("13"),
    ]
    result = service.compare(ComparisonRequest(refs=refs))
    assert [item.state for item in result.items] == ["current", "error", "current"]
    assert result.items[1].model_dump()["code"] == "SNAPSHOT_STALE"
    assert result.items[1].model_dump()["ref"] == refs[1].model_dump()


def test_projection_failure_does_not_erase_other_compared_cars(
    inventory_store: Store, snapshot_plan: PreparedStage, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)

    def mapping(
        item: CompactReference, *, eligibility: ListingEligibility | None = None
    ) -> ListingDetail:
        if item.ref.source_id == "13":
            raise ValueError("SYNTHETIC_ITEM_PROJECTION_FAILURE")
        return map_listing_detail(item, eligibility=eligibility)

    monkeypatch.setattr("app.inventory.details_service.map_listing_detail", mapping)
    refs = [
        snapshot_plan.candidate.manifest.reference(source_id) for source_id in ("12", "13", "20")
    ]
    result = harness.details.compare(ComparisonRequest(refs=refs))
    assert [item.state for item in result.items] == ["current", "error", "current"]
    assert result.items[1].model_dump()["ref"] == refs[1].model_dump()


def test_original_50_batch_order_duplicates_and_empty_are_not_comparison(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    refs = tuple(row.ref for row in reversed(snapshot_plan.candidate.listings[:49]))
    requested = (*refs, refs[0])
    result = harness.details.original_batch(requested)
    assert len(result) == 50 and all(isinstance(item, ListingDetail) for item in result)
    assert tuple(
        item.listing.ref.model_dump() for item in result if isinstance(item, ListingDetail)
    ) == tuple(ref.model_dump() for ref in requested)
    assert harness.details.original_batch(()) == ()
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        harness.details.original_batch((*requested, refs[0]))
    with pytest.raises(ValidationError):
        ComparisonRequest(refs=list(refs[:4]))
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        harness.details.lookup(refs[0], deadline_at=monotonic() - 1)


def test_handoff_preserves_expressed_needs_and_own_evidence_without_action(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    harness = public_harness(inventory_store, snapshot_plan)
    ref = snapshot_plan.candidate.manifest.reference("12")
    criteria = SearchCriteria.model_validate(
        {
            "filters": {
                "makes": [" Mazda "],
                "budget": {"currency": "AED", "maximum": 4000000},
                "mileage_km": {"maximum": 50000},
            }
        }
    )
    before = inventory_store.path.read_bytes()
    result = handoff(harness.details, ref, criteria)
    assert (
        result.selected_ref.model_dump() == ref.model_dump()
        and result.expressed_criteria == criteria
    )
    assert {reason.attribute for reason in result.fit_reasons} == {"make", "cash_price"}
    assert [question.attribute for question in result.unresolved_questions] == ["mileage_km"]
    assert isinstance(result.listing, ListingDetail)
    assert result.listing.eligibility == "configuration_missing"
    own_ids = {
        e.evidence_id
        for fact in (result.listing.listing.make, result.listing.listing.cash_price)
        if fact.status == "known"
        for e in fact.evidence
    }
    assert all(set(reason.evidence_ids) <= own_ids for reason in result.fit_reasons)
    assert inventory_store.path.read_bytes() == before
