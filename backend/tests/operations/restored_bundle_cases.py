"""Future T12 tests use an actual completed T11 restore and actual adopted inventory.

Fixture setup activates the restored snapshot explicitly. The producer never does.
Source-only until a separate applied-source runtime grant; no synthetic completion.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from app.database.store import Store, open_store
from app.inventory.snapshots import InventoryRepository
from app.operations.backup_files import BackupFiles
from app.operations.backup_restore import BackupService
from app.operations.restore_files import encoded
from app.operations.restore_operator import RestoreService
from app.operations.restored_bundle_contract import (
    RESTORED_BUNDLE_ROOT,
    RestoredBundleRequest,
    RestoredBundleResult,
)
from app.operations.restored_inventory_bundle import produce_restored_inventory_bundle
from app.operations.viewing_configuration import ActivationRequest, ViewingConfigurationOperator
from tests.operations.activation_cases import ActivationCase


@dataclass(frozen=True)
class RestoredBundleCase:
    store: Store
    project: Path
    request: RestoredBundleRequest
    restore_receipt_path: Path

    @property
    def bundle_dir(self) -> Path:
        return self.project / self.request.bundle

    def produce(self) -> RestoredBundleResult:
        return produce_restored_inventory_bundle(
            str(self.store.path),
            boundary=self.store.boundary,
            project_root=self.project,
            request=self.request,
        )

    def activation_request(self, result: RestoredBundleResult) -> ActivationRequest:
        return ActivationRequest(
            operation_id=self.request.operation_id,
            generation=self.request.expected_generation,
            configuration_id=result.configuration_id,
            expected_active_version=None,
            expected_revision=0,
            bundle=self.request.bundle,
            receipt_sha256=result.receipt_sha256,
        )

    def operator(
        self, checkpoint: Callable[[str], None] = lambda phase: None
    ) -> ViewingConfigurationOperator:
        return ViewingConfigurationOperator(
            str(self.store.path),
            boundary=self.store.boundary,
            project_root=self.project,
            _checkpoint=checkpoint,
        )


@pytest.fixture
def restored_bundle_case(activation_case: ActivationCase) -> RestoredBundleCase:
    original = activation_case.store
    selected = BackupService(original).create()
    completed = RestoreService(original.path, boundary=original.boundary).restore(
        selected.backup_id, expected_generation=original.generation
    )
    restored = open_store(original.path, boundary=original.boundary)
    assert restored.generation == completed.intent.candidate.new_generation
    assert restored.generation != original.generation
    repository = InventoryRepository(restored)
    absent = repository.active()
    assert absent.stage is None and absent.observation.snapshot_id is None
    assert absent.observation.active_revision == 0
    snapshot = activation_case.config.inventory.snapshot_id
    assert snapshot is not None
    observation = repository.activate(snapshot, expected_revision=0)
    catalogue = BackupFiles.for_store_path(restored.path, boundary=restored.boundary)
    receipt_path = catalogue.directory(create=False) / (
        f"restore.{completed.intent.restore_id}.receipt.json"
    )
    actual_receipt = receipt_path.read_bytes()
    assert actual_receipt == encoded(completed)
    request = RestoredBundleRequest(
        operation_id=activation_case.request.operation_id,
        restore_id=completed.intent.restore_id,
        restore_receipt_sha256=hashlib.sha256(actual_receipt).hexdigest(),
        expected_generation=restored.generation,
        expected_inventory=observation,
        bundle=RESTORED_BUNDLE_ROOT + activation_case.request.operation_id,
    )
    return RestoredBundleCase(restored, activation_case.project, request, receipt_path)
