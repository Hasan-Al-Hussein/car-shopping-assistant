"""Synthetic compact-reader setup; invoked only by granted tests and measurements."""

from app.core.readiness import InventoryObservation
from app.database.store import Store
from app.inventory.compact_reader import CompactInventoryReader
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage


def admitted(
    store: Store, plan: PreparedStage
) -> tuple[CompactInventoryReader, InventoryObservation]:
    repo = InventoryRepository(store)
    repo.stage(plan)
    observation = repo.activate(plan.index.snapshot_id, expected_revision=0)
    reader = CompactInventoryReader(store)
    reader.admit(plan.index.snapshot_id)
    return reader, observation


def admitted_pair(
    store: Store, first: PreparedStage, second: PreparedStage
) -> tuple[CompactInventoryReader, InventoryObservation]:
    repo = InventoryRepository(store)
    repo.stage(first)
    repo.stage(second)
    observation = repo.activate(first.index.snapshot_id, expected_revision=0)
    reader = CompactInventoryReader(store)
    reader.admit(first.index.snapshot_id)
    reader.admit(second.index.snapshot_id)
    return reader, observation
