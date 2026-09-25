"""Prepare a new-generation isolated candidate; never replace the canonical Store.

The later operator transition must hold actual publication/maintenance authority.
This module supplies no offline flag, simulated lease or service reactivation.
"""

import os
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.database.maintenance import MaintenanceLease, exclusive_store_lease, shared_store_lease
from app.database.models import (
    ActiveInventory,
    ActiveRules,
    ExportIntent,
    ExportState,
    OwnerCredential,
    StoreMetadata,
)
from app.database.paths import _io_path, _sqlite_uri
from app.database.store import Store, StoreError, assert_outside_write_transaction, open_store
from app.identity.service import utc_text
from app.leads import projection_repository as projection
from app.operations.backup_files import (
    MAX_BACKUPS,
    MAX_CATALOGUE_BYTES,
    MAX_CATALOGUE_ENTRIES,
    MAX_MANIFEST_BYTES,
    BackupError,
    BackupFiles,
    BackupManifest,
    RecordSummary,
)
from app.operations.backup_restore import BACKUP_SECONDS, summaries
from app.operations.restore_files import RestoreCandidate
from app.operations.restore_fingerprint import semantic_digest
from app.operations.restore_retention import (
    RetentionTransform,
    reconcile_candidate,
    require_exportable,
    summary_digest,
)


@dataclass(frozen=True)
class PreparedRestoreCandidate:
    candidate_id: str
    backup_id: str
    source_binding: str
    original_generation: str
    new_generation: str
    recovery_point: str
    prepared_at: str
    database_sha256: str
    database_bytes: int
    semantic_sha256: str
    records: tuple[RecordSummary, ...]
    revoked_credentials: int
    canonical_projection_version: int
    retention: RetentionTransform
    inventory_admission: str = "required"
    viewing_adoption: str = "required"


def _instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise BackupError("RESTORE_CLOCK_INVALID")
    return utc_text(value)


def _verified_source(files: BackupFiles, manifest: BackupManifest, now: str) -> Store:
    if not manifest.recovery_point <= now < manifest.expires_at:
        raise BackupError("RESTORE_BACKUP_EXPIRED_OR_FUTURE")
    if files.digest(manifest.backup_id) != (manifest.database_sha256, manifest.database_bytes):
        raise BackupError("RESTORE_BACKUP_IDENTITY_CHANGED")
    source = open_store(files.path(manifest.backup_id, "sqlite3"), boundary=files.boundary)
    if (source.generation, source.schema_version, source.inventory_mode) != (
        manifest.original_generation,
        manifest.schema_version,
        manifest.inventory_mode,
    ) or source.read(summaries) != manifest.records:
        raise BackupError("RESTORE_BACKUP_IDENTITY_CHANGED")
    return source


