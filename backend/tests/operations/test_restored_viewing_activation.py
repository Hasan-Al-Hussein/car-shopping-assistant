"""T12 actual-restore/I9 composition obligations, authored but not executed."""

import hashlib
import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from app.core.errors import ApiFailure
from app.database.store import Store, StoreError
from app.inventory.compact_reader import CompactInventoryReader
from app.operations import viewing_configuration as operation
from app.operations.restore_completion import CompletedRestoreObservation
from app.operations.restored_bundle_contract import RestoredBundleReceipt
from app.operations.viewing_configuration import (
    ActivationError,
    ActivationRequest,
    ActivationResult,
)
from app.sessions.state import canonical
from pydantic import ValidationError
from sqlalchemy.orm import Session
from tests.operations.activation_cases import business_state, sql, stored_state
from tests.operations.restored_bundle_cases import RestoredBundleCase
from tests.operations.restored_bundle_cases import restored_bundle_case as restored_bundle_case


def _changed_receipt(
    case: RestoredBundleCase,
    request: ActivationRequest,
    change: Callable[[dict[str, Any]], None],
) -> ActivationRequest:
    path = case.bundle_dir / "receipt.json"
    value = json.loads(path.read_bytes())
    change(value)
    raw = canonical(value)
    path.write_bytes(raw)  # Deliberate adverse fixture, never producer repair.
    return request.model_copy(update={"receipt_sha256": hashlib.sha256(raw).hexdigest()})


