"""Actual T11 restores/native admission; source-authored and NOT_RUN.

Corruption cases alter only their disposable fixture artifacts. No receipt DTO,
fake Store, projector or maintenance lease substitutes for the positive fixture.
"""

import hashlib
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from copy import copy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.identity import IdentityBootstrapRequest
from app.database.maintenance import (
    MaintenanceError,
    assert_store_lease,
    exclusive_store_lease,
    maintenance_paths,
)
from app.database.models import ExportState, StoreMetadata
from app.database.paths import RuntimeBoundary, guarded_store_path, initialize_runtime_root
from app.database.store import Store, open_store
from app.identity.service import IdentityService, utc_text
from app.leads.projection import CsvProjector
from app.operations import restore_completion
from app.operations.backup_files import BackupFiles, manifest_bytes
from app.operations.backup_restore import BackupService, summaries
from app.operations.restore_completion import (
    CompletedRestoreObservation,
    CompletedRestoreScope,
    RestoreCompletionError,
    completed_restore_scope,
    recheck_completed_restore_metadata,
)
from app.operations.restore_files import MAX_INTENT_BYTES, encoded
from app.operations.restore_operator import RestoreService
from app.operations.restore_transition import RestoreReceiptLike
from app.sessions.state import canonical
from tests.operations.backup_fixtures import BackupHarness, make_backup_harness
from tests.platform.test_identity import ACK
from tests.support.harness import configured_runtime_boundary


