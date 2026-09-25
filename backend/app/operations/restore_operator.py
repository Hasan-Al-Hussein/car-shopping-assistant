"""Explicit, fail-closed restore under actual publication and maintenance locks.

No app shutdown flag substitutes for quiescence. The marker survives any uncertain
step; only verified completion reopens normal admission.
"""

import hashlib
import os
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.common import Id
from app.database.maintenance import exclusive_store_lease
from app.database.models import ActiveInventory, ActiveRules, OwnerCredential, StoreMetadata
from app.database.paths import (
    COMPANIONS,
    RuntimeBoundary,
    StorePathError,
    _io_path,
    guarded_store_path,
)
from app.database.store import Store, StoreError, assert_outside_write_transaction, open_store
from app.identity.service import utc_text
from app.leads import projection_repository as projection
from app.leads.projection import CsvProjector
from app.leads.projection_files import ProjectionFiles
from app.operations.backup_files import MAX_CATALOGUE_BYTES, MAX_CATALOGUE_ENTRIES, BackupError
from app.operations.backup_restore import BackupService, summaries
from app.operations.restore_files import (
    RestoreCandidate,
    RestoreFiles,
    RestoreReceipt,
    digest_store,
    encoded,
)
from app.operations.restore_fingerprint import semantic_digest
from app.operations.restore_observation import (
    RestoreObservation,
    observe_current,
    withdraw_projection,
)
from app.operations.restore_retention import MAX_SWEEPS, ProtectedRetentionError, summary_digest
from app.operations.restore_state import prepare_candidate, prepare_reconciled_candidate
from app.operations.restore_transition import (
    RestoreIntentLike,
    RestoreIntentV2,
    RestoreReceiptLike,
    RestoreReceiptV2,
    as_v2,
    candidate_digest,
    settle_transition,
    stage_transition,
    update_path,
)

_ID = TypeAdapter(Id)


