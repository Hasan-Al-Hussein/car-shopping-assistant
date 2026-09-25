"""Explicit postcompletion orchestration with immutable original-command retention.

Inventory pointer equality is an observation, never an original activation receipt.
I9's existing event is the sole authority for its original operation's commit.
No second restore journal, hidden retry, credential bootstrap or provider call.
"""

import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict

from app.api.schemas.capabilities import Capability
from app.api.schemas.common import DTO, Digest, Id
from app.core.config import DemoPolicy, Settings
from app.core.readiness import InventoryObservation
from app.database.maintenance import MaintenanceError, shared_store_lease
from app.database.paths import RuntimeBoundary, parse_runtime_path
from app.database.store import Store, StoreError, assert_outside_write_transaction, open_store
from app.identity.service import utc_text
from app.inventory.snapshots import InventoryRepository
from app.leads.projection_files import ProjectionFiles
from app.operations.backup_files import BackupFiles, _regular_chain
from app.operations.restore_completion import completed_restore_scope
from app.operations.restore_files import MAX_INTENT_BYTES, encoded
from app.operations.restore_observation import RestoreObservation, observe_current
from app.operations.restore_transition import parse_receipt
from app.operations.restored_bundle_contract import (
    ADOPTED_SNAPSHOT, RESTORED_BUNDLE_ROOT, RestoredBundleRequest,
)
from app.operations.restored_inventory_bundle import produce_restored_inventory_bundle
from app.operations.viewing_configuration import (
    ActivationRequest, Reconciliation, ViewingConfigurationOperator,
)
from app.runtime_app import ApplicationComposition, build_composition
from app.runtime_observations import viewing_capability
from app.sessions.state import canonical
from app.viewings.scheduling import ViewingRules

_RECORD_LIMIT = 16_384
_InventoryAction = Literal["activated_return_observed", "existing_pointer_observed", "not_attempted"]


class ReadmissionError(ValueError):
    """Closed code only. Failure never implies that preceding phases rolled back."""


