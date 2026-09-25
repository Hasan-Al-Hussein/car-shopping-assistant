"""Versioned content of the existing restore marker, with one accepted predecessor.

No second journal, generation change, rollback or partial-marker guess. The
operator verifies actual basis/target files before promoting a prepared update.
"""

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.common import DTO, Digest, Id, Revision, UtcInstant
from app.database.paths import _io_path, _resolved_path
from app.operations.backup_files import (
    MAX_BACKUP_BYTES,
    BackupError,
    BackupManifest,
    _regular_chain,
)
from app.operations.restore_files import (
    MAX_INTENT_BYTES,
    RestoreCandidate,
    RestoreFiles,
    RestoreIntent,
    RestoreReceipt,
    encoded,
)
from app.operations.restore_retention import MAX_SWEEPS, RetentionTransform, summary_digest


def candidate_digest(value: RestoreCandidate) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


class RestoreIntentV2(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["store-restore-2"] = "store-restore-2"
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
    initial_candidate_id: Id
    initial_candidate_sha256: Digest
    initial_semantic_sha256: Digest
    initial_summary_sha256: Digest
    initial_retention: RetentionTransform | None
    revision: Annotated[int, Field(strict=True, ge=0, le=MAX_SWEEPS)] = 0
    previous_marker_sha256: Digest | None = None
    superseded_candidate: RestoreCandidate | None = None
    retention_steps: Annotated[tuple[RetentionTransform, ...], Field(max_length=MAX_SWEEPS)] = ()

    @model_validator(mode="after")
    def bound(self) -> "RestoreIntentV2":
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
            or candidate.recovery_point != selected.recovery_point
            or candidate.new_generation
            in {selected.original_generation, previous.original_generation}
            or len({candidate.candidate_id, selected.backup_id, previous.backup_id}) != 3
            or not selected.recovery_point <= self.started_at < selected.expires_at
            or not previous.recovery_point <= self.started_at < previous.expires_at
            or candidate.prepared_at > self.started_at
            or self.revision != len(self.retention_steps)
            or len(self.retention_steps) + int(self.initial_retention is not None) > MAX_SWEEPS
        ):
            raise ValueError("RESTORE_INTENT_INCOMPATIBLE")
        initial = self.initial_retention
        if initial is None:
            if self.initial_summary_sha256 != summary_digest(selected.records):
                raise ValueError("RESTORE_INITIAL_AUTHORITY_CHANGED")
        elif (
            initial.generation != selected.original_generation
            or initial.before_summary_sha256 != summary_digest(selected.records)
            or initial.after_summary_sha256 != self.initial_summary_sha256
            or initial.protected_expired_leads
            or initial.cutoff != candidate.prepared_at
            or initial.completed_at > self.started_at
        ):
            raise ValueError("RESTORE_INITIAL_RETENTION_INVALID")
        semantic, summary = self.initial_semantic_sha256, self.initial_summary_sha256
        previous_cutoff = self.started_at
        for step in self.retention_steps:
            if (
                step.generation != candidate.new_generation
                or step.protected_expired_leads
                or step.before_semantic_sha256 != semantic
                or step.before_summary_sha256 != summary
                or step.cutoff < previous_cutoff
            ):
                raise ValueError("RESTORE_RETENTION_CHAIN_INVALID")
            semantic, summary = step.after_semantic_sha256, step.after_summary_sha256
            previous_cutoff = step.completed_at
        if semantic != candidate.semantic_sha256 or summary != summary_digest(candidate.records):
            raise ValueError("RESTORE_TARGET_RETENTION_CHANGED")
        prior = self.superseded_candidate
        if self.revision == 0:
            if (
                prior is not None
                or self.previous_marker_sha256 is not None
                or candidate.candidate_id != self.initial_candidate_id
                or candidate_digest(candidate) != self.initial_candidate_sha256
            ):
                raise ValueError("RESTORE_INITIAL_CANDIDATE_CHANGED")
        elif (
            prior is None
            or self.previous_marker_sha256 is None
            or (
                prior.candidate_id == candidate.candidate_id
                or prior.semantic_sha256 != self.retention_steps[-1].before_semantic_sha256
                or summary_digest(prior.records) != self.retention_steps[-1].before_summary_sha256
                or stable_candidate(prior) != stable_candidate(candidate)
            )
        ):
            raise ValueError("RESTORE_PREDECESSOR_CHANGED")
        return self


