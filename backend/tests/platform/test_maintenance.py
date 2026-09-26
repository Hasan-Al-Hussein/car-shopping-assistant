"""Real lock/admission tests. Authored source only until a Windows runtime grant."""

import copy
import os
from pathlib import Path
from threading import Thread

import pytest

from app.database import maintenance
from app.database.maintenance import (
    MaintenanceBusy, MaintenanceError, MaintenanceLease, StoreLifetimeLease,
    exclusive_store_lease, initialize_maintenance_guard, maintenance_paths, shared_store_lease,
)
from app.database.maintenance_native import NativeFileLock
from app.database.paths import RuntimeBoundary, prepare_store_parent, reserve_new_store
from app.database.store import Store, StoreError, open_store
from tests.platform.maintenance_cases import contender, exclusion_state
from tests.platform.runtime_cases import runtime_path as runtime_path
from tests.platform.runtime_cases import runtime_store as runtime_store


def test_real_shared_coexistence_and_exclusive_cross_process(runtime_store: Store) -> None:
    store = runtime_store
    paths = maintenance_paths(store.path, boundary=store.boundary)
    identity = paths.lock_path.stat()
    before = paths.lock_path.read_bytes()
    with shared_store_lease(store.path, boundary=store.boundary):
        assert exclusion_state(store.path, store.boundary, exclusive=False) == "held"
        assert exclusion_state(store.path, store.boundary) == "busy"
        with pytest.raises(MaintenanceBusy, match="UPGRADE_FORBIDDEN"):
            with exclusive_store_lease(store.path, boundary=store.boundary):
                pytest.fail("shared scope upgraded")
    with exclusive_store_lease(store.path, boundary=store.boundary) as lease:
        lease.assert_held(store.path, boundary=store.boundary)
        assert exclusion_state(store.path, store.boundary, exclusive=False) == "busy"
        assert open_store(store.path, boundary=store.boundary).generation == store.generation
        assert store.read(lambda session: 7) == 7
    assert exclusion_state(store.path, store.boundary) == "held"
    assert paths.lock_path.read_bytes() == before
    after = paths.lock_path.stat()
    assert (after.st_dev, after.st_ino) == (identity.st_dev, identity.st_ino)


def test_tokens_are_issued_immutable_bound_and_thread_owned(runtime_store: Store) -> None:
    store = runtime_store
    alternate = RuntimeBoundary(store.boundary.logical_root.with_name("unused-logical"),
                                store.boundary.physical_root)
    with exclusive_store_lease(store.path, boundary=store.boundary) as lease:
        with pytest.raises(AttributeError):
            lease._boundary = alternate
        with pytest.raises(MaintenanceError, match="BINDING_MISMATCH"):
            lease.assert_held(store.path, boundary=alternate)
        object.__setattr__(lease, "_boundary", alternate)
        with pytest.raises(MaintenanceError, match="BINDING_MISMATCH"):
            lease.assert_held()
        object.__setattr__(lease, "_boundary", store.boundary)
        forged = object.__new__(MaintenanceLease)
        object.__setattr__(forged, "_scope", lease._scope)
        object.__setattr__(forged, "_boundary", lease._boundary)
        with pytest.raises(MaintenanceError, match="NOT_ISSUED"):
            forged.assert_held()
        try:
            cloned = copy.copy(lease)
        except AttributeError:
            pass
        else:
            with pytest.raises(MaintenanceError, match="NOT_ISSUED"):
                cloned.assert_held()
        errors: list[BaseException] = []

        def foreign() -> None:
            try:
                lease.assert_held()
            except BaseException as error:
                errors.append(error)

        thread = Thread(target=foreign)
        thread.start()
        thread.join(2)
        assert not thread.is_alive() and len(errors) == 1
        assert isinstance(errors[0], MaintenanceError)
        lease.assert_held()
    with pytest.raises(MaintenanceError):
        lease.assert_held()


