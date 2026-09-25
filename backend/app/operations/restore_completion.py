"""Read-only strict v1/v2 restore completion and current metadata association.

An observation is evidence, not authorization. The issued scope holds actual
maintenance admission; it does not freeze ordinary writes or inventory pointers.
"""

import hashlib
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import current_thread
from typing import Annotated, Literal

from pydantic import ConfigDict, StringConstraints, TypeAdapter, ValidationError
from sqlalchemy import Connection, select
from sqlalchemy.exc import UnboundExecutionError
from sqlalchemy.orm import Session

from app.api.schemas.common import DTO, Digest, Id, UtcInstant
from app.database.maintenance import (
    MaintenanceBusy,
    MaintenanceError,
    assert_store_lease,
    shared_store_lease,
)
from app.database.models import StoreMetadata
from app.database.paths import RuntimeBoundary, StorePathError, guarded_store_path
from app.database.store import StoreError, assert_outside_write_transaction, open_store
from app.identity.service import utc_text
from app.operations.backup_files import BackupError, BackupFiles, manifest_bytes
from app.operations.restore_files import MAX_INTENT_BYTES, encoded
from app.operations.restore_transition import parse_receipt


class RestoreCompletionError(ValueError):
    """Closed code only; no rejected paths, receipt contents or business data."""