@dataclass
class CompletedHarness:
    backup: BackupHarness
    store: Store
    receipt: RestoreReceiptLike
    receipt_path: Path
    receipt_sha256: str

    def scope(
        self,
        *,
        digest: str | None = None,
        generation: str | None = None,
        restore_id: str | None = None,
    ) -> AbstractContextManager[CompletedRestoreScope]:
        return completed_restore_scope(
            self.store.path,
            boundary=self.store.boundary,
            restore_id=self.receipt.intent.restore_id if restore_id is None else restore_id,
            expected_receipt_sha256=self.receipt_sha256 if digest is None else digest,
            expected_generation=self.store.generation if generation is None else generation,
        )

    def retained_hashes(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (path.name, hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(self.receipt_path.parent.iterdir())
            if path.is_file()
        )


@pytest.fixture
def completed(monkeypatch: pytest.MonkeyPatch) -> CompletedHarness:
    configured = configured_runtime_boundary()
    # Check the adopted mapping before creating any short disposable boundary.
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
    backup = make_backup_harness(monkeypatch, boundary=boundary)
    base = backup.retention.projection.leads.sessions
    # Observer uses actual UTC with no clock override. Align this isolated T11
    # fixture as the existing operator CLI fixture does, before its first backup.
    base.clock.value = datetime.now(UTC) - timedelta(seconds=2)

    def align(db: Session) -> None:
        metadata = db.get(StoreMetadata, 1)
        assert metadata is not None
        metadata.created_at = utc_text(base.clock.value)

    base.store.write(align)
    selected = backup.service.create()
    receipt = RestoreService(
        base.store.path, boundary=base.store.boundary, clock=base.clock.now
    ).restore(selected.backup_id, expected_generation=base.store.generation)
    store = open_store(base.store.path, boundary=base.store.boundary)
    catalogue = BackupFiles.for_store_path(store.path, boundary=store.boundary)
    path = catalogue.directory(create=False) / f"restore.{receipt.intent.restore_id}.receipt.json"
    data = path.read_bytes()
    assert data == encoded(receipt)
    return CompletedHarness(backup, store, receipt, path, hashlib.sha256(data).hexdigest())


def stable(observation: CompletedRestoreObservation) -> dict[str, Any]:
    return observation.model_dump(mode="json", exclude={"observed_at"})


def corrupt_receipt(
    completed: CompletedHarness,
    change: Callable[[dict[str, Any]], None],
) -> str:
    """Negative fixture mutation; never an accepted restore/observer substitute."""
    material = completed.receipt.model_dump(mode="json")
    change(material)
    data = canonical(material) + b"\n"
    completed.receipt_path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_actual_completed_restore_has_exact_immutable_association_without_writes(
    completed: CompletedHarness,
) -> None:
    before = completed.store.read(summaries), completed.retained_hashes()
    with completed.scope() as scope:
        entry = scope.observation
        selected, candidate = completed.receipt.intent.selected, completed.receipt.intent.candidate
        assert entry.receipt_format == "store-restore-receipt-2"
        assert entry.restore_id == completed.receipt.intent.restore_id
        assert entry.receipt_path == str(completed.receipt_path)
        assert entry.receipt_sha256 == completed.receipt_sha256
        assert entry.store_binding == selected.source_binding
        assert entry.store_generation == completed.store.generation == candidate.new_generation
        assert entry.schema_version == completed.store.schema_version == selected.schema_version
        assert entry.inventory_mode == completed.store.inventory_mode == selected.inventory_mode
        assert entry.source_created_at == selected.source_created_at
        assert entry.restored_at == candidate.prepared_at
        assert entry.recovery_point == selected.recovery_point
        assert entry.restore_started_at == completed.receipt.intent.started_at
        assert entry.restore_completed_at == completed.receipt.completed_at
        assert entry.selected_backup_id == selected.backup_id
        assert (
            entry.selected_backup_manifest_sha256
            == hashlib.sha256(manifest_bytes(selected)).hexdigest()
        )
        assert entry.selected_backup_database_sha256 == selected.database_sha256
        assert entry.selected_original_generation == selected.original_generation
        assert entry.previous_generation == completed.receipt.intent.previous.original_generation
        assert entry.completion == "historical_completed_associated"
        assert entry.absent_post_backup_authority == "unknown"
        assert not hasattr(scope, "store") and not hasattr(scope, "session")
        fresh = scope.revalidate()
        assert stable(fresh) == stable(entry)
        assert datetime.fromisoformat(fresh.observed_at) >= datetime.fromisoformat(
            entry.observed_at
        )
        with pytest.raises(ValidationError):
            # Exercise Pydantic's runtime frozen guard, not object.__setattr__.
            entry.__setattr__("store_generation", str(uuid4()))
    assert (completed.store.read(summaries), completed.retained_hashes()) == before
    with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
        scope.revalidate()


def test_business_and_projection_writes_do_not_erase_historical_completion(
    completed: CompletedHarness,
) -> None:
    base = completed.backup.retention.projection.leads.sessions
    before = completed.store.read(summaries)
    retained = completed.retained_hashes()
    with completed.scope() as scope:
        entry = scope.observation
        # Real new-owner bootstrap on the restored Store; no old-owner reauthentication claim.
        created = IdentityService(base.settings).bootstrap(
            IdentityBootstrapRequest.model_validate(ACK), None
        )
        assert created.generation == completed.store.generation
        assert completed.store.read(summaries) != before
        old_projection_time = completed.store.read(
            lambda db: db.scalar(select(ExportState.updated_at).where(ExportState.id == 1))
        )
        assert CsvProjector(completed.store).repair_once().state == "current"
        assert (
            completed.store.read(
                lambda db: db.scalar(select(ExportState.updated_at).where(ExportState.id == 1))
            )
            != old_projection_time
        )

        def pending(db: Session) -> None:
            row = db.get(ExportState, 1)
            assert row is not None
            row.state = "pending"

        # A current CSV bit is not a precondition and is not claimed by the DTO.
        completed.store.write(pending)
        assert stable(scope.revalidate()) == stable(entry)
    assert completed.retained_hashes() == retained
    files = BackupFiles(completed.store)
    assert files.pinned(completed.receipt.intent.previous.backup_id)
    assert not files.pinned(completed.receipt.intent.selected.backup_id)


def test_selected_source_expiry_is_not_a_completion_dependency(completed: CompletedHarness) -> None:
    base = completed.backup.retention.projection.leads.sessions
    base.clock.value += timedelta(days=8)
    backups = BackupService(completed.store, clock=base.clock.now)
    expiry = backups.inspect_expiry()
    selected = completed.receipt.intent.selected.backup_id
    previous = completed.receipt.intent.previous.backup_id
    assert selected in expiry.eligible and previous in expiry.protected
    assert backups.apply_expiry(expiry) == (selected,)
    assert not backups.files.path(selected, "sqlite3").exists()
    assert not backups.files.path(selected, "manifest.json").exists()
    retained = completed.retained_hashes()
    with completed.scope() as scope:
        assert scope.revalidate().selected_backup_id == selected
    assert completed.retained_hashes() == retained
    assert backups.files.pinned(previous)


@pytest.mark.parametrize("changed", ["restore_id", "digest", "generation"])
def test_malformed_request_is_closed(completed: CompletedHarness, changed: str) -> None:
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_INPUT_INVALID$"),
        completed.scope(
            restore_id="../bad" if changed == "restore_id" else None,
            digest="G" * 64 if changed == "digest" else None,
            generation="not-a-uuid" if changed == "generation" else None,
        ),
    ):
        pytest.fail("invalid input admitted")


