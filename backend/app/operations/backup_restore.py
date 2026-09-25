"""Bounded consistent backups and verified candidate inspection.

Restore mutation is a separate operator transition, pending the actual shared
maintenance lease. Nothing here copies a live database file or assumes quiescence.
"""

import hashlib
import os
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import DemoPolicy
from app.database.maintenance import shared_store_lease
from app.database.paths import _io_path, _sqlite_uri
from app.database.store import Store, StoreError, assert_outside_write_transaction, open_store
from app.identity.service import utc_text
from app.operations.backup_files import (
    MAX_BACKUP_BYTES,
    MAX_BACKUPS,
    MAX_CATALOGUE_BYTES,
    MAX_CATALOGUE_ENTRIES,
    MAX_MANIFEST_BYTES,
    BackupError,
    BackupFiles,
    BackupManifest,
    RecordSummary,
)
from app.sessions.state import canonical, fingerprint

MAX_AUTHORITY_ROWS = 10_000
BACKUP_SECONDS = 30
# Literal implementation-owned identifiers. No operator text becomes SQL.
SCANS = (
    ("owners", "id"),
    ("owner_credentials", "id,owner_id"),
    ("conversation_sessions", "id,owner_id,journey_id"),
    ("messages", "id,owner_id,session_id,payload_hash"),
    ("command_receipts", "id,owner_id,command_kind,client_action_id,payload_hash"),
    ("booking_drafts", "id,owner_id"),
    ("booking_reviews", "id,owner_id,operation_key,payload_hash,store_generation"),
    ("operation_outcomes", "id,owner_id,review_id,operation_key,payload_hash,store_generation"),
    ("bookings", "id,owner_id,review_id,operation_id"),
    ("leads", "id,owner_id,journey_id"),
    ("lead_bookings", "lead_id,booking_id,owner_id"),
)


@dataclass(frozen=True)
class BackupObservation:
    manifest: BackupManifest
    state: Literal["available", "expired"]
    pinned: bool


@dataclass(frozen=True)
class BackupExpiryInspection:
    source_binding: str
    cutoff: str
    digest: str
    eligible: tuple[str, ...]
    protected: tuple[str, ...]


def summaries(db: Session) -> tuple[RecordSummary, ...]:
    result = []
    connection = db.connection()
    for table, columns in SCANS:
        count = connection.exec_driver_sql(f"SELECT count(*) FROM {table}").scalar_one()
        if type(count) is not int or not 0 <= count <= MAX_AUTHORITY_ROWS:
            raise BackupError("BACKUP_AUTHORITY_SIZE_LIMIT")
        digest = hashlib.sha256()
        actual = 0
        for row in connection.exec_driver_sql(f"SELECT {columns} FROM {table} ORDER BY {columns}"):
            data = canonical(tuple(row))
            digest.update(len(data).to_bytes(8, "big") + data)
            actual += 1
        if actual != count:
            raise BackupError("BACKUP_SNAPSHOT_CHANGED")
        result.append(
            RecordSummary.model_validate(
                {
                    "table": table,
                    "count": count,
                    "identity_sha256": digest.hexdigest(),
                }
            )
        )
    return tuple(result)


