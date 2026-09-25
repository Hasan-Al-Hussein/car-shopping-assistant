"""Strict durable restore identity and pins; no implicit repair or Store swap."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.common import DTO, Digest, Id, Revision, UtcInstant
from app.database.maintenance import MaintenanceLease, maintenance_paths
from app.database.paths import RuntimeBoundary, _io_path, _resolved_path, guarded_store_path
from app.operations.backup_files import (
    MAX_BACKUP_BYTES,
    BackupError,
    BackupFiles,
    BackupManifest,
    RecordSummary,
    _regular_chain,
    manifest_bytes,
)
from app.sessions.state import canonical

if TYPE_CHECKING:
    from app.operations.restore_transition import RestoreIntentLike, RestoreReceiptLike

MAX_INTENT_BYTES = 64 * 1024


class RestoreCandidate(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    candidate_id: Id
    backup_id: Id
    source_binding: Digest
    original_generation: Id
    new_generation: Id
    recovery_point: UtcInstant
    prepared_at: UtcInstant
    database_sha256: Digest
    database_bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_BACKUP_BYTES)]
    semantic_sha256: Digest
    records: Annotated[tuple[RecordSummary, ...], Field(min_length=11, max_length=11)]
    revoked_credentials: Annotated[int, Field(strict=True, ge=0, le=10_000)]
    canonical_projection_version: Revision
    inventory_admission: Literal["required"] = "required"
    viewing_adoption: Literal["required"] = "required"


class RestoreIntent(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["store-restore-1"] = "store-restore-1"
    restore_id: Id
    source_binding: Digest
    started_at: UtcInstant
    previous: BackupManifest
    selected: BackupManifest
    candidate: RestoreCandidate
    canonical_before_sha256: Digest
    canonical_before_bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_BACKUP_BYTES)]
    previous_projection_version: Revision
    absent_post_backup_authority: Literal["unknown"] = "unknown"

    @model_validator(mode="after")
    def bound(self) -> RestoreIntent:
        candidate, selected, previous = self.candidate, self.selected, self.previous
        if (
            {
                self.source_binding,
                selected.source_binding,
                previous.source_binding,
                candidate.source_binding,
            }
            != {self.source_binding}
            or candidate.backup_id != selected.backup_id
            or candidate.original_generation != selected.original_generation
            or candidate.records != selected.records
            or candidate.recovery_point != selected.recovery_point
            or candidate.new_generation
            in {selected.original_generation, previous.original_generation}
            or len({candidate.candidate_id, selected.backup_id, previous.backup_id}) != 3
            or not selected.recovery_point <= self.started_at < selected.expires_at
            or not previous.recovery_point <= self.started_at < previous.expires_at
            or candidate.prepared_at > self.started_at
        ):
            raise ValueError("RESTORE_INTENT_INCOMPATIBLE")
        return self


class RestoreReceipt(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["store-restore-receipt-1"] = "store-restore-receipt-1"
    intent: RestoreIntent
    completed_at: UtcInstant
    state: Literal["restored"] = "restored"
    prior_evidence: Literal["held_pending_reconciliation"] = "held_pending_reconciliation"

    @model_validator(mode="after")
    def after_start(self) -> RestoreReceipt:
        if self.completed_at < self.intent.started_at:
            raise ValueError("RESTORE_RECEIPT_CLOCK_INVALID")
        return self


def encoded(value: DTO) -> bytes:
    data = canonical(value.model_dump(mode="json")) + b"\n"
    if len(data) > MAX_INTENT_BYTES:
        raise BackupError("RESTORE_RECORD_SIZE_LIMIT")
    return data


def digest_store(path: Path, *, boundary: RuntimeBoundary) -> tuple[str, int]:
    """Only a closed, quiescent canonical file or isolated owned candidate."""
    source = guarded_store_path(path, boundary=boundary, must_exist=True)
    size = _io_path(source).stat().st_size
    if not 0 < size <= MAX_BACKUP_BYTES:
        raise BackupError("RESTORE_DATABASE_SIZE_LIMIT")
    digest, actual = hashlib.sha256(), 0
    with _io_path(source).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            actual += len(block)
            if actual > MAX_BACKUP_BYTES:
                raise BackupError("RESTORE_DATABASE_SIZE_LIMIT")
            digest.update(block)
    guarded_store_path(path, boundary=boundary, must_exist=True)
    if size != actual or _io_path(source).stat().st_size != size:
        raise BackupError("RESTORE_DATABASE_CHANGED")
    return digest.hexdigest(), size


class RestoreFiles:
    def __init__(self, path: Path, *, boundary: RuntimeBoundary, lease: MaintenanceLease) -> None:
        self.boundary, self.lease = boundary, lease
        self.paths = maintenance_paths(path, boundary=boundary, must_exist=False)
        self.catalogue = BackupFiles.for_store_path(path, boundary=boundary, must_exist=False)
        self._held()

    def _held(self) -> None:
        self.lease.assert_held(self.paths.store_path, boundary=self.boundary)
        if (
            maintenance_paths(self.paths.store_path, boundary=self.boundary, must_exist=False)
            != self.paths
        ):
            raise BackupError("RESTORE_PATH_CHANGED")

    def marker(self) -> RestoreIntentLike | None:
        from app.operations.restore_transition import parse_intent

        self._held()
        path = self.paths.intent_path
        if not _io_path(path).exists():
            return None
        data = self._read(path)
        try:
            intent = parse_intent(data)
            if encoded(intent) != data or intent.source_binding != self.catalogue.binding:
                raise ValueError("INCOMPATIBLE")
            return intent
        except ValueError:
            raise BackupError("RESTORE_INTENT_INVALID") from None

    def _read(self, path: Path) -> bytes:
        _regular_chain(path)
        if _io_path(path).stat().st_size > MAX_INTENT_BYTES:
            raise BackupError("RESTORE_RECORD_SIZE_LIMIT")
        with _io_path(path).open("rb") as source:
            data = source.read(MAX_INTENT_BYTES + 1)
        if len(data) > MAX_INTENT_BYTES:
            raise BackupError("RESTORE_RECORD_SIZE_LIMIT")
        return data

    def _pin_bytes(self, intent: RestoreIntentLike, manifest: BackupManifest) -> bytes:
        return (
            canonical(
                {
                    "format": "store-restore-pin-1",
                    "restore_id": intent.restore_id,
                    "source_binding": intent.source_binding,
                    "started_at": intent.started_at,
                    "manifest_sha256": hashlib.sha256(manifest_bytes(manifest)).hexdigest(),
                }
            )
            + b"\n"
        )

    def begin(self, intent: RestoreIntentLike) -> None:
        """Caller holds catalogue lock; complete pins precede the fixed marker.

        A partial marker deliberately blocks ordinary admission and is never
        guessed or erased. Incomplete pre-marker pins remain conservatively held.
        """
        self._held()
        from app.operations.restore_transition import update_path

        if _io_path(update_path(self)).exists():
            raise BackupError("RESTORE_TRANSITION_RECOVERY_REQUIRED")
        if self.marker() is not None or intent.source_binding != self.catalogue.binding:
            raise BackupError("RESTORE_ALREADY_PENDING")
        for manifest in (intent.previous, intent.selected):
            if self.catalogue.manifest(manifest.backup_id) != manifest:
                raise BackupError("RESTORE_BACKUP_CHANGED")
            path = self.catalogue.path(manifest.backup_id, "pin.json")
            with _io_path(path).open("xb") as output:
                output.write(self._pin_bytes(intent, manifest))
                output.flush()
                os.fsync(output.fileno())
        with _io_path(self.paths.intent_path).open("xb") as output:
            output.write(encoded(intent))
            output.flush()
            os.fsync(output.fileno())
        if self.marker() != intent:
            raise BackupError("RESTORE_INTENT_CHANGED")

    def verify_pins(self, intent: RestoreIntentLike) -> None:
        self._held()
        for manifest in (intent.previous, intent.selected):
            if (
                self.catalogue.manifest(manifest.backup_id) != manifest
                or self.catalogue.digest(manifest.backup_id)
                != (manifest.database_sha256, manifest.database_bytes)
                or self._read(self.catalogue.path(manifest.backup_id, "pin.json"))
                != self._pin_bytes(intent, manifest)
            ):
                raise BackupError("RESTORE_RECOVERY_EVIDENCE_CHANGED")

    def receipt_path(self, restore_id: str, *, temporary: bool = False) -> Path:
        # Pydantic's Id is validated before this callable by every public route.
        from pydantic import TypeAdapter

        from app.api.schemas.common import Id

        restore_id = TypeAdapter(Id).validate_python(restore_id)
        suffix = "tmp" if temporary else "json"
        path = self.catalogue.directory() / f"restore.{restore_id}.receipt.{suffix}"
        _regular_chain(path)
        if _resolved_path(path, strict=False) != path:
            raise BackupError("RESTORE_RECEIPT_PATH_CHANGED")
        return path

    def receipt(self, restore_id: str) -> RestoreReceiptLike | None:
        from app.operations.restore_transition import parse_receipt

        self._held()
        path = self.receipt_path(restore_id)
        if not _io_path(path).exists():
            return None
        data = self._read(path)
        try:
            value = parse_receipt(data)
            if (
                encoded(value) != data
                or value.intent.restore_id != restore_id
                or value.intent.source_binding != self.catalogue.binding
            ):
                raise ValueError("INCOMPATIBLE")
            return value
        except ValueError:
            raise BackupError("RESTORE_RECEIPT_INVALID") from None

    def finish(self, value: RestoreReceiptLike) -> None:
        """Caller has reverified canonical/CSV state and holds both physical locks.

        Keep prior evidence pinned until a separate explicit reconciliation is
        proven. Completion releases only the selected source-backup pin; a failure
        after marker removal can only leave an extra selected-source pin.
        """
        self._held()
        from app.operations.restore_transition import parse_receipt, update_path

        if _io_path(update_path(self)).exists():
            raise BackupError("RESTORE_TRANSITION_RECOVERY_REQUIRED")
        intent = value.intent
        if self.marker() != intent:
            raise BackupError("RESTORE_INTENT_CHANGED")
        self.verify_pins(intent)
        final = self.receipt_path(intent.restore_id)
        old = self.receipt(intent.restore_id)
        if old is None:
            temporary = self.receipt_path(intent.restore_id, temporary=True)
            if _io_path(temporary).exists():
                # Only the exact completed receipt can recover its fsync/rename gap.
                try:
                    retained = parse_receipt(self._read(temporary))
                except ValueError:
                    raise BackupError("RESTORE_RECEIPT_INVALID") from None
                if (
                    encoded(retained) != self._read(temporary)
                    or retained.intent != intent
                    or retained.state != value.state
                ):
                    raise BackupError("RESTORE_RECEIPT_CHANGED")
                value = retained
            else:
                with _io_path(temporary).open("xb") as output:
                    output.write(encoded(value))
                    output.flush()
                    os.fsync(output.fileno())
            os.rename(_io_path(temporary), _io_path(final))
        elif old.intent != intent or old.state != value.state:
            raise BackupError("RESTORE_RECEIPT_CHANGED")
        completed = self.receipt(intent.restore_id)
        if completed is None:
            raise BackupError("RESTORE_RECEIPT_MISSING")
        duplicate = self.receipt_path(intent.restore_id, temporary=True)
        if _io_path(duplicate).exists():
            if self._read(duplicate) != encoded(completed):
                raise BackupError("RESTORE_RECEIPT_CHANGED")
            _io_path(duplicate).unlink()
        _io_path(self.paths.intent_path).unlink()
        self.release_completed_pins(intent.restore_id)

    def completed_record(self, intent: RestoreIntentLike) -> RestoreReceiptLike | None:
        """Exact final or complete fsynced temporary freezes the recorded operation.

        An unknown/partial temporary is preserved and closes recovery. A final and
        temporary pair must be byte-identical; finish alone removes an exact copy.
        """
        from app.operations.restore_transition import parse_receipt

        self._held()
        final = self.receipt(intent.restore_id)
        temporary = self.receipt_path(intent.restore_id, temporary=True)
        staged = None
        if _io_path(temporary).exists():
            data = self._read(temporary)
            try:
                staged = parse_receipt(data)
                if (
                    encoded(staged) != data
                    or staged.intent != intent
                    or staged.intent.source_binding != self.catalogue.binding
                ):
                    raise ValueError("INCOMPATIBLE")
            except ValueError:
                raise BackupError("RESTORE_RECEIPT_INVALID") from None
        if (final is not None and final.intent != intent) or (
            final is not None and staged is not None and final != staged
        ):
            raise BackupError("RESTORE_RECEIPT_CHANGED")
        return final if final is not None else staged

    def release_completed_pins(self, restore_id: str) -> RestoreReceiptLike:
        """Release only the source pin after completion; prior evidence stays held.

        CSV/data restore completion is not reconciliation of an absent later
        command or revocation. No automatic expiry of that sole evidence is allowed.
        """
        self._held()
        from app.operations.restore_transition import update_path

        if _io_path(update_path(self)).exists():
            raise BackupError("RESTORE_TRANSITION_RECOVERY_REQUIRED")
        if self.marker() is not None:
            raise BackupError("RESTORE_STILL_PENDING")
        value = self.receipt(restore_id)
        if value is None:
            raise BackupError("RESTORE_RECEIPT_MISSING")
        for manifest in (value.intent.selected,):
            path = self.catalogue.path(manifest.backup_id, "pin.json")
            if _io_path(path).exists():
                if self._read(path) != self._pin_bytes(value.intent, manifest):
                    raise BackupError("RESTORE_PIN_CHANGED")
                _io_path(path).unlink()
        return value
