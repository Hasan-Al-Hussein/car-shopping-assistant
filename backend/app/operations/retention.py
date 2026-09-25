"""Explicit bounded local retention: inspect, recheck and commit one owner graph.

No startup hook, background scheduler, browser endpoint or arbitrary deletion path.
Derived publication is separate and cannot roll back or misreport canonical cleanup.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DemoPolicy
from app.core.errors import ApiFailure
from app.database.models import ExportState, Lead, LeadBooking, Owner
from app.database.store import Store, StoreError, assert_outside_write_transaction
from app.identity.service import utc_text
from app.leads import projection_repository as projection
from app.leads.projection import CsvProjector, ProjectionRun
from app.operations.retention_graph import (
    MAX_REVISION, OwnerWork, RetentionError, apply_owner, graph_digest, payload, plan_owner,
)
from app.sessions.repository import valid_id
from app.sessions.state import fingerprint


@dataclass(frozen=True)
class RetentionInspection:
    generation: str
    cutoff: str
    owner_id: str | None
    scope_after_owner_id: str | None
    next_after_owner_id: str | None
    digest: str
    changes: tuple[tuple[str, int], ...]
    protected_records: int
    unresolved_authorities: int
    expired_leads_present: bool
    export_reconciliation: bool
    protected_expired_leads: int = 0
    protected_expired_reasons: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class RetentionCommit:
    generation: str
    cutoff: str
    owner_id: str | None
    changes: tuple[tuple[str, int], ...]
    changed: bool
    export_reconciliation: bool
    canonical_version: int | None
    protected_expired_leads: int = 0
    protected_expired_reasons: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class RetentionRun:
    canonical: RetentionCommit
    publication: ProjectionRun | None
    derived_state: Literal["not_needed", "current", "pending", "failed"]
    code: str | None = None


@dataclass
class _Prepared:
    inspection: RetentionInspection
    work: OwnerWork | None
    export_state: ExportState | None
    advance_export: bool
    export_status_change: bool


class RetentionService:
    def __init__(
        self, store: Store, *, policy: DemoPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        supplied = DemoPolicy() if policy is None else policy
        self.policy = DemoPolicy.model_validate(supplied.model_dump(mode="python"))
        self.clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> str:
        instant = self.clock()
        if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
            raise RetentionError("RETENTION_CLOCK_INVALID")
        return utc_text(instant)

    def _prepare(
        self, db: Session, *, cutoff: str, owner_id: str | None, after_owner_id: str | None,
    ) -> _Prepared:
        current = projection.state(db, self.store.generation)
        if current is not None and current.updated_at > cutoff:
            raise RetentionError("RETENTION_CLOCK_BEFORE_STATE")
        query = select(Owner).order_by(Owner.id)
        if owner_id is not None:
            query = query.where(Owner.id == valid_id(owner_id))
        elif after_owner_id is not None:
            query = query.where(Owner.id > valid_id(after_owner_id))
        owners = list(db.scalars(query.limit(2)))
        owner = owners[0] if owners else None
        try:
            work = None if owner is None else plan_owner(db, owner, cutoff)
        except (ApiFailure, TypeError, ValueError, AttributeError) as exc:
            if isinstance(exc, RetentionError):
                raise
            raise RetentionError("RETENTION_PROTECTION_INVALID") from None
        expired = db.scalar(select(Lead.id).where(Lead.expires_at <= cutoff).limit(1)) is not None
        canonical_change = work is not None and any(work.remove.get(model) for model in (Lead, LeadBooking))
        reconcile = bool(canonical_change or expired or current is not None and current.state != "current")
        if reconcile and current is None:
            raise RetentionError("RETENTION_EXPORT_METADATA_REQUIRED")
        advance = bool(canonical_change or expired and current is not None and current.state == "current")
        if advance and current is not None and current.canonical_version >= MAX_REVISION:
            raise RetentionError("RETENTION_EXPORT_VERSION_EXHAUSTED")
        export_change = bool(reconcile and current is not None and (advance or current.state == "current"))
        changes = () if work is None else work.counts()
        if export_change:
            changes = tuple(sorted((*changes, ("update.export_state", 1))))
        state = None if current is None else payload(current)
        base_digest = fingerprint({"owner": owner_id, "export_state": state}) if work is None else graph_digest(work, state)
        inspection = RetentionInspection(
            self.store.generation, cutoff, owner_id if owner is None else owner.id, after_owner_id,
            owner.id if owner is not None and len(owners) > 1 else None,
            fingerprint({"graph": base_digest, "expired": expired, "cutoff": cutoff}),
            changes, 0 if work is None else work.protected, 0 if work is None else work.unresolved,
            expired, reconcile,
            0 if work is None else work.protected_expired_leads,
            () if work is None else work.protected_expired_reasons,
        )
        return _Prepared(inspection, work, current, advance, export_change)

    def inspect(
        self, *, owner_id: str | None = None, after_owner_id: str | None = None,
    ) -> RetentionInspection:
        """Read-only, one complete bounded owner graph; explicit cursor for the next owner."""
        assert_outside_write_transaction()
        if owner_id is not None and after_owner_id is not None:
            raise RetentionError("RETENTION_SCOPE_CONFLICT")
        try:
            if owner_id is not None:
                owner_id = valid_id(owner_id)
            if after_owner_id is not None:
                after_owner_id = valid_id(after_owner_id)
        except ApiFailure:
            raise RetentionError("RETENTION_SCOPE_INVALID") from None
        cutoff = self._now()
        return self.store.read(lambda db: self._prepare(
            db, cutoff=cutoff, owner_id=owner_id, after_owner_id=after_owner_id,
        ).inspection)

    def _commit(self, observed: RetentionInspection) -> RetentionCommit:
        """Canonical half only; tests must not mistake this for derived-file compliance."""
        assert_outside_write_transaction()
        now = self._now()
        if type(observed) is not RetentionInspection or observed.generation != self.store.generation:
            raise RetentionError("RETENTION_GENERATION_CHANGED")
        if not datetime.fromisoformat(now) - timedelta(minutes=5) <= datetime.fromisoformat(observed.cutoff) <= datetime.fromisoformat(now):
            raise RetentionError("RETENTION_INSPECTION_EXPIRED")

        def write(db: Session) -> RetentionCommit:
            fresh = self._prepare(
                db, cutoff=observed.cutoff, owner_id=observed.owner_id,
                after_owner_id=observed.scope_after_owner_id if observed.owner_id is None else None,
            )
            if (fresh.inspection.digest != observed.digest
                    or fresh.inspection.export_reconciliation != observed.export_reconciliation
                    or fresh.inspection.protected_expired_leads != observed.protected_expired_leads
                    or fresh.inspection.protected_expired_reasons != observed.protected_expired_reasons):
                raise RetentionError("RETENTION_INSPECTION_CHANGED")
            if fresh.work is not None:
                apply_owner(db, fresh.work)
            state = fresh.export_state
            if fresh.export_status_change:
                assert state is not None
                if fresh.advance_export:
                    state.canonical_version += 1
                state.state, state.updated_at = "pending", now
            # The global pending version is the durable regeneration intent after
            # deletion, including the last lead. No synthetic lead/outbox FK.
            return RetentionCommit(
                self.store.generation, observed.cutoff, observed.owner_id,
                fresh.inspection.changes, bool(fresh.inspection.changes),
                fresh.inspection.export_reconciliation,
                None if state is None else state.canonical_version,
                fresh.inspection.protected_expired_leads,
                fresh.inspection.protected_expired_reasons,
            )

        return self.store.write(write)

    def apply(self, observed: RetentionInspection) -> RetentionRun:
        """Explicit operator apply. The publication lock precedes canonical cleanup."""
        from app.operations.retention_exports import withdraw_expired
        from app.leads.projection_files import ProjectionFiles

        assert_outside_write_transaction()
        if not observed.export_reconciliation:
            return RetentionRun(self._commit(observed), None, "not_needed")
        files = ProjectionFiles(self.store)
        # Ownership validation and all file work are outside the Store WRITE.
        # A busy/invalid lock fails before any canonical mutation.
        with files.lock():
            files.inspect_existing(
                generation=self.store.generation,
                version=self.store.read(lambda db: self._export_version(db)),
                reconcile_from_generation=None,
            )
            committed = self._commit(observed)
            try:
                withdraw_expired(files, generation=self.store.generation, version=committed.canonical_version)
            except (OSError, ValueError, StoreError):
                self._mark_failed(committed.canonical_version)
                return RetentionRun(committed, None, "failed", "RETENTION_CSV_WITHDRAWAL_FAILED")
        publication = CsvProjector(self.store, clock=self.clock).repair_once()
        state: Literal["current", "pending", "failed"] = (
            "current" if publication.state in {"current", "empty"}
            else "failed" if publication.state == "failed" else "pending"
        )
        return RetentionRun(committed, publication, state, publication.code)

    def _export_version(self, db: Session) -> int:
        state = projection.state(db, self.store.generation)
        return 0 if state is None else state.canonical_version

    def _mark_failed(self, version: int | None) -> None:
        try:
            self.store.write(lambda db: projection.failed(db, self.store.generation, version, self._now()))
        except (StoreError, projection.ProjectionError):
            # Caller still reports failed, never DB-current or a rolled-back cleanup.
            pass
