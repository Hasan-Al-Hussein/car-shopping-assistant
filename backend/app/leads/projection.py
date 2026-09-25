"""One bounded synchronous local CSV repair, independent of canonical buyer writes.

Compose one instance per app. Startup and an explicit operator CLI may call
repair_once; the physical Windows lock serializes separate instances/processes.
No background service, buyer endpoint, lead mutation or implicit retry is added.
"""

from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Literal
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.api.schemas.common import Id
from app.api.schemas.leads import ExportPending, RequestedExportOutcome
from app.database.paths import StorePathError
from app.database.store import Store, StoreError, assert_outside_write_transaction
from app.identity.service import utc_text
from app.leads import projection_repository as repo
from app.leads.csv_serialization import CsvSerializationError, serialize_leads_csv
from app.leads.projection_files import (
    CSV_NAME,
    MAX_BYTES,
    ProjectionFiles,
    PublicationBusy,
    PublicationManifest,
)

_ID = TypeAdapter(Id)


@dataclass(frozen=True)
class ProjectionRun:
    state: Literal["current", "pending", "failed", "busy", "empty"]
    store_generation: str
    canonical_version: int | None
    published_version: int | None
    row_count: int | None
    filename: str = CSV_NAME
    code: str | None = None
    status_persisted: bool = False


def startup_admitted(result: ProjectionRun) -> bool:
    """Unpersisted audit failures must not expose an old DB-current observation."""
    return result.state in {"current", "empty"} or result.status_persisted


def constrain_observation(
    observation: RequestedExportOutcome, attempt: ProjectionRun
) -> RequestedExportOutcome:
    """Downgrade a fresh CSV observation after repair; never change canonical facts.

    Postcommit transports use this even for busy/unpersisted failures. This pure
    helper never upgrades a pending observation or retries a canonical command.
    """
    if observation.state != "current":
        return observation
    if (
        attempt.state == "current" and attempt.status_persisted
        and attempt.store_generation == observation.store_generation
        and attempt.canonical_version == observation.canonical_version
        and attempt.published_version == observation.exported_version
    ):
        return observation
    return ExportPending(
        state="failed" if attempt.state == "failed" else "pending",
        store_generation=observation.store_generation,
        observed_at=observation.observed_at,
        canonical_version=observation.canonical_version,
        exported_version=observation.exported_version,
        code="CSV_EXPORT_FAILED" if attempt.state == "failed" else "CSV_AUDIT_PENDING",
    )


