"""Genuine sealed-v1 authority consumed by R2 and actual Inventory/I9 APIs.

Source authored, NOT_RUN. Only named interruption points are synthetic; positive
restore, native exclusion, candidate transformation and producer work are real.
"""

import hashlib
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.database.maintenance import maintenance_paths
from app.database.models import Lead, StoreMetadata
from app.database.store import open_store
from app.operations.backup_files import BackupError, BackupFiles
from app.operations.backup_restore import BackupService
from app.operations.restore_completion import completed_restore_scope
from app.operations.restore_files import RestoreIntent, RestoreReceipt, encoded
from app.operations.restore_operator import RestoreService
from app.operations.restore_transition import RestoreIntentV2, parse_intent, parse_receipt
from app.operations.restored_readmission import ReadmissionRequest, run_readmission
from tests.operations.activation_cases import ActivationCase, business_state
from tests.operations.backup_fixtures import make_backup_harness
from tests.operations.test_restore_retention import stop_pending
from tests.operations.v1_restore_fixtures import SealedV1
from tests.operations.v1_restore_fixtures import sealed_v1 as sealed_v1


class V1Interrupted(BaseException):
    """Synthetic lost control flow, never native process-kill evidence."""


def test_sealed_v1_strictly_refuses_actual_v2_marker_without_effects(
    monkeypatch: pytest.MonkeyPatch, sealed_v1: SealedV1,
) -> None:
    backup = make_backup_harness(monkeypatch)
    flow = backup.retention.projection
    flow.save()
    selected = backup.service.create()
    pending = stop_pending(backup, selected, monkeypatch, phase="before_swap")
    assert pending.format == "store-restore-2"
    marker = maintenance_paths(flow.store.path, boundary=flow.store.boundary).intent_path
    paths = (
        marker, flow.store.path,
        backup.service.files.path(selected.backup_id, "pin.json"),
        backup.service.files.path(pending.previous.backup_id, "pin.json"),
        backup.service.files.path(selected.backup_id, "sqlite3"),
        backup.service.files.path(pending.previous.backup_id, "sqlite3"),
        backup.service.files.path(pending.candidate.candidate_id, "sqlite3"),
    )
    before = {path: path.read_bytes() for path in paths}
    old = sealed_v1.service(
        flow.store.path, boundary=flow.store.boundary, clock=flow.leads.sessions.clock.now,
    )
    with pytest.raises(BackupError, match="^RESTORE_INTENT_INVALID$"):
        old.inspect()
    assert {path: path.read_bytes() for path in paths} == before
    current = RestoreService(
        flow.store.path, boundary=flow.store.boundary, clock=flow.leads.sessions.clock.now,
    )
    assert current.inspect() == pending
    assert {path: path.read_bytes() for path in paths} == before


def test_genuine_v1_pending_without_expiry_completes_without_wire_upgrade(
    monkeypatch: pytest.MonkeyPatch, sealed_v1: SealedV1,
) -> None:
    backup = make_backup_harness(monkeypatch)
    flow = backup.retention.projection
    base = flow.leads.sessions
    saved = flow.save()
    selected = backup.service.create()
    old = sealed_v1.service(base.store.path, boundary=base.store.boundary, clock=base.clock.now)

    def stop(*args: object) -> None:
        raise V1Interrupted("after actual sealed-v1 marker before swap")

    with monkeypatch.context() as fault:
        fault.setattr(old, "_continue", stop)
        with pytest.raises(V1Interrupted):
            old.restore(selected.backup_id, expected_generation=base.store.generation)
    issued = old.inspect()
    assert issued is not None and type(issued) is sealed_v1.files.RestoreIntent
    marker = maintenance_paths(base.store.path, boundary=base.store.boundary).intent_path
    wire = marker.read_bytes()
    assert wire == sealed_v1.encode(issued)
    pending = parse_intent(wire)
    assert isinstance(pending, RestoreIntent)
    observed = RestoreService(
        base.store.path, boundary=base.store.boundary, clock=base.clock.now,
    ).resume_observed(restore_id=pending.restore_id)
    assert isinstance(observed.receipt, RestoreReceipt)
    assert observed.receipt.format == "store-restore-receipt-1"
    assert observed.receipt.intent == pending and encoded(observed.receipt.intent) == wire
    assert observed.projection == "current" and observed.completion == "completed_current"
    restored = open_store(base.store.path, boundary=base.store.boundary)
    assert restored.generation == pending.candidate.new_generation
    assert restored.read(lambda db: db.get(Lead, saved.lead_id) is not None)
    assert len(flow.rows()) == 1 and not marker.exists()
    assert not backup.service.files.pinned(selected.backup_id)
    assert backup.service.files.pinned(pending.previous.backup_id)