def _rotate(
    candidate: Store, new_generation: str, recovery_point: str, now: str
) -> tuple[int, int]:
    def write(db: Session) -> tuple[int, int]:
        metadata = db.get(StoreMetadata, 1)
        if metadata is None or metadata.store_generation != candidate.generation:
            raise BackupError("RESTORE_CANDIDATE_GENERATION_CHANGED")
        state = projection.state(db, candidate.generation)
        if state is not None:
            # The actual T8 reader rejects malformed, future or expired export rows
            # before this candidate can become live. No source row is silently erased.
            projection.capture(db, candidate.generation, now)
        latest_credential = db.scalar(select(func.max(OwnerCredential.issued_at)))
        if latest_credential is not None and latest_credential > now:
            raise BackupError("RESTORE_CLOCK_BEFORE_CREDENTIAL")
        revoked = (
            db.scalar(
                select(func.count())
                .select_from(OwnerCredential)
                .where(OwnerCredential.revoked_at.is_(None))
            )
            or 0
        )
        db.execute(
            update(OwnerCredential)
            .where(OwnerCredential.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        # Historical snapshots/rules/reviews stay intact. Fresh admission must use
        # a new generation and real new viewing-policy authority.
        db.execute(delete(ActiveRules))
        db.execute(delete(ActiveInventory))
        if state is None:
            state = ExportState(
                id=1,
                store_generation=new_generation,
                canonical_version=0,
                exported_version=None,
                state="pending",
                updated_at=now,
            )
            db.add(state)
        else:
            state.store_generation = new_generation
            state.exported_version = None
            state.state, state.updated_at = "pending", now
        # Export intents are mutable projection work, not original outcome facts.
        # Keep their IDs/versions/lead bindings; start no invented business action.
        db.execute(
            update(ExportIntent).values(
                store_generation=new_generation, state="pending", last_error_code=None
            )
        )
        metadata.store_generation = new_generation
        metadata.restored_at, metadata.recovery_point = now, recovery_point
        return revoked, state.canonical_version

    return candidate.write(write)


def _copy_into(files: BackupFiles, source: Store, destination: Path) -> None:
    deadline = time.monotonic() + BACKUP_SECONDS

    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() > deadline:
            raise BackupError("RESTORE_CANDIDATE_TIME_LIMIT")
        if status not in {
            sqlite3.SQLITE_OK,
            sqlite3.SQLITE_DONE,
            sqlite3.SQLITE_BUSY,
            sqlite3.SQLITE_LOCKED,
        }:
            raise BackupError("RESTORE_CANDIDATE_COPY_FAILED")

    def copy(db: Session) -> None:
        raw = db.connection().connection.driver_connection
        if not isinstance(raw, sqlite3.Connection):
            raise StoreError("STORE_DRIVER_INCOMPATIBLE")
        with (
            shared_store_lease(destination, boundary=files.boundary),
            closing(
                sqlite3.connect(
                    _sqlite_uri(destination, "rw"), uri=True, isolation_level=None, timeout=1
                )
            ) as target,
        ):
            target.execute("PRAGMA journal_mode=DELETE")
            target.execute("PRAGMA synchronous=FULL")
            raw.backup(target, pages=128, progress=progress, sleep=0.01)

    source.read(copy)


def _flush(path: Path) -> None:
    with _io_path(path).open("r+b") as output:
        output.flush()
        os.fsync(output.fileno())


def prepare_candidate(
    files: BackupFiles,
    backup_id: str,
    *,
    now: datetime,
    clock: Callable[[], datetime] | None = None,
) -> PreparedRestoreCandidate:
    """Explicit isolated preparation. Caller cannot choose the mutable destination."""
    assert_outside_write_transaction()
    stamp = _instant(now)
    with files.lock():
        catalogue = files.catalogue()
        if len(catalogue) >= MAX_BACKUPS:
            raise BackupError("BACKUP_CATALOGUE_LIMIT")
        manifest = files.manifest(backup_id)
        source = _verified_source(files, manifest, stamp)
        count, occupied = files.usage()
        if (
            count + 3 > MAX_CATALOGUE_ENTRIES
            or occupied + manifest.database_bytes + 2 * MAX_MANIFEST_BYTES > MAX_CATALOGUE_BYTES
        ):
            raise BackupError("RESTORE_CANDIDATE_QUOTA")
        candidate_id, generation = str(uuid4()), str(uuid4())
        current = open_store(files.source, boundary=files.boundary)
        if generation in {source.generation, current.generation}:
            raise BackupError("RESTORE_GENERATION_NOT_FRESH")
        destination = files.reserve(candidate_id)
        input_semantic = source.read(semantic_digest)
        _copy_into(files, source, destination)
        with exclusive_store_lease(destination, boundary=files.boundary) as candidate_lease:
            candidate = open_store(destination, boundary=files.boundary)
            if (
                candidate.generation != manifest.original_generation
                or candidate.read(summaries) != manifest.records
            ):
                raise BackupError("RESTORE_CANDIDATE_COPY_CHANGED")
            transform = reconcile_candidate(
                files,
                candidate_id,
                lease=candidate_lease,
                expected_generation=manifest.original_generation,
                expected_semantic_sha256=input_semantic,
                expected_summary_sha256=summary_digest(manifest.records),
                cutoff=now,
                clock=clock,
            )
            require_exportable(transform)
            retained = candidate.read(summaries)
            revoked, version = _rotate(candidate, generation, manifest.recovery_point, stamp)
            rotated = open_store(destination, boundary=files.boundary)
            if rotated.generation != generation or rotated.read(summaries) != retained:
                raise BackupError("RESTORE_RETAINED_AUTHORITY_CHANGED")
            rotated.read(lambda db: projection.capture(db, generation, stamp))
            _flush(destination)
            digest, size = files.digest(candidate_id)
            content_digest = rotated.read(semantic_digest)
        if files.manifest(backup_id) != manifest:
            raise BackupError("RESTORE_SOURCE_BACKUP_CHANGED")
        return PreparedRestoreCandidate(
            candidate_id,
            backup_id,
            files.binding,
            manifest.original_generation,
            generation,
            manifest.recovery_point,
            stamp,
            digest,
            size,
            content_digest,
            retained,
            revoked,
            version,
            transform,
        )


def prepare_reconciled_candidate(
    files: BackupFiles,
    expected: RestoreCandidate,
    *,
    canonical_lease: MaintenanceLease,
    source_path: Path,
    now: datetime,
    clock: Callable[[], datetime],
) -> PreparedRestoreCandidate:
    """Internal operator step. Caller holds canonical exclusion and catalogue lock.

    Source is exactly canonical or the recognized staged target. No new generation,
    rotation timestamp or original operation is created by this isolated transform.
    """
    assert_outside_write_transaction()
    canonical_lease.assert_held(files.source, boundary=files.boundary)
    allowed = (files.source, files.path(expected.candidate_id, "sqlite3"))
    if source_path not in allowed or expected.source_binding != files.binding:
        raise BackupError("RESTORE_RETENTION_SOURCE_INVALID")
    stamp = _instant(now)
    source = open_store(source_path, boundary=files.boundary)
    if (
        source.generation != expected.new_generation
        or source.read(semantic_digest) != expected.semantic_sha256
        or source.read(summaries) != expected.records
    ):
        raise BackupError("RESTORE_RETENTION_SOURCE_CHANGED")
    count, occupied = files.usage()
    size = _io_path(source_path).stat().st_size
    if (
        count + 3 > MAX_CATALOGUE_ENTRIES
        or occupied + size + 2 * MAX_MANIFEST_BYTES > MAX_CATALOGUE_BYTES
    ):
        raise BackupError("RESTORE_CANDIDATE_QUOTA")
    candidate_id = str(uuid4())
    destination = files.reserve(candidate_id)
    _copy_into(files, source, destination)
    with exclusive_store_lease(destination, boundary=files.boundary) as candidate_lease:
        transform = reconcile_candidate(
            files,
            candidate_id,
            lease=candidate_lease,
            expected_generation=expected.new_generation,
            expected_semantic_sha256=expected.semantic_sha256,
            expected_summary_sha256=summary_digest(expected.records),
            cutoff=now,
            clock=clock,
        )
        require_exportable(transform)
        candidate = open_store(destination, boundary=files.boundary)
        snapshot = candidate.read(lambda db: projection.capture(db, candidate.generation, stamp))
        if snapshot is None:
            raise BackupError("RESTORE_PROJECTION_METADATA_REQUIRED")
        _flush(destination)
        digest, size = files.digest(candidate_id)
        return PreparedRestoreCandidate(
            candidate_id,
            expected.backup_id,
            files.binding,
            expected.original_generation,
            expected.new_generation,
            expected.recovery_point,
            expected.prepared_at,
            digest,
            size,
            candidate.read(semantic_digest),
            candidate.read(summaries),
            expected.revoked_credentials,
            snapshot.version,
            transform,
        )
