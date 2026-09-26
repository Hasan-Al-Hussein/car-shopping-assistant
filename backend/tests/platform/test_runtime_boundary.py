"""Portable boundary checks. Staged source only; real cases need a finite runtime grant."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core import readiness as readiness_module
from app.core.config import ConfigurationError, Settings, load_settings
from app.core.readiness import ReadinessRegistry, ReadinessService
from app.database import paths as paths_module
from app.database.paths import (
    RuntimeBoundary,
    StorePathError,
    boundary_from_environment,
    guarded_store_path,
    initialize_runtime_root,
    parse_runtime_path,
    reserve_new_store,
    validate_store_location,
)
from app.database.store import Store, StoreError, initialize_store, open_store
from app.identity import service as identity_module
from app.identity.service import IdentityService
from tests.platform.persistence_cases import seed
from tests.support.harness import (
    configured_runtime_boundary,
    runtime_environment,
    unopened_store_plan,
)


def inert_boundary() -> RuntimeBoundary:
    # Pure/no-I/O examples are explicit test inputs, never a default disk authority.
    root = Path(r"C:\portable-boundary-inert")
    return RuntimeBoundary(root, root)


@pytest.fixture
def ordinary_boundary() -> RuntimeBoundary:
    approved = configured_runtime_boundary()
    root = approved.physical_root / "test-stores" / ("portability-" + str(uuid4())) / "runtime"
    return RuntimeBoundary(root, root)


def test_parser_settings_and_validation_are_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("CONFIGURATION_PERFORMED_FILESYSTEM_IO")

    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    root = Path(r"D:\another-user\runtime")
    boundary = boundary_from_environment({"CSA_RUNTIME_ROOT": str(root)})
    assert boundary == RuntimeBoundary(root, root)
    assert boundary is not None
    location = root / "stores" / "instance.sqlite3"
    validate_store_location(location, boundary=boundary)
    settings = load_settings({"CSA_RUNTIME_ROOT": str(root), "CSA_STORE_PATH": str(location)})
    assert settings.runtime_boundary == boundary and settings.store_path == location
    assert boundary_from_environment({}) is None
    assert load_settings({}).runtime_boundary is None
    assert load_settings({}).store_path is None
    # A non-C lexical success is not proof that a D: drive exists or is fixed.


def test_explicit_mapping_is_not_derived_from_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "resolve", lambda *args, **kwargs: pytest.fail("UNEXPECTED_RESOLVE"))
    values = {
        "CSA_RUNTIME_ROOT": r"C:\logical-runtime",
        "CSA_RUNTIME_PHYSICAL_ROOT": r"D:\explicit-backing",
    }
    boundary = boundary_from_environment(values)
    assert boundary is not None
    assert boundary == RuntimeBoundary(
        Path(values["CSA_RUNTIME_ROOT"]), Path(values["CSA_RUNTIME_PHYSICAL_ROOT"])
    )
    values["CSA_RUNTIME_ROOT"] = r"C:\changed-after-parsing"
    assert boundary.logical_root == Path(r"C:\logical-runtime")
    with pytest.raises(FrozenInstanceError):
        boundary.logical_root = Path(r"C:\changed")  # type: ignore[misc]


@pytest.mark.parametrize(
    "values",
    [
        {"CSA_RUNTIME_PHYSICAL_ROOT": r"C:\physical-only"},
        {"CSA_RUNTIME_ROOT": ""},
        {"CSA_RUNTIME_ROOT": "relative"},
        {"CSA_RUNTIME_ROOT": "C:relative"},
        {"CSA_RUNTIME_ROOT": "C:\\"},
        {"CSA_RUNTIME_ROOT": r"\\server\share\runtime"},
        {"CSA_RUNTIME_ROOT": r"\\?\C:\runtime"},
        {"CSA_RUNTIME_ROOT": r"\\.\C:\runtime"},
        {"CSA_RUNTIME_ROOT": r"C:\runtime\.\nested"},
        {"CSA_RUNTIME_ROOT": r"C:\runtime\..\other"},
        {"CSA_RUNTIME_ROOT": r"C:\runtime.\nested"},
        {"CSA_RUNTIME_ROOT": "C:\\runtime \\nested"},
        {"CSA_RUNTIME_ROOT": r"C:\runtime:stream"},
        {"CSA_RUNTIME_ROOT": r"C:\CON\runtime"},
        {"CSA_RUNTIME_ROOT": r"C:\runtime", "CSA_RUNTIME_PHYSICAL_ROOT": r"C:\runtime\child"},
        {"CSA_RUNTIME_ROOT": r"C:\runtime\child", "CSA_RUNTIME_PHYSICAL_ROOT": r"C:\runtime"},
    ],
)
def test_invalid_operator_boundaries_reject_without_io(values: dict[str, str]) -> None:
    with pytest.raises(StorePathError):
        boundary_from_environment(values)
    with pytest.raises(ConfigurationError, match="^CONFIGURATION_INVALID$"):
        load_settings(values)


@pytest.mark.parametrize(
    "suffix",
    [r"stores\.\one.sqlite3", r"test-stores\..\stores\one.sqlite3", r"stores\one.sqlite3:stream"],
)
def test_raw_store_text_is_checked_before_path_normalization(suffix: str) -> None:
    boundary = inert_boundary()
    raw = str(boundary.logical_root) + "\\" + suffix
    with pytest.raises(StorePathError):
        parse_runtime_path(raw)
    with pytest.raises(ConfigurationError, match="^CONFIGURATION_INVALID$"):
        load_settings({**runtime_environment(boundary), "CSA_STORE_PATH": raw})


def test_settings_require_boundary_and_do_not_serialize_private_roots() -> None:
    boundary = inert_boundary()
    location = boundary.logical_root / "stores" / "instance.sqlite3"
    with pytest.raises(ConfigurationError, match="^CONFIGURATION_INVALID$"):
        load_settings({"CSA_STORE_PATH": str(location)})
    settings = Settings(store_path=location, runtime_boundary=boundary)
    assert settings.runtime_boundary is boundary
    assert "runtime_boundary" not in settings.model_dump()
    assert str(boundary.logical_root) not in repr(settings)
    assert boundary.logical_root.name not in settings.model_dump_json()


def test_unopened_plan_uses_explicit_test_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    boundary = inert_boundary()
    for name, value in runtime_environment(boundary).items():
        monkeypatch.setenv(name, value)
    plan = unopened_store_plan(
        run_id="40000000-0000-4000-8000-000000000001",
        case_id="case-portable-plan",
        generation="50000000-0000-4000-8000-000000000001",
    )
    assert Path(plan.path).is_relative_to(boundary.logical_root / "test-stores")
    assert plan.state == "unopened" and plan.requires_resolved_path_check
    monkeypatch.delenv("CSA_RUNTIME_ROOT")
    monkeypatch.delenv("CSA_RUNTIME_PHYSICAL_ROOT")
    with pytest.raises(ValueError, match="TEST_RUNTIME_BOUNDARY_NOT_CONFIGURED"):
        configured_runtime_boundary()


def test_default_identity_and_readiness_openers_keep_captured_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = inert_boundary()
    target = boundary.logical_root / "stores" / "instance.sqlite3"
    settings = Settings(store_path=target, runtime_boundary=boundary)
    descriptor = Store(target, str(uuid4()), boundary=boundary)
    calls: list[tuple[Path, RuntimeBoundary]] = []

    def opened(path: Path, *, boundary: RuntimeBoundary) -> Store:
        calls.append((path, boundary))
        return descriptor

    monkeypatch.setattr(identity_module, "open_store", opened)
    monkeypatch.setattr(readiness_module, "open_store", opened)
    identity = IdentityService(settings)
    readiness = ReadinessService(settings, ReadinessRegistry(), can_write=lambda _: True)
    monkeypatch.setenv("CSA_RUNTIME_ROOT", r"C:\different-after-service-construction")
    monkeypatch.delenv("CSA_RUNTIME_PHYSICAL_ROOT", raising=False)
    assert identity.open_store() is descriptor
    assert readiness.health().store.state == "ready"
    assert len(calls) == 2
    assert all(path == target and selected is boundary for path, selected in calls)


def test_missing_ordinary_root_observations_never_create(
    ordinary_boundary: RuntimeBoundary,
) -> None:
    root = ordinary_boundary.physical_root
    target = root / "stores" / "missing.sqlite3"
    assert not root.parent.exists()
    with pytest.raises((FileNotFoundError, StoreError, StorePathError)):
        open_store(target, boundary=ordinary_boundary)
    with pytest.raises((FileNotFoundError, StorePathError)):
        reserve_new_store(target, boundary=ordinary_boundary)
    settings = Settings(store_path=target, runtime_boundary=ordinary_boundary)
    observed = ReadinessService(settings, ReadinessRegistry()).health()
    assert observed.store.state == "unavailable"
    assert not root.parent.exists()


def test_ordinary_root_initialize_open_and_reopen(
    ordinary_boundary: RuntimeBoundary, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = ordinary_boundary.physical_root
    initialize_runtime_root(ordinary_boundary)
    assert root.is_dir() and root.resolve(strict=True) == root
    target = root / "test-stores" / "case-persistence" / "test.sqlite3"
    store = initialize_store(target, boundary=ordinary_boundary)
    assert store.boundary is ordinary_boundary
    unrelated = root.parent / "unused-runtime"
    monkeypatch.setenv("CSA_RUNTIME_ROOT", str(unrelated))
    monkeypatch.delenv("CSA_RUNTIME_PHYSICAL_ROOT", raising=False)
    # The already-open handle must not follow later environment changes.
    store.write(lambda db: seed(db, store.generation))
    assert store.read(lambda db: db.execute(text("SELECT count(*) FROM owners")).scalar_one()) == 2
    reopened = open_store(store.path, boundary=store.boundary)
    assert reopened.boundary is ordinary_boundary
    assert reopened.generation == store.generation
    assert (
        reopened.read(lambda db: db.execute(text("SELECT count(*) FROM bookings")).scalar_one())
        == 1
    )
    before = target.read_bytes()
    initialize_runtime_root(ordinary_boundary)
    assert target.read_bytes() == before
    with pytest.raises(FileExistsError):
        initialize_store(target, boundary=ordinary_boundary)
    assert target.read_bytes() == before and not unrelated.exists()
    # This is handle reopening in one process, not a claimed OS/process restart.


def test_reservation_preserves_pair_after_physical_canonicalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = configured_runtime_boundary()
    target = boundary.logical_root / "test-stores" / ("reserve-" + str(uuid4())) / "test.sqlite3"
    original = paths_module.guarded_store_path
    observed: list[tuple[Path, RuntimeBoundary]] = []

    def checked(path: Path, *, boundary: RuntimeBoundary, must_exist: bool) -> Path:
        observed.append((path, boundary))
        return original(path, boundary=boundary, must_exist=must_exist)

    monkeypatch.setattr(paths_module, "guarded_store_path", checked)
    physical = reserve_new_store(target, boundary=boundary)
    assert physical == boundary.physical_root / target.relative_to(boundary.logical_root)
    assert observed[0][0] == target
    assert all(pair is boundary for _, pair in observed)
    assert observed[-1][0] == physical
    assert physical.is_file() and physical.stat().st_size == 0


@pytest.mark.parametrize("drive_kind", [0, 2, 4, 5, 6])
def test_runtime_root_rejects_nonfixed_volume_before_creation(
    ordinary_boundary: RuntimeBoundary, monkeypatch: pytest.MonkeyPatch, drive_kind: int
) -> None:
    monkeypatch.setattr(paths_module.ctypes.windll.kernel32, "GetDriveTypeW", lambda _: drive_kind)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("INVALID_VOLUME_REACHED_MKDIR")

    monkeypatch.setattr(Path, "mkdir", forbidden)
    with pytest.raises(StorePathError, match="FIXED_LOCAL_VOLUME"):
        initialize_runtime_root(ordinary_boundary)


def test_runtime_root_rejects_nondirectory_parent_without_repair(
    ordinary_boundary: RuntimeBoundary,
) -> None:
    parent = ordinary_boundary.physical_root.parent
    parent.mkdir(parents=True)
    blocker = parent / "blocked"
    blocker.write_bytes(b"retain this synthetic blocker")
    invalid = RuntimeBoundary(blocker / "runtime", blocker / "runtime")
    with pytest.raises((StorePathError, OSError)):
        initialize_runtime_root(invalid)
    assert blocker.read_bytes() == b"retain this synthetic blocker"
    assert sorted(item.name for item in parent.iterdir()) == ["blocked"]


def test_missing_distinct_mapping_is_never_created(ordinary_boundary: RuntimeBoundary) -> None:
    physical = ordinary_boundary.physical_root
    logical = physical.parent / "logical-runtime"
    boundary = RuntimeBoundary(logical, physical)
    with pytest.raises(StorePathError):
        initialize_runtime_root(boundary)
    assert not physical.parent.exists()


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_orphaned_companion_blocks_reservation_without_overwrite(
    ordinary_boundary: RuntimeBoundary, suffix: str,
) -> None:
    initialize_runtime_root(ordinary_boundary)
    target = ordinary_boundary.physical_root / "test-stores" / "case-companion" / "test.sqlite3"
    target.parent.mkdir(parents=True)
    companion = Path(str(target) + suffix)
    companion.write_bytes(b"retain orphaned companion")
    with pytest.raises(StorePathError, match="ORPHANED_COMPANION"):
        reserve_new_store(target, boundary=ordinary_boundary)
    assert not target.exists() and companion.read_bytes() == b"retain orphaned companion"


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_companion_directory_is_rejected(ordinary_boundary: RuntimeBoundary, suffix: str) -> None:
    initialize_runtime_root(ordinary_boundary)
    target = ordinary_boundary.physical_root / "test-stores" / "case-directory" / "test.sqlite3"
    companion = Path(str(target) + suffix)
    companion.mkdir(parents=True)
    with pytest.raises(StorePathError, match="COMPANION_NOT_REGULAR_FILE"):
        guarded_store_path(target, boundary=ordinary_boundary, must_exist=False)
    assert companion.is_dir() and not target.exists()