class CompletedRestoreObservation(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")

    format: Literal["completed-restore-observation-1"]
    receipt_format: Literal["store-restore-receipt-1", "store-restore-receipt-2"]
    restore_id: Id
    receipt_path: Annotated[
        str, StringConstraints(strict=True, min_length=1, max_length=4096)
    ]
    receipt_sha256: Digest
    store_binding: Digest
    store_generation: Id
    schema_version: Literal["0001", "0002"]
    inventory_mode: Literal["fts5", "bounded_lexical"] | None
    source_created_at: UtcInstant
    restored_at: UtcInstant
    recovery_point: UtcInstant
    restore_started_at: UtcInstant
    restore_completed_at: UtcInstant
    observed_at: UtcInstant
    selected_backup_id: Id
    selected_backup_manifest_sha256: Digest
    selected_backup_database_sha256: Digest
    selected_original_generation: Id
    previous_generation: Id
    completion: Literal["historical_completed_associated"]
    absent_post_backup_authority: Literal["unknown"]


@dataclass(frozen=True, slots=True)
class _Request:
    path: Path
    physical: Path
    boundary: RuntimeBoundary
    restore_id: str
    receipt_sha256: str
    generation: str


@dataclass(frozen=True, slots=True)
class _ReceiptRead:
    data: bytes
    identity: tuple[int, int, int, int, int]
    handle_identity: tuple[int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class _Issued:
    request: _Request
    observation: CompletedRestoreObservation
    receipt: _ReceiptRead
    pid: int
    thread: object


_ID: TypeAdapter[str] = TypeAdapter(Id)
_DIGEST: TypeAdapter[str] = TypeAdapter(Digest)
_ISSUER = object()
_issued: dict["CompletedRestoreScope", _Issued] = {}
_Metadata = tuple[str, str, str, str | None, str | None]


def _outside_write() -> None:
    try:
        assert_outside_write_transaction()
    except StoreError as exc:
        raise RestoreCompletionError("RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED") from exc


def _pending(request: _Request) -> None:
    marker = Path(str(request.physical) + ".restore-intent.json")
    for path in (marker, Path(str(marker) + ".update.tmp")):
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE") from None
        raise RestoreCompletionError("RESTORE_COMPLETION_PENDING")


def _held(request: _Request) -> None:
    """Check the original lease before a fresh open can create another one."""
    _outside_write()
    try:
        physical = guarded_store_path(
            request.path, boundary=request.boundary, must_exist=True
        )
        if physical != request.physical:
            raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE")
        assert_store_lease(request.physical, boundary=request.boundary)
    except (OSError, StorePathError):
        raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE") from None
    except MaintenanceError as exc:
        code = (
            "RESTORE_COMPLETION_PENDING"
            if str(exc) == "MAINTENANCE_RECONCILIATION_REQUIRED"
            else "RESTORE_COMPLETION_SCOPE_NOT_LIVE"
        )
        raise RestoreCompletionError(code) from exc
    _pending(request)  # Also applies inside a same-thread exclusive scope.


@contextmanager
def _shared(request: _Request) -> Iterator[None]:
    lease = shared_store_lease(request.physical, boundary=request.boundary)
    try:
        lease.__enter__()
    except MaintenanceBusy as exc:
        raise RestoreCompletionError("RESTORE_COMPLETION_BUSY") from exc
    except MaintenanceError as exc:
        code = (
            "RESTORE_COMPLETION_PENDING"
            if str(exc) == "MAINTENANCE_RECONCILIATION_REQUIRED"
            else "RESTORE_COMPLETION_PATH_UNAVAILABLE"
        )
        raise RestoreCompletionError(code) from exc
    try:
        yield
    except BaseException as primary:
        try:
            lease.__exit__(None, None, None)
        except BaseException:
            primary.add_note("Restore completion scope release also failed.")
        raise
    else:
        try:
            lease.__exit__(None, None, None)
        except MaintenanceError as exc:
            raise RestoreCompletionError("RESTORE_COMPLETION_SCOPE_NOT_LIVE") from exc


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _receipt_identity(path: Path) -> tuple[int, int, int, int, int]:
    for parent in reversed(path.parents):
        info = parent.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE")
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_MISSING") from None
    identity = _file_identity(info)
    if path.resolve(strict=True) != path:
        raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE")
    return identity


def _read_receipt(path: Path) -> _ReceiptRead:
    try:
        before = _receipt_identity(path)
        if not 0 < before[2] <= MAX_INTENT_BYTES:
            raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_INVALID")
        with path.open("rb") as source:
            opened_stat = os.fstat(source.fileno())
            opened = _file_identity(opened_stat)
            data = source.read(MAX_INTENT_BYTES + 1)
            source.seek(0)
            repeated = source.read(MAX_INTENT_BYTES + 1)
            closed_stat = os.fstat(source.fileno())
            closed = _file_identity(closed_stat)
        after = _receipt_identity(path)
        stable = before == after and opened == closed
        if os.name == "nt":
            # CPython 3.13 path stat exposes birthtime as ctime, while fstat
            # exposes native ChangeTime. Keep each API's full stability check.
            stable = stable and (
                before[:4] == opened[:4] == closed[:4] == after[:4]
                and before[4] == opened_stat.st_birthtime_ns
                == closed_stat.st_birthtime_ns == after[4]
            )
        else:
            stable = stable and before == opened == closed == after
        if (
            not stable or data != repeated or len(data) != before[2]
        ):
            raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_CHANGED")
        return _ReceiptRead(data, after, closed)
    except OSError:
        raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE") from None


def _metadata(db: Session) -> _Metadata:
    # Column selection bypasses an old ORM identity-map value; no autoflush writes.
    with db.no_autoflush:
        row = db.execute(
            select(
                StoreMetadata.store_generation, StoreMetadata.schema_version,
                StoreMetadata.created_at, StoreMetadata.restored_at,
                StoreMetadata.recovery_point,
            ).where(StoreMetadata.id == 1)
        ).one_or_none()
    if row is None:
        raise RestoreCompletionError("RESTORE_COMPLETION_ASSOCIATION_CHANGED")
    return row[0], row[1], row[2], row[3], row[4]


def _observe(request: _Request) -> tuple[CompletedRestoreObservation, _ReceiptRead]:
    _held(request)
    try:
        catalogue = BackupFiles.for_store_path(
            request.path, boundary=request.boundary, must_exist=True
        )
        receipt_path = (
            catalogue.directory(create=False) / f"restore.{request.restore_id}.receipt.json"
        )
    except (OSError, StorePathError, BackupError):
        raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE") from None
    observed = _read_receipt(receipt_path)
    if hashlib.sha256(observed.data).hexdigest() != request.receipt_sha256:
        raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_CHANGED")
    try:
        receipt = parse_receipt(observed.data)
        if encoded(receipt) != observed.data or receipt.intent.restore_id != request.restore_id:
            raise ValueError("INVALID")
    except ValueError:
        raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_INVALID") from None
    intent, candidate = receipt.intent, receipt.intent.candidate
    selected = intent.selected
    if intent.source_binding != catalogue.binding:
        raise RestoreCompletionError("RESTORE_COMPLETION_ASSOCIATION_CHANGED")
    _held(request)
    try:
        store = open_store(request.physical, boundary=request.boundary)
        metadata = store.read(_metadata)
    except StoreError as exc:
        code = (
            "RESTORE_COMPLETION_BUSY" if str(exc) == "STORE_BUSY"
            else "RESTORE_COMPLETION_STORE_UNAVAILABLE"
        )
        raise RestoreCompletionError(code) from exc
    except (OSError, StorePathError):
        raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE") from None
    expected = (
        candidate.new_generation, selected.schema_version, selected.source_created_at,
        candidate.prepared_at, selected.recovery_point,
    )
    if (
        metadata != expected or store.generation != candidate.new_generation
        or store.generation != request.generation or store.schema_version != selected.schema_version
        or store.inventory_mode != selected.inventory_mode
    ):
        raise RestoreCompletionError("RESTORE_COMPLETION_ASSOCIATION_CHANGED")
    if _read_receipt(receipt_path) != observed:
        raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_CHANGED")
    _held(request)
    now = datetime.now(UTC)
    if not (
        datetime.fromisoformat(selected.source_created_at)
        <= datetime.fromisoformat(selected.recovery_point)
        <= datetime.fromisoformat(candidate.prepared_at)
        <= datetime.fromisoformat(intent.started_at)
        <= datetime.fromisoformat(receipt.completed_at) <= now
    ):
        raise RestoreCompletionError("RESTORE_COMPLETION_CLOCK_INVALID")
    try:
        result = CompletedRestoreObservation(
            format="completed-restore-observation-1",
            receipt_format=receipt.format,
            restore_id=intent.restore_id,
            receipt_path=str(receipt_path),
            receipt_sha256=request.receipt_sha256,
            store_binding=catalogue.binding,
            store_generation=store.generation,
            schema_version=selected.schema_version,
            inventory_mode=store.inventory_mode,
            source_created_at=selected.source_created_at,
            restored_at=candidate.prepared_at,
            recovery_point=selected.recovery_point,
            restore_started_at=intent.started_at,
            restore_completed_at=receipt.completed_at,
            observed_at=utc_text(now),
            selected_backup_id=selected.backup_id,
            selected_backup_manifest_sha256=hashlib.sha256(manifest_bytes(selected)).hexdigest(),
            selected_backup_database_sha256=selected.database_sha256,
            selected_original_generation=selected.original_generation,
            previous_generation=intent.previous.original_generation,
            completion="historical_completed_associated",
            absent_post_backup_authority="unknown",
        )
    except ValidationError:
        raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_INVALID") from None
    return result, observed


class CompletedRestoreScope:
    """Factory-issued capability. No Store, Session or mutable caller fields."""

    __slots__ = ()

    def __init__(self, issuer: object) -> None:
        if issuer is not _ISSUER:
            raise RestoreCompletionError("RESTORE_COMPLETION_SCOPE_NOT_LIVE")

    @property
    def observation(self) -> CompletedRestoreObservation:
        return _live(self).observation

    def revalidate(self) -> CompletedRestoreObservation:
        issued = _live(self)
        result, receipt = _observe(issued.request)
        if receipt != issued.receipt:
            raise RestoreCompletionError("RESTORE_COMPLETION_RECEIPT_CHANGED")
        if result.model_dump(exclude={"observed_at"}) != issued.observation.model_dump(
            exclude={"observed_at"}
        ):
            raise RestoreCompletionError("RESTORE_COMPLETION_ASSOCIATION_CHANGED")
        return result


def _live(scope: CompletedRestoreScope) -> _Issued:
    if type(scope) is not CompletedRestoreScope:
        raise RestoreCompletionError("RESTORE_COMPLETION_SCOPE_NOT_LIVE")
    issued = _issued.get(scope)
    if issued is None or issued.pid != os.getpid() or issued.thread is not current_thread():
        raise RestoreCompletionError("RESTORE_COMPLETION_SCOPE_NOT_LIVE")
    _held(issued.request)
    return issued


@contextmanager
def completed_restore_scope(
    path: Path, *, boundary: RuntimeBoundary, restore_id: str,
    expected_receipt_sha256: str, expected_generation: str,
) -> Iterator[CompletedRestoreScope]:
    _outside_write()
    try:
        original_id = _ID.validate_python(restore_id)
        digest = _DIGEST.validate_python(expected_receipt_sha256)
        generation = _ID.validate_python(expected_generation)
        if not isinstance(path, Path) or not isinstance(boundary, RuntimeBoundary):
            raise ValueError("INVALID")
    except ValueError:
        raise RestoreCompletionError("RESTORE_COMPLETION_INPUT_INVALID") from None
    try:
        physical = guarded_store_path(path, boundary=boundary, must_exist=True)
    except (OSError, StorePathError):
        raise RestoreCompletionError("RESTORE_COMPLETION_PATH_UNAVAILABLE") from None
    request = _Request(path, physical, boundary, original_id, digest, generation)
    _pending(request)
    with _shared(request):
        observation, receipt = _observe(request)
        scope = CompletedRestoreScope(_ISSUER)
        _issued[scope] = _Issued(request, observation, receipt, os.getpid(), current_thread())
        try:
            yield scope
            scope.revalidate()
        finally:
            _issued.pop(scope, None)


def recheck_completed_restore_metadata(
    db: Session, observation: CompletedRestoreObservation,
) -> None:
    """Compare metadata inside the caller's actual WRITE; no receipt authentication."""
    # Store binds Session to its already-begun Connection. Do not let Session
    # autobegin on an Engine manufacture the missing writer boundary.
    try:
        bound = db.get_bind()
    except UnboundExecutionError:
        raise RestoreCompletionError("RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED") from None
    if (
        not isinstance(bound, Connection) or not bound.in_transaction()
        or bound.get_execution_options().get("store_write") is not True
    ):
        raise RestoreCompletionError("RESTORE_COMPLETION_WRITE_BOUNDARY_REQUIRED")
    if _metadata(db) != (
        observation.store_generation, observation.schema_version, observation.source_created_at,
        observation.restored_at, observation.recovery_point,
    ):
        raise RestoreCompletionError("RESTORE_COMPLETION_ASSOCIATION_CHANGED")
