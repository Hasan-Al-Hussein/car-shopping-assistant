"""Store scope integration sources; real Windows/SQLite execution remains pending."""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.database import store as store_module
from app.database.maintenance import MaintenanceError, exclusive_store_lease, maintenance_paths
from app.database.paths import RuntimeBoundary
from app.database.store import Store, StoreError, _connect, initialize_store, open_store, upgrade_store
from tests.platform.maintenance_cases import contender, exclusion_state
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import runtime_store as runtime_store


@pytest.mark.parametrize("fail", [False, True])
def test_store_keeps_exclusion_through_callback_rollback_and_engine_disposal(
    runtime_store: Store, monkeypatch: pytest.MonkeyPatch, fail: bool,
) -> None:
    store = runtime_store
    observations: list[tuple[str, str]] = []
    original_dispose = Engine.dispose

    def dispose(engine: Engine, close: bool = True) -> None:
        observations.append(("dispose", exclusion_state(store.path, store.boundary)))
        original_dispose(engine, close=close)

    def work(session: Session) -> int:
        observations.append(("callback", exclusion_state(store.path, store.boundary)))
        assert session.execute(text("SELECT 1")).scalar_one() == 1
        if fail:
            raise RuntimeError("CONTROLLED_CALLBACK_FAILURE")
        return 1

    with monkeypatch.context() as scoped:
        scoped.setattr(Engine, "dispose", dispose)
        if fail:
            with pytest.raises(RuntimeError, match="CONTROLLED_CALLBACK_FAILURE"):
                store.write(work)
        else:
            assert store.write(work) == 1
    assert observations == [("callback", "busy"), ("dispose", "busy")]
    assert exclusion_state(store.path, store.boundary) == "held"
    assert store.read(lambda session: 2) == 2


def test_private_connect_needs_actual_scope_and_exclusive_maps_to_store_busy(runtime_store: Store) -> None:
    store = runtime_store
    with pytest.raises(MaintenanceError, match="SCOPE_REQUIRED"):
        _connect(store.path, "rw", None, boundary=store.boundary)
    with contender(store.path, store.boundary, exclusive=True) as (_, _, state):
        assert state == "held"
        with pytest.raises(StoreError, match="^STORE_BUSY$"):
            open_store(store.path, boundary=store.boundary)
        with pytest.raises(StoreError, match="^STORE_BUSY$"):
            store.read(lambda session: 1)


def test_initialize_and_upgrade_keep_lease_through_final_reopen(
    runtime_store: Store, monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = runtime_store
    target = parent.path.parent / "new-parent" / "new.sqlite3"
    observed: list[str] = []
    original_open = store_module.open_store

    def opened(path: Path, *, boundary: RuntimeBoundary, **kwargs: Any) -> Store:
        observed.append(exclusion_state(path, boundary))
        return original_open(path, boundary=boundary, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(store_module, "open_store", opened)
        created = initialize_store(target, boundary=parent.boundary)
        upgraded = upgrade_store(target, boundary=parent.boundary,
                                 expected_generation=created.generation)
    assert observed == ["busy", "busy"]
    assert created.generation == upgraded.generation
    assert maintenance_paths(target, boundary=parent.boundary).lock_path.exists()
    assert exclusion_state(target, parent.boundary) == "held"


def test_nested_initialization_refuses_before_creating_parent(runtime_store: Store) -> None:
    store = runtime_store
    target = store.path.parent / "nested-refused" / "test.sqlite3"
    with pytest.raises(StoreError, match="ONE_SYNCHRONOUS_UNIT"):
        store.read(lambda session: initialize_store(target, boundary=store.boundary))
    assert not target.parent.exists()


def test_exclusive_owner_can_read_after_marker_without_lending_thread_authority(runtime_store: Store) -> None:
    store = runtime_store
    paths = maintenance_paths(store.path, boundary=store.boundary)
    with exclusive_store_lease(store.path, boundary=store.boundary):
        paths.intent_path.write_text("synthetic exclusive marker", encoding="utf-8")
        try:
            assert open_store(store.path, boundary=store.boundary).generation == store.generation
            assert store.read(lambda session: 3) == 3
            assert exclusion_state(store.path, store.boundary, exclusive=False) == "unavailable"
        finally:
            paths.intent_path.unlink()
