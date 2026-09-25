"""Explicit local Windows installation boundary, rechecked at every connection.

This protects against misconfiguration and pre-existing links, not a hostile local
administrator racing filesystem replacement. The runtime directory is trusted operator state.
"""

import ctypes
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

COMPANIONS = ("-journal", "-wal", "-shm")
_LEGACY_DIRECTORY_LIMIT = 248


class StorePathError(ValueError):
    """A store path failed the selected local installation boundary."""


# Cache spelling only; filesystem, alias and admission checks remain fresh.
@lru_cache(maxsize=1024)
def _noncanonical(part: str) -> bool:
    return (
        part in (".", "..") or part.endswith((".", " ")) or ":" in part or os.path.isreserved(part)
    )


def _validate_windows_path(path: Path) -> None:
    drive = path.drive
    if (
        os.name != "nt"
        or not path.is_absolute()
        or len(drive) != 2
        or not drive[0].isascii()
        or not drive[0].isalpha()
        or drive[1] != ":"
        or path.anchor != drive + "\\"
    ):
        raise StorePathError("STORE_REQUIRES_ADOPTED_LOCAL_WINDOWS_PATH")
    if any(_noncanonical(part) for part in path.parts[1:]):
        raise StorePathError("STORE_NONCANONICAL_PATH")


def _io_path(path: Path) -> Path:
    """Internal Windows spelling only; callers still own boundary/identity checks.

    Keep ordinary short-path and adopted alias behavior. Extended spelling is
    used only at filesystem calls that may cross the legacy directory limit;
    it never becomes a Store identity, configured root, digest or public input.
    """
    _validate_windows_path(path)
    return path if len(str(path)) < _LEGACY_DIRECTORY_LIMIT else Path("\\\\?\\" + str(path))


def _sqlite_uri(path: Path, mode: Literal["ro", "rw"]) -> str:
    """Encode only the SQLite I/O filename; callers retain path and lease checks."""
    native = _io_path(path)
    if native == path:
        return path.as_uri() + f"?mode={mode}"
    # SQLite decodes this into /\\?\C:\..., then its Windows VFS removes /.
    # Keep backslashes: Windows does not normalize / in extended filenames.
    return f"file:/{quote(str(native), safe='')}?mode={mode}"


def _resolved_path(path: Path, *, strict: bool) -> Path:
    """Resolve through the same I/O spelling and return an ordinary identity."""
    value = str(_io_path(path).resolve(strict=strict))
    if value.startswith("\\\\?\\"):
        value = value[4:]
    result = Path(value)
    _validate_windows_path(result)
    return result


def parse_runtime_path(value: str) -> Path:
    """Validate raw operator text before Path can normalize away dot components."""
    if any(_noncanonical(part) for part in value.replace("/", "\\").split("\\")[1:]):
        raise StorePathError("STORE_NONCANONICAL_PATH")
    path = Path(value)
    _validate_windows_path(path)
    return path


@dataclass(frozen=True, slots=True)
class RuntimeBoundary:
    """Inert trusted operator configuration, never authority inferred from resolution."""

    logical_root: Path
    physical_root: Path

    def __post_init__(self) -> None:
        for root in (self.logical_root, self.physical_root):
            _validate_windows_path(root)
            if root == Path(root.anchor):
                raise StorePathError("STORE_RUNTIME_ROOT_TOO_BROAD")
        if self.logical_root != self.physical_root and (
            self.logical_root.is_relative_to(self.physical_root)
            or self.physical_root.is_relative_to(self.logical_root)
        ):
            raise StorePathError("STORE_RUNTIME_ROOTS_OVERLAP")

    @property
    def store_roots(self) -> tuple[Path, ...]:
        roots = (
            (self.logical_root,)
            if self.logical_root == self.physical_root
            else (self.logical_root, self.physical_root)
        )
        return tuple(root / directory for root in roots for directory in ("stores", "test-stores"))


def boundary_from_environment(values: Mapping[str, str]) -> RuntimeBoundary | None:
    """Read only an explicit supplied mapping; no filesystem or ambient-environment access."""
    logical = values.get("CSA_RUNTIME_ROOT")
    physical = values.get("CSA_RUNTIME_PHYSICAL_ROOT")
    if logical is None:
        if physical is not None:
            raise StorePathError("STORE_RUNTIME_LOGICAL_ROOT_REQUIRED")
        return None
    logical_root = parse_runtime_path(logical)
    physical_root = logical_root if physical is None else parse_runtime_path(physical)
    return RuntimeBoundary(logical_root, physical_root)


def validate_store_location(path: Path, *, boundary: RuntimeBoundary) -> None:
    """Pure lexical validation shared by Settings and the connection guard."""
    _validate_windows_path(path)
    if path.suffix != ".sqlite3" or not any(
        path.is_relative_to(root) for root in boundary.store_roots
    ):
        raise StorePathError("STORE_OUTSIDE_ALLOWED_DIRECTORY")


