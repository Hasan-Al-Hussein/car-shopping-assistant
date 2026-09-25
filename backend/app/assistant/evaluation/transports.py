"""Finite explicit offline script or opt-in, free-only bounded live transport."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from time import monotonic
from typing import Annotated

from pydantic import Field

from app.assistant.provider import ProviderFault, ProviderTransport, TransportRequest, TransportResponse
from app.core.config import FrozenSettings, Settings

from .schema import Step


class ScriptedTransport:
    def __init__(self) -> None:
        self.step: Step | None = None
        self.calls = 0

    async def generate(self, request: TransportRequest) -> TransportResponse:
        self.calls += 1
        step = self.step
        if step is None:
            raise ProviderFault("unavailable")
        if step.fault == "malformed":
            return TransportResponse("synthetic invalid JSON")
        if step.fault is not None:
            raise ProviderFault(step.fault)
        if step.intent is None:
            raise ProviderFault("unavailable")
        return TransportResponse(step.intent.model_dump_json())


class LivePermission(FrozenSettings):
    enabled: bool = False
    approved_free_only: bool = False
    max_calls: Annotated[int, Field(ge=1, le=100)] = 1
    max_seconds: Annotated[int, Field(ge=1, le=1500)] = 1500
    access_evidence_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    def require(self, settings: Settings) -> None:
        if not (self.enabled and self.approved_free_only and settings.assistant_enabled
                and settings.provider_configured and settings.policy.provider_spend_limit == 0):
            raise ValueError("LIVE_EVALUATION_NOT_AUTHORIZED")


@dataclass
class LimitedLiveTransport:
    delegate: ProviderTransport
    limit: int
    calls: int = 0
    refused: int = 0
    max_seconds: float = 1500
    clock: Callable[[], float] = field(default=monotonic, repr=False)
    sleep: Callable[[float], Awaitable[None]] = field(default=asyncio.sleep, repr=False)
    deadline_at: float = field(init=False)
    next_call_at: float = field(default=0, init=False)
    stopped_reason: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100 or not 0 < self.max_seconds <= 1500:
            raise ValueError("INVALID_LIVE_EVALUATION_BUDGET")
        self.deadline_at = self.clock() + self.max_seconds

    def stop_reason(self) -> str | None:
        if self.stopped_reason is not None:
            return self.stopped_reason
        if self.clock() >= self.deadline_at:
            return "LIVE_TIME_BUDGET_EXHAUSTED"
        if self.calls >= self.limit:
            return "LIVE_CALL_BUDGET_EXHAUSTED"
        return None

    async def generate(self, request: TransportRequest) -> TransportResponse:
        if self.stop_reason() is not None:
            self.refused += 1
            raise ProviderFault("attempt_limit")
        started = self.clock()
        delay = max(0.0, self.next_call_at - started)
        remaining = min(request.attempt_seconds, self.deadline_at - started)
        if delay >= remaining:
            self.stopped_reason = (
                "LIVE_TIME_BUDGET_EXHAUSTED"
                if self.deadline_at - started <= delay
                else "LIVE_PACING_EXCEEDS_ATTEMPT_DEADLINE"
            )
            self.refused += 1
            raise ProviderFault("attempt_limit")
        if delay:
            await self.sleep(delay)
        now = self.clock()
        remaining = min(request.attempt_seconds - (now - started), self.deadline_at - now)
        if remaining <= 0 or self.stop_reason() is not None:
            self.stopped_reason = self.stop_reason() or "LIVE_PACING_EXCEEDS_ATTEMPT_DEADLINE"
            self.refused += 1
            raise ProviderFault("attempt_limit")
        # Every delegate admission, including repair/retry, is spaced by six seconds.
        # This is conservative local pacing, not a statement about current account quota.
        self.next_call_at = now + 6.0
        self.calls += 1
        bounded = replace(
            request, attempt_seconds=remaining,
            connect_seconds=min(request.connect_seconds, remaining),
        )
        try:
            return await self.delegate.generate(bounded)
        except ProviderFault as fault:
            if fault.code in {"quota", "auth", "model_missing"}:
                self.stopped_reason = f"LIVE_PROVIDER_{fault.code.upper()}"
            raise
