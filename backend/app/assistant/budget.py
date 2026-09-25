"""One monotonic deadline and attempt ledger shared by the whole conversation turn."""

from collections.abc import Callable
from dataclasses import dataclass, field
from math import isfinite
from time import monotonic

from app.core.config import Timeouts


class BudgetExhausted(Exception):
    pass


@dataclass
class TurnBudget:
    timeouts: Timeouts
    deadline_at: float
    clock: Callable[[], float] = field(default=monotonic, repr=False)
    provider_attempts: int = field(default=0, init=False)
    tool_invocations: int = field(default=0, init=False)
    started_at: float = field(init=False)

    def __post_init__(self) -> None:
        self.started_at = self.clock()
        if not isfinite(self.deadline_at):
            raise ValueError("FINITE_DEADLINE_REQUIRED")
        self.deadline_at = min(self.deadline_at, self.started_at + self.timeouts.operation_seconds)

    def remaining(self) -> float:
        return max(0.0, self.deadline_at - self.clock())

    def begin_provider_attempt(self) -> tuple[float, float]:
        remaining = self.remaining()
        if remaining <= 0 or self.provider_attempts >= self.timeouts.provider_attempts:
            raise BudgetExhausted
        self.provider_attempts += 1
        attempt = min(remaining, self.timeouts.provider_attempt_seconds)
        return attempt, min(attempt, self.timeouts.provider_connect_seconds)

    def begin_tool(self) -> None:
        """Accounting only; the later coordinator still validates/authorizes each tool."""
        if self.remaining() <= 0 or self.tool_invocations >= self.timeouts.tool_invocations:
            raise BudgetExhausted
        self.tool_invocations += 1