def _inspect_chain(path: Path) -> None:
    for part in (*reversed(path.parents), path):
        try:
            info = _io_path(part).lstat()
        except FileNotFoundError as exc:
            if getattr(exc, "winerror", None) not in {None, 2, 3}:
                raise
            continue
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise StorePathError("STORE_REPARSE_POINT")
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise StorePathError("STORE_PARENT_NOT_DIRECTORY")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise StorePathError("STORE_HARDLINK")


def _fixed_volume(path: Path) -> None:
    if ctypes.windll.kernel32.GetDriveTypeW(str(path.anchor)) != 3:
        raise StorePathError("STORE_REQUIRES_FIXED_LOCAL_VOLUME")


def _physical_root(root: Path, *, must_exist: bool) -> None:
    _fixed_volume(root)
    _inspect_chain(root)
    if _io_path(root).exists() and not _io_path(root).is_dir():
        raise StorePathError("STORE_RUNTIME_NOT_DIRECTORY")
    if _resolved_path(root, strict=must_exist) != root:
        raise StorePathError("STORE_RUNTIME_MAPPING_CHANGED")


def initialize_runtime_root(boundary: RuntimeBoundary) -> None:
    """Explicit ordinary-root directory initialization only; never create a mapped alias."""
    root = boundary.physical_root
    _physical_root(root, must_exist=False)
    if _io_path(root).exists():
        _physical_root(root, must_exist=True)
        return
    if boundary.logical_root != root:
        raise StorePathError("STORE_MAPPED_RUNTIME_MUST_EXIST")
    for part in (*reversed(root.parents), root):
        if not _io_path(part).exists():
            _io_path(part).mkdir()
            _inspect_chain(part)
            if not _io_path(part).is_dir() or _resolved_path(part, strict=True) != part:
                raise StorePathError("STORE_RUNTIME_MAPPING_CHANGED")
    _physical_root(root, must_exist=True)


def guarded_store_path(path: Path, *, boundary: RuntimeBoundary, must_exist: bool) -> Path:
    validate_store_location(path, boundary=boundary)
    _fixed_volume(path)
    _physical_root(boundary.physical_root, must_exist=True)
    logical_input = path.is_relative_to(boundary.logical_root)
    if logical_input and boundary.logical_root != boundary.physical_root:
        _inspect_chain(boundary.logical_root)
        if _resolved_path(
            boundary.logical_root, strict=True
        ) != boundary.physical_root or not _io_path(boundary.logical_root).samefile(
            _io_path(boundary.physical_root)
        ):
            raise StorePathError("STORE_RUNTIME_MAPPING_CHANGED")
    _inspect_chain(path)
    resolved = _resolved_path(path, strict=must_exist)
    expected = (
        boundary.physical_root / path.relative_to(boundary.logical_root) if logical_input else path
    )
    if resolved != expected or not any(
        resolved.is_relative_to(boundary.physical_root / name) for name in ("stores", "test-stores")
    ):
        raise StorePathError("STORE_RESOLVED_OUTSIDE_BOUNDARY")
    _inspect_chain(resolved)
    if _io_path(path).exists() and not _io_path(path).is_file():
        raise StorePathError("STORE_NOT_REGULAR_FILE")
    for suffix in COMPANIONS:
        companion = Path(str(path) + suffix)
        _inspect_chain(companion)
        _inspect_chain(Path(str(resolved) + suffix))
        if _io_path(companion).exists() and not _io_path(companion).is_file():
            raise StorePathError("STORE_COMPANION_NOT_REGULAR_FILE")
    return resolved


def prepare_store_parent(path: Path, *, boundary: RuntimeBoundary) -> Path:
    """Explicit initializer-only directories; no Store or companion is created."""
    path = guarded_store_path(path, boundary=boundary, must_exist=False)
    for parent in reversed(path.parents):
        if not _io_path(parent).exists():
            _io_path(parent).mkdir()
            _inspect_chain(parent)
    return guarded_store_path(path, boundary=boundary, must_exist=False)


def reserve_new_store(path: Path, *, boundary: RuntimeBoundary) -> Path:
    """Explicit operator initialization only; never truncate or repair an existing path."""
    path = guarded_store_path(path, boundary=boundary, must_exist=False)
    if any(_io_path(Path(str(path) + suffix)).exists() for suffix in COMPANIONS):
        raise StorePathError("STORE_ORPHANED_COMPANION")
    path = prepare_store_parent(path, boundary=boundary)
    descriptor = os.open(_io_path(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    os.close(descriptor)
    return guarded_store_path(path, boundary=boundary, must_exist=True)