def test_missing_guard_never_created_by_open_and_explicit_provision_is_nontruncating(
    runtime_store: Store,
) -> None:
    store = runtime_store
    target = store.path.with_name("pre-t11.sqlite3")
    reserve_new_store(target, boundary=store.boundary)
    target.write_bytes(store.path.read_bytes())
    paths = maintenance_paths(target, boundary=store.boundary)
    before = target.read_bytes()
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        open_store(target, boundary=store.boundary)
    assert not paths.lock_path.exists() and target.read_bytes() == before
    initialize_maintenance_guard(target, boundary=store.boundary)
    paths.lock_path.write_bytes(b"retain stable guard bytes")
    initialize_maintenance_guard(target, boundary=store.boundary)
    assert paths.lock_path.read_bytes() == b"retain stable guard bytes"
    assert open_store(target, boundary=store.boundary).generation == store.generation


def test_marker_fences_shared_reentry_but_only_live_exclusive_may_reconcile(runtime_store: Store) -> None:
    store = runtime_store
    paths = maintenance_paths(store.path, boundary=store.boundary)
    with shared_store_lease(store.path, boundary=store.boundary):
        paths.intent_path.write_text("synthetic marker", encoding="utf-8")
        with pytest.raises(MaintenanceError, match="RECONCILIATION_REQUIRED"):
            with shared_store_lease(store.path, boundary=store.boundary):
                pytest.fail("shared reentry ignored marker")
    with pytest.raises(StoreError, match="STORE_UNAVAILABLE"):
        store.read(lambda session: 1)
    with pytest.raises(MaintenanceError):
        initialize_maintenance_guard(store.path, boundary=store.boundary)
    with exclusive_store_lease(store.path, boundary=store.boundary) as lease:
        lease.assert_held()
        assert store.read(lambda session: 2) == 2
        assert exclusion_state(store.path, store.boundary, exclusive=False) == "unavailable"
        # Test-only synthetic marker cleanup under the actual exclusive lease.
        paths.intent_path.unlink()
    assert store.read(lambda session: 3) == 3


