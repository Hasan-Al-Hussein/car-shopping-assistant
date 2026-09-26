"""Exact bounded projections and lifecycle isolation; no execution on import."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from tests.support.harness import configured_runtime_boundary
from sqlalchemy import create_engine
from sqlalchemy.exc import UnboundExecutionError
from sqlalchemy.orm import Session

from app.core.readiness import InventoryObservation, ReadinessRegistry
from app.database import store as store_module
from app.database.paths import RuntimeBoundary
from app.database.store import Store, initialize_store
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.extraction import ExtractedCandidate
from app.inventory.snapshot_codec import ListingRow
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage, prepare_stage
from tests.inventory.compact_cases import admitted, admitted_pair
from tests.inventory.snapshot_cases import record_evidence


def test_full_corpus_equivalence_is_bounded_and_never_reaudits_warm_reads(
    inventory_store: Store, snapshot_plan: PreparedStage, monkeypatch: pytest.MonkeyPatch
) -> None:
    statements: list[str] = []
    store = replace(inventory_store, trace=statements.append)
    reader, observation = admitted(store, snapshot_plan)
    original_bytes = store.path.read_bytes()
    statements.clear()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("WARM_READ_RECONSTRUCTED_CANDIDATE")

    for target in (
        "app.inventory.compact_reader.load_stage_set",
        "app.inventory.snapshot_codec.decode_candidate",
        "app.inventory.extraction.extract_reviewed",
        "app.inventory.normalization.normalize_candidate",
    ):
        monkeypatch.setattr(target, forbidden)
    listings = snapshot_plan.candidate.listings
    assert len(listings) == 100
    returned: list[ListingRow | None] = []
    for offset in (0, 50):
        expected = listings[offset : offset + 50]
        batch = reader.read_refs(tuple(row.ref for row in expected))
        assert batch.observation == observation
        assert tuple(item.listing for item in batch.items) == expected
        assert all(item.state == "current" for item in batch.items)
        assert len(batch.identity) <= 128 and all(len(part) <= 512 for part in batch.identity)
        returned.extend(item.listing for item in batch.items)

        def recheck(session: Session, prepared: CompactBatch = batch) -> None:
            reader.recheck(session, prepared)

        store.read(recheck)
        store.write(recheck)
    assert tuple(returned) == listings
    assert reader.read_header() == observation
    assert store.path.read_bytes() == original_bytes
    assert not any(
        sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP"))
        for sql in statements
    )
    record_evidence(
        "i5-full-corpus-equivalence",
        {
            "rows": 100,
            "batch_limit": 50,
            "exact_listing_row_equality": True,
            "warm_audit_extraction_normalization_forbidden": True,
            "same_unit_read_and_write_recheck": True,
            "database_bytes_unchanged": True,
            "sql_statement_count": len(statements),
        },
    )


def test_exact_history_missing_order_and_stale_requests_preserve_current_admission(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage
) -> None:
    reader, old = admitted_pair(inventory_store, snapshot_plan, second_plan)
    first_ref = snapshot_plan.candidate.manifest.reference("12")
    second_ref = second_plan.candidate.manifest.reference("12")
    previous = reader.read_refs((first_ref,))
    current = InventoryRepository(inventory_store).activate(
        second_plan.index.snapshot_id, expected_revision=old.active_revision
    )
    with pytest.raises(ValueError, match="EXPECTED_SNAPSHOT_CHANGED"):
        reader.read_refs((), expected_snapshot_id=snapshot_plan.index.snapshot_id)
    assert reader.read_header() == current
    with pytest.raises(ValueError, match="READ_IDENTITY_STALE"):
        inventory_store.write(lambda session: reader.recheck(session, previous))
    assert reader.read_header() == current
    missing = second_plan.candidate.manifest.reference("not-present")
    wrong_namespace = first_ref.model_copy(update={"namespace": "different-source"})
    refs = (second_ref, first_ref, missing, wrong_namespace, second_ref)
    batch = reader.read_refs(refs, expected_snapshot_id=second_plan.index.snapshot_id)
    assert tuple(item.ref for item in batch.items) == refs
    assert tuple(item.state for item in batch.items) == (
        "current",
        "historical",
        "missing",
        "missing",
        "current",
    )
    assert batch.observation == current
    assert batch.items[0].listing == next(
        row for row in second_plan.candidate.listings if row.ref == second_ref
    )
    assert batch.items[1].listing == next(
        row for row in snapshot_plan.candidate.listings if row.ref == first_ref
    )
    assert batch.items[0].listing != batch.items[1].listing
    assert batch.items[2].listing is None and batch.items[3].listing is None
    empty = reader.read_refs((), expected_snapshot_id=second_plan.index.snapshot_id)
    inventory_store.read(
        lambda session: reader.recheck_identity(session, empty.identity, expected_refs=())
    )


def test_restart_eviction_and_cold_historical_miss_do_not_revoke_other_admission(
    inventory_store: Store, snapshot_plan: PreparedStage, second_plan: PreparedStage
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.stage(second_plan)
    active = repo.activate(second_plan.index.snapshot_id, expected_revision=0)
    reader = CompactInventoryReader(inventory_store, capacity=1)
    reader.admit(snapshot_plan.index.snapshot_id)
    reader.admit(second_plan.index.snapshot_id)
    with pytest.raises(ValueError, match="AUDIT_ADMISSION_REQUIRED"):
        reader.read_refs((snapshot_plan.candidate.manifest.reference("12"),))
    assert reader.read_header() == active
    with pytest.raises(ValueError, match="AUDIT_ADMISSION_REQUIRED"):
        CompactInventoryReader(inventory_store).read_header()
    reader.invalidate()
    with pytest.raises(ValueError, match="AUDIT_ADMISSION_REQUIRED"):
        reader.read_header()
    reader.admit(second_plan.index.snapshot_id)
    assert reader.read_header() == active


def test_forged_batch_token_or_ref_cannot_bypass_existing_unit_contract(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    reader, observation = admitted(inventory_store, snapshot_plan)
    ref = snapshot_plan.candidate.manifest.reference("12")
    batch = reader.read_refs((ref,))
    with pytest.raises(ValueError, match="READ_IDENTITY_INVALID"):
        inventory_store.read(lambda session: reader.recheck(session, replace(batch, items=())))
    with pytest.raises(ValueError, match="READ_IDENTITY_INVALID"):
        inventory_store.write(
            lambda session: reader.recheck_identity(
                session, (*batch.identity[:-1], "0" * 64), expected_refs=(ref,)
            )
        )
    with pytest.raises(ValueError, match="READ_IDENTITY_INVALID"):
        inventory_store.read(
            lambda session: reader.recheck_identity(session, batch.identity, expected_refs=())
        )
    with Session() as unbound, pytest.raises(UnboundExecutionError):
        reader.recheck(unbound, batch)
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection, Session(bind=connection) as unowned:
            assert not connection.in_transaction()
            with pytest.raises(ValueError, match="EXISTING_STORE_UNIT_REQUIRED"):
                reader.recheck(unowned, batch)
    finally:
        engine.dispose()
    assert reader.read_header() == observation


@pytest.mark.parametrize("failure", ["open", "publish"])
def test_failed_refresh_invalidates_even_after_successful_observer(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    registry = ReadinessRegistry()
    reader.refresh(registry)

    if failure == "open":

        def fail_open(path: Path, *, boundary: RuntimeBoundary) -> Store:
            assert boundary is inventory_store.boundary
            raise OSError("synthetic fresh open failure")

        monkeypatch.setattr("app.inventory.compact_reader.open_store", fail_open)
    else:

        def fail_publish(observe: Callable[[], InventoryObservation]) -> None:
            assert observe().snapshot_id == snapshot_plan.index.snapshot_id
            raise RuntimeError("synthetic publication failure")

        monkeypatch.setattr(registry, "refresh_inventory", fail_publish)
    with pytest.raises((OSError, RuntimeError), match="synthetic"):
        reader.refresh(registry)
    if failure == "open":
        assert registry.snapshot().inventory == "unavailable"
    with pytest.raises(ValueError, match="AUDIT_ADMISSION_REQUIRED"):
        reader.read_header()


def test_empty_store_header_is_coherent_and_has_no_fabricated_reference(
    inventory_store: Store, snapshot_plan: PreparedStage
) -> None:
    reader = CompactInventoryReader(inventory_store)
    batch = reader.read_refs((snapshot_plan.candidate.manifest.reference("12"),))
    assert batch.observation.active_revision == 0
    assert batch.observation.snapshot_id is None
    assert batch.items[0].state == "missing" and batch.items[0].listing is None
    inventory_store.read(lambda session: reader.recheck(session, batch))


def test_reference_batch_rejects_fifty_one_before_database_read(
    inventory_store: Store, snapshot_plan: PreparedStage, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = CompactInventoryReader(inventory_store)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("OVERSIZE_BATCH_ENTERED_STORE")

    monkeypatch.setattr(Store, "read", forbidden)
    ref = snapshot_plan.candidate.manifest.reference("12")
    with pytest.raises(ValueError, match="REFERENCE_BATCH_LIMIT"):
        reader.read_refs((ref,) * 51)


def test_declared_lexical_profile_remains_explicit_and_equivalent(
    inventory_store_path: Path,
    snapshot_candidate: ExtractedCandidate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as absent:
        absent.setattr(store_module, "detect_fts5", lambda: False)
        absent.setattr(store_module, "fts5_registered", lambda _: False)
        store = initialize_store(inventory_store_path, boundary=configured_runtime_boundary())
        plan = prepare_stage(
            snapshot_candidate, policy_version="DEMO-POLICY-1", capability_probe=lambda: False
        )
        reader, observation = admitted(store, plan)
        assert observation.mode == "bounded_lexical"
        rows = plan.candidate.listings[:5]
        assert (
            tuple(item.listing for item in reader.read_refs(tuple(row.ref for row in rows)).items)
            == rows
        )
        registry = ReadinessRegistry()
        reader.refresh(registry)
        assert registry.snapshot().inventory == "degraded"
