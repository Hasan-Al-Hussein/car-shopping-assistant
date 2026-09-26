"""Real registry concurrency with controlled events; no sleep-based timing claims."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial
from threading import Event
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core import readiness as readiness_module
from app.core.config import Settings
from app.core.readiness import (
    DependencySnapshot,
    InventoryObservation,
    InventoryObservationConflict,
    ProviderObservation,
    ReadinessRegistry,
    ReadinessService,
)
from app.database.store import Store
from tests.support.harness import configured_runtime_boundary

GENERATION = str(uuid4())


def observation(revision: int = 1, **changes: Any) -> InventoryObservation:
    values = dict(
        generation=GENERATION,
        active_revision=revision,
        snapshot_id="a" * 64,
        index_version="b" * 64,
        mode="fts5",
    )
    return InventoryObservation.model_validate({**values, **changes})


def update(snapshot: DependencySnapshot, **changes: Any) -> DependencySnapshot:
    return DependencySnapshot.model_validate({**snapshot.model_dump(), **changes})


def test_independent_updates_survive_slow_inventory_observation() -> None:
    registry = ReadinessRegistry()
    entered, release = Event(), Event()
    provider = ProviderObservation(state="ready", observed_at=datetime.now(UTC))

    def observe() -> InventoryObservation:
        entered.set()
        assert release.wait(5)
        return observation()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(registry.refresh_inventory, observe)
        try:
            assert entered.wait(5)
            registry.update(lambda current: update(current, provider=provider, export="ready"))
            registry.update(lambda current: update(current, viewing="ready"))
        finally:
            release.set()
        future.result(timeout=5)
    state = registry.snapshot()
    assert state.inventory == "ready" and state.active_snapshot_id == "a" * 64
    assert state.provider == provider and state.export == "ready" and state.viewing == "ready"


def test_fresh_callbacks_are_serialized_and_second_reads_after_first() -> None:
    registry = ReadinessRegistry()
    entered, release, second_started = Event(), Event(), Event()
    order: list[str] = []

    def first() -> InventoryObservation:
        order.append("first-read")
        entered.set()
        assert release.wait(5)
        order.append("first-return")
        return observation(1)

    def second() -> InventoryObservation:
        order.append("second-read")
        assert registry.snapshot().active_snapshot_id == "a" * 64
        return observation(2, snapshot_id="c" * 64)

    def run_second() -> None:
        second_started.set()
        registry.refresh_inventory(second)

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(registry.refresh_inventory, first)
        try:
            assert entered.wait(5)
            two = pool.submit(run_second)
            assert second_started.wait(5)
            assert order == ["first-read"]
        finally:
            release.set()
        one.result(timeout=5)
        two.result(timeout=5)
    assert order == ["first-read", "first-return", "second-read"]
    assert registry.snapshot().active_snapshot_id == "c" * 64


@pytest.mark.parametrize(
    "stale",
    [
        observation(1),
        observation(2, snapshot_id="c" * 64),
        observation(2, index_version="d" * 64),
        observation(2, mode="bounded_lexical"),
        InventoryObservation(generation=GENERATION, active_revision=0),
    ],
)
def test_stale_or_equal_revision_conflict_leaves_newer_observation(
    stale: InventoryObservation,
) -> None:
    registry = ReadinessRegistry()
    registry.refresh_inventory(lambda: observation(2))
    before = registry.snapshot()
    with pytest.raises(InventoryObservationConflict):
        registry.refresh_inventory(lambda: stale)
    assert registry.snapshot() is before


def test_generation_transition_retires_old_generation_even_if_old_revision_is_higher() -> None:
    registry = ReadinessRegistry()
    registry.refresh_inventory(lambda: observation(100))
    registry.refresh_inventory(
        lambda: observation(1, generation=str(uuid4()), snapshot_id="c" * 64)
    )
    before = registry.snapshot()
    with pytest.raises(InventoryObservationConflict, match="GENERATION_RETIRED"):
        registry.refresh_inventory(lambda: observation(101))
    assert registry.snapshot() is before


def test_generation_fence_is_bounded_without_evicting_old_replay_protection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(readiness_module, "MAX_RETIRED_INVENTORY_GENERATIONS", 2)
    registry = ReadinessRegistry(DependencySnapshot(export="ready"))
    generations = [str(uuid4()) for _ in range(4)]
    for generation in generations[:3]:
        registry.refresh_inventory(partial(observation, generation=generation))
    last = registry.observed_snapshot()[1]
    with pytest.raises(RuntimeError, match="GENERATION_FENCE_EXHAUSTED"):
        registry.refresh_inventory(lambda: observation(generation=generations[3]))
    assert registry.snapshot().inventory == "unavailable"
    assert registry.snapshot().active_snapshot_id is None
    assert registry.snapshot().export == "ready"
    assert registry.observed_snapshot()[1] is last
    with pytest.raises(InventoryObservationConflict, match="GENERATION_RETIRED"):
        registry.refresh_inventory(lambda: observation(generation=generations[0]))
    assert len(registry._retired_generations) == 2


def test_observation_failure_preserves_watermark_and_recovers_from_fresh_same_revision() -> None:
    registry = ReadinessRegistry(DependencySnapshot(export="ready"))
    registry.refresh_inventory(lambda: observation(2))

    def fail() -> InventoryObservation:
        raise OSError("INJECTED_PUBLICATION_READ_FAILURE")

    with pytest.raises(OSError):
        registry.refresh_inventory(fail)
    assert registry.snapshot().inventory == "unavailable"
    assert registry.snapshot().active_snapshot_id is None
    assert registry.snapshot().export == "ready"
    with pytest.raises(InventoryObservationConflict):
        registry.refresh_inventory(lambda: observation(1))
    assert registry.snapshot().inventory == "unavailable"
    registry.refresh_inventory(lambda: observation(2))
    assert registry.snapshot().inventory == "ready"


def test_stale_whole_snapshot_cannot_lose_independent_update() -> None:
    registry = ReadinessRegistry()
    stale = registry.snapshot()
    registry.update(lambda current: update(current, export="ready"))
    assert not registry.publish(update(stale, viewing="ready"), expected=stale)
    current = registry.snapshot()
    assert registry.publish(update(current, viewing="ready"), expected=current)
    assert registry.snapshot().export == "ready"


@pytest.mark.parametrize("method", ["update", "publish"])
def test_general_publishers_cannot_bypass_inventory_coordinator(method: str) -> None:
    registry = ReadinessRegistry()
    current = registry.snapshot()
    changed = update(current, inventory="ready", active_snapshot_id="a" * 64)
    with pytest.raises(ValueError, match="COORDINATED_REFRESH"):
        if method == "update":
            registry.update(lambda _: changed)
        else:
            registry.publish(changed, expected=current)
    assert registry.snapshot() is current


def test_absent_and_fallback_observations_have_honest_public_state() -> None:
    registry = ReadinessRegistry()
    registry.refresh_inventory(
        lambda: InventoryObservation(generation=GENERATION, active_revision=0)
    )
    assert registry.snapshot().inventory == "unconfigured"
    registry.refresh_inventory(lambda: observation(mode="bounded_lexical"))
    assert registry.snapshot().inventory == "degraded"


def test_health_refuses_observation_from_a_different_opened_store_generation() -> None:
    registry = ReadinessRegistry(DependencySnapshot(viewing="ready"))
    registry.refresh_inventory(lambda: observation())
    boundary = configured_runtime_boundary()
    path = boundary.logical_root / "test-stores" / "readiness-no-io" / "test.sqlite3"
    current_generation = str(uuid4())
    service = ReadinessService(
        Settings(store_path=path, runtime_boundary=boundary),
        registry,
        store_opener=lambda value: Store(value, current_generation, boundary=boundary),
        can_write=lambda _: True,
    )
    health = service.health()
    assert health.store.state == "ready"
    assert health.inventory.state == "unavailable" and health.active_snapshot_id is None
    assert health.viewing.state == "unavailable"
    # Health does not publish, restore, activate or reset anything.
    assert registry.snapshot().inventory == "ready"
    registry.refresh_inventory(lambda: observation(generation=current_generation))
    assert service.health().inventory.state == "ready"


@pytest.mark.parametrize(
    "changes",
    [
        {"generation": "not-a-uuid"},
        {"active_revision": -1},
        {"snapshot_id": None},
        {"index_version": None},
        {"mode": None},
        {"active_revision": 0},
    ],
)
def test_partial_active_observation_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        observation(**changes)