def test_wrong_expected_digest_and_generation_are_distinct(completed: CompletedHarness) -> None:
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_RECEIPT_CHANGED$"),
        completed.scope(digest="0" * 64),
    ):
        pytest.fail("wrong digest admitted")
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_ASSOCIATION_CHANGED$"),
        completed.scope(generation=completed.receipt.intent.previous.original_generation),
    ):
        pytest.fail("old generation admitted")


def test_wrong_original_uuid_cannot_select_another_final_receipt(
    completed: CompletedHarness,
) -> None:
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_RECEIPT_MISSING$"),
        completed.scope(restore_id=str(uuid4())),
    ):
        pytest.fail("unknown original UUID admitted")


@pytest.mark.parametrize("suffix", [".restore-intent.json", ".restore-intent.json.update.tmp"])
def test_pending_marker_or_update_tmp_blocks_even_nested_exclusive_scope(
    completed: CompletedHarness,
    suffix: str,
) -> None:
    # Real exclusive token only. Contents may be incomplete; presence is sufficient.
    with exclusive_store_lease(completed.store.path, boundary=completed.store.boundary):
        pending = Path(str(completed.store.path) + suffix)
        pending.write_bytes(b"incomplete")
        with (
            pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_PENDING$"),
            completed.scope(),
        ):
            pytest.fail("pending completion admitted")
        assert pending.read_bytes() == b"incomplete"


def test_receipt_temporary_cannot_replace_missing_final(completed: CompletedHarness) -> None:
    temporary = completed.receipt_path.with_name(
        f"restore.{completed.receipt.intent.restore_id}.receipt.tmp"
    )
    completed.receipt_path.replace(temporary)
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_RECEIPT_MISSING$"),
        completed.scope(),
    ):
        pytest.fail("temporary admitted")
    assert temporary.read_bytes() == encoded(completed.receipt)


@pytest.mark.parametrize("kind", ["noncanonical", "format", "uuid", "extra", "oversized"])
def test_invalid_final_bytes_fail_even_with_their_exact_digest(
    completed: CompletedHarness,
    kind: str,
) -> None:
    material = completed.receipt.model_dump(mode="json")
    if kind == "format":
        material["format"] = "store-restore-receipt-3"
    elif kind == "uuid":
        material["intent"]["restore_id"] = str(uuid4())
    elif kind == "extra":
        material["unrecognized"] = True
    if kind == "oversized":
        data = b" " * (MAX_INTENT_BYTES + 1)
    elif kind == "noncanonical":
        data = json.dumps(material, indent=2).encode("utf-8")
    else:
        data = canonical(material) + b"\n"
    completed.receipt_path.write_bytes(data)
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_RECEIPT_INVALID$"),
        completed.scope(digest=hashlib.sha256(data).hexdigest()),
    ):
        pytest.fail("invalid receipt admitted")


def test_future_completion_is_closed(completed: CompletedHarness) -> None:
    def change(material: dict[str, Any]) -> None:
        material["completed_at"] = utc_text(datetime.now(UTC) + timedelta(days=1))

    digest = corrupt_receipt(completed, change)
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_CLOCK_INVALID$"),
        completed.scope(digest=digest),
    ):
        pytest.fail("future completion admitted")


def test_receipt_profile_must_equal_actual_admitted_store(completed: CompletedHarness) -> None:
    def change(material: dict[str, Any]) -> None:
        actual = material["intent"]["selected"]["inventory_mode"]
        material["intent"]["selected"]["inventory_mode"] = (
            "bounded_lexical" if actual == "fts5" else "fts5"
        )

    digest = corrupt_receipt(completed, change)
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_ASSOCIATION_CHANGED$"),
        completed.scope(digest=digest),
    ):
        pytest.fail("wrong profile admitted")