def test_marker_created_during_native_acquisition_is_rechecked(
    runtime_store: Store, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = runtime_store
    paths = maintenance_paths(store.path, boundary=store.boundary)
    original = NativeFileLock.lock

    def interleave(guard: NativeFileLock, *, exclusive: bool) -> None:
        original(guard, exclusive=exclusive)
        paths.intent_path.write_text("synthetic race marker", encoding="utf-8")

    with monkeypatch.context() as scoped:
        scoped.setattr(NativeFileLock, "lock", interleave)
        with pytest.raises(MaintenanceError, match="RECONCILIATION_REQUIRED"):
            with shared_store_lease(store.path, boundary=store.boundary):
                pytest.fail("post-acquisition marker ignored")
    with exclusive_store_lease(store.path, boundary=store.boundary):
        paths.intent_path.unlink()
    assert exclusion_state(store.path, store.boundary) == "held"


@pytest.mark.parametrize("suffix", [".maintenance.lock", ".restore-intent.json"])
def test_unsafe_companions_fail_without_repair(runtime_store: Store, suffix: str) -> None:
    store = runtime_store
    target = store.path.with_name("unsafe.sqlite3")
    reserve_new_store(target, boundary=store.boundary)
    companion = Path(str(target) + suffix)
    os.link(store.path, companion)
    original = companion.read_bytes()
    with pytest.raises(MaintenanceError, match="UNSAFE_COMPANION"):
        maintenance_paths(target, boundary=store.boundary)
    assert companion.read_bytes() == original


def test_lifetime_pin_retirement_retains_exclusion_until_final_close(runtime_store: Store) -> None:
    store = runtime_store
    pin = StoreLifetimeLease(store.path, boundary=store.boundary)
    assert exclusion_state(store.path, store.boundary) == "held"
    pin.acquire()
    try:
        pin.retire()
        with pytest.raises(MaintenanceError, match="RETIRED"):
            pin.acquire()
        assert exclusion_state(store.path, store.boundary) == "busy"
        errors: list[BaseException] = []

        def release() -> None:
            try:
                pin.close()
            except BaseException as error:
                errors.append(error)

        thread = Thread(target=release)
        thread.start()
        thread.join(2)
        assert not thread.is_alive() and not errors
        assert exclusion_state(store.path, store.boundary) == "held"
    finally:
        pin.close()


def test_foreign_pid_refused_before_native_or_thread_lock(
    runtime_store: Store, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = runtime_store
    pin = StoreLifetimeLease(store.path, boundary=store.boundary)
    original_pid = os.getpid()
    with exclusive_store_lease(store.path, boundary=store.boundary) as lease:
        with monkeypatch.context() as scoped:
            scoped.setattr(os, "getpid", lambda: original_pid + 1)
            with pytest.raises(MaintenanceError, match="FOREIGN_PROCESS"):
                pin.acquire()
            with pytest.raises(MaintenanceError):
                lease.assert_held()
        lease.assert_held()


def test_yielded_operation_error_is_not_reclassified(runtime_store: Store) -> None:
    error = OSError("CALLER_OPERATION_ERROR")
    with pytest.raises(OSError) as seen:
        with maintenance.shared_store_lease(runtime_store.path, boundary=runtime_store.boundary):
            raise error
    assert seen.value is error


def test_abrupt_process_exit_releases_lock_but_marker_stays_closed(runtime_store: Store) -> None:
    store = runtime_store
    paths = maintenance_paths(store.path, boundary=store.boundary)
    with contender(store.path, store.boundary, exclusive=True) as (process, pipe, state):
        assert state == "held"
        # Controlled interruption fixture: bytes are not a valid restore record.
        paths.intent_path.write_text("synthetic interrupted restore", encoding="utf-8")
        pipe.send("crash")
        process.join(3)
        assert not process.is_alive() and process.exitcode == 0
    assert exclusion_state(store.path, store.boundary, exclusive=False) == "unavailable"
    with exclusive_store_lease(store.path, boundary=store.boundary):
        paths.intent_path.unlink()
    assert exclusion_state(store.path, store.boundary) == "held"


def test_native_guard_is_noninherited_and_cannot_be_replaced_while_held(runtime_store: Store) -> None:
    store = runtime_store
    paths = maintenance_paths(store.path, boundary=store.boundary)
    guard = NativeFileLock.open(paths.lock_path)
    try:
        guard.lock(exclusive=False)
        assert guard._descriptor is not None and not os.get_inheritable(guard._descriptor)
        with pytest.raises(OSError):
            paths.lock_path.rename(paths.lock_path.with_name("forbidden-replacement"))
        with pytest.raises(OSError):
            paths.lock_path.unlink()
        assert guard.held and paths.lock_path.exists()
    finally:
        guard.close()


def test_long_companion_identity_and_marker_fence(runtime_store: Store) -> None:
    # Keep ordinary fixture paths short, but explicitly exercise the native/API
    # boundary above MAX_PATH without relying on registry or manifest opt-ins.
    target = runtime_store.path.with_name("long-" + "x" * 100 + ".sqlite3")
    boundary = runtime_store.boundary
    prepare_store_parent(target, boundary=boundary)
    initialize_maintenance_guard(target, boundary=boundary, must_exist=False)
    paths = maintenance_paths(target, boundary=boundary, must_exist=False)
    assert len(str(paths.lock_path)) > 260
    marker = Path("\\\\?\\" + str(paths.intent_path))
    with shared_store_lease(target, boundary=boundary, must_exist=False):
        marker.write_text("synthetic long-path marker", encoding="utf-8")
        with pytest.raises(MaintenanceError, match="RECONCILIATION_REQUIRED"):
            with shared_store_lease(target, boundary=boundary, must_exist=False):
                pytest.fail("long-path marker was treated as absent")
    with pytest.raises(MaintenanceError, match="RECONCILIATION_REQUIRED"):
        with shared_store_lease(target, boundary=boundary, must_exist=False):
            pytest.fail("long-path marker did not fence fresh admission")
    with exclusive_store_lease(target, boundary=boundary, must_exist=False) as lease:
        lease.assert_held(target, boundary=boundary)
        marker.unlink()
    with shared_store_lease(target, boundary=boundary, must_exist=False):
        pass