class RestoreService:
    def __init__(
        self, path: Path, *, boundary: RuntimeBoundary, clock: Callable[[], datetime] | None = None
    ) -> None:
        self.path, self.boundary = path, boundary
        self.clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> str:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise BackupError("RESTORE_CLOCK_INVALID")
        return utc_text(value)

    def restore(self, backup_id: str, *, expected_generation: str) -> RestoreReceiptLike:
        """Explicit apply only. A running app rejects before backup or marker writes."""
        assert_outside_write_transaction()
        backup_id, expected_generation = (
            _ID.validate_python(backup_id),
            _ID.validate_python(expected_generation),
        )
        publication = ProjectionFiles.for_store_path(self.path, boundary=self.boundary)
        with publication.lock(), exclusive_store_lease(self.path, boundary=self.boundary) as lease:
            files = RestoreFiles(self.path, boundary=self.boundary, lease=lease)
            if files.marker() is not None or _io_path(update_path(files)).exists():
                raise BackupError("RESTORE_RECOVERY_REQUIRED")
            current = open_store(self.path, boundary=self.boundary)
            if current.generation != expected_generation:
                raise BackupError("RESTORE_EXPECTED_GENERATION_CHANGED")
            version = current.read(lambda db: self._version(db, current.generation))
            publication.inspect_existing(
                generation=current.generation, version=version, reconcile_from_generation=None
            )
            service = BackupService(current, clock=self.clock)
            # Validate requested source before preserving another backup or candidate.
            selected = service.inspect(backup_id)
            if selected.state != "available":
                raise BackupError("RESTORE_BACKUP_EXPIRED_OR_FUTURE")
            previous = service.create()
            prepared = prepare_candidate(
                service.files, backup_id, now=self.clock(), clock=self.clock
            )
            before_digest, before_size = digest_store(self.path, boundary=self.boundary)
            material = asdict(prepared)
            material.pop("retention")
            candidate = RestoreCandidate.model_validate(material)
            intent = RestoreIntentV2(
                restore_id=str(uuid4()),
                source_binding=files.catalogue.binding,
                started_at=self._now(),
                previous=previous,
                selected=selected.manifest,
                candidate=candidate,
                canonical_before_sha256=before_digest,
                canonical_before_bytes=before_size,
                previous_projection_version=version,
                initial_candidate_id=candidate.candidate_id,
                initial_candidate_sha256=candidate_digest(candidate),
                initial_semantic_sha256=candidate.semantic_sha256,
                initial_summary_sha256=summary_digest(candidate.records),
                initial_retention=prepared.retention,
            )
            with files.catalogue.lock():
                entries, occupied = files.catalogue.usage()
                if (
                    entries + 5 > MAX_CATALOGUE_ENTRIES
                    or occupied + 256 * 1024 > MAX_CATALOGUE_BYTES
                ):
                    raise BackupError("RESTORE_RECORD_QUOTA")
                self._original(current, intent)
                self._candidate(files, intent)
                publication.assert_locked()
                lease.assert_held(self.path, boundary=self.boundary)
                files.begin(intent)
                return self._continue(files, publication, intent).receipt

    def restore_observed(self, backup_id: str, *, expected_generation: str) -> RestoreObservation:
        """Apply, then independently observe; the receipt does not promise current CSV."""
        receipt = self.restore(backup_id, expected_generation=expected_generation)
        return self.resume_observed(restore_id=receipt.intent.restore_id)

    def resume(self, *, restore_id: str | None = None) -> RestoreReceiptLike:
        """Compatibility receipt API. Use resume_observed for present readiness."""
        return self.resume_observed(restore_id=restore_id).receipt

    def resume_observed(self, *, restore_id: str | None = None) -> RestoreObservation:
        """Reconcile the original operation, separating historical/current evidence."""
        assert_outside_write_transaction()
        if restore_id is not None:
            restore_id = _ID.validate_python(restore_id)
        publication = ProjectionFiles.for_store_path(
            self.path, boundary=self.boundary, must_exist=False
        )
        with (
            publication.lock(),
            exclusive_store_lease(
                self.path,
                boundary=self.boundary,
                must_exist=False,
            ) as lease,
        ):
            files = RestoreFiles(self.path, boundary=self.boundary, lease=lease)
            with files.catalogue.lock():
                pending = files.marker()
                if (
                    pending is not None
                    and restore_id is not None
                    and pending.restore_id != restore_id
                ):
                    raise BackupError("RESTORE_ID_CHANGED")
                # A complete update is promoted only after actual basis/target checks.
                intent = settle_transition(
                    files, lambda old, new: self._transition_basis(files, old, new)
                )
                if intent is None:
                    if restore_id is None:
                        raise BackupError("RESTORE_INTENT_MISSING")
                    receipt = files.release_completed_pins(restore_id)
                    # Finish exact selected-pin bookkeeping after a receipt/marker
                    # crash gap; neither pin nor selected backup must still exist.
                    # Historical replay does not restore frozen business state.
                    return self._observe(files, publication, receipt)
                if restore_id is not None and intent.restore_id != restore_id:
                    raise BackupError("RESTORE_ID_CHANGED")
                return self._continue(files, publication, intent)

    def inspect(self) -> RestoreIntentLike | None:
        """Read the strict pending marker under actual operator exclusion."""
        assert_outside_write_transaction()
        publication = ProjectionFiles.for_store_path(
            self.path, boundary=self.boundary, must_exist=False
        )
        with (
            publication.lock(),
            exclusive_store_lease(
                self.path,
                boundary=self.boundary,
                must_exist=False,
            ) as lease,
        ):
            return RestoreFiles(self.path, boundary=self.boundary, lease=lease).marker()

    @staticmethod
    def _version(db: Session, generation: str) -> int:
        state = projection.state(db, generation)
        return 0 if state is None else state.canonical_version

    def _original(self, store: Store, intent: RestoreIntentLike) -> None:
        if (
            store.generation != intent.previous.original_generation
            or store.schema_version != intent.previous.schema_version
            or store.inventory_mode != intent.previous.inventory_mode
            or store.read(summaries) != intent.previous.records
            or store.read(lambda db: self._version(db, store.generation))
            != intent.previous_projection_version
            or digest_store(self.path, boundary=self.boundary)
            != (intent.canonical_before_sha256, intent.canonical_before_bytes)
        ):
            raise BackupError("RESTORE_ORIGINAL_CHANGED")

    def _candidate(self, files: RestoreFiles, intent: RestoreIntentLike) -> Store:
        candidate = intent.candidate
        if files.catalogue.digest(candidate.candidate_id) != (
            candidate.database_sha256,
            candidate.database_bytes,
        ):
            raise BackupError("RESTORE_CANDIDATE_CHANGED")
        staged = open_store(
            files.catalogue.path(candidate.candidate_id, "sqlite3"), boundary=self.boundary
        )
        self._rotated_identity(staged, intent, candidate)
        return staged

    def _rotated_identity(
        self,
        store: Store,
        intent: RestoreIntentLike,
        candidate: RestoreCandidate,
    ) -> None:
        if (store.generation, store.schema_version, store.inventory_mode) != (
            candidate.new_generation,
            intent.selected.schema_version,
            intent.selected.inventory_mode,
        ) or store.read(summaries) != candidate.records:
            raise BackupError("RESTORE_CANONICAL_IDENTITY_CHANGED")
        if store.read(semantic_digest) != candidate.semantic_sha256:
            raise BackupError("RESTORE_CANONICAL_CONTENT_CHANGED")

        def verify(db: Session) -> None:
            metadata = db.get(StoreMetadata, 1)
            if (
                metadata is None
                or metadata.recovery_point != candidate.recovery_point
                or metadata.restored_at != candidate.prepared_at
                or metadata.created_at != intent.selected.source_created_at
                or db.scalar(
                    select(func.count())
                    .select_from(OwnerCredential)
                    .where(OwnerCredential.revoked_at.is_(None))
                )
                or db.scalar(select(func.count()).select_from(ActiveInventory))
                or db.scalar(select(func.count()).select_from(ActiveRules))
            ):
                raise BackupError("RESTORE_ADMISSION_NOT_INVALIDATED")
            if self._version(db, store.generation) != candidate.canonical_projection_version:
                raise BackupError("RESTORE_PROJECTION_VERSION_CHANGED")

        store.read(verify)

    def _capture_current(self, store: Store, candidate: RestoreCandidate) -> None:
        snapshot = store.read(lambda db: projection.capture(db, store.generation, self._now()))
        if snapshot is None or snapshot.version != candidate.canonical_projection_version:
            raise BackupError("RESTORE_PROJECTION_VERSION_CHANGED")

    def _recognized(
        self,
        store: Store,
        intent: RestoreIntentLike,
    ) -> RestoreCandidate | None:
        if store.generation == intent.previous.original_generation:
            self._original(store, intent)
            return None
        if store.generation != intent.candidate.new_generation:
            raise BackupError("RESTORE_DISK_STATE_UNKNOWN")
        try:
            self._rotated_identity(store, intent, intent.candidate)
            return intent.candidate
        except BackupError as target_failure:
            prior = intent.superseded_candidate if isinstance(intent, RestoreIntentV2) else None
            if prior is None:
                raise
            try:
                self._rotated_identity(store, intent, prior)
                return prior
            except BackupError as prior_failure:
                raise target_failure from prior_failure

    def _transition_basis(
        self,
        files: RestoreFiles,
        old: RestoreIntentLike | None,
        revised: RestoreIntentV2,
    ) -> None:
        current = open_store(self.path, boundary=self.boundary)
        recognized = self._recognized(current, revised if old is None else old)
        # Before marker promotion the proposed target must still be staged.
        # An exact duplicate update beside its promoted marker can also describe
        # an already-installed target; no prior file is guessed or recreated.
        if old is not None or recognized != revised.candidate:
            self._candidate(files, revised)
        if recognized is None:
            prior = revised.superseded_candidate
            if prior is None:
                raise BackupError("RESTORE_PREDECESSOR_MISSING")
            path = files.catalogue.path(prior.candidate_id, "sqlite3")
            if files.catalogue.digest(prior.candidate_id) != (
                prior.database_sha256,
                prior.database_bytes,
            ):
                raise BackupError("RESTORE_PREDECESSOR_CHANGED")
            self._rotated_identity(open_store(path, boundary=self.boundary), revised, prior)

    def _reconcile_expiry(
        self,
        files: RestoreFiles,
        publication: ProjectionFiles,
        intent: RestoreIntentLike,
        basis: Store,
    ) -> RestoreIntentV2:
        previous = as_v2(intent)
        if (
            len(previous.retention_steps) + int(previous.initial_retention is not None)
            >= MAX_SWEEPS
        ):
            raise BackupError("RESTORE_RETENTION_REVISION_LIMIT")
        cutoff = self.clock()
        earliest = (
            previous.retention_steps[-1].completed_at
            if previous.retention_steps
            else previous.started_at
        )
        if (
            cutoff.tzinfo is None
            or cutoff.utcoffset() != timedelta(0)
            or utc_text(cutoff) < earliest
        ):
            raise BackupError("RESTORE_RETENTION_CLOCK_INVALID")
        try:
            prepared = prepare_reconciled_candidate(
                files.catalogue,
                intent.candidate,
                canonical_lease=files.lease,
                source_path=guarded_store_path(basis.path, boundary=self.boundary, must_exist=True),
                now=cutoff,
                clock=self.clock,
            )
        except ProtectedRetentionError as error:
            error.restore_id = intent.restore_id
            raise
        material = asdict(prepared)
        material.pop("retention")
        candidate = RestoreCandidate.model_validate(material)
        changed = previous.model_dump(mode="python")
        changed.update(
            candidate=candidate,
            revision=previous.revision + 1,
            previous_marker_sha256=hashlib.sha256(encoded(intent)).hexdigest(),
            superseded_candidate=intent.candidate,
            retention_steps=(*previous.retention_steps, prepared.retention),
        )
        revised = RestoreIntentV2.model_validate(changed)
        self._transition_basis(files, intent, revised)
        stage_transition(files, intent, revised)
        return revised

    def _observe(
        self,
        files: RestoreFiles,
        publication: ProjectionFiles,
        receipt: RestoreReceiptLike,
    ) -> RestoreObservation:
        if receipt.completed_at > self._now():
            raise BackupError("RESTORE_RECEIPT_CLOCK_INVALID")
        try:
            current = open_store(self.path, boundary=self.boundary)
        except (StoreError, StorePathError, OSError):
            current = None
        return observe_current(receipt, current, publication, now=self._now(), clock=self._now)

    def _withdraw(
        self,
        files: RestoreFiles,
        publication: ProjectionFiles,
        intent: RestoreIntentLike,
    ) -> None:
        current = open_store(self.path, boundary=self.boundary)
        recognized = self._recognized(current, intent)
        if recognized is not None:
            # Prove canonical authority and mark only mutable T8 status first.
            # An unlink/ownership refusal must not leave a false current DB bit.
            current.write(
                lambda db: projection.failed(
                    db,
                    current.generation,
                    recognized.canonical_projection_version,
                    self._now(),
                )
            )
        withdraw_projection(
            publication,
            generation=intent.candidate.new_generation,
            version=intent.candidate.canonical_projection_version,
            previous_generation=intent.previous.original_generation,
        )

    def _capture_or_withdraw(
        self,
        files: RestoreFiles,
        publication: ProjectionFiles,
        store: Store,
        intent: RestoreIntentLike,
    ) -> None:
        try:
            self._capture_current(store, intent.candidate)
        except projection.ProjectionError as exc:
            if str(exc) == "CSV_RETENTION_RECONCILIATION_REQUIRED":
                self._withdraw(files, publication, intent)
            raise

    def _no_sqlite_companions(self, path: Path) -> None:
        safe = guarded_store_path(path, boundary=self.boundary, must_exist=True)
        if any(_io_path(Path(str(safe) + suffix)).exists() for suffix in COMPANIONS):
            raise BackupError("RESTORE_SQLITE_COMPANION_REQUIRES_RECOVERY")

    def _continue(
        self, files: RestoreFiles, publication: ProjectionFiles, intent: RestoreIntentLike
    ) -> RestoreObservation:
        files.verify_pins(intent)
        current = open_store(self.path, boundary=self.boundary)
        completed = files.completed_record(intent)
        if completed is not None:
            # A durable receipt freezes the operation. Never transform its intent
            # after expiry, even if only the complete receipt temporary survived.
            self._rotated_identity(current, intent, intent.candidate)
            if completed.completed_at > self._now():
                raise BackupError("RESTORE_RECEIPT_CLOCK_INVALID")
            try:
                self._capture_current(current, intent.candidate)
            except projection.ProjectionError as exc:
                if str(exc) != "CSV_RETENTION_RECONCILIATION_REQUIRED":
                    raise
                self._withdraw(files, publication, intent)
            files.finish(completed)
            return self._observe(files, publication, completed)

        recognized = self._recognized(current, intent)
        basis = current if recognized == intent.candidate else self._candidate(files, intent)
        try:
            self._capture_or_withdraw(files, publication, basis, intent)
        except projection.ProjectionError as exc:
            if str(exc) != "CSV_RETENTION_RECONCILIATION_REQUIRED":
                raise
            # If a promoted transition awaits its first DB swap, settle that
            # exact predecessor/target pair before preparing another revision.
            if recognized is not None and recognized != intent.candidate:
                self._replace(files, publication, intent)
                basis = open_store(self.path, boundary=self.boundary)
            intent = self._reconcile_expiry(files, publication, intent, basis)
            current = open_store(self.path, boundary=self.boundary)
            recognized = self._recognized(current, intent)

        if recognized != intent.candidate:
            # Never leave old-generation buyer contact bytes behind as a current CSV.
            self._replace(files, publication, intent)
            current = open_store(self.path, boundary=self.boundary)
        self._rotated_identity(current, intent, intent.candidate)
        self._capture_or_withdraw(files, publication, current, intent)
        result = CsvProjector(current, clock=self.clock).repair_locked(
            publication,
            reconcile_from_generation=intent.previous.original_generation,
        )
        current = open_store(self.path, boundary=self.boundary)
        self._rotated_identity(current, intent, intent.candidate)
        self._capture_or_withdraw(files, publication, current, intent)
        if result.state != "current" or not result.status_persisted:
            raise BackupError("RESTORE_CSV_NOT_CURRENT")
        publication.assert_locked()
        files.lease.assert_held(self.path, boundary=self.boundary)
        receipt = (
            RestoreReceiptV2(intent=intent, completed_at=self._now())
            if isinstance(intent, RestoreIntentV2)
            else RestoreReceipt(intent=intent, completed_at=self._now(), state="restored")
        )
        observation = observe_current(
            receipt, current, publication, now=self._now(), clock=self._now
        )
        if observation.projection != "current":
            if observation.projection == "retention_required":
                self._withdraw(files, publication, intent)
            raise BackupError("RESTORE_CSV_NOT_CURRENT")
        files.finish(receipt)
        return observation

    def _replace(
        self,
        files: RestoreFiles,
        publication: ProjectionFiles,
        intent: RestoreIntentLike,
    ) -> None:
        recognized = self._recognized(open_store(self.path, boundary=self.boundary), intent)
        if recognized == intent.candidate:
            return
        self._candidate(files, intent)
        self._withdraw(files, publication, intent)
        self._recognized(open_store(self.path, boundary=self.boundary), intent)
        self._candidate(files, intent)
        source = files.catalogue.path(intent.candidate.candidate_id, "sqlite3")
        self._no_sqlite_companions(source)
        self._no_sqlite_companions(self.path)
        publication.assert_locked()
        files.lease.assert_held(self.path, boundary=self.boundary)
        if files.marker() != intent or _io_path(update_path(files)).exists():
            raise BackupError("RESTORE_INTENT_CHANGED")
        os.replace(_io_path(source), _io_path(files.paths.store_path))
        with _io_path(files.paths.store_path).open("r+b") as output:
            output.flush()
            os.fsync(output.fileno())