def test_hardlinked_receipt_is_not_a_private_final_file(completed: CompletedHarness) -> None:
    alias = completed.receipt_path.with_name("receipt-hardlink-evidence.bin")
    alias.hardlink_to(completed.receipt_path)
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_PATH_UNAVAILABLE$"),
        completed.scope(),
    ):
        pytest.fail("multiply-linked receipt admitted")
    assert alias.read_bytes() == encoded(completed.receipt)


def test_same_bytes_replacement_is_detected_and_exit_invalidates_scope(
    completed: CompletedHarness,
) -> None:
    replacement = completed.receipt_path.with_name("replacement-evidence.tmp")
    replacement.write_bytes(completed.receipt_path.read_bytes())
    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_RECEIPT_CHANGED$"),
        completed.scope() as scope,
    ):
        replacement.replace(completed.receipt_path)
        scope.revalidate()
    with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
        _ = scope.observation


def test_normal_exit_revalidates_actual_metadata(completed: CompletedHarness) -> None:
    def change(db: Session) -> None:
        row = db.get(StoreMetadata, 1)
        assert row is not None
        row.restored_at = utc_text(datetime.now(UTC))

    with (
        pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_ASSOCIATION_CHANGED$"),
        completed.scope() as scope,
    ):
        completed.store.write(change)
    with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
        scope.revalidate()


def test_copied_fabricated_foreign_thread_and_closed_scopes_are_not_authority(
    completed: CompletedHarness,
) -> None:
    with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
        CompletedRestoreScope(object())
    fabricated = object.__new__(CompletedRestoreScope)
    with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
        fabricated.revalidate()
    with completed.scope() as scope:
        copied = copy(scope)
        assert copied is not scope
        with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
            copied.revalidate()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(scope.revalidate)
            with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
                future.result(timeout=5)
        assert scope.revalidate().store_generation == completed.store.generation
    with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
        _ = scope.observation


def test_actual_concurrent_restore_is_excluded_until_scope_closes(
    completed: CompletedHarness,
) -> None:
    before = completed.retained_hashes(), completed.store.read(summaries)

    def restore_again() -> RestoreReceiptLike:
        return RestoreService(completed.store.path, boundary=completed.store.boundary).restore(
            completed.receipt.intent.selected.backup_id,
            expected_generation=completed.store.generation,
        )

    with completed.scope() as scope, ThreadPoolExecutor(max_workers=1) as executor:
        attempt = executor.submit(restore_again)
        with pytest.raises(MaintenanceError):
            attempt.result(timeout=5)
        assert not maintenance_paths(
            completed.store.path, boundary=completed.store.boundary
        ).intent_path.exists()
        assert scope.revalidate().restore_id == completed.receipt.intent.restore_id
    assert (completed.retained_hashes(), completed.store.read(summaries)) == before
    with exclusive_store_lease(completed.store.path, boundary=completed.store.boundary) as lease:
        lease.assert_held(completed.store.path, boundary=completed.store.boundary)


def test_consumer_oserror_is_not_translated_and_guard_is_released(
    completed: CompletedHarness,
) -> None:
    error = OSError("synthetic consumer failure")
    with pytest.raises(OSError) as caught, completed.scope() as scope:
        raise error
    assert caught.value is error
    with pytest.raises(RestoreCompletionError, match="^RESTORE_COMPLETION_SCOPE_NOT_LIVE$"):
        scope.revalidate()
    with exclusive_store_lease(completed.store.path, boundary=completed.store.boundary) as lease:
        lease.assert_held(completed.store.path, boundary=completed.store.boundary)


