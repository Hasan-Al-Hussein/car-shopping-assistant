"""Shared activity/exclusive maintenance over an explicitly provisioned guard.

No Store is opened and no directory is created here. The fixed restore marker's
contents and durable transitions belong to the explicit restore operator.
"""

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock, current_thread, local
from typing import cast

from app.database.maintenance_native import NativeFileLock, NativeLockBusy
from app.database.paths import RuntimeBoundary, StorePathError, _io_path, guarded_store_path


class MaintenanceError(RuntimeError):
    """Sanitized helper failure; ordinary Store entrypoints translate it."""


class MaintenanceBusy(MaintenanceError):
    pass


@dataclass(frozen=True, slots=True)
class MaintenancePaths:
    store_path: Path
    lock_path: Path
    intent_path: Path


def _inspect_companion(path: Path) -> bool:
    try:
        native = Path("\\\\?\\" + str(path))
        info = native.lstat()
    except FileNotFoundError:
        return False
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or native.resolve(strict=True) != native
    ):
        raise MaintenanceError("MAINTENANCE_UNSAFE_COMPANION")
    return True


def maintenance_paths(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    must_exist: bool = True,
) -> MaintenancePaths:
    try:
        physical = guarded_store_path(path, boundary=boundary, must_exist=must_exist)
        if not _io_path(physical.parent).is_dir():
            raise MaintenanceError("MAINTENANCE_PARENT_UNAVAILABLE")
        paths = MaintenancePaths(
            physical,
            Path(str(physical) + ".maintenance.lock"),
            Path(str(physical) + ".restore-intent.json"),
        )
        _inspect_companion(paths.lock_path)
        _inspect_companion(paths.intent_path)
        return paths
    except (OSError, StorePathError):
        raise MaintenanceError("MAINTENANCE_PATH_UNAVAILABLE") from None


def _no_marker(paths: MaintenancePaths) -> None:
    if _inspect_companion(paths.intent_path):
        raise MaintenanceError("MAINTENANCE_RECONCILIATION_REQUIRED")


