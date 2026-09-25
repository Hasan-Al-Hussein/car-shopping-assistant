"""Actual T10 policy on an exclusively leased, uninstalled restore candidate.

No publication, source-backup mutation, TTL renewal or live canonical cleanup.
The operator must verify the copied input before entering this bounded transform.
"""

import hashlib
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, select

from app.api.schemas.common import DTO, Digest, Id, UtcInstant
from app.core.config import DemoPolicy
from app.database.maintenance import MaintenanceLease
from app.database.models import Lead
from app.database.paths import _io_path
from app.database.store import assert_outside_write_transaction, open_store
from app.identity.service import utc_text
from app.operations.backup_files import BackupError, BackupFiles, RecordSummary
from app.operations.backup_restore import summaries
from app.operations.restore_fingerprint import semantic_digest
from app.operations.retention import RetentionService
from app.operations.retention_graph import PROTECTION_REASONS
from app.sessions.state import canonical

MAX_RETENTION_OWNERS = 10_000
RETENTION_SECONDS = 30.0
MAX_SWEEPS = 32
_Count = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]
_Label = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-z_.]{1,80}$")]


class RetentionTransform(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["restore-retention-transform-1"] = "restore-retention-transform-1"
    generation: Id
    cutoff: UtcInstant
    completed_at: UtcInstant
    policy_sha256: Digest
    source_sha256: Digest
    before_semantic_sha256: Digest
    after_semantic_sha256: Digest
    before_summary_sha256: Digest
    after_summary_sha256: Digest
    owners_inspected: Annotated[int, Field(strict=True, ge=0, le=MAX_RETENTION_OWNERS)]
    changes: Annotated[tuple[tuple[_Label, _Count], ...], Field(max_length=64)]
    protected_expired_leads: Annotated[int, Field(strict=True, ge=0, le=10_000)]
    protected_reasons: Annotated[tuple[tuple[_Label, _Count], ...], Field(max_length=10)]
    complete: Literal[True] = True

    @model_validator(mode="after")
    def coherent(self) -> "RetentionTransform":
        if self.completed_at < self.cutoff:
            raise ValueError("RESTORE_RETENTION_CLOCK_INVALID")
        for counts in (self.changes, self.protected_reasons):
            if tuple(sorted(counts)) != counts or len({key for key, _ in counts}) != len(counts):
                raise ValueError("RESTORE_RETENTION_COUNTS_INVALID")
        if any(
            key not in PROTECTION_REASONS or count > self.protected_expired_leads
            for key, count in self.protected_reasons
        ):
            raise ValueError("RESTORE_RETENTION_REASONS_INVALID")
        if bool(self.protected_expired_leads) != bool(self.protected_reasons):
            raise ValueError("RESTORE_RETENTION_REASONS_INVALID")
        return self


class ProtectedRetentionError(BackupError):
    """Only materialized reason counts escape; no original keys/contact fields."""

    def __init__(self, transform: RetentionTransform) -> None:
        super().__init__("RESTORE_RETENTION_PROTECTED_EXPIRED_LEADS")
        self.expired_leads = transform.protected_expired_leads
        self.reasons = transform.protected_reasons
        self.restore_id: str | None = None


def require_exportable(transform: RetentionTransform) -> None:
    if transform.protected_expired_leads:
        raise ProtectedRetentionError(transform)


def summary_digest(records: tuple[RecordSummary, ...]) -> str:
    return hashlib.sha256(canonical([row.model_dump(mode="json") for row in records])).hexdigest()


def _instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise BackupError("RESTORE_RETENTION_CLOCK_INVALID")
    return utc_text(value)


def _policy_sources() -> str:
    # Read operator code outside every Store callback. Hashes are provenance,
    # never a substitute for actually running the policy or holding the lease.
    from app.operations import retention, retention_graph

    hashes: dict[str, str] = {}
    for module in (retention, retention_graph):
        module_file = module.__file__
        if module_file is None:
            raise BackupError("RESTORE_RETENTION_SOURCE_UNAVAILABLE")
        location = Path(module_file)
        with location.open("rb") as source:
            data = source.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise BackupError("RESTORE_RETENTION_SOURCE_LIMIT")
        hashes[module.__name__] = hashlib.sha256(data).hexdigest()
    return hashlib.sha256(canonical(hashes)).hexdigest()


def reconcile_candidate(
    files: BackupFiles,
    candidate_id: str,
    *,
    lease: MaintenanceLease,
    expected_generation: str,
    expected_semantic_sha256: str,
    expected_summary_sha256: str,
    cutoff: datetime,
    clock: Callable[[], datetime] | None = None,
    policy: DemoPolicy | None = None,
) -> RetentionTransform:
    assert_outside_write_transaction()
    path = files.path(candidate_id, "sqlite3")
    if path == files.source:
        raise BackupError("RESTORE_RETENTION_REQUIRES_ISOLATED_CANDIDATE")
    lease.assert_held(path, boundary=files.boundary)
    if any(
        _io_path(files.path(candidate_id, suffix)).exists()
        for suffix in (
            "manifest.json",
            "manifest.tmp",
            "pin.json",
            "expiry.json",
            "expiry.tmp",
        )
    ):
        raise BackupError("RESTORE_RETENTION_CANDIDATE_ALREADY_EVIDENCE")
    stamp = _instant(cutoff)
    trusted_clock = clock or (lambda: datetime.now(UTC))
    began = time.monotonic()
    last_wall = cutoff

    def budget() -> str:
        nonlocal last_wall
        lease.assert_held(path, boundary=files.boundary)
        now = trusted_clock()
        text = _instant(now)
        if not last_wall <= now <= cutoff + timedelta(minutes=5):
            raise BackupError("RESTORE_RETENTION_CLOCK_INVALID")
        last_wall = now
        if time.monotonic() - began > RETENTION_SECONDS:
            raise BackupError("RESTORE_RETENTION_TIME_LIMIT")
        return text

    budget()
    candidate = open_store(path, boundary=files.boundary)
    if candidate.generation != expected_generation:
        raise BackupError("RESTORE_RETENTION_GENERATION_CHANGED")
    before_semantic = candidate.read(semantic_digest)
    before_summary = summary_digest(candidate.read(summaries))
    if (before_semantic, before_summary) != (expected_semantic_sha256, expected_summary_sha256):
        raise BackupError("RESTORE_RETENTION_CANDIDATE_CHANGED")
    supplied = DemoPolicy() if policy is None else policy
    adopted = DemoPolicy.model_validate(supplied.model_dump(mode="python"))
    sources = _policy_sources()
    service = RetentionService(candidate, policy=adopted, clock=lambda: cutoff)
    cursor: str | None = None
    owner_count, protected = 0, 0
    changes: dict[str, int] = {}
    reasons: dict[str, int] = {}
    while True:
        budget()
        observed = service.inspect(after_owner_id=cursor)
        if observed.owner_id is not None:
            if owner_count >= MAX_RETENTION_OWNERS or (
                cursor is not None and observed.owner_id <= cursor
            ):
                raise BackupError("RESTORE_RETENTION_OWNER_LIMIT")
            owner_count += 1
        committed = service._commit(observed)
        for key, count in committed.changes:
            changes[key] = changes.get(key, 0) + count
        protected += committed.protected_expired_leads
        for key, count in committed.protected_expired_reasons:
            reasons[key] = reasons.get(key, 0) + count
        budget()
        if observed.next_after_owner_id is None:
            break
        if observed.owner_id != observed.next_after_owner_id:
            raise BackupError("RESTORE_RETENTION_CURSOR_INVALID")
        cursor = observed.next_after_owner_id
    expired = (
        candidate.read(
            lambda db: db.scalar(
                select(func.count()).select_from(Lead).where(Lead.expires_at <= stamp)
            )
        )
        or 0
    )
    if expired != protected:
        raise BackupError("RESTORE_RETENTION_SWEEP_INCOMPLETE")
    after_semantic = candidate.read(semantic_digest)
    after_summary = summary_digest(candidate.read(summaries))
    completed_at = budget()
    return RetentionTransform(
        generation=expected_generation,
        cutoff=stamp,
        completed_at=completed_at,
        policy_sha256=hashlib.sha256(canonical(adopted.model_dump(mode="json"))).hexdigest(),
        source_sha256=sources,
        before_semantic_sha256=before_semantic,
        after_semantic_sha256=after_semantic,
        before_summary_sha256=before_summary,
        after_summary_sha256=after_summary,
        owners_inspected=owner_count,
        changes=tuple(sorted(changes.items())),
        protected_expired_leads=protected,
        protected_reasons=tuple(sorted(reasons.items())),
    )
