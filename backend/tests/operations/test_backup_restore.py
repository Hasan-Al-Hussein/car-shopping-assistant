"""Authored source-only evidence; execution and restore cases remain separate gates."""

import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.database.paths import RuntimeBoundary, guarded_store_path, initialize_runtime_root
from app.database.store import open_store
from app.operations import backup_files, backup_restore
from app.operations.backup_files import BackupError, BackupFiles, manifest_bytes
from app.operations.backup_restore import BackupService, summaries
from tests.operations.backup_fixtures import BackupHarness, make_backup_harness
from tests.support.harness import configured_runtime_boundary
from tests.transactions.projection_fixtures import deny_replacement, make_projection_harness


@pytest.fixture
def backup(monkeypatch: pytest.MonkeyPatch) -> BackupHarness:
    configured = configured_runtime_boundary()
    guarded_store_path(
        configured.logical_root / "test-stores" / "boundary-probe.sqlite3",
        boundary=configured,
        must_exist=False,
    )
    physical_parent = configured.physical_root / "t"
    initialize_runtime_root(RuntimeBoundary(physical_parent, physical_parent))
    case_id = uuid4().hex[:10]
    physical = physical_parent / case_id
    physical.mkdir(exist_ok=False)
    boundary = RuntimeBoundary(configured.logical_root / "t" / case_id, physical)
    return make_backup_harness(monkeypatch, boundary=boundary)


def test_actual_sqlite_backup_is_nonmutating_and_preserves_ids(backup: BackupHarness) -> None:
    projection = backup.retention.projection
    projection.save(email="synthetic-backup@example.invalid")
    before = backup.retention.facts()
    source_rows = projection.store.read(summaries)
    manifest = backup.service.create()
    assert backup.retention.facts() == before
    assert manifest.original_generation == projection.store.generation
    assert manifest.records == source_rows
    copied = open_store(
        backup.service.files.path(manifest.backup_id, "sqlite3"), boundary=projection.store.boundary
    )
    assert copied.read(summaries) == source_rows
    assert backup.service.inspect(manifest.backup_id).state == "available"
    metadata = manifest_bytes(manifest)
    assert b"synthetic-backup@example.invalid" not in metadata


def test_later_canonical_change_does_not_mutate_earlier_backup(backup: BackupHarness) -> None:
    manifest = backup.service.create()
    backup.retention.projection.save()
    assert backup.retention.projection.store.read(summaries) != manifest.records
    assert backup.service.files.manifest(manifest.backup_id) == manifest
    assert backup.service.inspect(manifest.backup_id).manifest == manifest


def test_tampered_database_bytes_are_not_an_accepted_backup(backup: BackupHarness) -> None:
    manifest = backup.service.create()
    path = backup.service.files.path(manifest.backup_id, "sqlite3")
    data = path.read_bytes()
    path.write_bytes(data + b"synthetic mutation")
    before = backup.retention.facts()
    with pytest.raises(BackupError, match="BACKUP_DATABASE_CHANGED"):
        backup.service.inspect(manifest.backup_id)
    assert backup.retention.facts() == before


