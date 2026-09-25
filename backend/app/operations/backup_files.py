"""Owned backup pairs inside the existing allowed runtime Store subtree.

The local operator directory is trusted. Guards reject configuration/link mistakes;
they do not claim to defend against a hostile administrator racing replacement.
"""

import hashlib
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.common import DTO, Digest, Id, UtcInstant
from app.database.maintenance import MaintenanceError, initialize_maintenance_guard
from app.database.paths import (
    RuntimeBoundary,
    _io_path,
    _resolved_path,
    guarded_store_path,
    reserve_new_store,
)
from app.database.store import Store, assert_outside_write_transaction
from app.sessions.state import canonical

MAX_BACKUP_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 32 * 1024
MAX_BACKUPS = 128
MAX_CATALOGUE_ENTRIES = MAX_BACKUPS * 6 + 1
MAX_CATALOGUE_BYTES = 512 * 1024 * 1024
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
_BACKUP = re.compile(
    rf"backup\.({_UUID})\.(sqlite3|manifest\.json|manifest\.tmp|pin\.json|expiry\.json|expiry\.tmp)\Z"
)


class BackupError(ValueError):
    """Closed operator code; never include private values or rejected paths."""


class RecordSummary(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    table: Literal[
        "owners",
        "owner_credentials",
        "conversation_sessions",
        "messages",
        "command_receipts",
        "booking_drafts",
        "booking_reviews",
        "operation_outcomes",
        "bookings",
        "leads",
        "lead_bookings",
    ]
    count: Annotated[int, Field(strict=True, ge=0, le=10_000)]
    identity_sha256: Digest


class BackupManifest(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["store-backup-1"] = "store-backup-1"
    backup_id: Id
    source_binding: Digest
    original_generation: Id
    schema_version: Literal["0001", "0002"]
    inventory_mode: Literal["fts5", "bounded_lexical"] | None
    source_created_at: UtcInstant
    recovery_point: UtcInstant
    expires_at: UtcInstant
    database_sha256: Digest
    database_bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_BACKUP_BYTES)]
    records: Annotated[tuple[RecordSummary, ...], Field(min_length=11, max_length=11)]

    @model_validator(mode="after")
    def consistent(self) -> "BackupManifest":
        if (
            datetime.fromisoformat(self.expires_at) - datetime.fromisoformat(self.recovery_point)
            != timedelta(days=7)
            or len({row.table for row in self.records}) != 11
        ):
            raise ValueError("BACKUP_MANIFEST_INCOMPATIBLE")
        if (self.schema_version == "0001") != (self.inventory_mode is None):
            raise ValueError("BACKUP_PROFILE_INCOMPATIBLE")
        return self


