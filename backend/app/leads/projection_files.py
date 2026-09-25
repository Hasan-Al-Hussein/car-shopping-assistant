"""Private Windows projection paths, publication lock and recoverable file pair.

The selected runtime directory is trusted operator state. These checks reject
misconfiguration and pre-existing links, not a hostile administrator racing paths.
All publishers and future restore tools must acquire this same physical lock.
"""

import ctypes
import hashlib
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import get_ident
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from app.api.schemas.common import DTO, Digest, Id, Revision, UtcInstant
from app.database.paths import RuntimeBoundary, guarded_store_path
from app.database.store import Store, assert_outside_write_transaction
from app.leads.projection_repository import MAX_ROWS, ProjectionError

CSV_NAME = "leads.csv"
MANIFEST_NAME = "leads.manifest.json"
PENDING_NAME = "leads.pending.json"
LOCK_NAME = "leads.publication.lock"
MAX_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 4096
_TEMP = re.compile(
    r"leads\.[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
    r"\.(?:csv|json)\.tmp\Z"
)


class PublicationManifest(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")

    format: Literal["leads-publication-1"] = "leads-publication-1"
    store_binding: Digest
    store_generation: Id
    projection_version: Revision
    publication_id: Id
    sha256: Digest
    byte_length: Annotated[int, Field(strict=True, ge=1, le=MAX_BYTES)]
    row_count: Annotated[int, Field(strict=True, ge=0, le=MAX_ROWS)]
    captured_at: UtcInstant


class PublicationBusy(ProjectionError):
    pass


def manifest_bytes(value: PublicationManifest) -> bytes:
    return (json.dumps(
        value.model_dump(mode="json"), sort_keys=True, ensure_ascii=False,
        allow_nan=False, separators=(",", ":"),
    ) + "\n").encode("utf-8")


def _inspect(path: Path, *, directory: bool = False) -> None:
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ProjectionError("CSV_REPARSE_POINT")
        if part != path or directory:
            if not stat.S_ISDIR(info.st_mode):
                raise ProjectionError("CSV_PARENT_NOT_DIRECTORY")
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ProjectionError("CSV_NOT_PRIVATE_REGULAR_FILE")


class ProjectionFiles:
    def __init__(self, store: Store) -> None:
        self._bind(store.path, boundary=store.boundary, must_exist=True)

    def _bind(self, path: Path, *, boundary: RuntimeBoundary, must_exist: bool) -> None:
        self.boundary = boundary
        # Reuse the Store guard only for its Store path, never for a CSV path.
        physical_store = guarded_store_path(
            path, boundary=self.boundary, must_exist=must_exist
        )
        self.store_binding = hashlib.sha256(
            str(physical_store).casefold().encode("utf-8")
        ).hexdigest()
        self.root = self.boundary.physical_root / "exports"
        self._held_lock: tuple[int, int, int] | None = None

    @classmethod
    def for_store_path(cls, path: Path, *, boundary: RuntimeBoundary,
                       must_exist: bool = True) -> "ProjectionFiles":
        """Locate the same physical lock before opening a marker-blocked Store.

        No generation, accepted Store or maintenance authority is fabricated.
        The operator must separately acquire its real exclusive Store lease.
        """
        value = cls.__new__(cls)
        value._bind(path, boundary=boundary, must_exist=must_exist)
        return value

    def directory(self, *, create: bool = False) -> Path:
        assert_outside_write_transaction()
        root = self.boundary.physical_root
        if os.name != "nt" or ctypes.windll.kernel32.GetDriveTypeW(str(root.anchor)) != 3:
            raise ProjectionError("CSV_FIXED_WINDOWS_VOLUME_REQUIRED")
        _inspect(root, directory=True)
        if root.resolve(strict=True) != root:
            raise ProjectionError("CSV_RUNTIME_MAPPING_CHANGED")
        _inspect(self.root, directory=True)
        if not self.root.exists() and create:
            self.root.mkdir()
        if self.root.resolve(strict=True) != root / "exports":
            raise ProjectionError("CSV_OUTSIDE_EXPORT_BOUNDARY")
        _inspect(self.root, directory=True)
        return self.root

    def path(self, name: str) -> Path:
        if name not in {CSV_NAME, MANIFEST_NAME, PENDING_NAME, LOCK_NAME} and not _TEMP.fullmatch(name):
            raise ProjectionError("CSV_INVALID_COMPANION_NAME")
        root = self.directory()
        value = root / name
        _inspect(value)
        if value.resolve(strict=False) != value:
            raise ProjectionError("CSV_COMPANION_MAPPING_CHANGED")
        return value

    @contextmanager
    def lock(self) -> Iterator[None]:
        import msvcrt

        if self._held_lock is not None:
            raise PublicationBusy("CSV_PUBLISHER_BUSY")
        self.directory(create=True)
        path = self.path(LOCK_NAME)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_BINARY, 0o600)
        locked = False
        try:
            self.path(LOCK_NAME)
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise PublicationBusy("CSV_PUBLISHER_BUSY") from None
            locked = True
            self._held_lock = os.getpid(), get_ident(), descriptor
            yield
        finally:
            try:
                if locked:
                    self._held_lock = None
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(descriptor)

    def assert_locked(self) -> None:
        """Require this instance's actual handle in its owning thread and process."""
        held = self._held_lock
        if held is None or held[:2] != (os.getpid(), get_ident()):
            raise ProjectionError("CSV_PUBLICATION_LOCK_REQUIRED")
        try:
            opened = os.fstat(held[2])
            current = self.path(LOCK_NAME).stat()
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise ProjectionError("CSV_PUBLICATION_LOCK_CHANGED")
        except OSError:
            raise ProjectionError("CSV_PUBLICATION_LOCK_LOST") from None

    def read_bytes(self, name: str, limit: int) -> bytes | None:
        assert_outside_write_transaction()
        path = self.path(name)
        if not path.exists():
            return None
        if path.stat().st_size > limit:
            raise ProjectionError("CSV_FILE_LIMIT")
        with path.open("rb") as source:
            value = source.read(limit + 1)
        if len(value) > limit:
            raise ProjectionError("CSV_FILE_LIMIT")
        return value

    def manifest(self, name: str) -> PublicationManifest | None:
        data = self.read_bytes(name, MAX_MANIFEST_BYTES)
        if data is None:
            return None
        try:
            value = PublicationManifest.model_validate_json(data)
            if manifest_bytes(value) != data:
                raise ValueError("NONCANONICAL")
        except (TypeError, ValueError):
            raise ProjectionError("CSV_MANIFEST_INCOMPATIBLE") from None
        if value.store_binding != self.store_binding:
            raise ProjectionError("CSV_DIFFERENT_STORE")
        return value

    def inspect_existing(
        self, *, generation: str, version: int, reconcile_from_generation: str | None
    ) -> tuple[PublicationManifest | None, PublicationManifest | None]:
        values = self.manifest(MANIFEST_NAME), self.manifest(PENDING_NAME)
        for value in values:
            if value is None:
                continue
            if value.store_generation != generation:
                if value.store_generation != reconcile_from_generation:
                    raise ProjectionError("CSV_OLD_GENERATION_REQUIRES_RECONCILIATION")
            elif value.projection_version > version:
                raise ProjectionError("CSV_PUBLICATION_NEWER_THAN_CANONICAL")
        # CSV without any ownership descriptor is never inferred from a plausible header.
        if self.path(CSV_NAME).exists() and all(value is None for value in values):
            raise ProjectionError("CSV_UNOWNED_PUBLICATION")
        return values

    def matches(self, manifest: PublicationManifest, data: bytes) -> bool:
        return (
            len(data) == manifest.byte_length
            and hashlib.sha256(data).hexdigest() == manifest.sha256
        )

    @staticmethod
    def _temporary(manifest: PublicationManifest, suffix: str) -> str:
        return f"leads.{manifest.publication_id}.{suffix}.tmp"

    def _write(self, name: str, data: bytes) -> None:
        assert_outside_write_transaction()
        path = self.path(name)
        with path.open("xb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())

    def prune_temporary_files(self) -> None:
        """Under the installation lock, remove only reserved UUID temp companions.

        Covers a process interruption while writing a descriptor before its atomic
        rename. Every such file is scratch; final/pending/lock files are excluded.
        Enumeration and deletion are bounded; unexpected directory size fails closed.
        """
        assert_outside_write_transaction()
        names = []
        with os.scandir(self.directory()) as entries:
            for index, entry in enumerate(entries):
                if index >= 256:
                    raise ProjectionError("CSV_DIRECTORY_LIMIT")
                if _TEMP.fullmatch(entry.name):
                    names.append(entry.name)
        if len(names) > 32:
            raise ProjectionError("CSV_TEMPORARY_CLEANUP_LIMIT")
        for name in names:
            self.path(name).unlink()

    def discard_known_temporary(self, manifest: PublicationManifest) -> None:
        for suffix in ("csv", "json"):
            path = self.path(self._temporary(manifest, suffix))
            if path.exists():
                path.unlink()

    def stage(self, manifest: PublicationManifest, data: bytes) -> None:
        assert_outside_write_transaction()
        metadata_temp = self._temporary(manifest, "json")
        self._write(metadata_temp, manifest_bytes(manifest))
        # Durable ownership/intended digest exists before the CSV can replace anything.
        os.replace(self.path(metadata_temp), self.path(PENDING_NAME))
        csv_temp = self._temporary(manifest, "csv")
        self._write(csv_temp, data)
        staged = self.read_bytes(csv_temp, MAX_BYTES)
        if staged != data or not self.matches(manifest, staged):
            raise ProjectionError("CSV_TEMPORARY_VERIFICATION_FAILED")

    def publish(self, manifest: PublicationManifest) -> None:
        """Only two renames in the dedicated Store READ fence, never a WRITE unit."""
        assert_outside_write_transaction()
        os.replace(self.path(self._temporary(manifest, "csv")), self.path(CSV_NAME))
        os.replace(self.path(PENDING_NAME), self.path(MANIFEST_NAME))

    def verified(self, expected: PublicationManifest) -> bool:
        actual = self.manifest(MANIFEST_NAME)
        data = self.read_bytes(CSV_NAME, MAX_BYTES)
        return actual == expected and data is not None and self.matches(expected, data)