def test_wrong_physical_store_manifest_is_refused(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = backup.service.create()
    other = make_projection_harness(monkeypatch)
    foreign = BackupFiles(other.store)
    with foreign.lock():
        target = foreign.reserve(manifest.backup_id)
        # Closed fixture bytes only, never a live canonical Store file copy.
        target.write_bytes(backup.service.files.path(manifest.backup_id, "sqlite3").read_bytes())
        foreign.path(manifest.backup_id, "manifest.json").write_bytes(manifest_bytes(manifest))
    with pytest.raises(BackupError, match="BACKUP_DIFFERENT_STORE"):
        BackupService(other.store).inspect(manifest.backup_id)


def test_exact_seven_day_expiry_is_explicit_and_unresolved_pin_is_preserved(
    backup: BackupHarness,
) -> None:
    service = backup.service
    base = backup.retention.projection.leads.sessions
    ordinary, protected = service.create(), service.create()
    # Conservative unresolved pin fixture; it is not a restore-success receipt.
    service.files.path(protected.backup_id, "pin.json").write_text("{}", encoding="utf-8")
    base.clock.value += timedelta(days=7, microseconds=-1)
    assert service.inspect_expiry().eligible == ()
    base.clock.value += timedelta(microseconds=1)
    plan = service.inspect_expiry()
    assert plan.eligible == (ordinary.backup_id,) and plan.protected == (protected.backup_id,)
    before = backup.retention.facts()
    assert service.files.path(ordinary.backup_id, "sqlite3").exists()
    assert service.apply_expiry(plan) == (ordinary.backup_id,)
    assert backup.retention.facts() == before
    assert not service.files.path(ordinary.backup_id, "sqlite3").exists()
    assert service.files.manifest(protected.backup_id) == protected
    assert service.apply_expiry(service.inspect_expiry()) == ()


def test_changed_expiry_plan_cannot_delete_an_unselected_backup(backup: BackupHarness) -> None:
    manifest = backup.service.create()
    plan = backup.service.inspect_expiry()
    with pytest.raises(BackupError, match="BACKUP_EXPIRY_INSPECTION_CHANGED"):
        backup.service.apply_expiry(replace(plan, eligible=(manifest.backup_id,)))
    assert backup.service.files.manifest(manifest.backup_id) == manifest


def test_pending_pin_added_after_inspection_invalidates_cleanup(backup: BackupHarness) -> None:
    manifest = backup.service.create()
    backup.retention.projection.leads.sessions.clock.value += timedelta(days=7)
    plan = backup.service.inspect_expiry()
    backup.service.files.path(manifest.backup_id, "pin.json").write_text("{}", encoding="utf-8")
    with pytest.raises(BackupError, match="BACKUP_EXPIRY_INSPECTION_CHANGED"):
        backup.service.apply_expiry(plan)
    assert backup.service.files.manifest(manifest.backup_id) == manifest


def test_backup_copy_failure_never_publishes_success(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Actual copy progress deadline is forced closed; no fake successful backup.
    before = backup.retention.facts()
    monkeypatch.setattr(backup_restore, "BACKUP_SECONDS", -1)
    with pytest.raises(BackupError, match="BACKUP_TIME_LIMIT"):
        backup.service.create()
    assert backup.retention.facts() == before
    with backup.service.files.lock():
        assert backup.service.files.catalogue() == ()


def test_operator_backup_id_does_not_accept_arbitrary_paths(backup: BackupHarness) -> None:
    with backup.service.files.lock():
        for value in ("../outside", str(uuid4()) + "/other", "C:\\unowned"):
            with pytest.raises(BackupError, match="BACKUP_NAME_INVALID"):
                backup.service.files.path(value, "sqlite3")


def test_partial_pair_expiry_has_a_durable_explicit_recovery_path(backup: BackupHarness) -> None:
    service = backup.service
    manifest = service.create()
    backup.retention.projection.leads.sessions.clock.value += timedelta(days=7)
    plan = service.inspect_expiry()
    with (
        deny_replacement(service.files.path(manifest.backup_id, "manifest.json")),
        pytest.raises(OSError),
    ):
        service.apply_expiry(plan)
    assert not service.files.path(manifest.backup_id, "sqlite3").exists()
    assert service.files.path(manifest.backup_id, "manifest.json").exists()
    assert service.files.path(manifest.backup_id, "expiry.json").exists()
    with pytest.raises(BackupError, match="BACKUP_EXPIRY_RECOVERY_REQUIRED"):
        service.inspect_expiry()
    assert service.resume_expiry() == (manifest.backup_id,)
    assert not service.files.path(manifest.backup_id, "manifest.json").exists()
    assert not service.files.path(manifest.backup_id, "expiry.json").exists()
    assert service.inspect_expiry().eligible == ()
    # New backups remain possible after resolving the partial unlink.
    assert service.create().original_generation == backup.retention.projection.store.generation


def test_unmanifested_reserved_bytes_count_toward_catalogue_quota(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = backup.service
    manifest = service.create()
    with service.files.lock():
        orphan = service.files.reserve(str(uuid4()))
        # Closed accepted backup bytes, not a raw live SQLite copy.
        orphan.write_bytes(service.files.path(manifest.backup_id, "sqlite3").read_bytes())
        _, actual_bytes = service.files.usage()
        quota = actual_bytes - manifest.database_bytes // 2
        assert manifest.database_bytes < quota
        monkeypatch.setattr(backup_files, "MAX_CATALOGUE_BYTES", quota)
        with pytest.raises(BackupError, match="BACKUP_CATALOGUE_SIZE_LIMIT"):
            service.files.catalogue()


def test_complete_expiry_temporary_can_be_explicitly_recovered(
    backup: BackupHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = backup.service
    manifest = service.create()
    backup.retention.projection.leads.sessions.clock.value += timedelta(days=7)
    plan = service.inspect_expiry()
    rename = os.rename

    def fail_rename(source: Path, target: Path) -> None:
        if target.name.endswith("expiry.json"):
            raise OSError("synthetic failure after completed intent fsync")
        rename(source, target)

    monkeypatch.setattr(os, "rename", fail_rename)
    with pytest.raises(OSError, match="completed intent fsync"):
        service.apply_expiry(plan)
    assert service.files.path(manifest.backup_id, "expiry.tmp").exists()
    assert service.files.path(manifest.backup_id, "sqlite3").exists()
    with pytest.raises(BackupError, match="BACKUP_EXPIRY_RECOVERY_REQUIRED"):
        service.inspect_expiry()
    monkeypatch.setattr(os, "rename", rename)
    assert service.resume_expiry() == (manifest.backup_id,)
    assert not service.files.path(manifest.backup_id, "sqlite3").exists()
    assert service.inspect_expiry().eligible == ()
