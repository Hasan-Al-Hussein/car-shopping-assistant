"""Load exact sealed v1 code only at separately authorized future test runtime.

These are genuine old operator/state/file implementations with current shared
native Store dependencies. No receipt, intent or generation is relabelled.
The sealed files and the live app module registrations are never modified.
"""

import hashlib
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

from app.api.schemas.common import DTO
from app.database.paths import RuntimeBoundary
from tests.support.harness import PROJECT

_SEALED = PROJECT / "Records/build/OP-01/T11/staged/backend/app/operations"
_SOURCE_HASHES = {
    "restore_files": "ae0eab8a80771446b013ac9dbb4799d7eab1a22edfb14d65085f6a901a8d3842",
    "restore_state": "76554c4f2f716daef1c483db249259f77fa44cc82c523c27465f4901221788f7",
    "restore_operator": "7ee148f54a0e61e258d410af2dff434e52fc499dd113645c6070db48caee0272",
}


class V1Service(Protocol):
    """Shared public wire shape only; the actual returned classes belong to v1."""

    def restore(self, backup_id: str, *, expected_generation: str) -> DTO: ...

    def inspect(self) -> DTO | None: ...


def _load(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    path = _SEALED / (name + ".py")
    expected = _SOURCE_HASHES[name]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    module_name = "tests.operations._sealed_t11_v1_" + name
    assert module_name not in sys.modules
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their defining module during execution. This private
    # registration is removed by the fixture, never installed under app.*.
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    return module


@dataclass(frozen=True)
class SealedV1:
    files: ModuleType
    state: ModuleType
    operator: ModuleType

    def service(
        self, path: Path, *, boundary: RuntimeBoundary,
        clock: Callable[[], datetime] | None = None,
    ) -> V1Service:
        factory = cast(Callable[..., V1Service], self.operator.RestoreService)
        return factory(path, boundary=boundary, clock=clock)

    def encode(self, value: DTO) -> bytes:
        encoder = cast(Callable[[DTO], bytes], self.files.encoded)
        return encoder(value)


@pytest.fixture
def sealed_v1(monkeypatch: pytest.MonkeyPatch) -> SealedV1:
    files = _load("restore_files", monkeypatch)
    state = _load("restore_state", monkeypatch)
    operator = _load("restore_operator", monkeypatch)
    # Loading old source alone is insufficient: its absolute imports initially
    # resolve to the applied overlay. Bind every imported restore DTO/file helper
    # and prepare function to the exact old module, without changing app.*.
    for name in ("RestoreCandidate", "RestoreFiles", "RestoreIntent", "RestoreReceipt", "digest_store"):
        setattr(operator, name, getattr(files, name))
    operator.prepare_candidate = state.prepare_candidate
    assert operator.prepare_candidate is state.prepare_candidate
    assert operator.RestoreFiles is files.RestoreFiles
    assert operator.RestoreReceipt is files.RestoreReceipt
    assert operator.RestoreIntent is files.RestoreIntent
    assert operator.RestoreCandidate is files.RestoreCandidate
    assert operator.digest_store is files.digest_store
    assert files.RestoreReceipt.__module__ == files.__name__
    assert state.PreparedRestoreCandidate.__module__ == state.__name__
    assert operator.RestoreService.__module__ == operator.__name__
    return SealedV1(files, state, operator)