def test_held_scope_is_asserted_before_every_fresh_open(
    completed: CompletedHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_assert = assert_store_lease
    actual_open = open_store
    events: list[str] = []

    def checked_assert(path: Path, *, boundary: RuntimeBoundary) -> None:
        actual_assert(path, boundary=boundary)
        events.append("held")

    def checked_open(path: Path, *, boundary: RuntimeBoundary) -> Store:
        assert events and events[-1] == "held"
        events.append("open")
        return actual_open(path, boundary=boundary)

    monkeypatch.setattr(restore_completion, "assert_store_lease", checked_assert)
    monkeypatch.setattr(restore_completion, "open_store", checked_open)
    with completed.scope() as scope:
        scope.revalidate()
    assert events.count("open") == 3  # Entry, explicit revalidation, normal exit.


def test_readonly_observer_cannot_run_inside_store_write(completed: CompletedHarness) -> None:
    before = completed.retained_hashes(), completed.store.read(summaries)

    def work(db: Session) -> None:
        with (
            pytest.raises(
                RestoreCompletionError, match="^RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED$"
            ),
            completed.scope(),
        ):
            pytest.fail("filesystem observer entered WRITE")

    completed.store.write(work)
    assert (completed.retained_hashes(), completed.store.read(summaries)) == before


def test_writer_helper_requires_real_write_and_performs_no_external_work(
    completed: CompletedHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with completed.scope() as scope:
        observation = scope.revalidate()
        with pytest.raises(
            RestoreCompletionError, match="^RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED$"
        ):
            completed.store.read(lambda db: recheck_completed_restore_metadata(db, observation))
        with Session() as unbound:
            with pytest.raises(
                RestoreCompletionError, match="^RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED$"
            ):
                recheck_completed_restore_metadata(unbound, observation)
            assert not unbound.in_transaction()

        def forbidden(*args: object, **kwargs: object) -> None:
            pytest.fail("writer helper performed external observer work")

        with monkeypatch.context() as isolated:
            for name in ("open_store", "shared_store_lease", "guarded_store_path", "_read_receipt"):
                isolated.setattr(restore_completion, name, forbidden)
            completed.store.write(lambda db: recheck_completed_restore_metadata(db, observation))


@pytest.mark.parametrize("option", [False, 1], ids=["read-flag", "integer-is-not-true"])
def test_writer_helper_requires_literal_true_execution_option(
    completed: CompletedHarness,
    option: bool | int,
) -> None:
    with completed.scope() as scope:
        observation = scope.observation

        def work(db: Session) -> None:
            connection = db.connection()
            connection.execution_options(store_write=option)
            try:
                with pytest.raises(
                    RestoreCompletionError, match="^RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED$"
                ):
                    recheck_completed_restore_metadata(db, observation)
            finally:
                connection.execution_options(store_write=True)

        completed.store.write(work)


@pytest.mark.parametrize(
    "field", ["store_generation", "schema_version", "created_at", "restored_at", "recovery_point"]
)
def test_writer_helper_detects_metadata_change_in_same_unit_and_rolls_back(
    completed: CompletedHarness,
    field: str,
) -> None:
    with completed.scope() as scope:
        observation = scope.observation

        def work(db: Session) -> None:
            metadata = db.get(StoreMetadata, 1)
            assert metadata is not None
            value = utc_text(datetime.now(UTC))
            if field == "store_generation":
                value = str(uuid4())
            elif field == "schema_version":
                value = "0001"
            setattr(metadata, field, value)
            db.flush()
            recheck_completed_restore_metadata(db, observation)

        with pytest.raises(
            RestoreCompletionError, match="^RESTORE_COMPLETION_ASSOCIATION_CHANGED$"
        ):
            completed.store.write(work)
        assert stable(scope.revalidate()) == stable(observation)


def test_writer_helper_does_not_restart_an_ended_store_transaction(
    completed: CompletedHarness,
) -> None:
    class EndedTestUnit(Exception):
        pass

    with completed.scope() as scope:
        observation = scope.observation

        def work(db: Session) -> None:
            connection = db.connection()
            connection.rollback()  # Deliberate negative fixture, not a supported callback.
            assert not connection.in_transaction()
            with pytest.raises(
                RestoreCompletionError, match="^RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED$"
            ):
                recheck_completed_restore_metadata(db, observation)
            assert not connection.in_transaction()
            raise EndedTestUnit

        with pytest.raises(EndedTestUnit):
            completed.store.write(work)
        assert stable(scope.revalidate()) == stable(observation)


def test_writer_helper_rejects_absent_metadata_and_rolls_back(completed: CompletedHarness) -> None:
    with completed.scope() as scope:
        observation = scope.observation

        def work(db: Session) -> None:
            metadata = db.get(StoreMetadata, 1)
            assert metadata is not None
            db.delete(metadata)
            db.flush()
            recheck_completed_restore_metadata(db, observation)

        with pytest.raises(
            RestoreCompletionError, match="^RESTORE_COMPLETION_ASSOCIATION_CHANGED$"
        ):
            completed.store.write(work)
        assert stable(scope.revalidate()) == stable(observation)
