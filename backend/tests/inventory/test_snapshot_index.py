"""Real persisted FTS and explicitly injected absence use exact reviewed corpus oracles."""

from pathlib import Path

import pytest

from app.core.readiness import ReadinessRegistry
from app.database import store as store_module
from app.database.store import Store, StoreError, initialize_store, open_store
from app.inventory import lexical_index
from app.inventory.extraction import ExtractedCandidate
from app.inventory.index_storage import matching_ids
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage, prepare_stage
from tests.inventory.snapshot_cases import execute, record_evidence
from tests.support.harness import configured_runtime_boundary

# Independently read across all 100 accepted reviews; not computed from the index being tested.
ORACLES = {"toyota": ("61", "76", "91", "95", "98"), "كاميرا": ("19", "26"), "707": ("22",)}


def matches(store: Store, plan: PreparedStage) -> dict[str, tuple[str, ...]]:
    return store.read(
        lambda session: {term: matching_ids(session, plan.index, term) for term in ORACLES}
    )


def test_real_fts_corpus_membership_and_snapshot_isolation(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    assert lexical_index.detect_fts5() is True
    assert inventory_store.inventory_mode == snapshot_plan.index.mode == "fts5"
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.stage(second_plan)
    assert matches(inventory_store, snapshot_plan) == ORACLES
    assert matches(inventory_store, second_plan) == ORACLES
    assert (
        inventory_store.read(
            lambda session: matching_ids(session, snapshot_plan.index, "synthetic")
        )
        == ()
    )
    assert inventory_store.read(
        lambda session: matching_ids(session, second_plan.index, "synthetic")
    ) == ("12",)
    record_evidence(
        "real-fts-oracles",
        {
            "actual_functional_fts5_probe": True,
            "oracles": ORACLES,
            "snapshot_isolation": True,
            "mode": snapshot_plan.index.mode,
        },
    )


def test_injected_absence_fallback_is_versioned_complete_and_explicitly_degraded(
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
        repo = InventoryRepository(store)
        repo.stage(plan)
        repo.activate(plan.index.snapshot_id, expected_revision=0)
        reopened = InventoryRepository(open_store(inventory_store_path, boundary=store.boundary))
        assert reopened.active().stage == plan
        assert matches(store, plan) == ORACLES
        assert matches(store, plan) == ORACLES
        registry = ReadinessRegistry()
        repo.refresh(registry)
        assert registry.snapshot().inventory == "degraded"
        assert registry.snapshot().active_snapshot_id == plan.index.snapshot_id
    with pytest.raises(StoreError, match="CAPABILITY_INCOMPATIBLE"):
        open_store(inventory_store_path, boundary=store.boundary)
    record_evidence(
        "injected-absence-oracles",
        {
            "simulated_absence_not_host_capability": True,
            "oracles": ORACLES,
            "snapshot": plan.index.snapshot_id,
            "index": plan.index.version,
            "mode": plan.index.mode,
            "ready_state": "degraded",
            "capable_reopen_rejected": True,
        },
    )


def test_missing_fts_table_is_an_operational_failure_not_fallback(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    execute(inventory_store, "DROP TABLE inventory_search_fts")
    with pytest.raises(StoreError, match="SCHEMA_STRUCTURE_INCOMPATIBLE"):
        repo.active()


def test_capability_probe_errors_propagate_and_probe_cannot_run_inside_write(
    inventory_store: Store,
    snapshot_candidate: ExtractedCandidate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail() -> bool:
        calls.append("probe")
        raise PermissionError("SYNTHETIC_PROBE_OPERATIONAL_FAILURE")

    monkeypatch.setattr(lexical_index, "shared_detect_fts5", fail)
    with pytest.raises(StoreError, match="EXTERNAL_WORK_INSIDE_WRITE"):
        inventory_store.write(lambda session: lexical_index.detect_fts5())
    assert calls == []
    with pytest.raises(PermissionError, match="SYNTHETIC"):
        prepare_stage(snapshot_candidate, policy_version="DEMO-POLICY-1")
    assert calls == ["probe"]


def test_prepared_fallback_is_not_admitted_to_an_fts_profile(
    inventory_store: Store,
    snapshot_candidate: ExtractedCandidate,
) -> None:
    plan = prepare_stage(
        snapshot_candidate, policy_version="DEMO-POLICY-1", capability_probe=lambda: False
    )
    with pytest.raises(ValueError, match="CAPABILITY_PROFILE_MISMATCH"):
        InventoryRepository(inventory_store).stage(plan)