@pytest.mark.parametrize("phase", ["before_swap", "after_swap"])
def test_real_v1_pending_expiry_becomes_same_identity_v2_transform(
    monkeypatch: pytest.MonkeyPatch, sealed_v1: SealedV1, phase: str,
) -> None:
    backup = make_backup_harness(monkeypatch)
    flow = backup.retention.projection
    base = flow.leads.sessions
    saved = flow.save()
    base.clock.value += timedelta(days=89)
    selected = backup.service.create()
    original = sealed_v1.service(base.store.path, boundary=base.store.boundary, clock=base.clock.now)
    with monkeypatch.context() as fault:
        if phase == "before_swap":
            def stop(*args: object) -> None:
                raise V1Interrupted("after actual sealed-v1 marker before swap")
            fault.setattr(original, "_continue", stop)
        else:
            actual_replace = sealed_v1.operator.os.replace

            def swapped(source: Path, target: Path) -> None:
                actual_replace(source, target)
                if target == base.store.path.resolve():
                    raise V1Interrupted("after actual sealed-v1 canonical swap")
            fault.setattr(sealed_v1.operator.os, "replace", swapped)
        with pytest.raises(V1Interrupted):
            original.restore(selected.backup_id, expected_generation=base.store.generation)
    issued = original.inspect()
    assert issued is not None and type(issued) is sealed_v1.files.RestoreIntent
    marker = maintenance_paths(base.store.path, boundary=base.store.boundary).intent_path
    original_bytes = marker.read_bytes()
    assert original_bytes == sealed_v1.encode(issued)
    pending = parse_intent(original_bytes)  # Interpret genuine bytes; do not rewrite them.
    assert isinstance(pending, RestoreIntent) and pending.format == "store-restore-1"
    assert encoded(pending) == original_bytes
    source_bytes = backup.service.files.path(selected.backup_id, "sqlite3").read_bytes()
    prior_bytes = backup.service.files.path(pending.previous.backup_id, "sqlite3").read_bytes()
    base.clock.value += timedelta(days=2)
    observed = RestoreService(base.store.path, boundary=base.store.boundary, clock=base.clock.now).resume_observed(
        restore_id=pending.restore_id,
    )
    revised = observed.receipt.intent
    assert isinstance(revised, RestoreIntentV2)
    assert revised.initial_retention is None  # Old operator never ran an R2 initial sweep.
    assert revised.initial_candidate_id == pending.candidate.candidate_id
    assert revised.restore_id == pending.restore_id and revised.started_at == pending.started_at
    assert revised.selected == pending.selected and revised.previous == pending.previous
    assert revised.candidate.new_generation == pending.candidate.new_generation
    assert revised.candidate.prepared_at == pending.candidate.prepared_at
    assert revised.candidate.recovery_point == pending.candidate.recovery_point
    assert revised.superseded_candidate == pending.candidate and revised.revision == 1
    assert len(revised.retention_steps) == 1 and revised.retention_steps[0].protected_expired_leads == 0
    assert observed.projection == "current" and observed.completion == "completed_current"
    restored = open_store(base.store.path, boundary=base.store.boundary)
    assert restored.read(lambda db: db.get(Lead, saved.lead_id) is None)
    assert restored.read(lambda db: db.scalar(select(func.count()).select_from(Lead))) == 0
    assert restored.read(lambda db: db.scalar(select(StoreMetadata.restored_at))) == pending.candidate.prepared_at
    assert flow.rows() == [] and not marker.exists()
    assert backup.service.files.path(selected.backup_id, "sqlite3").read_bytes() == source_bytes
    assert backup.service.files.path(pending.previous.backup_id, "sqlite3").read_bytes() == prior_bytes
    assert backup.service.files.pinned(pending.previous.backup_id)


def test_genuine_completed_v1_receipt_survives_observer_and_real_inventory_i9_readmission(
    activation_case: ActivationCase, sealed_v1: SealedV1,
) -> None:
    # Existing I9 fixture contains actual admitted inventory with explicitly
    # synthetic initial producer-format provenance. It is not bootstrap CLI proof.
    initial = activation_case.store
    selected = BackupService(initial).create()
    old = sealed_v1.service(initial.path, boundary=initial.boundary)
    completed = old.restore(selected.backup_id, expected_generation=initial.generation)
    assert type(completed) is sealed_v1.files.RestoreReceipt
    wire = sealed_v1.encode(completed)
    historical = parse_receipt(wire)
    assert isinstance(historical, RestoreReceipt)
    assert historical.format == "store-restore-receipt-1"
    assert encoded(historical) == wire
    restored = open_store(initial.path, boundary=initial.boundary)
    catalogue = BackupFiles(restored)
    receipt_path = catalogue.directory(create=False) / f"restore.{historical.intent.restore_id}.receipt.json"
    assert receipt_path.read_bytes() == wire
    digest = hashlib.sha256(wire).hexdigest()
    with completed_restore_scope(
        restored.path, boundary=restored.boundary, restore_id=historical.intent.restore_id,
        expected_receipt_sha256=digest, expected_generation=restored.generation,
    ) as completion:
        assert completion.observation.receipt_format == "store-restore-receipt-1"
        assert completion.revalidate().receipt_sha256 == digest
    before = business_state(restored)
    request = ReadmissionRequest(
        operation_id=activation_case.request.operation_id, restore_id=historical.intent.restore_id,
        restore_receipt_sha256=digest, expected_generation=restored.generation,
    )
    result = run_readmission(str(restored.path), boundary=restored.boundary,
                            project_root=activation_case.project, request=request)
    assert result.inventory_action == "activated_return_observed"
    assert result.inventory is not None and result.inventory.active_revision == 1
    assert result.viewing.result is not None
    assert result.viewing.result.request.operation_id == request.operation_id
    assert result.current_viewing.state == "ready"
    assert result.current_csv is not None and result.current_csv.projection == "current"
    assert result.current_csv.receipt.format == "store-restore-receipt-1"
    assert encoded(result.current_csv.receipt) == wire
    repeated = run_readmission(str(restored.path), boundary=restored.boundary,
                              project_root=activation_case.project, request=request)
    assert repeated.viewing.result == result.viewing.result
    assert repeated.inventory_action == "not_attempted"
    assert receipt_path.read_bytes() == wire and business_state(restored) == before
