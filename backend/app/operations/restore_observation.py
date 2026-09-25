"""Read-only current CSV evidence, separate from an immutable restore receipt."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import ConfigDict
from sqlalchemy.orm import Session

from app.api.schemas.common import DTO, Id, Revision, UtcInstant
from app.database.models import StoreMetadata
from app.database.paths import StorePathError
from app.database.store import Store, StoreError, assert_outside_write_transaction
from app.identity.service import utc_text
from app.leads.csv_serialization import CsvSerializationError, serialize_leads_csv
from app.leads.projection_files import CSV_NAME, MAX_BYTES, ProjectionFiles
from app.leads import projection_repository as projection
from app.operations.restore_transition import RestoreReceiptLike

_ObservationCode = Literal[
    "RESTORE_POSTCOMPLETION_RETENTION_REQUIRED", "RESTORE_CURRENT_CSV_UNVERIFIED",
    "RESTORE_CURRENT_ASSOCIATION_CHANGED", "RESTORE_CURRENT_STORE_UNAVAILABLE",
]


class RestoreObservation(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["restore-observation-1"] = "restore-observation-1"
    receipt: RestoreReceiptLike
    completion: Literal[
        "completed_current", "historically_completed_retention_required",
        "historically_completed_observation_unavailable",
    ]
    observed_at: UtcInstant
    observed_generation: Id | None
    canonical_version: Revision | None
    projection: Literal["current", "retention_required", "unavailable"]
    code: _ObservationCode | None


def withdraw_projection(
    files: ProjectionFiles, *, generation: str, version: int, previous_generation: str,
) -> None:
    """Restore-only withdrawal: both generations belong to this exact restore.

    Descriptors stay as evidence. Unknown data is never erased; no generic
    temporary pruning is performed by this recovery operation.
    """
    assert_outside_write_transaction()
    files.assert_locked()
    existing, pending = files.inspect_existing(
        generation=generation, version=version,
        reconcile_from_generation=previous_generation,
    )
    data = files.read_bytes(CSV_NAME, MAX_BYTES)
    if data is not None:
        if not any(value is not None and files.matches(value, data)
                   for value in (existing, pending)):
            raise projection.ProjectionError("CSV_RETENTION_BYTES_UNVERIFIED")
        files.path(CSV_NAME).unlink()
    if pending is not None:
        files.discard_known_temporary(pending)
    if files.read_bytes(CSV_NAME, MAX_BYTES) is not None:
        raise projection.ProjectionError("CSV_RETENTION_WITHDRAWAL_UNVERIFIED")


def observe_current(
    receipt: RestoreReceiptLike, store: Store | None, files: ProjectionFiles, *, now: str,
    clock: Callable[[], str] | None = None,
) -> RestoreObservation:
    """Caller holds publication and maintenance exclusion; performs no repair.

    The read transaction fences canonical capture, metadata acknowledgement and
    exact publication bytes together. Historical target fingerprints and pins are
    intentionally not current-state predicates after completion.
    """
    assert_outside_write_transaction()
    files.assert_locked()
    generation = None if store is None else store.generation
    version: int | None = None
    fresh_time = clock or (lambda: utc_text(datetime.now(UTC)))
    proof_time = now
    code: _ObservationCode = "RESTORE_CURRENT_STORE_UNAVAILABLE"
    if store is not None:
        candidate, selected = receipt.intent.candidate, receipt.intent.selected

        def audit(db: Session) -> tuple[bool, int | None]:
            nonlocal proof_time
            metadata = db.get(StoreMetadata, 1)
            if (metadata is None or
                (store.generation, store.schema_version, store.inventory_mode,
                 metadata.store_generation, metadata.schema_version, metadata.created_at,
                 metadata.restored_at, metadata.recovery_point) !=
                (candidate.new_generation, selected.schema_version, selected.inventory_mode,
                 candidate.new_generation, selected.schema_version, selected.source_created_at,
                 candidate.prepared_at, candidate.recovery_point)):
                raise projection.ProjectionError("RESTORE_CURRENT_ASSOCIATION_CHANGED")
            snapshot = projection.capture(db, store.generation, now)
            if snapshot is None:
                return False, None
            current = projection.state(db, store.generation)
            serialized = serialize_leads_csv(
                snapshot.rows, store_generation=snapshot.generation,
                projection_version=snapshot.version,
            )
            manifest, pending = files.inspect_existing(
                generation=store.generation, version=snapshot.version,
                reconcile_from_generation=receipt.intent.previous.original_generation,
            )
            data = files.read_bytes(CSV_NAME, MAX_BYTES)
            valid = serialized.validation
            verified = (
                current is not None and current.state == "current"
                and current.exported_version == snapshot.version
                and manifest is not None and pending is None
                and manifest.store_generation == snapshot.generation
                and manifest.projection_version == snapshot.version
                and manifest.sha256 == valid.sha256 and manifest.byte_length == valid.byte_length
                and manifest.row_count == valid.row_count and data == serialized.data
                and files.matches(manifest, serialized.data)
            )
            proof_time = fresh_time()
            if proof_time < now:
                raise projection.ProjectionError("RESTORE_OBSERVATION_CLOCK_INVALID")
            projection.require_unexpired(snapshot, proof_time)
            return verified, snapshot.version

        try:
            verified, version = store.read(audit)
            if verified:
                return RestoreObservation(
                    receipt=receipt, completion="completed_current", observed_at=proof_time,
                    observed_generation=generation, canonical_version=version,
                    projection="current", code=None,
                )
            code = "RESTORE_CURRENT_CSV_UNVERIFIED"
        except projection.ProjectionError as exc:
            if str(exc) == "CSV_RETENTION_RECONCILIATION_REQUIRED":
                return RestoreObservation(
                    receipt=receipt, completion="historically_completed_retention_required",
                    observed_at=proof_time, observed_generation=generation,
                    canonical_version=version, projection="retention_required",
                    code="RESTORE_POSTCOMPLETION_RETENTION_REQUIRED",
                )
            code = ("RESTORE_CURRENT_ASSOCIATION_CHANGED"
                    if str(exc) == "RESTORE_CURRENT_ASSOCIATION_CHANGED"
                    else "RESTORE_CURRENT_CSV_UNVERIFIED")
        except (OSError, StorePathError, StoreError, CsvSerializationError):
            code = "RESTORE_CURRENT_CSV_UNVERIFIED"
    return RestoreObservation(
        receipt=receipt, completion="historically_completed_observation_unavailable",
        observed_at=proof_time, observed_generation=generation, canonical_version=version,
        projection="unavailable", code=code,
    )
