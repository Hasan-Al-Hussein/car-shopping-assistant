"""Real restore effects with narrowly labelled failure seams; NOT_RUN."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.database.maintenance import exclusive_store_lease, maintenance_paths
from app.database.models import ExportState, Lead
from app.database.store import open_store
from app.leads.projection_files import CSV_NAME, ProjectionFiles, PublicationManifest
from app.leads.projection_repository import ProjectionError
from app.operations import restore_operator, restore_retention
from app.operations.backup_files import BackupError
from app.operations.restore_fingerprint import semantic_digest
from app.operations.restore_transition import parse_receipt
from tests.operations.backup_fixtures import BackupHarness, make_backup_harness
from tests.operations.test_restore_retention import (
    service_for, stop_pending, young_backup_with_old_lead,
)


@pytest.fixture
def backup(monkeypatch: pytest.MonkeyPatch) -> BackupHarness:
    return make_backup_harness(monkeypatch)


@pytest.mark.parametrize("changed_pin", [False, True])
def test_marker_absent_retry_finishes_only_exact_selected_pin_release(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch, changed_pin: bool,
) -> None:
    flow = backup.retention.projection
    flow.save()
    selected = backup.service.create()
    selected_pin = backup.service.files.path(selected.backup_id, "pin.json")
    marker = maintenance_paths(flow.store.path, boundary=flow.store.boundary).intent_path
    actual_unlink = Path.unlink

    def refuse_selected(self: Path, missing_ok: bool = False) -> None:
        if self == selected_pin:
            assert not marker.exists()  # Actual finish already removed the marker.
            raise OSError("synthetic selected-pin unlink failure")
        actual_unlink(self, missing_ok=missing_ok)

    with monkeypatch.context() as fault:
        fault.setattr(Path, "unlink", refuse_selected)
        with pytest.raises(OSError, match="selected-pin unlink"):
            service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    paths = tuple(backup.service.files.directory().glob("restore.*.receipt.json"))
    assert len(paths) == 1
    receipt_bytes = paths[0].read_bytes()
    completed = parse_receipt(receipt_bytes)
    prior_pin = backup.service.files.path(completed.intent.previous.backup_id, "pin.json")
    prior_bytes = prior_pin.read_bytes()
    before = flow.store.path.read_bytes(), flow.files.path(CSV_NAME).read_bytes()
    assert selected_pin.exists() and not marker.exists()
    if changed_pin:
        changed = selected_pin.read_bytes() + b"unrecognized trailing bytes"
        selected_pin.write_bytes(changed)  # Explicit negative fixture corruption.
        with pytest.raises(BackupError, match="RESTORE_PIN_CHANGED"):
            service_for(backup).resume_observed(restore_id=completed.intent.restore_id)
        assert selected_pin.read_bytes() == changed
    else:
        observed = service_for(backup).resume_observed(restore_id=completed.intent.restore_id)
        assert observed.receipt == completed and observed.projection == "current"
        assert not selected_pin.exists()
    assert paths[0].read_bytes() == receipt_bytes and prior_pin.read_bytes() == prior_bytes
    assert (flow.store.path.read_bytes(), flow.files.path(CSV_NAME).read_bytes()) == before


@pytest.mark.parametrize("bound", ["revision", "owners"])
def test_after_ack_expiry_withdraws_owned_csv_before_bounded_transform_refusal(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch, bound: str,
) -> None:
    selected = young_backup_with_old_lead(backup)
    flow = backup.retention.projection
    pending = stop_pending(backup, selected, monkeypatch, phase="after_ack")
    assert flow.files.path(CSV_NAME).exists()
    flow.leads.sessions.clock.value += timedelta(days=2)
    if bound == "revision":
        monkeypatch.setattr(restore_operator, "MAX_SWEEPS", 1)
        code = "RESTORE_RETENTION_REVISION_LIMIT"
    else:
        # At least one actual retained owner; reduce only the numeric loop bound.
        monkeypatch.setattr(restore_retention, "MAX_RETENTION_OWNERS", 0)
        code = "RESTORE_RETENTION_OWNER_LIMIT"
    with pytest.raises(BackupError, match=code):
        service_for(backup).resume(restore_id=pending.restore_id)
    assert service_for(backup).inspect() == pending
    assert not flow.files.path(CSV_NAME).exists()
    with flow.files.lock(), exclusive_store_lease(flow.store.path, boundary=flow.store.boundary):
        current = open_store(flow.store.path, boundary=flow.store.boundary)
        assert current.read(semantic_digest) == pending.candidate.semantic_sha256
        assert current.read(lambda db: db.scalar(select(ExportState.state))) == "failed"
        assert current.read(lambda db: db.scalar(select(func.count()).select_from(Lead))) == 1
    assert backup.service.files.pinned(selected.backup_id)
    assert backup.service.files.pinned(pending.previous.backup_id)


@pytest.mark.parametrize("failure", ["unlink", "unknown_bytes"])
def test_pending_expiry_records_failed_status_even_when_csv_cannot_be_withdrawn(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    selected = young_backup_with_old_lead(backup)
    flow = backup.retention.projection
    pending = stop_pending(backup, selected, monkeypatch, phase="after_ack")
    csv = flow.files.path(CSV_NAME)
    if failure == "unknown_bytes":
        csv.write_bytes(csv.read_bytes() + b"unknown contact artifact")
    retained_bytes = csv.read_bytes()
    flow.leads.sessions.clock.value += timedelta(days=2)
    actual_unlink = Path.unlink

    def refuse_csv(self: Path, missing_ok: bool = False) -> None:
        if self == csv:
            raise OSError("synthetic CSV unlink failure")
        actual_unlink(self, missing_ok=missing_ok)

    with monkeypatch.context() as fault:
        if failure == "unlink":
            fault.setattr(Path, "unlink", refuse_csv)
        # Actual file ownership validation supplies the error for unknown bytes.
        with pytest.raises((OSError, ProjectionError)):
            service_for(backup).resume(restore_id=pending.restore_id)
    assert csv.read_bytes() == retained_bytes
    assert service_for(backup).inspect() == pending
    with flow.files.lock(), exclusive_store_lease(flow.store.path, boundary=flow.store.boundary):
        current = open_store(flow.store.path, boundary=flow.store.boundary)
        assert current.read(semantic_digest) == pending.candidate.semantic_sha256
        assert current.read(lambda db: db.scalar(select(ExportState.state))) == "failed"
    assert backup.service.files.pinned(selected.backup_id)
    assert backup.service.files.pinned(pending.previous.backup_id)


def test_expiry_during_actual_publication_withdraws_even_when_projector_returns_failed(
    backup: BackupHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = young_backup_with_old_lead(backup)
    flow = backup.retention.projection
    actual_publish = ProjectionFiles.publish

    def publish_then_expire(files: ProjectionFiles, manifest: PublicationManifest) -> None:
        actual_publish(files, manifest)
        flow.leads.sessions.clock.value += timedelta(days=2)

    monkeypatch.setattr(ProjectionFiles, "publish", publish_then_expire)
    with pytest.raises(ProjectionError, match="CSV_RETENTION_RECONCILIATION_REQUIRED"):
        service_for(backup).restore(selected.backup_id, expected_generation=flow.store.generation)
    pending = service_for(backup).inspect()
    assert pending is not None
    assert not flow.files.path(CSV_NAME).exists()
    with flow.files.lock(), exclusive_store_lease(flow.store.path, boundary=flow.store.boundary):
        current = open_store(flow.store.path, boundary=flow.store.boundary)
        assert current.read(semantic_digest) == pending.candidate.semantic_sha256
        assert current.read(lambda db: db.scalar(select(ExportState.state))) == "failed"
    assert backup.service.files.pinned(selected.backup_id)
    assert backup.service.files.pinned(pending.previous.backup_id)
