"""Source-authored producer proof; actual restore fixtures, no synthetic completion claim."""

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.database.paths import RuntimeBoundary
from app.database.store import Store
from app.inventory.compact_reader import AuditReceipt, CompactBatch, CompactInventoryReader
from app.inventory.references import ImmutableInventoryRef
from app.operations import restored_inventory_bundle as producer
from app.operations.restore_completion import (
    CompletedRestoreObservation,
    CompletedRestoreScope,
    RestoreCompletionError,
)
from app.operations.restored_bundle_contract import RestoredBundleReceipt
from app.sessions.state import canonical
from sqlalchemy.orm import Session
from tests.operations.activation_cases import sql, stored_state
from tests.operations.restored_bundle_cases import RestoredBundleCase
from tests.operations.restored_bundle_cases import restored_bundle_case as restored_bundle_case
from tests.support.harness import PROJECT


@pytest.fixture
def publication_directory() -> Path:
    path = PROJECT / "Records/build/OP-02/T12-restored-readmission/test-runs" / str(uuid4())
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_real_restore_audit_has_two_fifty_ref_proofs_and_no_database_writer(
    restored_bundle_case: RestoredBundleCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = restored_bundle_case
    before = stored_state(case.store)
    requested: list[tuple[ImmutableInventoryRef, ...]] = []
    units: list[Session] = []
    original_read = CompactInventoryReader.read_refs
    original_recheck = CompactInventoryReader.recheck

    def read_refs(
        reader: CompactInventoryReader,
        refs: tuple[ImmutableInventoryRef, ...],
        *,
        expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        requested.append(refs)
        return original_read(reader, refs, expected_snapshot_id=expected_snapshot_id)

    def recheck(reader: CompactInventoryReader, db: Session, batch: CompactBatch) -> None:
        units.append(db)
        original_recheck(reader, db, batch)

    def forbidden_write(store: Store, work: Callable[[Session], object]) -> object:
        raise AssertionError("Producer attempted a Store writer")

    monkeypatch.setattr(CompactInventoryReader, "read_refs", read_refs)
    monkeypatch.setattr(CompactInventoryReader, "recheck", recheck)
    monkeypatch.setattr(Store, "write", forbidden_write)
    started = datetime.now(UTC)
    result = case.produce()
    finished = datetime.now(UTC)
    raw = (case.bundle_dir / "receipt.json").read_bytes()
    receipt = RestoredBundleReceipt.model_validate_json(raw)
    config = (case.bundle_dir / "pending-viewing-configuration.json").read_bytes()
    assert result.publication == "created" and result.request == case.request
    assert result.receipt_sha256 == hashlib.sha256(raw).hexdigest()
    assert receipt.inventory == case.request.expected_inventory
    assert receipt.restore.restore_id == case.request.restore_id
    assert receipt.restore.receipt_sha256 == case.request.restore_receipt_sha256
    assert receipt.listing_count == 100 and receipt.evidence_count == 1079
    assert receipt.configuration_sha256 == hashlib.sha256(config).hexdigest()
    assert receipt.configuration_bytes == len(config)
    assert receipt.configuration_id == result.configuration_id
    assert receipt.producer_source_sha256 == hashlib.sha256(
        Path(producer.__file__).read_bytes()
    ).hexdigest()
    assert receipt.inventory_activation == "NOT_PERFORMED_BY_PRODUCER"
    assert receipt.rules_activation == "NOT_PERFORMED_BY_PRODUCER"
    assert receipt.application_launch == "NOT_PERFORMED_BY_PRODUCER"
    assert receipt.reader_admission == "COLD_AUDIT_PASSED"
    assert started <= datetime.fromisoformat(receipt.started_at)
    assert datetime.fromisoformat(receipt.completed_at) <= finished
    assert [len(refs) for refs in requested] == [50, 50]
    assert len(set(requested[0] + requested[1])) == 100
    assert len(units) == 2 and units[0] is units[1]
    assert stored_state(case.store) == before
    assert set(path.name for path in case.bundle_dir.iterdir()) == {
        "receipt.json", "pending-viewing-configuration.json"
    }


def test_exact_retry_reaudits_but_preserves_original_receipt_bytes_and_times(
    restored_bundle_case: RestoredBundleCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = restored_bundle_case
    admitted: list[str] = []
    original = CompactInventoryReader.admit

    def admit(reader: CompactInventoryReader, snapshot_id: str) -> AuditReceipt:
        admitted.append(snapshot_id)
        return original(reader, snapshot_id)

    monkeypatch.setattr(CompactInventoryReader, "admit", admit)
    first = case.produce()
    raw = (case.bundle_dir / "receipt.json").read_bytes()
    second = case.produce()
    assert first.publication == "created" and second.publication == "reused"
    assert first.receipt_sha256 == second.receipt_sha256
    assert first.configuration_id == second.configuration_id
    assert (case.bundle_dir / "receipt.json").read_bytes() == raw
    assert admitted == [case.request.expected_inventory.snapshot_id] * 2


def test_configuration_only_retry_publishes_receipt_without_replacing_configuration(
    restored_bundle_case: RestoredBundleCase,
) -> None:
    case = restored_bundle_case
    case.produce()
    config_path = case.bundle_dir / "pending-viewing-configuration.json"
    config, identity = config_path.read_bytes(), config_path.stat().st_ino
    (case.bundle_dir / "receipt.json").unlink()
    result = case.produce()
    assert result.publication == "created"
    assert config_path.read_bytes() == config and config_path.stat().st_ino == identity
    assert hashlib.sha256((case.bundle_dir / "receipt.json").read_bytes()).hexdigest() == (
        result.receipt_sha256
    )


def test_receipt_without_configuration_is_not_repaired(
    restored_bundle_case: RestoredBundleCase,
) -> None:
    case = restored_bundle_case
    case.produce()
    receipt = (case.bundle_dir / "receipt.json").read_bytes()
    config_path = case.bundle_dir / "pending-viewing-configuration.json"
    config_path.unlink()
    with pytest.raises(producer.RestoredBundleError, match="RESTORED_BUNDLE_CONFIGURATION_MISSING"):
        case.produce()
    assert not config_path.exists()
    assert (case.bundle_dir / "receipt.json").read_bytes() == receipt


@pytest.mark.parametrize("mutation", ["duplicate", "producer", "cross_request", "partial"])
def test_existing_receipt_conflict_is_retained_after_fresh_audit(
    restored_bundle_case: RestoredBundleCase,
    mutation: str,
) -> None:
    case = restored_bundle_case
    case.produce()
    path = case.bundle_dir / "receipt.json"
    raw = path.read_bytes()
    material = json.loads(raw)
    if mutation == "duplicate":
        changed = b'{"format":"restored-inventory-viewing-bundle-1",' + raw[1:]
    elif mutation == "producer":
        material["producer_source_sha256"] = "0" * 64
        changed = canonical(material)
    elif mutation == "cross_request":
        operation_id = str(uuid4())
        material["request"]["operation_id"] = operation_id
        material["request"]["bundle"] = case.request.bundle.rsplit("/", 1)[0] + "/" + operation_id
        changed = canonical(material)
    else:
        changed = raw[:17]
    path.write_bytes(changed)
    before = stored_state(case.store)
    with pytest.raises(producer.RestoredBundleError, match="RESTORED_BUNDLE_RECEIPT_"):
        case.produce()
    assert path.read_bytes() == changed
    assert stored_state(case.store) == before


@pytest.mark.parametrize("mutation", ["revision", "mapping", "payload"])
def test_inventory_changes_after_audit_before_final_read_close_publication(
    restored_bundle_case: RestoredBundleCase,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    case = restored_bundle_case
    original = CompletedRestoreScope.revalidate
    applied: list[str] = []

    def revalidate(scope: CompletedRestoreScope) -> CompletedRestoreObservation:
        observed = original(scope)
        if not applied:
            statements: dict[str, tuple[str, tuple[object, ...]]] = {
                "revision": ("UPDATE active_inventory SET revision=revision+1 WHERE id=1", ()),
                "mapping": (
                    "UPDATE vehicle_resources SET mapping_version='different-reviewed-version' "
                    "WHERE id=(SELECT resource_id FROM listing_resource_mappings LIMIT 1)",
                    (),
                ),
                "payload": (
                    "UPDATE inventory_snapshot_payloads SET payload_sha256=? WHERE snapshot_id=?",
                    ("0" * 64, case.request.expected_inventory.snapshot_id),
                ),
            }
            sql(case.store, (statements[mutation],))
            applied.append(mutation)
        return observed

    monkeypatch.setattr(CompletedRestoreScope, "revalidate", revalidate)
    with pytest.raises(producer.RestoredBundleError):
        case.produce()
    assert applied == [mutation]
    assert not case.bundle_dir.exists()


def test_final_scalar_fence_rejects_valid_stage_change_between_active_and_admit(
    restored_bundle_case: RestoredBundleCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = restored_bundle_case
    original = CompactInventoryReader.admit
    admitted: list[str] = []

    def change_then_admit(reader: CompactInventoryReader, snapshot_id: str) -> AuditReceipt:
        def write(db: Session) -> None:
            connection = db.connection()
            row = connection.exec_driver_sql(
                "SELECT payload_json FROM inventory_snapshot_payloads WHERE snapshot_id=?",
                (snapshot_id,),
            ).one()
            payload = json.loads(row[0])
            payload["policy_version"] = "test-restored-other-policy"
            encoded = canonical(payload)
            connection.exec_driver_sql(
                "UPDATE inventory_snapshots SET policy_version=? WHERE snapshot_id=?",
                (payload["policy_version"], snapshot_id),
            )
            connection.exec_driver_sql(
                "UPDATE inventory_snapshot_payloads SET payload_json=?,payload_sha256=? "
                "WHERE snapshot_id=?",
                (encoded.decode("utf-8"), hashlib.sha256(encoded).hexdigest(), snapshot_id),
            )

        case.store.write(write)
        result = original(reader, snapshot_id)
        admitted.append(snapshot_id)
        return result

    monkeypatch.setattr(CompactInventoryReader, "admit", change_then_admit)
    with pytest.raises(producer.RestoredBundleError, match="^RESTORED_BUNDLE_INVENTORY_CHANGED$"):
        case.produce()
    assert admitted == [case.request.expected_inventory.snapshot_id]
    assert not case.bundle_dir.exists()


def test_scope_exit_failure_retains_published_files_without_success_return(
    restored_bundle_case: RestoredBundleCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = restored_bundle_case
    original = producer.completed_restore_scope
    finished: list[bool] = []

    @contextmanager
    def failing_exit(
        path: Path,
        *,
        boundary: RuntimeBoundary,
        restore_id: str,
        expected_receipt_sha256: str,
        expected_generation: str,
    ) -> Iterator[CompletedRestoreScope]:
        with original(
            path,
            boundary=boundary,
            restore_id=restore_id,
            expected_receipt_sha256=expected_receipt_sha256,
            expected_generation=expected_generation,
        ) as scope:
            yield scope
        finished.append(True)
        raise RestoreCompletionError("RESTORE_COMPLETION_ASSOCIATION_CHANGED")

    with monkeypatch.context() as patch:
        patch.setattr(producer, "completed_restore_scope", failing_exit)
        with pytest.raises(
            producer.RestoredBundleError, match="RESTORED_BUNDLE_RESTORE_UNAVAILABLE"
        ):
            case.produce()
    assert finished == [True]
    raw = (case.bundle_dir / "receipt.json").read_bytes()
    result = case.produce()
    assert result.publication == "reused"
    assert result.receipt_sha256 == hashlib.sha256(raw).hexdigest()
    assert (case.bundle_dir / "receipt.json").read_bytes() == raw


def test_raw_dot_segment_is_refused_before_completion_scope(
    restored_bundle_case: RestoredBundleCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = restored_bundle_case

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Malformed raw path reached completion scope")

    monkeypatch.setattr(producer, "completed_restore_scope", forbidden)
    raw = str(case.store.path.parent) + "/ignored/../" + case.store.path.name
    with pytest.raises(producer.RestoredBundleError):
        producer.produce_restored_inventory_bundle(
            raw, boundary=case.store.boundary, project_root=case.project, request=case.request
        )
    assert not case.bundle_dir.exists()


def test_duck_request_is_rejected_without_calling_its_serializer(
    restored_bundle_case: RestoredBundleCase,
) -> None:
    case = restored_bundle_case

    class Duck:
        def model_dump(self, **kwargs: object) -> object:
            raise AssertionError("Producer invoked an untyped request")

    with pytest.raises(producer.RestoredBundleError, match="RESTORED_BUNDLE_INPUT_INVALID"):
        producer.produce_restored_inventory_bundle(
            str(case.store.path),
            boundary=case.store.boundary,
            project_root=case.project,
            request=Duck(),  # type: ignore[arg-type]
        )


def test_short_write_is_retained_and_never_reported_complete(
    publication_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = publication_directory / "receipt.json"
    original = Path.open

    class ShortWriter:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        def __enter__(self) -> "ShortWriter":
            return self

        def __exit__(self, *args: object) -> None:
            self.stream.close()

        def fileno(self) -> int:
            return int(self.stream.fileno())

        def write(self, raw: bytes) -> int:
            return int(self.stream.write(raw[:7]))

    def open_file(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = original(path, mode, *args, **kwargs)
        return ShortWriter(stream) if path == target and mode == "xb" else stream

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", open_file)
        with pytest.raises(producer.RestoredBundleError, match="RESTORED_BUNDLE_PARTIAL_WRITE"):
            producer._write_exclusive(target, b'{"complete":true}', 100)
    assert target.read_bytes() == b'{"compl'
    with pytest.raises(FileExistsError):
        producer._write_exclusive(target, b'{"complete":true}', 100)
    assert target.read_bytes() == b'{"compl'


def test_successful_exclusive_write_fsyncs_and_refuses_replacement(
    publication_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = publication_directory / "receipt.json"
    calls: list[int] = []
    original = os.fsync

    def fsync(descriptor: int) -> None:
        calls.append(descriptor)
        original(descriptor)

    monkeypatch.setattr(os, "fsync", fsync)
    producer._write_exclusive(target, b'{"complete":true}', 100)
    assert len(calls) == 1 and target.read_bytes() == b'{"complete":true}'
    with pytest.raises(FileExistsError):
        producer._write_exclusive(target, b'{"changed":true}', 100)
    assert len(calls) == 1 and target.read_bytes() == b'{"complete":true}'


def test_actual_hardlink_and_unknown_artifact_are_retained_and_rejected(
    publication_directory: Path,
) -> None:
    original = publication_directory / "receipt.json"
    original.write_bytes(b"original")
    linked = publication_directory / "linked.json"
    os.link(original, linked)
    with pytest.raises(producer.RestoredBundleError, match="RESTORED_BUNDLE_REGULAR_FILE_REQUIRED"):
        producer._read_bounded(original, 100)
    assert original.read_bytes() == linked.read_bytes() == b"original"
    linked.unlink()
    extra = publication_directory / "unexpected.json"
    extra.write_bytes(b"retain")
    with pytest.raises(producer.RestoredBundleError, match="RESTORED_BUNDLE_UNKNOWN_ARTIFACT"):
        producer._check_contents(publication_directory)
    assert extra.read_bytes() == b"retain" and original.read_bytes() == b"original"


@pytest.mark.parametrize("raw", [b"", b"x" * 101])
def test_bounded_file_reader_refuses_empty_or_oversized_bytes(
    publication_directory: Path,
    raw: bytes,
) -> None:
    target = publication_directory / "receipt.json"
    target.write_bytes(raw)
    with pytest.raises(producer.RestoredBundleError, match="RESTORED_BUNDLE_FILE_SIZE"):
        producer._read_bounded(target, 100)
    assert target.read_bytes() == raw