class BackupExpiryIntent(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["backup-expiry-1"] = "backup-expiry-1"
    manifest: BackupManifest
    cutoff: UtcInstant

    @model_validator(mode="after")
    def expired(self) -> "BackupExpiryIntent":
        if datetime.fromisoformat(self.manifest.expires_at) > datetime.fromisoformat(self.cutoff):
            raise ValueError("BACKUP_NOT_EXPIRED")
        return self


def manifest_bytes(value: BackupManifest) -> bytes:
    return canonical(value.model_dump(mode="json")) + b"\n"


def _regular_chain(path: Path, *, directory: bool = False) -> None:
    for part in (*reversed(path.parents), path):
        try:
            info = _io_path(part).lstat()
        except FileNotFoundError as exc:
            if getattr(exc, "winerror", None) not in {None, 2, 3}:
                raise
            continue
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise BackupError("BACKUP_REPARSE_POINT")
        if part != path or directory:
            if not stat.S_ISDIR(info.st_mode):
                raise BackupError("BACKUP_PARENT_NOT_DIRECTORY")
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise BackupError("BACKUP_NOT_PRIVATE_REGULAR_FILE")


class BackupFiles:
    def __init__(self, store: Store) -> None:
        self._bind(store.path, boundary=store.boundary, must_exist=True)

    def _bind(self, path: Path, *, boundary: RuntimeBoundary, must_exist: bool) -> None:
        self.boundary = boundary
        self.source = guarded_store_path(path, boundary=boundary, must_exist=must_exist)
        self.must_exist = must_exist
        self.binding = hashlib.sha256(str(self.source).casefold().encode("utf-8")).hexdigest()
        self.root = boundary.physical_root / "stores" / "backups" / self.binding

    @classmethod
    def for_store_path(
        cls, path: Path, *, boundary: RuntimeBoundary, must_exist: bool = True
    ) -> "BackupFiles":
        """Locate guarded artifacts without inventing an accepted Store object.

        This grants no Store/restore authority. Recovery still acquires the real
        maintenance lease and validates its durable intent before any mutation.
        """
        value = cls.__new__(cls)
        value._bind(path, boundary=boundary, must_exist=must_exist)
        return value

    def directory(self, *, create: bool = False) -> Path:
        assert_outside_write_transaction()
        if (
            guarded_store_path(self.source, boundary=self.boundary, must_exist=self.must_exist)
            != self.source
        ):
            raise BackupError("BACKUP_SOURCE_MAPPING_CHANGED")
        _regular_chain(self.root, directory=True)
        if create:
            for part in reversed(self.root.parents):
                if not _io_path(part).exists():
                    _io_path(part).mkdir()
                    _regular_chain(part, directory=True)
            if not _io_path(self.root).exists():
                _io_path(self.root).mkdir()
        _regular_chain(self.root, directory=True)
        if _resolved_path(self.root, strict=True) != self.root:
            raise BackupError("BACKUP_MAPPING_CHANGED")
        return self.root

    def path(self, backup_id: str, suffix: str) -> Path:
        name = f"backup.{backup_id}.{suffix}"
        if _BACKUP.fullmatch(name) is None:
            raise BackupError("BACKUP_NAME_INVALID")
        path = self.directory() / name
        _regular_chain(path)
        if _resolved_path(path, strict=False) != path:
            raise BackupError("BACKUP_MAPPING_CHANGED")
        return path

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Bounded catalogue exclusion; never delete this shared lock file."""
        import msvcrt

        path = self.directory(create=True) / "catalogue.lock"
        _regular_chain(path)
        descriptor = os.open(_io_path(path), os.O_RDWR | os.O_CREAT | os.O_BINARY, 0o600)
        locked = False
        try:
            _regular_chain(path)
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise BackupError("BACKUP_CATALOGUE_BUSY") from None
            locked = True
            yield
        finally:
            try:
                if locked:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(descriptor)

    def reserve(self, backup_id: str) -> Path:
        path = self.path(backup_id, "sqlite3")
        try:
            initialize_maintenance_guard(path, boundary=self.boundary, must_exist=False)
        except MaintenanceError:
            raise BackupError("BACKUP_MAINTENANCE_GUARD_UNAVAILABLE") from None
        return reserve_new_store(path, boundary=self.boundary)

    def digest(self, backup_id: str) -> tuple[str, int]:
        path = guarded_store_path(
            self.path(backup_id, "sqlite3"), boundary=self.boundary, must_exist=True
        )
        size = _io_path(path).stat().st_size
        if not 0 < size <= MAX_BACKUP_BYTES:
            raise BackupError("BACKUP_DATABASE_SIZE_LIMIT")
        digest, read = hashlib.sha256(), 0
        with _io_path(path).open("rb") as source:
            while block := source.read(1024 * 1024):
                read += len(block)
                if read > MAX_BACKUP_BYTES:
                    raise BackupError("BACKUP_DATABASE_SIZE_LIMIT")
                digest.update(block)
        self.path(backup_id, "sqlite3")
        if read != size or _io_path(path).stat().st_size != size:
            raise BackupError("BACKUP_DATABASE_CHANGED")
        return digest.hexdigest(), size

    def publish(self, manifest: BackupManifest) -> None:
        if manifest.source_binding != self.binding:
            raise BackupError("BACKUP_DIFFERENT_STORE")
        target, temporary = (
            self.path(manifest.backup_id, "manifest.json"),
            self.path(manifest.backup_id, "manifest.tmp"),
        )
        if _io_path(target).exists():
            raise BackupError("BACKUP_ALREADY_PUBLISHED")
        data = manifest_bytes(manifest)
        if len(data) > MAX_MANIFEST_BYTES:
            raise BackupError("BACKUP_MANIFEST_SIZE_LIMIT")
        with _io_path(temporary).open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        self.path(manifest.backup_id, "manifest.json")
        os.rename(_io_path(temporary), _io_path(target))  # Windows still refuses overwrite.

    def _entries(self) -> Iterator[Path]:
        root = self.directory()
        for entry in _io_path(root).iterdir():
            # Names come from the same directory; no extended identity escapes.
            yield root / entry.name

    def usage(self) -> tuple[int, int]:
        """Charge every regular artifact, including preserved failed/unmanifested files."""
        count, total = 0, 0
        for path in self._entries():
            count += 1
            if count > MAX_CATALOGUE_ENTRIES:
                raise BackupError("BACKUP_CATALOGUE_LIMIT")
            _regular_chain(path)
            total += _io_path(path).stat().st_size
            if total > MAX_CATALOGUE_BYTES:
                raise BackupError("BACKUP_CATALOGUE_SIZE_LIMIT")
        return count, total

    def manifest(self, backup_id: str) -> BackupManifest:
        if any(
            _io_path(self.path(backup_id, suffix)).exists()
            for suffix in ("expiry.json", "expiry.tmp")
        ):
            raise BackupError("BACKUP_EXPIRY_RECOVERY_REQUIRED")
        path = self.path(backup_id, "manifest.json")
        if _io_path(path).stat().st_size > MAX_MANIFEST_BYTES:
            raise BackupError("BACKUP_MANIFEST_SIZE_LIMIT")
        with _io_path(path).open("rb") as source:
            data = source.read(MAX_MANIFEST_BYTES + 1)
        try:
            value = BackupManifest.model_validate_json(data)
            if data != manifest_bytes(value) or value.backup_id != backup_id:
                raise ValueError("BACKUP_MANIFEST_NONCANONICAL")
        except ValueError:
            raise BackupError("BACKUP_MANIFEST_INCOMPATIBLE") from None
        if value.source_binding != self.binding:
            raise BackupError("BACKUP_DIFFERENT_STORE")
        if self.digest(backup_id) != (value.database_sha256, value.database_bytes):
            raise BackupError("BACKUP_DATABASE_CHANGED")
        return value

    def catalogue(self) -> tuple[BackupManifest, ...]:
        self.usage()
        names = []
        total = 0
        for count, path in enumerate(self._entries(), 1):
            if count > MAX_CATALOGUE_ENTRIES:
                raise BackupError("BACKUP_CATALOGUE_LIMIT")
            match = _BACKUP.fullmatch(path.name)
            if match is not None and match[2] in {"expiry.json", "expiry.tmp"}:
                raise BackupError("BACKUP_EXPIRY_RECOVERY_REQUIRED")
            if match is not None and match[2] == "manifest.json":
                names.append(match[1])
        if len(names) > MAX_BACKUPS:
            raise BackupError("BACKUP_CATALOGUE_LIMIT")
        result = []
        for backup_id in sorted(names):
            value = self.manifest(backup_id)
            total += value.database_bytes
            if total > MAX_CATALOGUE_BYTES:
                raise BackupError("BACKUP_CATALOGUE_SIZE_LIMIT")
            result.append(value)
        return tuple(result)

    def pinned(self, backup_id: str) -> bool:
        # Any guarded pin is conservative protection, not permission to restore.
        return _io_path(self.path(backup_id, "pin.json")).exists()

    def begin_expiry(self, manifest: BackupManifest, cutoff: str) -> BackupExpiryIntent:
        """Caller holds catalogue lock; durable identity precedes the first unlink."""
        if self.manifest(manifest.backup_id) != manifest or self.pinned(manifest.backup_id):
            raise BackupError("BACKUP_EXPIRY_INSPECTION_CHANGED")
        value = BackupExpiryIntent(manifest=manifest, cutoff=cutoff)
        temporary = self.path(manifest.backup_id, "expiry.tmp")
        target = self.path(manifest.backup_id, "expiry.json")
        with _io_path(temporary).open("xb") as output:
            output.write(canonical(value.model_dump(mode="json")) + b"\n")
            output.flush()
            os.fsync(output.fileno())
        os.rename(_io_path(temporary), _io_path(target))
        return value

    def pending_expiries(self) -> tuple[BackupExpiryIntent, ...]:
        self.usage()
        result: dict[str, BackupExpiryIntent] = {}
        for path in sorted(self._entries()):
            match = _BACKUP.fullmatch(path.name)
            if match is None or match[2] not in {"expiry.json", "expiry.tmp"}:
                continue
            guarded = self.path(match[1], match[2])
            if _io_path(guarded).stat().st_size > MAX_MANIFEST_BYTES:
                raise BackupError("BACKUP_EXPIRY_INTENT_LIMIT")
            with _io_path(guarded).open("rb") as source:
                data = source.read(MAX_MANIFEST_BYTES + 1)
            try:
                value = BackupExpiryIntent.model_validate_json(data)
                if (
                    value.manifest.backup_id != match[1]
                    or value.manifest.source_binding != self.binding
                    or data != canonical(value.model_dump(mode="json")) + b"\n"
                ):
                    raise ValueError("INCOMPATIBLE")
            except ValueError:
                raise BackupError("BACKUP_EXPIRY_INTENT_INVALID") from None
            previous = result.get(match[1])
            if previous is not None and previous != value:
                raise BackupError("BACKUP_EXPIRY_INTENT_CONFLICT")
            result[match[1]] = value
        return tuple(result[key] for key in sorted(result))

    def finish_expiry(self, intent: BackupExpiryIntent, *, now: str) -> None:
        """Reconcile exact owned bytes, including either already-completed unlink."""
        if intent not in self.pending_expiries():
            raise BackupError("BACKUP_EXPIRY_INTENT_MISSING")
        manifest, cutoff = intent.manifest, datetime.fromisoformat(intent.cutoff)
        if (
            manifest.source_binding != self.binding
            or cutoff > datetime.fromisoformat(now)
            or self.pinned(manifest.backup_id)
        ):
            raise BackupError("BACKUP_EXPIRY_NOT_AUTHORIZED")
        temporary = self.path(manifest.backup_id, "expiry.tmp")
        durable = self.path(manifest.backup_id, "expiry.json")
        if _io_path(temporary).exists():
            if _io_path(durable).exists():
                _io_path(temporary).unlink()  # Both strict, identical intents were checked above.
            else:
                os.rename(_io_path(temporary), _io_path(durable))
        path = self.path(manifest.backup_id, "manifest.json")
        if _io_path(path).exists() and (
            _io_path(path).stat().st_size > MAX_MANIFEST_BYTES
            or _io_path(path).read_bytes() != manifest_bytes(manifest)
        ):
            raise BackupError("BACKUP_EXPIRY_MANIFEST_CHANGED")
        database = self.path(manifest.backup_id, "sqlite3")
        if _io_path(database).exists():
            if self.digest(manifest.backup_id) != (
                manifest.database_sha256,
                manifest.database_bytes,
            ):
                raise BackupError("BACKUP_EXPIRY_DATABASE_CHANGED")
            _io_path(database).unlink()
        if _io_path(path).exists():
            _io_path(path).unlink()
        _io_path(durable).unlink()