class CsvProjector:
    def __init__(self, store: Store, *, clock: Callable[[], datetime] | None = None) -> None:
        self.store = store
        self.clock = clock or (lambda: datetime.now(UTC))
        self._running = Lock()

    def _now(self) -> str:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise repo.ProjectionError("CSV_CLOCK_INVALID")
        return utc_text(value)

    def repair_once(self, *, reconcile_from_generation: str | None = None) -> ProjectionRun:
        """One normal pass under its own physical publication lock."""
        return self._repair(reconcile_from_generation=reconcile_from_generation)

    def repair_locked(
        self, files: ProjectionFiles, *, reconcile_from_generation: str | None = None,
    ) -> ProjectionRun:
        """Restore-only composition seam; reuse the already-held physical lock.

        Caller acquired publication before exclusive Store maintenance. The same
        capture/stage/fence/ack implementation runs without nested file locking.
        """
        assert_outside_write_transaction()
        files.assert_locked()
        expected = ProjectionFiles(self.store)
        if (files.store_binding, files.root) != (expected.store_binding, expected.root):
            raise repo.ProjectionError("CSV_DIFFERENT_STORE")
        return self._repair(reconcile_from_generation=reconcile_from_generation, locked_files=files)

    def _repair(
        self, *, reconcile_from_generation: str | None = None,
        locked_files: ProjectionFiles | None = None,
    ) -> ProjectionRun:
        """One pass; caller decides when to try again. No hidden loop or scheduled job.

        An explicit old-generation argument authorizes only replacing this same
        Store's old publication. Restore must already reconcile ExportState/intents
        and credentials while holding ProjectionFiles.lock. This is not a restore.
        """
        assert_outside_write_transaction()
        if reconcile_from_generation is not None:
            try:
                reconcile_from_generation = _ID.validate_python(reconcile_from_generation)
            except ValueError:
                raise repo.ProjectionError("CSV_ORIGINAL_GENERATION_INVALID") from None
            if reconcile_from_generation == self.store.generation:
                raise repo.ProjectionError("CSV_ORIGINAL_GENERATION_INVALID")
        if not self._running.acquire(blocking=False):
            return self._busy()
        snapshot: repo.ProjectionSnapshot | None = None
        published: PublicationManifest | None = None
        try:
            files = ProjectionFiles(self.store) if locked_files is None else locked_files
            with (files.lock() if locked_files is None else nullcontext()):
                files.assert_locked()
                try:
                    snapshot = self.store.read(
                        lambda db: repo.capture(db, self.store.generation, self._now())
                    )
                    existing, pending = files.inspect_existing(
                        generation=self.store.generation,
                        version=0 if snapshot is None else snapshot.version,
                        reconcile_from_generation=reconcile_from_generation,
                    )
                    if snapshot is None:
                        if existing is not None or pending is not None:
                            raise repo.ProjectionError("CSV_RESTORE_METADATA_REQUIRED")
                        return ProjectionRun("empty", self.store.generation, 0, None, 0)
                    serialized = serialize_leads_csv(
                        snapshot.rows, store_generation=snapshot.generation,
                        projection_version=snapshot.version,
                    )
                    if len(serialized.data) > MAX_BYTES:
                        raise repo.ProjectionError("CSV_FILE_LIMIT")
                    validation = serialized.validation
                    if (
                        existing is not None
                        and existing.store_generation == snapshot.generation
                        and existing.projection_version == snapshot.version
                        and existing.sha256 == validation.sha256
                        and existing.byte_length == validation.byte_length
                        and existing.row_count == validation.row_count
                        and files.verified(existing)
                    ):
                        # Includes crash after replace/before acknowledgement; no duplicate rows.
                        published = existing
                    else:
                        self.store.write(lambda db: repo.attempting(db, snapshot, self._now()))
                        if pending is not None:
                            files.discard_known_temporary(pending)
                        files.prune_temporary_files()
                        planned = PublicationManifest(
                            store_binding=files.store_binding,
                            store_generation=snapshot.generation,
                            projection_version=snapshot.version,
                            publication_id=str(uuid4()), sha256=validation.sha256,
                            byte_length=validation.byte_length, row_count=validation.row_count,
                            captured_at=snapshot.captured_at,
                        )
                        files.stage(planned, serialized.data)

                        def publish_fenced(db: Session) -> None:
                            # Store validates generation and delete journal mode on entry.
                            # Keep its SHARED read lock through both renames, so no canonical
                            # COMMIT can overtake this exact tuple. Bulk I/O is already finished.
                            repo.fence(db, snapshot, self._now())
                            files.publish(planned)

                        self.store.read(publish_fenced)
                        if not files.verified(planned):
                            raise repo.ProjectionError("CSV_PUBLISHED_PAIR_UNVERIFIED")
                        published = planned
                    try:
                        canonical_version = self.store.write(
                            lambda db: repo.acknowledge(db, snapshot, self._now())
                        )
                    except StoreError:
                        return ProjectionRun(
                            "pending", snapshot.generation, snapshot.version,
                            published.projection_version, published.row_count,
                            code="CSV_ACKNOWLEDGEMENT_PENDING",
                        )
                    current = canonical_version == snapshot.version
                    return ProjectionRun(
                        "current" if current else "pending", snapshot.generation,
                        canonical_version, published.projection_version, published.row_count,
                        code=None if current else "CSV_CANONICAL_VERSION_ADVANCED",
                        status_persisted=True,
                    )
                except repo.StaleProjection:
                    return ProjectionRun(
                        "pending", self.store.generation,
                        None if snapshot is None else snapshot.version, None, None,
                        code="CSV_CANONICAL_VERSION_ADVANCED",
                    )
                except (OSError, StorePathError, StoreError, repo.ProjectionError,
                        CsvSerializationError):
                    persisted = False
                    try:
                        persisted = self.store.write(lambda db: repo.failed(
                            db, self.store.generation,
                            None if snapshot is None else snapshot.version, self._now(),
                        ))
                    except (StoreError, StorePathError, repo.ProjectionError):
                        pass
                    return ProjectionRun(
                        "failed", self.store.generation,
                        None if snapshot is None else snapshot.version,
                        None if published is None else published.projection_version,
                        None if published is None else published.row_count,
                        code="CSV_EXPORT_FAILED", status_persisted=persisted,
                    )
        except PublicationBusy:
            return self._busy()
        except (OSError, StorePathError, StoreError, repo.ProjectionError):
            return ProjectionRun(
                "failed", self.store.generation, None, None, None,
                code="CSV_EXPORT_PATH_UNAVAILABLE",
            )
        finally:
            self._running.release()

    def _busy(self) -> ProjectionRun:
        return ProjectionRun(
            "busy", self.store.generation, None, None, None, code="CSV_PUBLISHER_BUSY"
        )
