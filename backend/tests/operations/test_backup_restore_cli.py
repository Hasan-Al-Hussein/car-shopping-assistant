"""Actual child-process operator commands; source authored, execution separately granted."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.database.maintenance import maintenance_paths, shared_store_lease
from app.database.models import StoreMetadata
from app.database.paths import _io_path
from app.database.store import open_store
from app.identity.service import utc_text
from app.leads.projection_files import CSV_NAME
from tests.operations.backup_fixtures import BackupHarness, make_backup_harness

ROOT = Path(__file__).resolve().parents[3]


def run_cli(
    script: str, *arguments: str, without_boundary: bool = False
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend")
    if without_boundary:
        environment.pop("CSA_RUNTIME_ROOT", None)
        environment.pop("CSA_RUNTIME_PHYSICAL_ROOT", None)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "operations" / script), *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
        check=False,
    )


@pytest.fixture
def backup(monkeypatch: pytest.MonkeyPatch) -> BackupHarness:
    flow = make_backup_harness(monkeypatch)
    base = flow.retention.projection.leads.sessions
    # Child processes use real UTC. Align only this isolated CLI fixture to it;
    # never introduce a production clock override or a seven-day calendar bomb.
    base.clock.value = datetime.now(UTC)

    def align(db: Session) -> None:
        metadata = db.get(StoreMetadata, 1)
        assert metadata is not None
        metadata.created_at = utc_text(base.clock.value)

    base.store.write(align)
    return flow


def test_backup_cli_create_inspect_and_default_expiry_do_not_restore_or_delete(
    backup: BackupHarness,
) -> None:
    store = backup.retention.projection.store
    flags = ("--store", str(store.path), "--expected-generation", store.generation)
    before = backup.retention.facts()
    created = run_cli("backup_store.py", *flags, "create")
    assert created.returncode == 0, created.stderr
    manifest = json.loads(created.stdout)["manifest"]
    inspected = run_cli("backup_store.py", *flags, "inspect", "--backup-id", manifest["backup_id"])
    assert inspected.returncode == 0, inspected.stderr
    assert json.loads(inspected.stdout)["manifest"] == manifest
    expiry = run_cli("backup_store.py", *flags, "expiry")
    assert expiry.returncode == 0, expiry.stderr
    assert json.loads(expiry.stdout)["state"] == "expiry_inspection"
    assert _io_path(backup.service.files.path(manifest["backup_id"], "sqlite3")).exists()
    assert backup.retention.facts() == before


def test_restore_cli_apply_and_completed_receipt_resume_are_explicit(backup: BackupHarness) -> None:
    store = backup.retention.projection.store
    selected = backup.service.create()
    flags = ("--store", str(store.path))
    observed = run_cli("restore_store.py", *flags, "inspect")
    assert observed.returncode == 0, observed.stderr
    assert json.loads(observed.stdout) == {"state": "no_pending_restore"}
    result = run_cli(
        "restore_store.py",
        *flags,
        "apply",
        "--backup-id",
        selected.backup_id,
        "--expected-generation",
        store.generation,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["format"] == "restore-observation-1"
    assert observed["completion"] == "completed_current"
    assert observed["projection"] == "current" and observed["code"] is None
    receipt = observed["receipt"]
    assert receipt["state"] == "restored"
    assert (
        open_store(store.path, boundary=store.boundary).generation
        == receipt["intent"]["candidate"]["new_generation"]
    )
    repeated = run_cli(
        "restore_store.py", *flags, "resume", "--restore-id", receipt["intent"]["restore_id"]
    )
    assert repeated.returncode == 0, repeated.stderr
    repeated_observation = json.loads(repeated.stdout)
    assert repeated_observation["receipt"] == receipt
    assert repeated_observation["completion"] == "completed_current"
    assert repeated_observation["projection"] == "current"
    assert repeated_observation["observed_at"] >= observed["observed_at"]
    assert not _io_path(maintenance_paths(store.path, boundary=store.boundary).intent_path).exists()


def test_completed_cli_missing_csv_reports_historical_receipt_without_repair(
    backup: BackupHarness,
) -> None:
    flow = backup.retention.projection
    selected = backup.service.create()
    flags = ("--store", str(flow.store.path))
    applied = run_cli(
        "restore_store.py",
        *flags,
        "apply",
        "--backup-id",
        selected.backup_id,
        "--expected-generation",
        flow.store.generation,
    )
    assert applied.returncode == 0, applied.stderr
    receipt = json.loads(applied.stdout)["receipt"]
    csv_path = flow.files.path(CSV_NAME)
    assert csv_path.exists()
    csv_path.unlink()  # Deliberate missing-publication fault in this isolated runtime.
    before = flow.store.path.read_bytes()
    observed = run_cli(
        "restore_store.py", *flags, "resume", "--restore-id", receipt["intent"]["restore_id"]
    )
    assert observed.returncode == 1 and observed.stderr == ""
    payload = json.loads(observed.stdout)
    assert payload["receipt"] == receipt
    assert payload["completion"] == "historically_completed_observation_unavailable"
    assert payload["projection"] == "unavailable"
    assert payload["code"] == "RESTORE_CURRENT_CSV_UNVERIFIED"
    assert not csv_path.exists() and flow.store.path.read_bytes() == before


def test_restore_child_process_cannot_bypass_parent_shared_lease(backup: BackupHarness) -> None:
    store = backup.retention.projection.store
    selected = backup.service.create()
    before = backup.retention.facts(), backup.service.files.catalogue()
    with shared_store_lease(store.path, boundary=store.boundary):
        result = run_cli(
            "restore_store.py",
            "--store",
            str(store.path),
            "apply",
            "--backup-id",
            selected.backup_id,
            "--expected-generation",
            store.generation,
        )
    assert result.returncode == 1
    assert json.loads(result.stdout)["code"] == "RESTORE_NOT_VERIFIED"
    assert str(store.path) not in result.stdout and result.stderr == ""
    assert (backup.retention.facts(), backup.service.files.catalogue()) == before
    assert not _io_path(maintenance_paths(store.path, boundary=store.boundary).intent_path).exists()


@pytest.mark.parametrize("script", ["backup_store.py", "restore_store.py"])
def test_operator_cli_missing_store_does_not_initialize_any_store(
    backup: BackupHarness, script: str
) -> None:
    store = backup.retention.projection.store
    missing = store.path.parent / (str(uuid4()) + ".sqlite3")
    arguments = (
        ("--expected-generation", store.generation, "create")
        if script == "backup_store.py"
        else ("apply", "--backup-id", str(uuid4()), "--expected-generation", store.generation)
    )
    result = run_cli(script, "--store", str(missing), *arguments)
    assert result.returncode == 1
    assert json.loads(result.stdout)["state"] == "unresolved"
    assert not _io_path(missing).exists()
    assert not _io_path(Path(str(missing) + ".maintenance.lock")).exists()
    assert not _io_path(Path(str(missing) + ".restore-intent.json")).exists()
    assert str(missing) not in result.stdout


def test_operator_cli_requires_explicit_runtime_boundary(backup: BackupHarness) -> None:
    store = backup.retention.projection.store
    result = run_cli(
        "backup_store.py",
        "--store",
        str(store.path),
        "--expected-generation",
        store.generation,
        "create",
        without_boundary=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"state": "unresolved", "code": "BACKUP_NOT_VERIFIED"}
    assert result.stderr == ""


def test_restore_cli_generation_error_is_sanitized(backup: BackupHarness) -> None:
    store = backup.retention.projection.store
    selected = backup.service.create()
    before = backup.retention.facts()
    result = run_cli(
        "restore_store.py",
        "--store",
        str(store.path),
        "apply",
        "--backup-id",
        selected.backup_id,
        "--expected-generation",
        str(uuid4()),
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["code"] == "RESTORE_NOT_VERIFIED"
    assert result.stderr == "" and str(store.path) not in result.stdout
    assert backup.retention.facts() == before
