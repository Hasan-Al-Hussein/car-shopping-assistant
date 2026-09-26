"""Authored I9 proof obligations; apply/run only under a separate runtime grant.

Real disposable 100-record inventory is used. Synthetic producer-format receipts
and a preexisting deny-all row are fixtures, not new production policy adoption.
"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from app.core.errors import ApiFailure
from app.database.store import Store, StoreError
from app.inventory import compact_reader
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.references import ImmutableInventoryRef
from app.operations import viewing_configuration as operation
from app.operations.viewing_configuration import (
    ActivationError,
    ActivationRequest,
    ActivationResult,
)
from app.sessions.state import canonical
from app.viewings.draft_configuration import configuration_id, eligibility_version
from app.viewings.eligibility import EligibilityPolicy
from pydantic import ValidationError
from sqlalchemy.orm import Session
from tests.operations.activation_cases import NOW, ActivationCase, business_state, sql, stored_state

from scripts import activate_viewing_configuration as cli


def next_request(case: ActivationCase, version: str | None, revision: int) -> ActivationRequest:
    return case.request.model_copy(
        update={
            "operation_id": str(uuid4()),
            "expected_active_version": version,
            "expected_revision": revision,
        }
    )


def seed_other_configuration(case: ActivationCase, revision: int) -> str:
    """Explicit preexisting synthetic state, never accepted by the public bundle gate."""
    other = case.config.model_copy(
        update={
            "eligibility": EligibilityPolicy(version="test-preexisting-deny", eligible_refs=()),
            "inventory": case.config.inventory.model_copy(update={"generation": str(uuid4())}),
        }
    )
    version = configuration_id(other)
    sql(
        case.store,
        (
            (
                "INSERT INTO rule_versions "
                "(version,policy_version,rules_json,eligibility_version,created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    version,
                    other.policy.version,
                    canonical(other.model_dump(mode="json")).decode(),
                    eligibility_version(other),
                    "2026-09-24T05:00:00.000000Z",
                ),
            ),
            (
                "INSERT INTO active_rules(id,version,revision) VALUES(1,?,?) "
                "ON CONFLICT(id) DO UPDATE SET version=excluded.version,revision=excluded.revision",
                (version, revision),
            ),
        ),
    )
    return version


def test_real_first_activation_batches_and_same_session_write_boundary(
    activation_case: ActivationCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = activation_case
    before = business_state(case.store)
    operator = case.operator()
    original_read = CompactInventoryReader.read_refs
    original_check = CompactInventoryReader.recheck_identity
    original_commit = operator._commit
    lengths: list[int] = []
    checks: list[tuple[Session, bool]] = []

    def read(
        self: CompactInventoryReader,
        refs: tuple[ImmutableInventoryRef, ...],
        *,
        expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        lengths.append(len(refs))
        return original_read(self, refs, expected_snapshot_id=expected_snapshot_id)

    def check(
        self: CompactInventoryReader,
        db: Session,
        token: tuple[str, ...],
        *,
        expected_refs: tuple[ImmutableInventoryRef, ...],
    ) -> None:
        assert token[0] == "inventory-read-1" and len(expected_refs) == 50
        checks.append((db, db.connection().get_execution_options()["store_write"]))
        original_check(self, db, token, expected_refs=expected_refs)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("external work or full-stage preparation inside WRITE")

    def commit(
        db: Session, reader: CompactInventoryReader, prepared: operation._Prepared, created_at: str
    ) -> ActivationResult:
        with monkeypatch.context() as patch:
            patch.setattr(Store, "read", forbidden)
            patch.setattr(Store, "write", forbidden)
            patch.setattr(operation, "_read_file", forbidden)
            patch.setattr(operation, "_stage_digest", forbidden)
            patch.setattr(CompactInventoryReader, "read_refs", forbidden)
            patch.setattr(compact_reader, "load_stage_set", forbidden)
            return original_commit(db, reader, prepared, created_at)

    monkeypatch.setattr(CompactInventoryReader, "read_refs", read)
    monkeypatch.setattr(CompactInventoryReader, "recheck_identity", check)
    monkeypatch.setattr(operator, "_commit", commit)
    result = operator.activate(case.request)
    assert result.changed and result.revision == 1
    assert lengths == [50, 50]
    assert [write for _, write in checks] == [False, False, True, True]
    assert checks[0][0] is checks[1][0] and checks[2][0] is checks[3][0]
    assert checks[0][0] is not checks[2][0]
    assert business_state(case.store) == before
    state = stored_state(case.store)
    assert (
        len(state["rule_versions"])
        == len(state["active_rules"])
        == len(state["operational_events"])
        == 1
    )
    assert operator.reconcile(case.request).result == result


def test_noop_requires_matching_expectations_and_preserves_immutable_row(
    activation_case: ActivationCase,
) -> None:
    case = activation_case
    operator = case.operator()
    first = operator.activate(case.request)
    before = stored_state(case.store)
    stale = next_request(case, None, 0)
    with pytest.raises(ActivationError, match="ACTIVATION_EXPECTATION_CONFLICT"):
        operator.activate(stale)
    assert stored_state(case.store) == before
    same = case.operator(now=NOW + timedelta(minutes=1)).activate(
        next_request(case, first.request.configuration_id, 1)
    )
    after = stored_state(case.store)
    assert not same.changed and same.revision == 1
    assert after["active_rules"] == before["active_rules"]
    assert after["rule_versions"] == before["rule_versions"]
    assert len(after["operational_events"]) == 2
    assert business_state(case.store) == {
        key: value
        for key, value in before.items()
        if key not in {"rule_versions", "active_rules", "operational_events"}
    }


def test_two_prepared_operators_cannot_both_advance_same_expected_pointer(
    activation_case: ActivationCase,
) -> None:
    case = activation_case
    before_business = business_state(case.store)
    rendezvous = Barrier(2, timeout=30)
    intents = (case.request, next_request(case, None, 0))

    def checkpoint(phase: str) -> None:
        if phase == "activation.prepared":
            rendezvous.wait()

    def activate(intent: ActivationRequest) -> ActivationResult | Exception:
        try:
            return case.operator(checkpoint).activate(intent)
        except (ActivationError, StoreError) as failure:
            return failure

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(activate, intents))
    successes = [item for item in results if isinstance(item, ActivationResult)]
    assert len(successes) == 1 and successes[0].revision == 1
    rejected = next(intent for intent in intents if intent != successes[0].request)
    with pytest.raises(ActivationError, match="ACTIVATION_EXPECTATION_CONFLICT"):
        case.operator().activate(rejected)
    state = stored_state(case.store)
    assert len(state["rule_versions"]) == len(state["operational_events"]) == 1
    assert business_state(case.store) == before_business


def test_a_b_a_preserves_immutable_versions_and_advances_revision(
    activation_case: ActivationCase,
) -> None:
    case = activation_case
    operator = case.operator()
    original = operator.activate(case.request)
    original_rows = stored_state(case.store)["rule_versions"]
    before_business = business_state(case.store)
    other_id = seed_other_configuration(case, 2)
    both_rows = stored_state(case.store)["rule_versions"]
    returned = case.operator(now=NOW + timedelta(minutes=2)).activate(
        next_request(case, other_id, 2)
    )
    assert returned.changed and returned.revision == 3
    assert original_rows[0] in both_rows and len(both_rows) == 2
    assert stored_state(case.store)["rule_versions"] == both_rows
    assert business_state(case.store) == before_business
    observed = operator.reconcile(case.request)
    assert observed.result == original and observed.active_revision == 3
    assert observed.active_version == original.request.configuration_id


def test_generic_empty_batch_uses_real_proof_without_adopting_new_public_permission(
    activation_case: ActivationCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = activation_case
    pending = operation._pending(case.project, case.store, case.request)
    denied = case.config.model_copy(
        update={
            "eligibility": EligibilityPolicy(version="test-only-empty-batch", eligible_refs=()),
        }
    )
    # Only the lower-level inventory preparation helper sees this synthetic policy.
    # The production _pending gate continues to require the adopted exact100 refs.
    pending = replace(pending, config=denied)
    original = CompactInventoryReader.read_refs
    batches: list[tuple[ImmutableInventoryRef, ...]] = []

    def read(
        self: CompactInventoryReader,
        refs: tuple[ImmutableInventoryRef, ...],
        *,
        expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        batches.append(refs)
        return original(self, refs, expected_snapshot_id=expected_snapshot_id)

    reader = CompactInventoryReader(case.store)
    monkeypatch.setattr(CompactInventoryReader, "read_refs", read)
    prepared = operation._prepare(case.store, reader, pending)
    assert batches == [()] and len(prepared.proofs) == 1 and not prepared.members
    reader.invalidate()
    with pytest.raises(ValueError):
        case.store.read(lambda db: operation._recheck(db, reader, prepared))
    assert not stored_state(case.store)["active_rules"]


@pytest.mark.parametrize("changed", [False, True])
def test_revision_exhaustion_never_wraps(activation_case: ActivationCase, changed: bool) -> None:
    case = activation_case
    operator = case.operator()
    operator.activate(case.request)
    if changed:
        version = seed_other_configuration(case, operation.MAX_REVISION)
    else:
        version = case.request.configuration_id
        sql(
            case.store,
            (("UPDATE active_rules SET revision=? WHERE id=1", (operation.MAX_REVISION,)),),
        )
    before = stored_state(case.store)
    request = next_request(case, version, operation.MAX_REVISION)
    if changed:
        with pytest.raises(ActivationError, match="ACTIVATION_REVISION_EXHAUSTED"):
            operator.activate(request)
        assert stored_state(case.store) == before
    else:
        result = operator.activate(request)
        assert not result.changed and result.revision == operation.MAX_REVISION


@pytest.mark.parametrize(
    "phase", ["activation.row_staged", "activation.pointer_staged", "activation.event_staged"]
)
def test_each_writer_checkpoint_rolls_back_rule_pointer_and_event(
    activation_case: ActivationCase,
    phase: str,
) -> None:
    case = activation_case
    before = stored_state(case.store)

    def interrupt(actual: str) -> None:
        if actual == phase:
            raise RuntimeError("INJECTED_ATOMIC_ROLLBACK")

    with pytest.raises(RuntimeError, match="INJECTED_ATOMIC_ROLLBACK"):
        case.operator(interrupt).activate(case.request)
    assert stored_state(case.store) == before


@pytest.mark.parametrize(
    "mutation", ["generation", "index", "mode", "revision", "mapping", "resource"]
)
def test_prepared_inventory_changes_cannot_activate_rules(
    activation_case: ActivationCase,
    mutation: str,
) -> None:
    case = activation_case
    before = stored_state(case.store)
    applied: list[str] = []

    def mutate(phase: str) -> None:
        if phase != "activation.prepared":
            return
        statements: tuple[tuple[str, tuple[object, ...]], ...]
        if mutation == "generation":
            statements = (
                ("UPDATE store_metadata SET store_generation=? WHERE id=1", (str(uuid4()),)),
            )
        elif mutation == "index":
            statements = (
                ("PRAGMA defer_foreign_keys=ON", ()),
                ("UPDATE inventory_snapshots SET index_version=?", ("0" * 64,)),
                ("UPDATE active_inventory SET index_version=?", ("0" * 64,)),
                ("UPDATE inventory_search_documents SET index_version=?", ("0" * 64,)),
            )
        elif mutation == "mode":
            statements = (
                (
                    "UPDATE inventory_storage_profile SET mode=CASE mode WHEN 'fts5' "
                    "THEN 'bounded_lexical' ELSE 'fts5' END WHERE id=1",
                    (),
                ),
            )
        elif mutation == "revision":
            statements = (("UPDATE active_inventory SET revision=revision+1 WHERE id=1", ()),)
        elif mutation == "mapping":
            statements = (("UPDATE listing_resource_mappings SET mapping_version='changed'", ()),)
        else:
            statements = (("UPDATE vehicle_resources SET mapping_version='changed'", ()),)
        sql(case.store, statements)
        applied.append(mutation)

    with pytest.raises((ActivationError, ApiFailure, StoreError, ValueError)):
        case.operator(mutate).activate(case.request)
    assert applied == [mutation]
    assert stored_state(case.store) == before


@pytest.mark.parametrize(
    "mutation",
    ["missing_default", "unsorted", "duplicate", "oversized", "empty_permission", "mapping"],
)
def test_recomputed_bundle_hashes_do_not_authorize_invalid_or_unadopted_config(
    activation_case: ActivationCase,
    mutation: str,
) -> None:
    case = activation_case
    before = stored_state(case.store)
    material = case.config.model_dump(mode="json")
    if mutation == "missing_default":
        del material["policy"]["capacity"]
    elif mutation == "unsorted":
        material["eligibility"]["eligible_refs"].reverse()
    elif mutation == "empty_permission":
        material["eligibility"]["eligible_refs"] = []
    elif mutation == "mapping":
        material["mapping_digest"] = "0" * 64
    raw = canonical(material)
    if mutation == "duplicate":
        raw = b'{"format":"viewing-configuration-1",' + raw[1:]
    elif mutation == "oversized":
        raw = b" " * 65_537
    if mutation in {"empty_permission", "mapping"}:
        changed = case.config.model_validate_json(raw)
        request = case.repack(
            raw,
            eligibility_version=eligibility_version(changed),
            mapping_digest=changed.mapping_digest,
        )
    else:
        request = case.repack(raw)
    with pytest.raises((ActivationError, ApiFailure, ValidationError)):
        case.operator().activate(request)
    assert stored_state(case.store) == before


@pytest.mark.parametrize(
    "mutation", ["producer", "source_hash", "destination", "receipt_duplicate", "receipt_size"]
)
def test_receipt_provenance_and_target_fail_closed(
    activation_case: ActivationCase, mutation: str
) -> None:
    case = activation_case
    before = stored_state(case.store)
    if mutation == "producer":
        case.receipt["bootstrap_source_sha256"] = "0" * 64
    elif mutation == "source_hash":
        case.receipt["input_hashes"] = {
            **case.receipt["input_hashes"],
            operation.WORKBOOK: "0" * 64,
        }
    elif mutation == "destination":
        case.receipt["destination"] = str(case.store.path.parent / "missing.sqlite3")
    raw = canonical(case.receipt)
    if mutation == "receipt_duplicate":
        raw = b'{"simulation_only":true,' + raw[1:]
    elif mutation == "receipt_size":
        raw = b" " * (operation.MAX_RECEIPT_BYTES + 1)
    (case.project / case.request.bundle / "receipt.json").write_bytes(raw)
    request = case.request.model_copy(update={"receipt_sha256": hashlib.sha256(raw).hexdigest()})
    with pytest.raises((ActivationError, OSError, ValueError)):
        case.operator().activate(request)
    assert stored_state(case.store) == before


@pytest.mark.parametrize(
    "producer",
    [
        "1c89258d0b75455f2f64af7397a3b26c3d5c995bc7821a68f362cb38e1b265c8",
        "e707efa672e0e3153af89c7a092eb2b3153c7e6fa73ba900c490a2c8a39cf318",
    ],
)
def test_explicitly_reviewed_producers_retain_identical_adoption_requirements(
    activation_case: ActivationCase,
    producer: str,
) -> None:
    case = activation_case
    request = case.repack(
        canonical(case.config.model_dump(mode="json")),
        bootstrap_source_sha256=producer,
    )
    before = stored_state(case.store)
    pending = operation._pending(case.project, case.store, request)
    assert pending.receipt.bootstrap_source_sha256 == producer
    assert pending.config == case.config
    assert len(pending.config.eligibility.eligible_refs) == 100
    assert stored_state(case.store) == before


def test_immutable_existing_target_is_not_repaired(activation_case: ActivationCase) -> None:
    case = activation_case
    operator = case.operator()
    operator.activate(case.request)
    sql(
        case.store,
        (
            (
                "UPDATE rule_versions SET rules_json='{}' WHERE version=?",
                (case.request.configuration_id,),
            ),
        ),
    )
    before = stored_state(case.store)
    with pytest.raises(ApiFailure):
        operator.activate(next_request(case, case.request.configuration_id, 1))
    assert stored_state(case.store) == before


def test_postcommit_receipt_loss_reconciles_original_event_after_pointer_moves(
    activation_case: ActivationCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = activation_case
    before_business = business_state(case.store)

    def fail_receipt(phase: str) -> None:
        if phase == "receipt.before_write":
            raise OSError("INJECTED_RECEIPT_FAILURE")

    operator = case.operator(fail_receipt)
    result = operator.activate(case.request)
    with pytest.raises(OSError, match="INJECTED_RECEIPT_FAILURE"):
        operator.publish_receipt(result)
    other = seed_other_configuration(case, 2)
    before = stored_state(case.store)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("terminal event replay must bypass pending material and admission")

    monkeypatch.setattr(operation, "_pending", forbidden)
    observed = operator.reconcile(case.request)
    assert (
        observed.result == result
        and observed.active_version == other
        and observed.active_revision == 2
    )
    assert operator.activate(case.request) == result
    changed = case.request.model_copy(
        update={"expected_active_version": other, "expected_revision": 2}
    )
    with pytest.raises(ActivationError, match="ACTIVATION_OPERATION_ID_CONFLICT"):
        operator.activate(changed)
    assert stored_state(case.store) == before
    assert business_state(case.store) == before_business
    unknown = operator.reconcile(next_request(case, other, 2))
    assert unknown.result is None and stored_state(case.store) == before


def test_receipt_publication_reuses_exact_bytes_and_refuses_conflicting_file(
    activation_case: ActivationCase,
) -> None:
    case = activation_case
    operator = case.operator()
    result = operator.activate(case.request)
    before = stored_state(case.store)
    path = operator.publish_receipt(result)
    expected = canonical(
        {
            "format": "viewing-activation-receipt-1",
            "result": result.model_dump(mode="json"),
        }
    )
    assert path == case.project / (
        "Records/operations/viewing-configurations/" + case.request.operation_id + ".json"
    )
    assert path.read_bytes() == expected
    assert operator.publish_receipt(result) == path and path.read_bytes() == expected
    path.write_bytes(b"existing-partial-receipt")
    with pytest.raises(ActivationError, match="ACTIVATION_RECEIPT_CONFLICT"):
        operator.publish_receipt(result)
    assert path.read_bytes() == b"existing-partial-receipt"
    assert operator.reconcile(case.request).result == result
    assert stored_state(case.store) == before


def test_partial_receipt_write_preserves_original_committed_outcome(
    activation_case: ActivationCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = activation_case
    operator = case.operator()
    result = operator.activate(case.request)
    before = stored_state(case.store)
    target = case.project / (
        "Records/operations/viewing-configurations/" + case.request.operation_id + ".json"
    )
    original_open = Path.open

    class PartialWrite:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        def __enter__(self) -> "PartialWrite":
            return self

        def __exit__(self, *args: object) -> None:
            self.stream.close()

        def write(self, raw: bytes) -> None:
            self.stream.write(raw[:17])
            self.stream.flush()
            raise OSError("INJECTED_PARTIAL_RECEIPT")

    def open_file(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = original_open(path, mode, *args, **kwargs)
        return PartialWrite(stream) if path == target and mode == "xb" else stream

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", open_file)
        with pytest.raises(OSError, match="INJECTED_PARTIAL_RECEIPT"):
            operator.publish_receipt(result)
    partial = target.read_bytes()
    assert len(partial) == 17
    with pytest.raises(ActivationError, match="ACTIVATION_RECEIPT_CONFLICT"):
        operator.publish_receipt(result)
    assert target.read_bytes() == partial
    assert operator.reconcile(case.request).result == result
    assert stored_state(case.store) == before


def test_changed_pinned_adoption_is_not_replaced_by_bundle_claims(
    activation_case: ActivationCase,
) -> None:
    case = activation_case
    source = case.project / (operation.ADOPTED + "adoption.json")
    original = source.read_bytes()
    changed = original.replace(b"ADOPTED", b"AD0PTED", 1)
    assert changed != original and len(changed) == len(original)
    before = stored_state(case.store)
    try:
        source.write_bytes(changed)
        with pytest.raises(ActivationError, match="ADOPTED_SOURCE_CHANGED"):
            case.operator().activate(case.request)
        assert stored_state(case.store) == before
    finally:
        # This is the disposable copied fixture file, never original G03 source.
        source.write_bytes(original)


@pytest.mark.parametrize("mutation", ["oversized", "duplicate", "revision", "other_event_type"])
def test_original_event_is_bounded_and_validated_before_reconciliation(
    activation_case: ActivationCase,
    mutation: str,
) -> None:
    case = activation_case
    operator = case.operator()
    result = operator.activate(case.request)
    raw = canonical(
        operation._Event(format="viewing-activation-event-1", result=result).model_dump(mode="json")
    )
    if mutation == "oversized":
        raw = b" " * (operation.MAX_EVENT_BYTES + 1)
    elif mutation == "duplicate":
        raw = b'{"format":"viewing-activation-event-1",' + raw[1:]
    elif mutation == "revision":
        value = json.loads(raw)
        value["result"]["revision"] = 2
        raw = canonical(value)
    sql(
        case.store,
        (
            (
                "UPDATE operational_events SET source_reference=? WHERE id=?",
                (raw.decode(), case.request.operation_id),
            ),
        ),
    )
    if mutation == "other_event_type":
        sql(
            case.store,
            (
                (
                    "UPDATE operational_events SET event_type='unrelated_operator_event' "
                    "WHERE id=?",
                    (case.request.operation_id,),
                ),
            ),
        )
    before = stored_state(case.store)
    with pytest.raises(ActivationError):
        operator.reconcile(case.request)
    assert stored_state(case.store) == before


def test_cli_preserves_raw_store_path_and_reports_postcommit_receipt_failure(
    activation_case: ActivationCase,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = activation_case
    boundary = case.store.boundary
    monkeypatch.setenv("CSA_RUNTIME_ROOT", str(boundary.logical_root))
    monkeypatch.setenv("CSA_RUNTIME_PHYSICAL_ROOT", str(boundary.physical_root))
    monkeypatch.setattr(cli, "PROJECT", case.project)
    request = case.request
    args = [
        "activate",
        "--store",
        str(case.store.path),
        "--operation-id",
        request.operation_id,
        "--expected-generation",
        request.generation,
        "--configuration-id",
        request.configuration_id,
        "--expected-active-configuration",
        "absent",
        "--expected-revision",
        "0",
        "--bundle",
        request.bundle,
        "--receipt-sha256",
        request.receipt_sha256,
    ]
    invalid = list(args)
    invalid[2] = str(case.store.path.parent) + "\\.\\" + case.store.path.name
    before = stored_state(case.store)
    assert cli.main(invalid) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "ACTIVATION_NOT_CONFIRMED"
    assert stored_state(case.store) == before

    def lose_receipt(
        self: operation.ViewingConfigurationOperator, result: ActivationResult
    ) -> None:
        raise OSError("SYNTHETIC_AFTER_COMMIT")

    monkeypatch.setattr(operation.ViewingConfigurationOperator, "publish_receipt", lose_receipt)
    assert cli.main(args) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ACTIVATION_COMMITTED_RECEIPT_UNAVAILABLE"
    assert output["result"]["request"]["operation_id"] == request.operation_id
    assert case.operator().reconcile(request).result is not None


@pytest.mark.parametrize(
    "bundle",
    [
        "../outside",
        "Records/build/BE-05/I7/runs/../other",
        "C:/arbitrary",
        "Records/build/BE-05/I7/runs/folder/child",
    ],
)
def test_bundle_paths_are_rejected_before_file_access(bundle: str) -> None:
    with pytest.raises(ValidationError):
        ActivationRequest(
            operation_id=str(uuid4()),
            generation=str(uuid4()),
            configuration_id="viewing-config-1:" + "0" * 64,
            expected_active_version=None,
            expected_revision=0,
            bundle=bundle,
            receipt_sha256="0" * 64,
        )


@pytest.mark.parametrize("revision", [True, False, -1, operation.MAX_REVISION + 1, "0"])
def test_expected_revision_requires_bounded_integer(revision: object) -> None:
    with pytest.raises(ValidationError):
        ActivationRequest.model_validate(
            {
                "operation_id": str(uuid4()),
                "generation": str(uuid4()),
                "configuration_id": "viewing-config-1:" + "0" * 64,
                "expected_active_version": None,
                "expected_revision": revision,
                "bundle": "Records/build/BE-05/I7/runs/invalid-revision",
                "receipt_sha256": "0" * 64,
            }
        )


def test_project_file_reader_rejects_actual_hardlink(operator_project: Path) -> None:
    relative = "Records/build/BE-05/I7/runs/hardlink-" + str(uuid4())
    folder = operator_project / relative
    folder.mkdir(parents=True)
    source = folder / "original.json"
    source.write_bytes(b"{}")
    assert operation._read_file(operator_project, relative + "/original.json", 2) == b"{}"
    linked = folder / "receipt.json"
    linked.hardlink_to(source)
    with pytest.raises(ActivationError, match="OPERATOR_FILE_HARDLINK"):
        operation._read_file(operator_project, relative + "/receipt.json", 2)
