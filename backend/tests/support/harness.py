"""Stateless synthetic dependencies. No SDK, database, socket or filesystem writes."""

import asyncio
import json
import os
import re
from collections import deque
from collections.abc import Callable, Coroutine, Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath
from typing import Any, Literal
from uuid import UUID

import httpx

from app.database.paths import RuntimeBoundary, boundary_from_environment

PROJECT = Path(__file__).resolve().parents[3]


def configured_runtime_boundary() -> RuntimeBoundary:
    """Read explicit operator test authority lazily; never create or resolve a path."""
    boundary = boundary_from_environment(os.environ)
    if boundary is None:
        raise ValueError("TEST_RUNTIME_BOUNDARY_NOT_CONFIGURED")
    return boundary


def runtime_environment(boundary: RuntimeBoundary | None = None) -> dict[str, str]:
    """Supply only boundary settings, not unrelated inherited CSA/provider inputs."""
    selected = boundary if boundary is not None else configured_runtime_boundary()
    return {
        "CSA_RUNTIME_ROOT": str(selected.logical_root),
        "CSA_RUNTIME_PHYSICAL_ROOT": str(selected.physical_root),
    }


def read_seed() -> dict[str, Any]:
    value = json.loads((PROJECT / "fixtures/shared/harness-seed.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Harness seed must be an object.")
    return value


@dataclass
class FrozenClock:
    instant: datetime

    def __post_init__(self) -> None:
        if self.instant.tzinfo is None or self.instant.utcoffset() != timedelta(0):
            raise ValueError("A fixture clock requires an explicit UTC instant.")

    def now(self) -> datetime:
        return self.instant

    def advance(self, seconds: int) -> None:
        if seconds < 0:
            raise ValueError("Advance is monotonic; create a fresh fixture to reset time.")
        self.instant += timedelta(seconds=seconds)


@dataclass(frozen=True)
class OwnerSpec:
    """Synthetic test input, never a verified authorization context or credential."""

    owner_id: str
    context_id: str
    display_name: str


def owner_specs() -> tuple[OwnerSpec, OwnerSpec]:
    owners = read_seed()["owners"]
    return OwnerSpec(**owners[0]), OwnerSpec(**owners[1])


def new_clock() -> FrozenClock:
    return FrozenClock(datetime.fromisoformat(read_seed()["clock_utc"]).astimezone(UTC))


def run_bounded(exercise: Coroutine[Any, Any, None], timeout_seconds: float = 3) -> None:
    async def bounded() -> None:
        async with asyncio.timeout(timeout_seconds):
            await exercise

    asyncio.run(bounded())


class ProviderFault(RuntimeError):
    def __init__(self, code: Literal["timeout", "quota", "unavailable"]) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderStep:
    kind: Literal["success", "malformed", "timeout", "quota", "unavailable"]
    payload: dict[str, Any] | str = ""


class ScriptedProvider:
    """Finite script only: exhausted scripts fail instead of calling a live provider."""

    def __init__(self, steps: Iterable[ProviderStep]) -> None:
        self._steps = deque(deepcopy(list(steps)))
        self.calls = 0

    def complete(self, prompt: str) -> dict[str, Any] | str:
        if not prompt or len(prompt) > 16000:
            raise ValueError("Fixture prompts must be nonempty and bounded.")
        if not self._steps:
            raise AssertionError("UNSCRIPTED_PROVIDER_CALL")
        self.calls += 1
        step = self._steps.popleft()
        if step.kind in {"timeout", "quota", "unavailable"}:
            raise ProviderFault(step.kind)
        return deepcopy(step.payload)


@dataclass(frozen=True)
class HttpStep:
    method: str
    path: str
    status: int = 200
    payload: Any = None
    gate: asyncio.Event | None = None
    on_accept: Callable[[], None] | None = None
    lose_response: bool = False


class ScriptedHttpTransport(httpx.AsyncBaseTransport):
    """Inject into AsyncClient; gates order replies without clock sleeps or real I/O."""

    def __init__(self, steps: Iterable[HttpStep]) -> None:
        self._steps = deque(steps)
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "fixture.invalid" or not self._steps:
            raise AssertionError("UNSCRIPTED_HTTP_CALL")
        step = self._steps.popleft()
        if (request.method, request.url.path) != (step.method, step.path):
            raise AssertionError("UNEXPECTED_HTTP_COMMAND")
        self.calls += 1
        if step.on_accept:
            step.on_accept()
        if step.gate:
            await step.gate.wait()
        if step.lose_response:
            raise httpx.ReadError("SYNTHETIC_RESPONSE_LOST_AFTER_ACCEPT", request=request)
        return httpx.Response(step.status, json=deepcopy(step.payload), request=request)


@dataclass(frozen=True)
class UnopenedStorePlan:
    """An inert plan, not permission to create/open a store or skip later path checks."""

    path: PureWindowsPath
    store_generation: str
    schema_state: Literal["fresh", "old_revision", "incompatible", "corrupt"]
    fault: Literal["none", "write_rejected", "projection_failed", "response_lost"]
    state: Literal["unopened"] = "unopened"
    requires_resolved_path_check: Literal[True] = True


def unopened_store_plan(
    *,
    run_id: str,
    case_id: str,
    generation: str,
    schema_state: Literal["fresh", "old_revision", "incompatible", "corrupt"] = "fresh",
    fault: Literal["none", "write_rejected", "projection_failed", "response_lost"] = "none",
) -> UnopenedStorePlan:
    run = str(UUID(run_id))
    gen = str(UUID(generation))
    if not re.fullmatch(r"case-[a-z0-9][a-z0-9-]{0,60}", case_id):
        raise ValueError("Use a bounded case-prefixed slug; path input is not allowed.")
    return UnopenedStorePlan(
        path=(
            PureWindowsPath(configured_runtime_boundary().logical_root)
            / "test-stores" / run / case_id / "test.sqlite3"
        ),
        store_generation=gen,
        schema_state=schema_state,
        fault=fault,
    )