class ReadmissionRequest(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    operation_id: Id
    restore_id: Id
    restore_receipt_sha256: Digest
    expected_generation: Id


class _RetainedRequest(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["restored-readmission-request-1"] = "restored-readmission-request-1"
    request: ReadmissionRequest
    store_binding: Digest


class _RetainedActivation(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    format: Literal["restored-readmission-activation-1"] = "restored-readmission-activation-1"
    original: _RetainedRequest
    activation: ActivationRequest


class ReadmissionResult(DTO):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ReadmissionRequest
    inventory_action: _InventoryAction
    inventory: InventoryObservation | None
    viewing: Reconciliation
    current_viewing: Capability
    current_csv: RestoreObservation | None
    application_launch: Literal["not_performed"] = "not_performed"
    original_inventory_commit: Literal["not_proven_by_pointer_observation"] = "not_proven_by_pointer_observation"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReadmissionError(code)


def _path(project: Path, operation: str, name: str, *, create: bool) -> Path:
    # All components except the already-validated UUID are fixed implementation
    # names. Only canonical project records are created, never runtime state.
    base = project.resolve(strict=True)
    _require(project.is_absolute() and project == base, "READMISSION_PROJECT_PATH_CHANGED")
    target = base / "Records" / "operations" / "restored-readmission" / operation / name
    _regular_chain(target)
    _require(target.resolve(strict=False) == target, "READMISSION_RECORD_PATH_CHANGED")
    if create:
        target.parent.mkdir(parents=True, exist_ok=True)
        _regular_chain(target)
    return target


def _read(path: Path) -> bytes | None:
    _regular_chain(path)
    if not path.exists():
        return None
    _require(path.stat().st_size <= _RECORD_LIMIT, "READMISSION_RECORD_LIMIT")
    with path.open("rb") as source:
        raw = source.read(_RECORD_LIMIT + 1)
    _regular_chain(path)
    _require(len(raw) <= _RECORD_LIMIT, "READMISSION_RECORD_LIMIT")
    return raw


def _retain(path: Path, value: DTO) -> None:
    raw = canonical(value.model_dump(mode="json")) + b"\n"
    _require(len(raw) <= _RECORD_LIMIT, "READMISSION_RECORD_LIMIT")
    existing = _read(path)
    if existing is None:
        try:
            with path.open("xb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError:
            pass  # Another exact caller may have retained it; verify actual bytes.
    _require(_read(path) == raw, "READMISSION_ORIGINAL_REQUEST_CHANGED")


def _activation(path: Path, expected: _RetainedRequest) -> ActivationRequest | None:
    raw = _read(path)
    if raw is None:
        return None
    value = _RetainedActivation.model_validate_json(raw)
    request = value.activation
    _require(
        canonical(value.model_dump(mode="json")) + b"\n" == raw
        and value.original == expected
        and request.operation_id == expected.request.operation_id
        and request.generation == expected.request.expected_generation
        and request.bundle == RESTORED_BUNDLE_ROOT + request.operation_id
        and request.expected_active_version is None and request.expected_revision == 0,
        "READMISSION_ORIGINAL_REQUEST_CHANGED",
    )
    return request


def _csv(
    store: Store, publication: ProjectionFiles, request: ReadmissionRequest,
) -> RestoreObservation:
    # Factory authenticates the derived final receipt and fresh metadata. Parsing
    # below materializes the same bounded bytes for the independent CSV observer.
    with completed_restore_scope(
        store.path, boundary=store.boundary, restore_id=request.restore_id,
        expected_receipt_sha256=request.restore_receipt_sha256,
        expected_generation=request.expected_generation,
    ) as completed:
        path = Path(completed.observation.receipt_path)
        with path.open("rb") as source:
            raw = source.read(MAX_INTENT_BYTES + 1)
        _require(hashlib.sha256(raw).hexdigest() == request.restore_receipt_sha256,
                 "READMISSION_RECEIPT_CHANGED")
        receipt = parse_receipt(raw)
        _require(encoded(receipt) == raw, "READMISSION_RECEIPT_CHANGED")
        result = observe_current(receipt, store, publication, now=utc_text(datetime.now(UTC)))
        completed.revalidate()
        return result


def _observed_inventory(store: Store) -> InventoryObservation | None:
    try:
        return InventoryRepository(store).active().observation
    except (OSError, StoreError, MaintenanceError, ValueError):
        return None


def _completed_result(
    store: Store, publication: ProjectionFiles, request: ReadmissionRequest,
    viewing: Reconciliation, action: _InventoryAction,
) -> ReadmissionResult:
    try:
        csv = _csv(store, publication, request)
    except (OSError, StoreError, MaintenanceError, ValueError):
        csv = None  # Immutable I9 commit remains known even if observation is unavailable.
    inventory = _observed_inventory(store)
    capability = viewing_capability(store, ViewingRules(DemoPolicy()), inventory)
    return ReadmissionResult(
        request=request, inventory_action=action, inventory=inventory,
        viewing=viewing, current_viewing=capability, current_csv=csv,
    )


def run_readmission(
    raw_store_path: str, *, boundary: RuntimeBoundary, project_root: Path,
    request: ReadmissionRequest,
) -> ReadmissionResult:
    assert_outside_write_transaction()
    request = ReadmissionRequest.model_validate(request.model_dump(mode="python"))
    path = parse_runtime_path(raw_store_path)
    publication = ProjectionFiles.for_store_path(path, boundary=boundary)
    # Same lock order as restore; keep CSV publication fixed while normal short
    # inventory/I9 writes run. Shared admission excludes a competing restore.
    with publication.lock(), shared_store_lease(path, boundary=boundary):
        store = open_store(path, boundary=boundary)
        _require(store.generation == request.expected_generation, "READMISSION_GENERATION_CHANGED")
        retained = _RetainedRequest(
            request=request, store_binding=BackupFiles.for_store_path(path, boundary=boundary).binding,
        )
        original_path = _path(project_root, request.operation_id, "request.json", create=False)
        activation_path = _path(project_root, request.operation_id, "activation-request.json", create=False)
        original_bytes = _read(original_path)
        if original_bytes is not None:
            _require(original_bytes == canonical(retained.model_dump(mode="json")) + b"\n",
                     "READMISSION_ORIGINAL_REQUEST_CHANGED")
        original = _activation(activation_path, retained)
        _require(original is None or original_bytes is not None, "READMISSION_ORIGINAL_REQUEST_MISSING")
        operator = ViewingConfigurationOperator(
            raw_store_path, boundary=boundary, project_root=project_root,
        )
        if original is not None:
            known = operator.reconcile(original)
            if known.result is not None:
                # Terminal event FIRST: never reload producer/bundle/adoption to
                # decide whether the original I9 operation already committed.
                return _completed_result(store, publication, request, known, "not_attempted")

        with completed_restore_scope(
            path, boundary=boundary, restore_id=request.restore_id,
            expected_receipt_sha256=request.restore_receipt_sha256,
            expected_generation=request.expected_generation,
        ) as completed:
            _require(_csv(store, publication, request).projection == "current", "READMISSION_CSV_REQUIRED")
            original_path = _path(project_root, request.operation_id, "request.json", create=True)
            _retain(original_path, retained)  # Original IDs precede EVERY activation effect.
            repository = InventoryRepository(store)
            active = repository.active()
            action: _InventoryAction = "existing_pointer_observed"
            if (active.stage is None and active.observation.snapshot_id is None
                    and active.observation.active_revision == 0):
                repository.activate(ADOPTED_SNAPSHOT, expected_revision=0)
                action = "activated_return_observed"
                active = repository.active()
            _require(
                active.stage is not None and active.observation.snapshot_id == ADOPTED_SNAPSHOT
                and active.observation.generation == request.expected_generation
                and active.observation.active_revision == 1,
                "READMISSION_INVENTORY_STATE_CONFLICT",
            )
            bundle = produce_restored_inventory_bundle(
                raw_store_path, boundary=boundary, project_root=project_root,
                request=RestoredBundleRequest(
                    operation_id=request.operation_id, restore_id=request.restore_id,
                    restore_receipt_sha256=request.restore_receipt_sha256,
                    expected_generation=request.expected_generation,
                    expected_inventory=active.observation,
                    bundle=RESTORED_BUNDLE_ROOT + request.operation_id,
                ),
            )
            intended = ActivationRequest(
                operation_id=request.operation_id, generation=request.expected_generation,
                configuration_id=bundle.configuration_id, expected_active_version=None,
                expected_revision=0, bundle=bundle.request.bundle, receipt_sha256=bundle.receipt_sha256,
            )
            _require(original is None or intended == original, "READMISSION_ORIGINAL_REQUEST_CHANGED")
            activation_path = _path(project_root, request.operation_id, "activation-request.json", create=True)
            _retain(activation_path, _RetainedActivation(original=retained, activation=intended))
            completed.revalidate()
            operator.activate(intended)
            # Postcommit publication is deliberately not a commit precondition.
            # Its own explicit I9 command may publish later using this exact event.
            reconciled = operator.reconcile(intended)
            _require(reconciled.result is not None, "READMISSION_I9_RESULT_UNAVAILABLE")
            result = _completed_result(store, publication, request, reconciled, action)
        return result  # Actual outer completion normal-exit checks have finished.


@contextmanager
def readmitted_runtime(
    settings: Settings, *, project_root: Path, request: ReadmissionRequest,
) -> Iterator[tuple[ApplicationComposition, ReadmissionResult]]:
    """Create fresh process authority and verify it; caller owns the yielded app.

    No HTTP listener, buyer credentials, model call or retained old capability.
    This explicit context audits CSV via the actual startup projector and closes
    its fresh composition after the caller finishes, including exceptional exit.
    """
    boundary = settings.runtime_boundary
    if boundary is None or settings.store_path is None:
        raise ReadmissionError("READMISSION_BOUNDARY_REQUIRED")
    result = run_readmission(
        str(settings.store_path), boundary=boundary, project_root=project_root, request=request,
    )
    original = result.viewing.result
    _require(original is not None, "READMISSION_I9_RESULT_UNAVAILABLE")
    assert original is not None
    with completed_restore_scope(
        settings.store_path, boundary=boundary, restore_id=request.restore_id,
        expected_receipt_sha256=request.restore_receipt_sha256,
        expected_generation=request.expected_generation,
    ) as completed:
        store = open_store(settings.store_path, boundary=boundary)
        composition = build_composition(settings, store)
        try:
            observation = composition.admit_inventory()
            _require(observation == result.inventory, "READMISSION_INVENTORY_STATE_CONFLICT")
            attempt = composition.projector.repair_once()
            _require(attempt.state == "current" and attempt.status_persisted,
                     "READMISSION_CSV_REQUIRED")
            operator = ViewingConfigurationOperator(
                str(settings.store_path), boundary=boundary, project_root=project_root,
            )
            current = operator.reconcile(original.request)
            _require(current.result == original and current.active_version == original.request.configuration_id
                     and current.active_revision == original.revision, "READMISSION_RULES_NOT_CURRENT")
            _require(viewing_capability(store, ViewingRules(settings.policy), observation).state == "ready",
                     "READMISSION_VIEWING_UNAVAILABLE")
            completed.revalidate()
            yield composition, result
        except BaseException as error:
            try:
                if not composition.close():
                    error.add_note("Readmission composition did not settle; retained lifetime remains held.")
            except BaseException:
                error.add_note("Readmission composition cleanup failed; settlement is unverified.")
            raise
        else:
            _require(composition.close(), "READMISSION_RUNTIME_NOT_SETTLED")
