"""Fresh observations preserve independent state and materialize one coherent snapshot."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, local

import pytest

from app.core.readiness import InventoryObservation, ProviderObservation, ReadinessRegistry
from app.database.paths import RuntimeBoundary
from app.database.store import Store, open_store
from app.inventory import snapshots
from app.inventory.snapshots import InventoryRepository, observe_inventory
from app.inventory.staging_plan import PreparedStage
from tests.inventory.snapshot_cases import NOW, execute, record_evidence
from tests.support.harness import configured_runtime_boundary


def test_readonly_fresh_refresh_preserves_concurrent_independent_observations(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = InventoryRepository(inventory_store)
    registry = ReadinessRegistry()
    repo.refresh(registry)
    assert registry.snapshot().inventory == "unconfigured"
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    statements: list[str] = []
    opens: list[Path] = []
    provider = ProviderObservation(state="ready", observed_at=NOW)

    def fresh_open(path: Path, *, boundary: RuntimeBoundary) -> Store:
        assert boundary is inventory_store.boundary
        opens.append(path)
        registry.update(
            lambda current: current.model_copy(
                update={
                    "provider": provider,
                    "export": "ready",
                    "viewing": "ready",
                }
            )
        )
        return open_store(path, boundary=boundary, trace=statements.append)

    monkeypatch.setattr(snapshots, "open_store", fresh_open)
    before = inventory_store.path.read_bytes()
    repo.refresh(registry)
    repo.refresh(registry)
    published = registry.snapshot()
    assert opens == [inventory_store.path, inventory_store.path]
    assert (
        published.inventory == "ready"
        and published.active_snapshot_id == snapshot_plan.index.snapshot_id
    )
    assert published.provider == provider and published.export == published.viewing == "ready"
    assert inventory_store.path.read_bytes() == before
    prohibited = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE")
    assert not any(sql.lstrip().upper().startswith(prohibited) for sql in statements)
    record_evidence(
        "fresh-readonly-observation",
        {
            "fresh_open_count": len(opens),
            "published": published.model_dump(mode="json"),
            "no_write_statements": True,
            "store_bytes_unchanged": True,
            "provider_export_viewing_updates_preserved": True,
        },
    )


def test_failed_publication_after_commit_is_reconciled_by_observation_without_reactivation(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = InventoryRepository(inventory_store)
    registry = ReadinessRegistry()
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    repo.refresh(registry)
    repo.stage(second_plan)
    committed = repo.activate(second_plan.index.snapshot_id, expected_revision=1)

    def unavailable(path: Path, *, boundary: RuntimeBoundary) -> Store:
        raise OSError("SYNTHETIC_OBSERVATION_FAILURE")

    with monkeypatch.context() as patched:
        patched.setattr(snapshots, "open_store", unavailable)
        with pytest.raises(OSError, match="SYNTHETIC"):
            repo.refresh(registry)
    assert registry.snapshot().inventory == "unavailable"
    assert registry.snapshot().active_snapshot_id is None
    assert repo.active().observation == committed
    repo.refresh(registry)
    assert registry.observed_snapshot()[1] == committed
    assert repo.active().observation.active_revision == 2
    record_evidence(
        "publication-after-commit",
        {
            "durable_tuple": committed.model_dump(),
            "retry_observed_without_activation": True,
            "published": registry.snapshot().model_dump(mode="json"),
        },
    )


def test_corruption_clears_readiness_and_never_reuses_a_cached_ready_tuple(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    registry = ReadinessRegistry()
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    repo.refresh(registry)
    execute(
        inventory_store,
        "UPDATE inventory_search_fts SET document_text='corrupt' WHERE source_id='12'",
    )
    with pytest.raises(ValueError, match="FTS_CONTENT_MISMATCH"):
        repo.refresh(registry)
    assert registry.snapshot().inventory == "unavailable"
    assert registry.snapshot().active_snapshot_id is None


def test_missing_observer_does_not_initialize_a_store(inventory_store_path: Path) -> None:
    parent_existed = inventory_store_path.parent.exists()
    assert not inventory_store_path.exists()
    with pytest.raises((OSError, RuntimeError, ValueError)):
        observe_inventory(inventory_store_path, boundary=configured_runtime_boundary())
    assert not inventory_store_path.exists()
    assert inventory_store_path.parent.exists() == parent_existed


def test_reader_pins_complete_old_tuple_while_writer_prepares_new_pointer(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.stage(second_plan)
    old = repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    selected, pointer_changed, reader_closed = Event(), Event(), Event()

    def reader_checkpoint(phase: str) -> None:
        if phase == "read.active_selected":
            selected.set()
            assert pointer_changed.wait(10), "writer did not reach the uncommitted pointer"

    def writer_checkpoint(phase: str) -> None:
        if phase == "activation.pointer":
            pointer_changed.set()
            # Release the pinned reader before attempting SQLite's exclusive commit lock.
            assert reader_closed.wait(10), "pinned reader did not close its read unit"

    def read_old() -> snapshots.ActiveSnapshot:
        try:
            return InventoryRepository(inventory_store, _checkpoint=reader_checkpoint).active()
        finally:
            reader_closed.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(read_old)
        try:
            assert selected.wait(10), "reader did not pin the old active tuple"
            writer = pool.submit(
                InventoryRepository(inventory_store, _checkpoint=writer_checkpoint).activate,
                second_plan.index.snapshot_id,
                expected_revision=1,
            )
            observed = reader.result(timeout=15)
            committed = writer.result(timeout=15)
        finally:
            pointer_changed.set()
            reader_closed.set()
    assert observed.observation == old and observed.stage == snapshot_plan
    assert committed.snapshot_id == second_plan.index.snapshot_id and committed.active_revision == 2
    fresh = repo.active()
    assert fresh.observation == committed and fresh.stage == second_plan
    record_evidence(
        "coherent-reader-writer",
        {
            "pinned_read": old.model_dump(),
            "fresh_read": committed.model_dump(),
            "full_candidate_equality": True,
            "events_not_sleeps": True,
            "worker_futures_joined": True,
        },
    )


def test_two_prepared_writers_cannot_both_advance_the_same_expected_revision(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.stage(second_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    loser_prepared, winner_committed = Event(), Event()

    def first_checkpoint(phase: str) -> None:
        if phase == "activation.prepared":
            assert loser_prepared.wait(10)

    def second_checkpoint(phase: str) -> None:
        if phase == "activation.prepared":
            loser_prepared.set()
            assert winner_committed.wait(10)

    def first_write() -> InventoryObservation:
        try:
            return InventoryRepository(inventory_store, _checkpoint=first_checkpoint).activate(
                second_plan.index.snapshot_id,
                expected_revision=1,
            )
        finally:
            winner_committed.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(first_write)
        loser = pool.submit(
            InventoryRepository(inventory_store, _checkpoint=second_checkpoint).activate,
            second_plan.index.snapshot_id,
            expected_revision=1,
        )
        try:
            committed = winner.result(timeout=15)
            with pytest.raises(ValueError, match="REVISION_CONFLICT"):
                loser.result(timeout=15)
        finally:
            loser_prepared.set()
            winner_committed.set()
    assert repo.active().observation == committed and committed.active_revision == 2
    record_evidence(
        "two-writer-cas",
        {
            "committed": committed.model_dump(),
            "stale_prepared_writer_rejected": True,
        },
    )


def test_queued_refresh_reads_after_the_coordinator_and_observes_latest_activation(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inside_observer = local()

    class TrackedRegistry(ReadinessRegistry):
        def refresh_inventory(self, observe: Callable[[], InventoryObservation]) -> None:
            def tracked() -> InventoryObservation:
                inside_observer.active = True
                try:
                    return observe()
                finally:
                    inside_observer.active = False

            super().refresh_inventory(tracked)

    registry = TrackedRegistry()
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.stage(second_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    held, release, queued = Event(), Event(), Event()
    observed_revisions: list[int] = []

    def checked_observer(path: Path, *, boundary: RuntimeBoundary) -> InventoryObservation:
        assert boundary is inventory_store.boundary
        assert getattr(inside_observer, "active", False), (
            "observation happened before coordinator entry"
        )
        observation = observe_inventory(path, boundary=boundary)
        observed_revisions.append(observation.active_revision)
        return observation

    monkeypatch.setattr(snapshots, "observe_inventory", checked_observer)

    def hold_first() -> InventoryObservation:
        observation = checked_observer(inventory_store.path, boundary=inventory_store.boundary)
        held.set()
        assert release.wait(10)
        return observation

    def queued_refresh() -> None:
        queued.set()
        repo.refresh(registry)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(registry.refresh_inventory, hold_first)
        try:
            assert held.wait(10)
            second = pool.submit(queued_refresh)
            assert queued.wait(10)
            committed = repo.activate(second_plan.index.snapshot_id, expected_revision=1)
            release.set()
            first.result(timeout=15)
            second.result(timeout=15)
        finally:
            release.set()
    assert observed_revisions == [1, 2]
    assert registry.observed_snapshot()[1] == committed
    record_evidence(
        "queued-fresh-observer",
        {
            "observed_revisions": observed_revisions,
            "latest_tuple": committed.model_dump(),
            "every_observation_inside_coordinator_callback": True,
        },
    )