def stable_candidate(value: RestoreCandidate) -> tuple[object, ...]:
    return (
        value.backup_id,
        value.source_binding,
        value.original_generation,
        value.new_generation,
        value.recovery_point,
        value.prepared_at,
        value.revoked_credentials,
        value.inventory_admission,
        value.viewing_adoption,
    )


class RestoreReceiptV2(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["store-restore-receipt-2"] = "store-restore-receipt-2"
    intent: RestoreIntentV2
    completed_at: UtcInstant
    state: Literal["restored"] = "restored"
    prior_evidence: Literal["held_pending_reconciliation"] = "held_pending_reconciliation"

    @model_validator(mode="after")
    def chronological(self) -> "RestoreReceiptV2":
        if self.completed_at < self.intent.started_at:
            raise ValueError("RESTORE_RECEIPT_CLOCK_INVALID")
        if (
            self.intent.retention_steps
            and self.completed_at < self.intent.retention_steps[-1].completed_at
        ):
            raise ValueError("RESTORE_RECEIPT_CLOCK_INVALID")
        return self


RestoreIntentLike = RestoreIntent | RestoreIntentV2
RestoreReceiptLike = RestoreReceipt | RestoreReceiptV2


def parse_intent(data: bytes) -> RestoreIntentLike:
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("RESTORE_INTENT_INVALID")
    version = payload.get("format")
    if version == "store-restore-1":
        return RestoreIntent.model_validate_json(data)
    if version == "store-restore-2":
        return RestoreIntentV2.model_validate_json(data)
    raise ValueError("RESTORE_INTENT_VERSION_UNSUPPORTED")


def parse_receipt(data: bytes) -> RestoreReceiptLike:
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("RESTORE_RECEIPT_INVALID")
    version = payload.get("format")
    if version == "store-restore-receipt-1":
        return RestoreReceipt.model_validate_json(data)
    if version == "store-restore-receipt-2":
        return RestoreReceiptV2.model_validate_json(data)
    raise ValueError("RESTORE_RECEIPT_VERSION_UNSUPPORTED")


def as_v2(intent: RestoreIntentLike) -> RestoreIntentV2:
    if isinstance(intent, RestoreIntentV2):
        return intent
    data = intent.model_dump(mode="python", exclude={"format"})
    return RestoreIntentV2(
        **data,
        initial_candidate_id=intent.candidate.candidate_id,
        initial_candidate_sha256=candidate_digest(intent.candidate),
        initial_semantic_sha256=intent.candidate.semantic_sha256,
        initial_summary_sha256=summary_digest(intent.candidate.records),
        initial_retention=None,
    )


def root_identity(intent: RestoreIntentLike) -> dict[str, object]:
    return as_v2(intent).model_dump(
        mode="python",
        exclude={
            "candidate",
            "revision",
            "superseded_candidate",
            "retention_steps",
            "previous_marker_sha256",
        },
    )


def assert_successor(old: RestoreIntentLike, revised: RestoreIntentV2) -> None:
    before = as_v2(old)
    if (
        root_identity(before) != root_identity(revised)
        or revised.revision != before.revision + 1
        or revised.previous_marker_sha256 != hashlib.sha256(encoded(old)).hexdigest()
        or revised.superseded_candidate != before.candidate
        or revised.retention_steps[:-1] != before.retention_steps
    ):
        raise BackupError("RESTORE_TRANSITION_ROOT_CHANGED")


def update_path(files: RestoreFiles) -> Path:
    files.lease.assert_held(files.paths.store_path, boundary=files.boundary)
    path = Path(str(files.paths.intent_path) + ".update.tmp")
    _regular_chain(path)
    if _resolved_path(path, strict=False) != path:
        raise BackupError("RESTORE_TRANSITION_PATH_CHANGED")
    return path


def read_update(files: RestoreFiles) -> RestoreIntentV2 | None:
    path = update_path(files)
    if not _io_path(path).exists():
        return None
    if _io_path(path).stat().st_size > MAX_INTENT_BYTES:
        raise BackupError("RESTORE_TRANSITION_INVALID")
    with _io_path(path).open("rb") as source:
        data = source.read(MAX_INTENT_BYTES + 1)
    _regular_chain(path)
    if len(data) > MAX_INTENT_BYTES:
        raise BackupError("RESTORE_TRANSITION_INVALID")
    try:
        value = RestoreIntentV2.model_validate_json(data)
        if (
            encoded(value) != data
            or value.source_binding != files.catalogue.binding
            or value.revision < 1
            or value.previous_marker_sha256 is None
        ):
            raise ValueError("INVALID")
        return value
    except ValueError:
        raise BackupError("RESTORE_TRANSITION_INVALID") from None


def stage_transition(files: RestoreFiles, old: RestoreIntentLike, revised: RestoreIntentV2) -> None:
    assert_successor(old, revised)
    if files.marker() != old:
        raise BackupError("RESTORE_INTENT_CHANGED")
    files.verify_pins(old)
    if (
        _io_path(files.receipt_path(old.restore_id)).exists()
        or _io_path(files.receipt_path(old.restore_id, temporary=True)).exists()
    ):
        raise BackupError("RESTORE_COMPLETED_INTENT_CANNOT_CHANGE")
    path = update_path(files)
    if _io_path(path).exists():
        raise BackupError("RESTORE_TRANSITION_RECOVERY_REQUIRED")
    data = encoded(revised)  # These exact bytes will become the fixed marker.
    with _io_path(path).open("xb") as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())
    if read_update(files) != revised or files.marker() != old:
        raise BackupError("RESTORE_TRANSITION_CHANGED")
    # Caller already verified actual original basis and target before staging.
    os.replace(_io_path(path), _io_path(files.paths.intent_path))
    with _io_path(files.paths.intent_path).open("r+b") as target:
        target.flush()
        os.fsync(target.fileno())
    if files.marker() != revised:
        raise BackupError("RESTORE_TRANSITION_CHANGED")


