"""Windows byte-range primitive; importing performs no native or file operations.

The caller owns path policy and scope. This handle is noninherited, synchronous,
non-waiting and opened without delete sharing. Never replace the companion file.
"""

import ctypes
import os
from pathlib import Path
from typing import Any


class NativeLockError(OSError):
    pass


class NativeLockBusy(NativeLockError):
    pass


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", ctypes.c_uint32),
        ("OffsetHigh", ctypes.c_uint32),
        ("hEvent", ctypes.c_void_p),
    ]


def _kernel() -> Any:
    if os.name != "nt":
        raise NativeLockError("MAINTENANCE_WINDOWS_REQUIRED")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                               ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    api.CreateFileW.restype = ctypes.c_void_p
    api.LockFileEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                              ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(_Overlapped)]
    api.LockFileEx.restype = ctypes.c_int
    api.CloseHandle.argtypes = [ctypes.c_void_p]
    api.CloseHandle.restype = ctypes.c_int
    return api


class NativeFileLock:
    """One actual OS handle; callers serialize cross-thread use where needed."""

    def __init__(self, descriptor: int, api: Any) -> None:
        self._descriptor: int | None = descriptor
        self._api = api
        self._pid = os.getpid()
        self._locked = False
        self._overlapped = _Overlapped()

    @classmethod
    def open(cls, path: Path, *, create: bool = False) -> "NativeFileLock":
        api = _kernel()
        import msvcrt

        # GENERIC_READ|WRITE, FILE_SHARE_READ|WRITE (no DELETE), null security
        # attributes (not inherited), OPEN_ALWAYS only for explicit provisioning,
        # otherwise OPEN_EXISTING; inspect reparse objects instead of following.
        # The caller has already validated the absolute physical local path.
        # Use extended Win32 spelling so native open supports approved long paths
        # without changing the stored path, boundary checks, or sharing flags.
        native_path = "\\\\?\\" + str(path)
        handle = api.CreateFileW(native_path, 0xC0000000, 0x00000003, None,
                                 4 if create else 3, 0x00200000, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            code = ctypes.get_last_error()
            if code in {32, 33}:
                raise NativeLockBusy("MAINTENANCE_GUARD_BUSY")
            raise NativeLockError("MAINTENANCE_GUARD_UNAVAILABLE")
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_BINARY | os.O_NOINHERIT)
        except BaseException:
            api.CloseHandle(handle)
            raise
        return cls(descriptor, api)

    def _live_descriptor(self) -> int:
        if os.getpid() != self._pid or self._descriptor is None:
            raise NativeLockError("MAINTENANCE_HANDLE_NOT_LIVE")
        return self._descriptor

    def stat(self) -> os.stat_result:
        return os.fstat(self._live_descriptor())

    @property
    def held(self) -> bool:
        self._live_descriptor()
        return self._locked

    def lock(self, *, exclusive: bool) -> None:
        import msvcrt

        descriptor = self._live_descriptor()
        if self._locked:
            raise NativeLockError("MAINTENANCE_HANDLE_ALREADY_LOCKED")
        # LOCKFILE_FAIL_IMMEDIATELY | optional LOCKFILE_EXCLUSIVE_LOCK.
        flags = 1 | (2 if exclusive else 0)
        if not self._api.LockFileEx(msvcrt.get_osfhandle(descriptor), flags, 0,
                                    1, 0, ctypes.byref(self._overlapped)):
            code = ctypes.get_last_error()
            if code in {32, 33, 997}:
                raise NativeLockBusy("MAINTENANCE_GUARD_BUSY")
            raise NativeLockError("MAINTENANCE_LOCK_UNAVAILABLE")
        self._locked = True

    def close(self) -> None:
        if os.getpid() != self._pid:
            raise NativeLockError("MAINTENANCE_FOREIGN_PROCESS")
        descriptor = self._descriptor
        if descriptor is None:
            return
        # Closing the actual handle releases its byte-range lock. Do not unlock
        # first: a later close failure must not leave an unlocked retained pin.
        os.close(descriptor)
        self._descriptor = None
        self._locked = False
