"""Complete staging, activation boundaries, immutable reuse and retained history."""

import json
from dataclasses import replace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database.store import Store, open_store
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage, stage_payload
from tests.inventory.snapshot_cases import (
    NOW,
    anchors,
    counts,
    execute,
    mapping_for,
    record_evidence,
    seed_historical_anchors,
    with_mappings,
)


def test_complete_stage_reopen_and_readonly_roundtrip(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    repository = InventoryRepository(inventory_store, clock=lambda: NOW)
    receipt = repository.stage(snapshot_plan)
    assert not receipt.reused
    assert repository.active().stage is None
    before = inventory_store.path.read_bytes()
    reopened = InventoryRepository(open_store(inventory_store.path, boundary=inventory_store.boundary))
    loaded = reopened.snapshot(snapshot_plan.index.snapshot_id)
    assert loaded is not None
    assert loaded == snapshot_plan
    assert stage_payload(loaded) == stage_payload(snapshot_plan)
    assert inventory_store.path.read_bytes() == before
    persisted = counts(inventory_store, receipt.snapshot_id)
    assert persisted == {
        "inventory_snapshots": 1,
        "inventory_snapshot_payloads": 1,
        "listing_versions": 100,
        "attribute_evidence": 1079,
        "inventory_search_documents": 100,
        "listing_resource_mappings": 0,
    }
    record_evidence(
        "complete-roundtrip",
        {
            "store": str(inventory_store.path),
            "snapshot": receipt.snapshot_id,
            "index": receipt.index_version,
            "payload_sha256": receipt.payload_sha256,
            "counts": persisted,
            "all_source_claims_and_photos_equal": loaded == snapshot_plan,
            "read_reopen_unchanged_bytes": True,
            "active": False,
        },
    )


def test_reuse_and_activation_revision_rules(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    assert repo.stage(snapshot_plan).reused
    first = repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    assert first.active_revision == 1
    assert repo.activate(snapshot_plan.index.snapshot_id, expected_revision=1) == first
    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    with pytest.raises(ValueError, match="METADATA_MISMATCH"):
        repo.stage(replace(snapshot_plan, policy_version="different-policy"))
    repo.stage(second_plan)
    second = repo.activate(second_plan.index.snapshot_id, expected_revision=1)
    old = repo.activate(snapshot_plan.index.snapshot_id, expected_revision=2)
    assert second.active_revision == 2 and old.active_revision == 3
    assert repo.snapshot(snapshot_plan.index.snapshot_id) == snapshot_plan
    record_evidence(
        "reuse-reactivation",
        {
            "first": first.model_dump(),
            "second": second.model_dump(),
            "reactivated": old.model_dump(),
            "identical_reuse": True,
            "incompatible_reuse_rejected": True,
        },
    )


@pytest.mark.parametrize(
    "boundary",
    [
        "stage.snapshot",
        "stage.listings",
        "stage.evidence",
        "stage.index",
        "stage.validated",
    ],
)
def test_interrupted_stage_preserves_active_and_rolls_back_complete_candidate(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    boundary: str,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    active = repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)

    def fail(phase: str) -> None:
        if phase == boundary:
            raise RuntimeError("SYNTHETIC_STAGE_INTERRUPTION")

    with pytest.raises(RuntimeError, match="SYNTHETIC"):
        InventoryRepository(inventory_store, _checkpoint=fail).stage(second_plan)
    restarted = InventoryRepository(open_store(inventory_store.path, boundary=inventory_store.boundary))
    assert restarted.active().observation == active
    assert restarted.snapshot(second_plan.index.snapshot_id) is None
    assert set(counts(inventory_store, second_plan.index.snapshot_id).values()) == {0}
    fts_count = inventory_store.read(
        lambda session: session.execute(
            text("SELECT count(*) FROM inventory_search_fts WHERE snapshot_id=:snapshot"),
            {"snapshot": second_plan.index.snapshot_id},
        ).scalar_one()
    )
    assert fts_count == 0
    record_evidence(
        boundary.replace(".", "-") + "-rollback",
        {
            "active": active.model_dump(),
            "new_candidate_counts": counts(inventory_store, second_plan.index.snapshot_id),
            "new_fts_rows": fts_count,
            "reopened": True,
        },
    )


@pytest.mark.parametrize(
    "boundary", ["activation.pointer", "activation.committed", "stage.committed"]
)
def test_commit_boundary_failures_report_actual_persisted_state(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    boundary: str,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    first = repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)

    def fail(phase: str) -> None:
        if phase == boundary:
            raise RuntimeError("SYNTHETIC_LOST_RESPONSE")

    faulty = InventoryRepository(inventory_store, _checkpoint=fail)
    if boundary == "stage.committed":
        with pytest.raises(RuntimeError, match="LOST_RESPONSE"):
            faulty.stage(second_plan)
        assert repo.snapshot(second_plan.index.snapshot_id) == second_plan
        assert repo.stage(second_plan).reused
    else:
        repo.stage(second_plan)
        with pytest.raises(RuntimeError, match="LOST_RESPONSE"):
            faulty.activate(second_plan.index.snapshot_id, expected_revision=1)
    current = InventoryRepository(open_store(inventory_store.path, boundary=inventory_store.boundary)).active().observation
    committed = boundary == "activation.committed"
    assert current.snapshot_id == (
        second_plan.index.snapshot_id if committed else first.snapshot_id
    )
    assert current.active_revision == (2 if committed else 1)
    record_evidence(
        boundary.replace(".", "-") + "-failure",
        {
            "observed_after_reopen": current.model_dump(),
            "activation_committed": committed,
            "response_failure_is_not_rollback_proof": True,
        },
    )


def test_historical_refs_receipts_and_photos_never_retarget(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    mapped = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    repo = InventoryRepository(inventory_store)
    repo.stage(mapped)
    repo.activate(mapped.index.snapshot_id, expected_revision=0)
    inventory_store.write(
        lambda session: seed_historical_anchors(session, inventory_store.generation, mapped)
    )
    before = anchors(inventory_store)
    old_ref = mapped.candidate.manifest.reference("12")
    old_listing = repo.listing(old_ref)
    repo.stage(second_plan)
    repo.activate(second_plan.index.snapshot_id, expected_revision=1)
    historical = repo.listing(old_ref)
    current = repo.listing(second_plan.candidate.manifest.reference("12"))
    assert historical.state == "historical" and historical.listing == old_listing.listing
    assert current.state == "current" and current.listing != historical.listing
    assert historical.listing is not None and current.listing is not None
    old_data = json.loads(historical.listing.normalized_json)
    new_data = json.loads(current.listing.normalized_json)
    assert old_data["photo"].get("url") != new_data["photo"].get("url")
    old_make = next(item for item in old_data["resolutions"] if item["family"] == "make")
    new_make = next(item for item in new_data["resolutions"] if item["family"] == "make")
    assert old_make["groups"][0]["value"]["value"] != "synthetic different make"
    assert new_make["groups"][0]["value"]["value"] == "synthetic different make"
    assert anchors(inventory_store) == before
    missing = old_ref.model_copy(update={"snapshot_id": "f" * 64})
    assert repo.listing(missing).state == "missing"
    with pytest.raises(IntegrityError):
        execute(
            inventory_store,
            "DELETE FROM listing_versions WHERE snapshot_id=:snapshot AND source_id='12'",
            {"snapshot": mapped.index.snapshot_id},
        )
    assert anchors(inventory_store) == before
    record_evidence(
        "historical-anchors",
        {
            "old_ref": old_ref.model_dump(),
            "current_ref": current.ref.model_dump(),
            "old_listing_and_photo_unchanged": True,
            "receipt_shortlist_presentation_unchanged": True,
            "referenced_removal_rejected": True,
        },
    )


def test_revision_exhaustion_rejects_before_commit(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.stage(second_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    execute(inventory_store, "UPDATE active_inventory SET revision=2147483647 WHERE id=1")
    with pytest.raises(ValueError):
        repo.activate(second_plan.index.snapshot_id, expected_revision=2147483647)
    assert repo.active().observation.snapshot_id == snapshot_plan.index.snapshot_id
    assert repo.active().observation.active_revision == 2147483647
