"""Physical identity is explicit, evidence bound, historical and transactionally checked."""

import json

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.models import InventorySnapshotPayload, ListingResourceMapping
from app.database.store import Store
from app.inventory.resource_lineage import ReviewedResourceMapping, lineage_version
from app.inventory.snapshot_codec import canonical_json, digest_text
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage
from tests.inventory.snapshot_cases import (
    counts,
    execute,
    mapping_for,
    record_evidence,
    with_mappings,
)


def test_explicit_predecessor_chain_roundtrips_without_remapping_history(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    first = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    second = with_mappings(second_plan, mapping_for(second_plan, predecessor=first))
    repo.stage(first)
    repo.stage(second)
    repo.activate(second.index.snapshot_id, expected_revision=0)
    assert repo.snapshot(first.index.snapshot_id) == first
    assert repo.snapshot(second.index.snapshot_id) == second
    resources = inventory_store.read(
        lambda session: session.execute(
            text("SELECT count(*) FROM vehicle_resources"),
        ).scalar_one()
    )
    assert resources == 1
    record_evidence(
        "explicit-lineage",
        {
            "root": first.mappings[0].model_dump(mode="json"),
            "successor": second.mappings[0].model_dump(mode="json"),
            "resource_count": resources,
            "original_mapping_preserved": True,
        },
    )


@pytest.mark.parametrize(
    "mutation", ["resource-version", "parent-evidence", "parent-version", "parent-projection"]
)
def test_successor_rejects_an_invalid_predecessor_even_when_mapping_fragment_matches(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    mutation: str,
) -> None:
    repo = InventoryRepository(inventory_store)
    first = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    second = with_mappings(second_plan, mapping_for(second_plan, predecessor=first))
    repo.stage(first)

    def corrupt(session: Session) -> None:
        if mutation == "resource-version":
            session.execute(text("UPDATE vehicle_resources SET mapping_version='corrupt-version'"))
            return
        if mutation == "parent-projection":
            session.execute(
                text("UPDATE listing_versions SET normalized_json='{}' WHERE source_id='12'")
            )
            return
        row = session.get(InventorySnapshotPayload, first.index.snapshot_id)
        assert row is not None
        data = json.loads(canonical_json(row.payload_json))
        if mutation == "parent-version":
            data["version"] = "unsupported-stage-version"
        else:
            evidence = next(item for item in first.candidate.evidence if item.ref.source_id != "12")
            data["mappings"][0]["source_evidence_ids"] = [evidence.evidence_id]
            forged = ReviewedResourceMapping.model_validate(data["mappings"][0])
            data["mapping_digest"] = lineage_version((forged,))
            mapping = session.scalars(select(ListingResourceMapping)).one()
            mapping.provenance_json = forged.model_dump(mode="json")
        row.payload_json = data
        row.payload_sha256 = digest_text(canonical_json(data))

    inventory_store.write(corrupt)
    with pytest.raises(ValueError):
        repo.stage(second)
    assert set(counts(inventory_store, second.index.snapshot_id).values()) == {0}
    assert repo.active().stage is None
    record_evidence(
        "predecessor-" + mutation,
        {
            "successor_rejected": True,
            "successor_rows": counts(inventory_store, second.index.snapshot_id),
        },
    )


@pytest.mark.parametrize("action", ["stage", "activate"])
def test_predecessor_changes_between_preparation_and_write_are_rechecked(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    action: str,
) -> None:
    repo = InventoryRepository(inventory_store)
    first = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    second = with_mappings(second_plan, mapping_for(second_plan, predecessor=first))
    repo.stage(first)
    if action == "activate":
        repo.stage(second)

    def change_after_preparation(phase: str) -> None:
        if phase == ("stage.prepared" if action == "stage" else "activation.prepared"):
            execute(
                inventory_store, "UPDATE vehicle_resources SET mapping_version='changed-after-read'"
            )

    faulty = InventoryRepository(inventory_store, _checkpoint=change_after_preparation)
    with pytest.raises(ValueError, match="RESOURCE_VERSION_MISMATCH"):
        if action == "stage":
            faulty.stage(second)
        else:
            faulty.activate(second.index.snapshot_id, expected_revision=0)
    assert repo.active().stage is None
    if action == "stage":
        assert set(counts(inventory_store, second.index.snapshot_id).values()) == {0}


@pytest.mark.parametrize("kind", ["existing-new-resource", "missing-resource", "wrong-predecessor"])
def test_numeric_source_id_does_not_authorize_resource_reuse(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    kind: str,
) -> None:
    repo = InventoryRepository(inventory_store)
    first = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    repo.stage(first)
    if kind == "existing-new-resource":
        mapping = mapping_for(second_plan)
    elif kind == "missing-resource":
        mapping = mapping_for(second_plan, predecessor=first, resource_label="missing-resource")
    else:
        mapping = mapping_for(second_plan, predecessor=first).model_copy(
            update={
                "predecessor_ref": first.candidate.manifest.reference("1"),
            }
        )
    with pytest.raises(ValueError, match="LINEAGE_"):
        repo.stage(with_mappings(second_plan, mapping))
    assert set(counts(inventory_store, second_plan.index.snapshot_id).values()) == {0}
    repo.stage(second_plan)
    assert repo.snapshot(second_plan.index.snapshot_id) == second_plan
    assert counts(inventory_store, second_plan.index.snapshot_id)["listing_resource_mappings"] == 0


def test_lineage_bound_rejects_before_any_successor_persistence(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = InventoryRepository(inventory_store)
    first = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    repo.stage(first)
    monkeypatch.setattr("app.inventory.snapshot_storage.MAX_LINEAGE_SNAPSHOTS", 1)
    with pytest.raises(ValueError, match="SNAPSHOT_LIMIT"):
        repo.stage(with_mappings(second_plan, mapping_for(second_plan, predecessor=first)))
    assert set(counts(inventory_store, second_plan.index.snapshot_id).values()) == {0}


def test_corrupted_predecessor_cycle_fails_closed(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    first = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    second = with_mappings(second_plan, mapping_for(second_plan, predecessor=first))
    repo.stage(first)
    repo.stage(second)

    def corrupt(session: Session) -> None:
        row = session.get(InventorySnapshotPayload, first.index.snapshot_id)
        assert row is not None
        data = json.loads(canonical_json(row.payload_json))
        cycle = first.mappings[0].model_copy(
            update={
                "decision": "reviewed_same_vehicle",
                "predecessor_ref": second.candidate.manifest.reference("12"),
            }
        )
        data["mappings"] = [cycle.model_dump(mode="json")]
        data["mapping_digest"] = lineage_version((cycle,))
        row.payload_json = data
        row.payload_sha256 = digest_text(canonical_json(data))
        mapping = session.get(
            ListingResourceMapping,
            (
                cycle.ref.namespace,
                cycle.ref.snapshot_id,
                cycle.ref.source_id,
            ),
        )
        assert mapping is not None
        mapping.provenance_json = cycle.model_dump(mode="json")

    inventory_store.write(corrupt)
    with pytest.raises(ValueError, match="CYCLE_REJECTED"):
        repo.activate(second.index.snapshot_id, expected_revision=0)
    assert repo.active().stage is None
    record_evidence("lineage-cycle", {"cycle_rejected": True, "no_activation": True})


def test_interrupted_stage_rolls_back_new_resource_as_well_as_index(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    def fail(phase: str) -> None:
        if phase == "stage.index":
            raise RuntimeError("SYNTHETIC_INTERRUPT_AFTER_RESOURCE")

    with pytest.raises(RuntimeError, match="SYNTHETIC"):
        InventoryRepository(inventory_store, _checkpoint=fail).stage(
            with_mappings(snapshot_plan, mapping_for(snapshot_plan)),
        )
    assert set(counts(inventory_store, snapshot_plan.index.snapshot_id).values()) == {0}
    assert (
        inventory_store.read(
            lambda session: session.execute(
                text("SELECT count(*) FROM vehicle_resources"),
            ).scalar_one()
        )
        == 0
    )