def test_actual_completed_restore_producer_and_i9_original_replay(
    restored_bundle_case: RestoredBundleCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = restored_bundle_case
    produced = case.produce()
    request = case.activation_request(produced)
    receipt = RestoredBundleReceipt.model_validate_json(
        (case.bundle_dir / "receipt.json").read_bytes()
    )
    assert receipt.restore.restore_id == case.request.restore_id
    assert receipt.producer_source_sha256 in operation.SUPPORTED_RESTORED_PRODUCERS
    assert receipt.reader_admission == "COLD_AUDIT_PASSED"
    before = business_state(case.store)
    operator = case.operator()
    result = operator.activate(request)
    assert result.changed and result.revision == 1 and result.request == request
    assert operator.reconcile(request).result == result
    assert operator.reconcile(request).active_version == result.request.configuration_id
    assert business_state(case.store) == before
    published = operator.publish_receipt(result)
    assert published.is_file()
    # The durable original event remains terminal even after historical bundle loss.
    (case.bundle_dir / "pending-viewing-configuration.json").unlink()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("recorded operation must return before pending source reload")

    monkeypatch.setattr(operation, "_pending", forbidden)
    monkeypatch.setattr(operation, "completed_restore_scope", forbidden)
    assert operator.activate(request) == result
    assert operator.reconcile(request).result == result
    assert operator.publish_receipt(result) == published


@pytest.mark.parametrize(
    "fault",
    (
        "producer", "format", "operation", "bundle", "restore_hash", "restore_generation",
        "mapping", "input", "unknown", "audit_status", "observation_time", "future_audit",
    ),
)
def test_consistent_outer_hash_cannot_authorize_changed_restored_bundle(
    restored_bundle_case: RestoredBundleCase, fault: str
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())
    before = stored_state(case.store)

    def change(value: dict[str, Any]) -> None:
        if fault == "producer":
            value["producer_source_sha256"] = "0" * 64
        elif fault == "format":
            value["format"] = "restored-inventory-viewing-bundle-2"
        elif fault == "operation":
            value["request"]["operation_id"] = str(uuid4())
        elif fault == "bundle":
            value["request"]["bundle"] += "/.."
        elif fault == "restore_hash":
            value["restore"]["receipt_sha256"] = "0" * 64
            value["request"]["restore_receipt_sha256"] = "0" * 64
        elif fault == "restore_generation":
            value["restore"]["store_generation"] = str(uuid4())
        elif fault == "mapping":
            value["mapping_digest"] = "0" * 64
        elif fault == "input":
            value["input_hashes"] = {}
        elif fault == "unknown":
            value["activation_authority"] = True
        elif fault == "audit_status":
            value["reader_admission"] = "NOT_RUN"
        elif fault == "future_audit":
            value["started_at"] = value["completed_at"] = "2999-01-01T00:00:00Z"
            value["restore"]["observed_at"] = "2999-01-01T00:00:00Z"
        else:
            value["restore"]["observed_at"] = "2999-01-01T00:00:00Z"

    changed = _changed_receipt(case, request, change)
    with pytest.raises((ActivationError, ValidationError)):
        case.operator().activate(changed)
    assert stored_state(case.store) == before


def test_fresh_completion_revalidation_rejects_receipt_change_before_writer(
    restored_bundle_case: RestoredBundleCase,
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())
    before = stored_state(case.store)
    original = case.restore_receipt_path.read_bytes()
    applied: list[bool] = []

    def checkpoint(phase: str) -> None:
        if phase == "activation.prepared":
            case.restore_receipt_path.write_bytes(original + b" ")
            applied.append(True)

    try:
        with pytest.raises(ActivationError, match="RESTORED_COMPLETION_UNAVAILABLE"):
            case.operator(checkpoint).activate(request)
    finally:
        case.restore_receipt_path.write_bytes(original)
    assert applied == [True]
    assert stored_state(case.store) == before


def test_inventory_aba_after_preparation_does_not_activate_rules(
    restored_bundle_case: RestoredBundleCase,
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())
    before = stored_state(case.store)
    applied: list[bool] = []

    def checkpoint(phase: str) -> None:
        if phase == "activation.prepared":
            sql(case.store, (("UPDATE active_inventory SET revision=revision+2 WHERE id=1", ()),))
            applied.append(True)

    with pytest.raises((ActivationError, ApiFailure, ValueError)):
        case.operator(checkpoint).activate(request)
    assert applied == [True]
    actual_revision = case.store.read(
        lambda db: db.connection().exec_driver_sql(
            "SELECT revision FROM active_inventory WHERE id=1"
        ).scalar_one()
    )
    assert actual_revision == case.request.expected_inventory.active_revision + 2
    assert stored_state(case.store) == before


def test_database_metadata_is_checked_in_same_actual_writer(
    restored_bundle_case: RestoredBundleCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())
    operator = case.operator()
    original = operation.recheck_completed_restore_metadata
    original_commit = operator._commit
    checked: list[Session] = []
    committed: list[Session] = []

    def check(db: Session, observed: CompletedRestoreObservation) -> None:
        assert db.connection().get_execution_options()["store_write"] is True
        assert observed.store_generation == case.store.generation
        checked.append(db)
        original(db, observed)

    def commit(
        db: Session,
        reader: CompactInventoryReader,
        prepared: operation._Prepared,
        created_at: str,
        restoration: CompletedRestoreObservation | None = None,
    ) -> ActivationResult:
        committed.append(db)
        return original_commit(db, reader, prepared, created_at, restoration)

    monkeypatch.setattr(operation, "recheck_completed_restore_metadata", check)
    monkeypatch.setattr(operator, "_commit", commit)
    result = operator.activate(request)
    assert result.revision == 1 and len(checked) == len(committed) == 1
    assert checked[0] is committed[0]


def test_metadata_change_between_revalidation_and_writer_is_refused(
    restored_bundle_case: RestoredBundleCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())
    operator = case.operator()
    before = stored_state(case.store)
    original_write = Store.write
    changed = False

    def write(self: Store, work: Callable[[Session], Any]) -> Any:
        nonlocal changed
        if self is operator.store and not changed:
            changed = True

            def alter_metadata(db: Session) -> None:
                db.connection().exec_driver_sql(
                    "UPDATE store_metadata SET restored_at=? WHERE id=1",
                    ("2026-01-01T00:00:00Z",),
                )

            original_write(self, alter_metadata)
        return original_write(self, work)

    monkeypatch.setattr(Store, "write", write)
    with pytest.raises(ActivationError, match="RESTORED_COMPLETION_UNAVAILABLE"):
        operator.activate(request)
    assert changed
    assert stored_state(case.store) == before


def test_postcommit_publication_failure_recovers_only_original_operation(
    restored_bundle_case: RestoredBundleCase,
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())

    def checkpoint(phase: str) -> None:
        if phase == "receipt.before_write":
            raise OSError("synthetic publication interruption")

    operator = case.operator(checkpoint)
    result = operator.activate(request)
    with pytest.raises(OSError, match="synthetic publication"):
        operator.publish_receipt(result)
    retry = case.operator()
    assert retry.reconcile(request).result == result
    assert retry.activate(request) == result
    assert retry.publish_receipt(result).is_file()
    changed = request.model_copy(update={"receipt_sha256": "0" * 64})
    with pytest.raises(ActivationError, match="ACTIVATION_OPERATION_ID_CONFLICT"):
        retry.activate(changed)


def test_scope_exit_failure_after_commit_preserves_original_event_for_reconcile(
    restored_bundle_case: RestoredBundleCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())
    operator = case.operator()
    original_receipt = case.restore_receipt_path.read_bytes()
    original_write = Store.write
    committed: list[ActivationResult] = []

    def write(self: Store, work: Callable[[Session], Any]) -> Any:
        result = original_write(self, work)
        if self is operator.store:
            assert isinstance(result, ActivationResult)
            committed.append(result)
            # Actual writer has returned/committed; genuine scope exit must reread.
            case.restore_receipt_path.write_bytes(original_receipt + b" ")
        return result

    monkeypatch.setattr(Store, "write", write)
    try:
        with pytest.raises(ActivationError, match="RESTORED_COMPLETION_UNAVAILABLE"):
            operator.activate(request)
    finally:
        case.restore_receipt_path.write_bytes(original_receipt)
    assert len(committed) == 1
    retry = case.operator()
    observed = retry.reconcile(request)
    assert observed.result == committed[0]
    assert observed.active_version == request.configuration_id
    assert observed.active_revision == 1
    assert retry.activate(request) == committed[0]


def test_restore_marker_blocks_before_new_activation(
    restored_bundle_case: RestoredBundleCase,
) -> None:
    case = restored_bundle_case
    request = case.activation_request(case.produce())
    operator = case.operator()
    before = stored_state(case.store)
    marker = case.store.path.with_name(case.store.path.name + ".restore-intent.json")
    assert not marker.exists()
    marker.write_bytes(b"{}")  # Explicit synthetic pending marker; no guessed recovery.
    try:
        with pytest.raises(StoreError):
            operator.activate(request)
    finally:
        marker.unlink()
    assert stored_state(case.store) == before