def _same_handle(paths: MaintenancePaths, guard: NativeFileLock) -> None:
    if not _inspect_companion(paths.lock_path):
        raise MaintenanceError("MAINTENANCE_GUARD_MISSING")
    held, named = guard.stat(), Path("\\\\?\\" + str(paths.lock_path)).stat()
    if (
        not stat.S_ISREG(held.st_mode)
        or held.st_nlink != 1
        or (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise MaintenanceError("MAINTENANCE_GUARD_CHANGED")


def _acquire(paths: MaintenancePaths, *, exclusive: bool, create: bool = False) -> NativeFileLock:
    guard = NativeFileLock.open(paths.lock_path, create=create)
    try:
        _same_handle(paths, guard)
        guard.lock(exclusive=exclusive)
        _same_handle(paths, guard)
        if not exclusive:
            _no_marker(paths)
        return guard
    except BaseException:
        guard.close()
        raise


@contextmanager
def _translate() -> Iterator[None]:
    try:
        yield
    except NativeLockBusy:
        raise MaintenanceBusy("MAINTENANCE_BUSY") from None
    except (OSError, StorePathError):
        raise MaintenanceError("MAINTENANCE_UNAVAILABLE") from None


def initialize_maintenance_guard(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    must_exist: bool = True,
) -> None:
    """Explicit provisioning only; no truncation, marker repair or Store creation."""
    with _translate():
        paths = maintenance_paths(path, boundary=boundary, must_exist=must_exist)
        _no_marker(paths)
        guard = _acquire(paths, exclusive=False, create=True)
        guard.close()


@dataclass(slots=True, eq=False)
class _Scope:
    paths: MaintenancePaths
    guard: NativeFileLock
    exclusive: bool
    pid: int = field(default_factory=os.getpid)
    thread: object = field(default_factory=current_thread)
    active: bool = True
    depth: int = 1
    tokens: dict["MaintenanceLease", RuntimeBoundary] = field(default_factory=dict)


_local = local()
_ISSUER = object()


def _scopes() -> dict[Path, _Scope]:
    if not hasattr(_local, "pid"):
        _local.pid, _local.scopes = os.getpid(), {}
    if _local.pid != os.getpid():
        raise MaintenanceError("MAINTENANCE_FOREIGN_PROCESS")
    return cast(dict[Path, _Scope], _local.scopes)


def _live(scope: _Scope) -> None:
    if (
        not scope.active
        or scope.pid != os.getpid()
        or scope.thread is not current_thread()
        or _scopes().get(scope.paths.store_path) is not scope
        or not scope.guard.held
    ):
        raise MaintenanceError("MAINTENANCE_SCOPE_NOT_LIVE")
    _same_handle(scope.paths, scope.guard)


@contextmanager
def _lease(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    exclusive: bool,
    must_exist: bool,
) -> Iterator[_Scope]:
    with _translate():
        paths = maintenance_paths(path, boundary=boundary, must_exist=must_exist)
        scopes = _scopes()
        existing = scopes.get(paths.store_path)
        if existing is not None:
            _live(existing)
            if exclusive and not existing.exclusive:
                raise MaintenanceBusy("MAINTENANCE_UPGRADE_FORBIDDEN")
            if not existing.exclusive:
                _no_marker(paths)
            if existing.depth >= 64:
                raise MaintenanceError("MAINTENANCE_SCOPE_LIMIT")
            existing.depth += 1
            scope = existing
        else:
            if len(scopes) >= 64:
                raise MaintenanceError("MAINTENANCE_SCOPE_LIMIT")
            if not exclusive:
                _no_marker(paths)
            guard = _acquire(paths, exclusive=exclusive)
            scope = _Scope(paths, guard, exclusive)
            scopes[paths.store_path] = scope
    # Caller exceptions remain caller exceptions. Translate only this helper's
    # acquisition/release I/O, never an OSError raised by the yielded operation.
    try:
        yield scope
    finally:
        if scope.pid != os.getpid() or scope.thread is not current_thread():
            raise MaintenanceError("MAINTENANCE_FOREIGN_SCOPE_RELEASE")
        if existing is not None:
            scope.depth -= 1
        else:
            with _translate():
                scope.active = False
                scope.tokens.clear()
                scopes.pop(paths.store_path)
                scope.guard.close()


class MaintenanceLease:
    __slots__ = ("_scope", "_boundary")
    _scope: _Scope
    _boundary: RuntimeBoundary

    def __init__(self, scope: _Scope, boundary: RuntimeBoundary, issuer: object) -> None:
        if issuer is not _ISSUER:
            raise MaintenanceError("MAINTENANCE_LEASE_NOT_ISSUED")
        object.__setattr__(self, "_scope", scope)
        object.__setattr__(self, "_boundary", boundary)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("MaintenanceLease is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("MaintenanceLease is immutable")

    @property
    def paths(self) -> MaintenancePaths:
        self.assert_held()
        return self._scope.paths

    def assert_held(
        self,
        path: Path | None = None,
        *,
        boundary: RuntimeBoundary | None = None,
    ) -> None:
        with _translate():
            scope = getattr(self, "_scope", None)
            if (
                not isinstance(scope, _Scope)
                or not scope.exclusive
                or self not in scope.tokens
                or (path is None) != (boundary is None)
            ):
                raise MaintenanceError("MAINTENANCE_LEASE_NOT_ISSUED")
            _live(scope)
            issued_boundary = scope.tokens[self]
            selected_path = scope.paths.store_path if path is None else path
            selected_boundary = self._boundary if boundary is None else boundary
            if (
                self._boundary != issued_boundary
                or selected_boundary != issued_boundary
                or maintenance_paths(
                    selected_path,
                    boundary=selected_boundary,
                    must_exist=False,
                )
                != scope.paths
            ):
                raise MaintenanceError("MAINTENANCE_LEASE_BINDING_MISMATCH")


@contextmanager
def shared_store_lease(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    must_exist: bool = True,
) -> Iterator[None]:
    with _lease(path, boundary=boundary, exclusive=False, must_exist=must_exist):
        yield


@contextmanager
def exclusive_store_lease(
    path: Path,
    *,
    boundary: RuntimeBoundary,
    must_exist: bool = True,
) -> Iterator[MaintenanceLease]:
    with _lease(path, boundary=boundary, exclusive=True, must_exist=must_exist) as scope:
        token = MaintenanceLease(scope, boundary, _ISSUER)
        scope.tokens[token] = boundary
        try:
            yield token
        finally:
            if scope.pid != os.getpid() or scope.thread is not current_thread():
                raise MaintenanceError("MAINTENANCE_FOREIGN_SCOPE_RELEASE")
            scope.tokens.pop(token, None)


def assert_store_lease(path: Path, *, boundary: RuntimeBoundary) -> None:
    """Internal connection guard: actual thread scope, never a boolean caller flag."""
    with _translate():
        paths = maintenance_paths(path, boundary=boundary)
        scope = _scopes().get(paths.store_path)
        if scope is None:
            raise MaintenanceError("MAINTENANCE_SCOPE_REQUIRED")
        _live(scope)
        if not scope.exclusive:
            _no_marker(paths)


class StoreLifetimeLease:
    """Inert process-owned shared pin; serialized admission/retirement across threads."""

    def __init__(self, path: Path, *, boundary: RuntimeBoundary) -> None:
        self._path, self._boundary = path, boundary
        self._pid = os.getpid()
        self._mutex = RLock()
        self._retired = False
        self._guard: NativeFileLock | None = None

    def _process(self) -> None:
        if os.getpid() != self._pid:
            raise MaintenanceError("MAINTENANCE_FOREIGN_PROCESS")

    def acquire(self) -> None:
        self._process()
        with self._mutex, _translate():
            if self._retired:
                raise MaintenanceError("MAINTENANCE_LIFETIME_RETIRED")
            paths = maintenance_paths(self._path, boundary=self._boundary)
            _no_marker(paths)
            if self._guard is None:
                self._guard = _acquire(paths, exclusive=False)
            else:
                _same_handle(paths, self._guard)

    def retire(self) -> None:
        self._process()
        with self._mutex:
            self._retired = True

    def close(self) -> None:
        self._process()
        with self._mutex, _translate():
            self._retired = True
            if self._guard is not None:
                self._guard.close()
                self._guard = None