def settle_transition(
    files: RestoreFiles,
    verify: Callable[[RestoreIntentLike | None, RestoreIntentV2], None],
) -> RestoreIntentLike | None:
    current = files.marker()
    revised = read_update(files)
    if revised is None:
        return current
    if current is None:
        raise BackupError("RESTORE_TRANSITION_WITHOUT_MARKER")
    files.verify_pins(current)
    if (
        _io_path(files.receipt_path(current.restore_id)).exists()
        or _io_path(files.receipt_path(current.restore_id, temporary=True)).exists()
    ):
        raise BackupError("RESTORE_TRANSITION_CONFLICTS_WITH_COMPLETION")
    if current == revised:
        verify(None, revised)
        _io_path(update_path(files)).unlink()  # Only exact guarded duplicate transition bytes.
        return current
    if hashlib.sha256(encoded(current)).hexdigest() != revised.previous_marker_sha256:
        raise BackupError("RESTORE_TRANSITION_PREDECESSOR_CHANGED")
    assert_successor(current, revised)
    verify(current, revised)
    if files.marker() != current or read_update(files) != revised:
        raise BackupError("RESTORE_TRANSITION_CHANGED")
    os.replace(_io_path(update_path(files)), _io_path(files.paths.intent_path))
    with _io_path(files.paths.intent_path).open("r+b") as target:
        target.flush()
        os.fsync(target.fileno())
    if files.marker() != revised:
        raise BackupError("RESTORE_TRANSITION_CHANGED")
    return revised