class BackupService:
    def __init__(self, store: Store, *, clock: Callable[[], datetime] | None = None) -> None:
        self.store = store
        self.files = BackupFiles(store)
        self.policy = DemoPolicy()
        self.clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> str:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise BackupError("BACKUP_CLOCK_INVALID")
        return utc_text(value)

    def create(self) -> BackupManifest:
        """One SQLite API snapshot, then closed-file integrity and manifest publication."""
        assert_outside_write_transaction()
        with self.files.lock():
            existing = self.files.catalogue()
            if len(existing) >= MAX_BACKUPS:
                raise BackupError("BACKUP_CATALOGUE_LIMIT")
            entries, occupied = self.files.usage()
            if entries + 3 > MAX_CATALOGUE_ENTRIES:
                raise BackupError("BACKUP_CATALOGUE_LIMIT")
            backup_id = str(uuid4())
            destination = self.files.reserve(backup_id)
            deadline = time.monotonic() + BACKUP_SECONDS

            def progress(status: int, remaining: int, total: int) -> None:
                if time.monotonic() > deadline:
                    raise BackupError("BACKUP_TIME_LIMIT")
                if status not in {
                    sqlite3.SQLITE_OK,
                    sqlite3.SQLITE_DONE,
                    sqlite3.SQLITE_BUSY,
                    sqlite3.SQLITE_LOCKED,
                }:
                    raise BackupError("BACKUP_COPY_FAILED")

            def capture(db: Session) -> tuple[str, str, tuple[RecordSummary, ...]]:
                connection = db.connection()
                page_size = connection.exec_driver_sql("PRAGMA page_size").scalar_one()
                pages = connection.exec_driver_sql("PRAGMA page_count").scalar_one()
                size = page_size * pages
                if not 0 < size <= MAX_BACKUP_BYTES:
                    raise BackupError("BACKUP_DATABASE_SIZE_LIMIT")
                if occupied + size + 2 * MAX_MANIFEST_BYTES > MAX_CATALOGUE_BYTES:
                    raise BackupError("BACKUP_CATALOGUE_SIZE_LIMIT")
                metadata = connection.exec_driver_sql(
                    "SELECT store_generation,schema_version,created_at "
                    "FROM store_metadata WHERE id=1"
                ).one()
                if metadata[:2] != (self.store.generation, self.store.schema_version):
                    raise BackupError("BACKUP_SOURCE_GENERATION_CHANGED")
                recovery_point = self._now()
                if metadata[2] > recovery_point:
                    raise BackupError("BACKUP_CLOCK_BEFORE_SOURCE")
                records = summaries(db)
                source = connection.connection.driver_connection
                if not isinstance(source, sqlite3.Connection):
                    raise StoreError("STORE_DRIVER_INCOMPATIBLE")
                # READ snapshot is already established. The backup API copies that
                # coherent snapshot; the independently reserved target is private.
                with (
                    shared_store_lease(destination, boundary=self.store.boundary),
                    closing(
                        sqlite3.connect(
                            _sqlite_uri(destination, "rw"),
                            uri=True,
                            isolation_level=None,
                            timeout=1,
                        )
                    ) as target,
                ):
                    target.execute("PRAGMA journal_mode=DELETE")
                    target.execute("PRAGMA synchronous=FULL")
                    source.backup(target, pages=128, progress=progress, sleep=0.01)
                    if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                        raise BackupError("BACKUP_INTEGRITY_FAILED")
                return metadata[2], recovery_point, records

            created, recovery_point, records = self.store.read(capture)
            with _io_path(destination).open("r+b") as output:
                output.flush()
                os.fsync(output.fileno())
            candidate = open_store(destination, boundary=self.store.boundary)
            if (candidate.generation, candidate.schema_version, candidate.inventory_mode) != (
                self.store.generation,
                self.store.schema_version,
                self.store.inventory_mode,
            ) or candidate.read(summaries) != records:
                raise BackupError("BACKUP_COPY_IDENTITY_MISMATCH")
            digest, size = self.files.digest(backup_id)
            manifest = BackupManifest.model_validate(
                {
                    "backup_id": backup_id,
                    "source_binding": self.files.binding,
                    "original_generation": candidate.generation,
                    "schema_version": candidate.schema_version,
                    "inventory_mode": candidate.inventory_mode,
                    "source_created_at": created,
                    "recovery_point": recovery_point,
                    "expires_at": utc_text(
                        datetime.fromisoformat(recovery_point)
                        + timedelta(days=self.policy.backups_retention_days)
                    ),
                    "database_sha256": digest,
                    "database_bytes": size,
                    "records": records,
                }
            )
            self.files.publish(manifest)
            if self.files.manifest(backup_id) != manifest:
                raise BackupError("BACKUP_PUBLISHED_PAIR_CHANGED")
            return manifest

    def inspect(self, backup_id: str) -> BackupObservation:
        """Read-only verified pair. Expired backup observation is not restore permission."""
        assert_outside_write_transaction()
        with self.files.lock():
            value = self.files.manifest(backup_id)
            candidate = open_store(
                self.files.path(backup_id, "sqlite3"), boundary=self.store.boundary
            )
            if (candidate.generation, candidate.schema_version, candidate.inventory_mode) != (
                value.original_generation,
                value.schema_version,
                value.inventory_mode,
            ) or candidate.read(summaries) != value.records:
                raise BackupError("BACKUP_CANDIDATE_IDENTITY_MISMATCH")
            return BackupObservation(
                value,
                "expired" if value.expires_at <= self._now() else "available",
                self.files.pinned(backup_id),
            )

    def _expiry(self, cutoff: str) -> BackupExpiryInspection:
        values = self.files.catalogue()
        pins = tuple(value.backup_id for value in values if self.files.pinned(value.backup_id))
        eligible = tuple(
            value.backup_id
            for value in values
            if value.expires_at <= cutoff and value.backup_id not in pins
        )
        return BackupExpiryInspection(
            self.files.binding,
            cutoff,
            fingerprint(
                {
                    "backups": [value.model_dump(mode="json") for value in values],
                    "pins": pins,
                    "cutoff": cutoff,
                }
            ),
            eligible,
            pins,
        )

    def inspect_expiry(self) -> BackupExpiryInspection:
        assert_outside_write_transaction()
        with self.files.lock():
            return self._expiry(self._now())

    def apply_expiry(self, observed: BackupExpiryInspection) -> tuple[str, ...]:
        """Explicit bounded cleanup of verified expired unpinned owned pairs only."""
        assert_outside_write_transaction()
        now = datetime.fromisoformat(self._now())
        if (
            type(observed) is not BackupExpiryInspection
            or observed.source_binding != self.files.binding
        ):
            raise BackupError("BACKUP_EXPIRY_SCOPE_CHANGED")
        if not now - timedelta(minutes=5) <= datetime.fromisoformat(observed.cutoff) <= now:
            raise BackupError("BACKUP_EXPIRY_INSPECTION_EXPIRED")
        with self.files.lock():
            fresh = self._expiry(observed.cutoff)
            if fresh != observed:
                raise BackupError("BACKUP_EXPIRY_INSPECTION_CHANGED")
            removed = []
            for backup_id in fresh.eligible:
                intent = self.files.begin_expiry(self.files.manifest(backup_id), fresh.cutoff)
                self.files.finish_expiry(intent, now=self._now())
                removed.append(backup_id)
            return tuple(removed)

    def resume_expiry(self) -> tuple[str, ...]:
        """Explicit recovery only; incomplete pair deletion is never silently skipped."""
        assert_outside_write_transaction()
        with self.files.lock():
            finished = []
            for intent in self.files.pending_expiries():
                self.files.finish_expiry(intent, now=self._now())
                finished.append(intent.manifest.backup_id)
            return tuple(finished)
