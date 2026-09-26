"""Explicit disposable P13 fixtures. No setup occurs at import or through HTTP."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings, load_settings
from app.database.paths import RuntimeBoundary, initialize_runtime_root
from app.database.store import Store, initialize_store
from app.inventory.extraction import ExtractedCandidate
from app.inventory.snapshots import InventoryRepository
from app.runtime_app import ApplicationComposition, build_composition
from tests.support.harness import FrozenClock, configured_runtime_boundary, runtime_environment

ACCEPTED_SNAPSHOT = "5fe31b5951317db6d77b6786596861e32ccd2442f2f5f98927d57e6b4a2092f3"


def settings_for(path: Path) -> Settings:
    return load_settings(
        {**runtime_environment(), "CSA_STORE_PATH": str(path), "CSA_ASSISTANT_ENABLED": "false"}
    )


@pytest.fixture
def runtime_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    # T8 CSV publication is per runtime root, so each test needs its own root,
    # not just a different SQLite filename beside another test's exports.
    configured = configured_runtime_boundary()
    root = configured.physical_root / "test-stores" / ("p16-" + str(uuid4())) / "runtime"
    boundary = RuntimeBoundary(root, root)
    for key, value in runtime_environment(boundary).items():
        monkeypatch.setenv(key, value)
    return root / "test-stores" / "case-p13-composition.sqlite3"


@pytest.fixture
def runtime_clock() -> FrozenClock:
    return FrozenClock(datetime(2030, 1, 7, 4, tzinfo=UTC))


@pytest.fixture
def runtime_store(runtime_path: Path) -> Store:
    boundary = configured_runtime_boundary()
    initialize_runtime_root(boundary)
    return initialize_store(runtime_path, boundary=boundary)


@pytest.fixture
def runtime_composition(
    runtime_store: Store, runtime_clock: FrozenClock
) -> Iterator[ApplicationComposition]:
    composition = build_composition(
        settings_for(runtime_store.path),
        runtime_store,
        clock=runtime_clock.now,
        event_sink=lambda event: None,
    )
    try:
        yield composition
    finally:
        composition.close()


@pytest.fixture
def active_runtime(
    runtime_composition: ApplicationComposition, snapshot_candidate: ExtractedCandidate
) -> ApplicationComposition:
    # Trusted test setup only. Production factory never imports this module.
    repo = InventoryRepository(runtime_composition.store, clock=runtime_composition.clock)
    plan = repo.prepare(snapshot_candidate, policy_version="DEMO-POLICY-1")
    assert plan.index.snapshot_id == ACCEPTED_SNAPSHOT
    assert len(plan.candidate.listings) == 100
    repo.stage(plan)
    activated = repo.activate(plan.index.snapshot_id, expected_revision=0)
    observed = runtime_composition.admit_inventory()
    assert observed == activated
    assert observed.snapshot_id == ACCEPTED_SNAPSHOT and observed.active_revision == 1
    return runtime_composition
