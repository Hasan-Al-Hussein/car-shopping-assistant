"""Coherent publication, same-unit recheck and predecessor mutation regressions."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database.store import Store, initialize_store
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage
from tests.inventory.compact_cases import admitted, admitted_pair
from tests.inventory.snapshot_cases import execute, mapping_for, with_mappings
from tests.support.harness import unopened_store_plan


def test_activation_between_pointer_and_projection_returns_one_coherent_tuple(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage
) -> None:
    selected, pointer_changed, reader_closed = Event(), Event(), Event()
    enabled = False

    def reader_checkpoint(phase: str) -> None:
        if enabled and phase == "compact.active_selected":
            selected.set()
            assert pointer_changed.wait(10), "writer did not prepare its new pointer"

    def writer_checkpoint(phase: str) -> None:
        if phase == "activation.pointer":
            pointer_changed.set()
            assert reader_closed.wait(10), "pinned read did not finish before writer commit"

    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.stage(second_plan)
    old = repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    reader = CompactInventoryReader(inventory_store, _checkpoint=reader_checkpoint)
    reader.admit(snapshot_plan.index.snapshot_id)
    reader.admit(second_plan.index.snapshot_id)
    refs = (
        snapshot_plan.candidate.manifest.reference("12"),
        second_plan.candidate.manifest.reference("12"),
    )

    def read_old() -> CompactBatch:
        try:
            return reader.read_refs(refs)
        finally:
            reader_closed.set()

    enabled = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        old_future = pool.submit(read_old)
        try:
            assert selected.wait(10), "reader did not pin an active tuple"
            new_future = pool.submit(
                InventoryRepository(inventory_store, _checkpoint=writer_checkpoint).activate,
                second_plan.index.snapshot_id,
                expected_revision=1,
            )
            pinned = old_future.result(timeout=15)
            committed = new_future.result(timeout=15)
        finally:
            pointer_changed.set()
            reader_closed.set()
    enabled = False
    assert pinned.observation == old
    assert tuple(item.state for item in pinned.items) == ("current", "historical")
    fresh = reader.read_refs(refs)
    assert fresh.observation == committed
    assert tuple(item.state for item in fresh.items) == ("historical", "current")
    assert tuple(item.listing for item in pinned.items) == tuple(
        item.listing for item in fresh.items
    )


def test_mutation_after_audit_before_certificate_publication_is_not_trusted(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)

    def mutate(phase: str) -> None:
        if phase == "admission.before_publish":
            execute(
                inventory_store,
                "UPDATE listing_versions SET original_json='{}' WHERE source_id='12'",
            )

    reader = CompactInventoryReader(inventory_store, _checkpoint=mutate)
    reader.admit(snapshot_plan.index.snapshot_id)
    with pytest.raises(ValueError, match="CERTIFIED_CONTENT_CHANGED"):
        reader.read_refs((snapshot_plan.candidate.manifest.reference("1"),))


@pytest.mark.parametrize(
    "marker,statement,error",
    [
        ("migration", "UPDATE alembic_version SET version_num='0001'", "SCHEMA_VERSION_MISMATCH"),
        ("migration-missing", "DELETE FROM alembic_version", "SCHEMA_VERSION_MISMATCH"),
        (
            "migration-extra",
            "INSERT INTO alembic_version(version_num) VALUES('0001')",
            "SCHEMA_VERSION_MISMATCH",
        ),
        ("metadata", "UPDATE store_metadata SET schema_version='0001'", "STORE_IDENTITY_MISMATCH"),
        (
            "profile",
            "UPDATE inventory_storage_profile SET mode='bounded_lexical'",
            "STORAGE_PROFILE_MISMATCH",
        ),
        (
            "generation",
            "UPDATE store_metadata SET store_generation='00000000-0000-0000-0000-000000000001'",
            "STORE_IDENTITY_MISMATCH",
        ),
    ],
    ids=["migration", "migration-missing", "migration-extra", "metadata", "profile", "generation"],
)
def test_identity_marker_mutation_after_preflight_is_rejected_in_same_unit(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    marker: str,
    statement: str,
    error: str,
) -> None:
    reader, observation = admitted(inventory_store, snapshot_plan)
    batch = reader.read_refs(())

    def mutate_then_recheck(session: Session) -> None:
        session.connection().exec_driver_sql(statement)
        reader.recheck(session, batch)

    with pytest.raises(ValueError, match=error):
        inventory_store.write(mutate_then_recheck)
    # The failed owned unit rolls back the mutation, but still loses admission.
    with pytest.raises(ValueError, match="AUDIT_ADMISSION_REQUIRED"):
        reader.read_header()
    assert InventoryRepository(inventory_store).active().observation == observation, marker


@pytest.mark.parametrize(
    "mutation", ["parent-projection", "parent-envelope", "resource", "mapping"]
)
def test_predecessor_changes_after_prepare_abort_consuming_write(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    mutation: str,
) -> None:
    first = with_mappings(snapshot_plan, mapping_for(snapshot_plan))
    second = with_mappings(second_plan, mapping_for(second_plan, predecessor=first))
    reader, old = admitted_pair(inventory_store, first, second)
    InventoryRepository(inventory_store).activate(second.index.snapshot_id, expected_revision=1)
    ref = second.candidate.manifest.reference("12")
    batch = reader.read_refs((ref,))
    assert batch.items[0].mapping == second.mappings[0]
    assert batch.items[0].resource_version == first.mappings[0].mapping_version
    mutations = {
        "parent-projection": "UPDATE listing_versions SET original_json='{}' WHERE snapshot_id=:s",
        "parent-envelope": (
            "UPDATE inventory_snapshot_payloads SET payload_json='{}' WHERE snapshot_id=:s"
        ),
        "resource": "UPDATE vehicle_resources SET mapping_version='changed'",
        "mapping": "UPDATE listing_resource_mappings SET provenance_json='{}' WHERE snapshot_id=:s",
    }
    execute(inventory_store, mutations[mutation], {"s": first.index.snapshot_id})

    def consuming_write(session: Session) -> None:
        # A real mutation before validation must be rolled back if the recheck fails.
        session.connection().exec_driver_sql(
            "UPDATE active_inventory SET revision=revision+1 WHERE id=1"
        )
        reader.recheck_identity(session, batch.identity, expected_refs=(ref,))

    with pytest.raises(ValueError, match="CERTIFIED_CONTENT_CHANGED"):
        inventory_store.write(consuming_write)
    revision = inventory_store.read(
        lambda session: (
            session.connection()
            .exec_driver_sql("SELECT revision FROM active_inventory WHERE id=1")
            .scalar_one()
        )
    )
    assert revision == old.active_revision + 1


def test_unrelated_staging_requires_new_global_fts_admission(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage
) -> None:
    reader, observation = admitted(inventory_store, snapshot_plan)
    InventoryRepository(inventory_store).stage(second_plan)
    with pytest.raises(ValueError, match="CERTIFIED_CONTENT_CHANGED"):
        reader.read_header()
    reader.admit(snapshot_plan.index.snapshot_id)
    assert reader.read_header() == observation


def test_valid_foreign_store_unit_and_ended_transaction_are_rejected(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    batch = reader.read_refs(())
    foreign = initialize_store(
        Path(
            unopened_store_plan(
                run_id=str(uuid4()), case_id="case-i5-foreign-unit", generation=str(uuid4())
            ).path
        ),
        boundary=inventory_store.boundary,
    )
    with pytest.raises(ValueError, match="STORE_IDENTITY_MISMATCH"):
        foreign.read(lambda session: reader.recheck(session, batch))
    reader.admit(snapshot_plan.index.snapshot_id)
    batch = reader.read_refs(())

    def end_then_recheck(session: Session) -> None:
        session.connection().rollback()
        reader.recheck(session, batch)

    with pytest.raises(ValueError, match="EXISTING_STORE_UNIT_REQUIRED"):
        inventory_store.write(end_then_recheck)
