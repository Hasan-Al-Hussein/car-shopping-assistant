"""Stateless structured-output adapter. No domain tools or mutation authority exist here."""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Annotated, Any, Final, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.api.schemas.common import Id
from app.core.config import CONFIGURATION_VERSION, FrozenSettings, Settings
from app.core.diagnostics import ProviderFailurePhase, ProviderHttpStatus
from app.core.readiness import ProviderObservation, ReadinessRegistry
from app.database.store import assert_outside_write_transaction

from .budget import BudgetExhausted, TurnBudget
from .packet import (
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_BYTES,
    MAX_OUTPUT_TOKENS,
    EvidencePacket,
    output_system_instruction,
)

ADAPTER_VERSION: Final = "BE20-ADAPTER-1"
SDK_VERSION: Final = "2.25.0"
FailureCode = Literal[
    "disabled",
    "not_configured",
    "auth",
    "quota",
    "model_missing",
    "timeout",
    "unavailable",
    "malformed",
    "output_too_large",
    "input_too_large",
    "invalid_schema",
    "attempt_limit",
]


class UsageSummary(FrozenSettings):
    # None is unavailable usage, never a fabricated zero.
    input_tokens: Annotated[int | None, Field(ge=0, le=10**9)] = None
    output_tokens: Annotated[int | None, Field(ge=0, le=10**9)] = None
    total_tokens: Annotated[int | None, Field(ge=0, le=10**9)] = None


class ProviderDiagnostic(FrozenSettings):
    request_id: Id
    model: Literal["gemini-3.5-flash-lite"] = "gemini-3.5-flash-lite"
    sdk_version: Literal["2.25.0"] = SDK_VERSION
    adapter_version: Literal["BE20-ADAPTER-1"] = ADAPTER_VERSION
    configuration_version: Literal["F04-CONFIG-2"] = CONFIGURATION_VERSION
    state: Literal["available", "unavailable"]
    code: FailureCode | None
    attempts: Annotated[int, Field(ge=0, le=2)]
    failure_phase: ProviderFailurePhase | None = None
    http_status: ProviderHttpStatus = None
    elapsed_ms: Annotated[int, Field(ge=0, le=2_147_483_647)]
    usage: UsageSummary


@dataclass(frozen=True)
class TransportRequest:
    contents: str = field(repr=False)
    schema: dict[str, Any] = field(repr=False)
    repair: bool = False
    attempt_seconds: float = 15
    connect_seconds: float = 5


@dataclass(frozen=True)
class TransportResponse:
    text: str = field(repr=False)
    usage: UsageSummary = field(default_factory=UsageSummary)


class ProviderFault(Exception):
    def __init__(
        self, code: FailureCode, *, failure_phase: ProviderFailurePhase | None = None,
        http_status: ProviderHttpStatus = None,
    ) -> None:
        self.code = code
        self.failure_phase = failure_phase
        self.http_status = http_status
        super().__init__(code)


class ProviderBoundaryFailure(Exception):
    """Safe metadata for setup/cleanup errors that already terminate without retry."""

    def __init__(
        self, *, failure_phase: ProviderFailurePhase, http_status: ProviderHttpStatus = None,
    ) -> None:
        self.failure_phase = failure_phase
        self.http_status = http_status
        super().__init__("PROVIDER_BOUNDARY_FAILURE")


class ProviderTransport(Protocol):
    async def generate(self, request: TransportRequest) -> TransportResponse: ...


@dataclass(frozen=True)
class ProviderResult[T: BaseModel]:
    state: Literal["available", "unavailable"]
    proposal: T | None
    diagnostic: ProviderDiagnostic


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("DUPLICATE_JSON_KEY")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError("NONFINITE_JSON_CONSTANT")


def _finite_float(value: str) -> float:
    number = float(value)
    if not isfinite(number):
        raise ValueError("NONFINITE_JSON_NUMBER")
    return number


class GeminiAdapter:
    """One transport attempt in flight per instance; queued time consumes turn budget.

    The lock remains held until a cancelled transport actually finishes. This prevents
    retries piling up behind a cancellation-resistant transport, without accepting late data.
    No background finalizer publishes results/readiness or performs domain actions.
    """

    def __init__(
        self,
        settings: Settings,
        transport: ProviderTransport,
        *,
        readiness: ReadinessRegistry | None = None,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._readiness = readiness
        self._utc_now = utc_now
        self._lock = asyncio.Lock()
        self._active: asyncio.Task[TransportResponse] | None = None
        self._stopped = False
        self._running = 0
        self._idle = asyncio.Event()
        self._idle.set()
        self._shutdown_cancelled: asyncio.Task[TransportResponse] | None = None

    @property
    def pending(self) -> bool:
        """Actual adapter calls or retained transport work, including lock waiters."""
        return self._running > 0 or self._active is not None

    def _refresh_idle(self) -> None:
        if self.pending:
            self._idle.clear()
        else:
            self._idle.set()

    def stop(self) -> None:
        """Permanently stop admission on the application's owning event loop."""
        self._stopped = True

    async def close(self, *, timeout_seconds: float = 5.0) -> bool:
        """Stop and request cancellation, returning False until all work really settles.

        This never closes/replaces the owner's underlying HTTP transport. The application
        must retain this adapter and its client while False, and close the client only
        after True. Cancellation-resistant transport remains visible through pending.
        """
        if not isfinite(timeout_seconds) or not 0 <= timeout_seconds <= 30:
            raise ValueError("PROVIDER_CLOSE_TIMEOUT_INVALID")
        self.stop()
        active = self._active
        if active is not None and not active.done() and active is not self._shutdown_cancelled:
            self._shutdown_cancelled = active
            active.cancel()
        if not self.pending:
            return True
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return False
        return not self.pending

    async def _attempt(
        self, contents: str, schema: dict[str, Any], repair: bool, budget: TurnBudget
    ) -> TransportResponse:
        if budget.remaining() <= 0:
            raise ProviderFault("timeout", failure_phase="attempt")
        try:
            await asyncio.wait_for(self._lock.acquire(), timeout=budget.remaining())
        except TimeoutError:
            raise ProviderFault("timeout", failure_phase="attempt") from None
        if self._stopped:
            self._lock.release()
            raise ProviderFault("disabled", failure_phase="attempt")
        try:
            attempt_seconds, connect_seconds = budget.begin_provider_attempt()
        except BudgetExhausted:
            self._lock.release()
            raise ProviderFault(
                "timeout" if budget.remaining() <= 0 else "attempt_limit",
                failure_phase="attempt",
            ) from None
        started = budget.clock()
        task = asyncio.create_task(
            self._transport.generate(
                TransportRequest(
                    contents=contents,
                    schema=schema,
                    repair=repair,
                    attempt_seconds=attempt_seconds,
                    connect_seconds=connect_seconds,
                )
            )
        )
        self._active = task

        def finished(completed: asyncio.Task[TransportResponse]) -> None:
            self._active = None
            self._shutdown_cancelled = None
            self._lock.release()
            self._refresh_idle()
            # Retrieve exceptions from late completions, but never their content/output.
            if not completed.cancelled():
                completed.exception()

        task.add_done_callback(finished)
        try:
            done, _ = await asyncio.wait({task}, timeout=attempt_seconds)
            if not done:
                task.cancel()
                raise ProviderFault("timeout", failure_phase="attempt")
            if budget.remaining() <= 0 or budget.clock() - started >= attempt_seconds:
                raise ProviderFault("timeout", failure_phase="attempt")
            return task.result()
        except asyncio.CancelledError:
            task.cancel()
            raise

    async def generate[T: BaseModel](
        self,
        packet: EvidencePacket,
        output_type: type[T],
        *,
        budget: TurnBudget,
        request_id: str,
        private_values: tuple[str, ...] = (),
    ) -> ProviderResult[T]:
        """Track admitted and queued calls until their actual coroutine settlement."""
        self._running += 1
        self._refresh_idle()
        try:
            return await self._generate(
                packet, output_type, budget=budget, request_id=request_id,
                private_values=private_values,
            )
        finally:
            self._running -= 1
            self._refresh_idle()

    async def _generate[T: BaseModel](
        self,
        packet: EvidencePacket,
        output_type: type[T],
        *,
        budget: TurnBudget,
        request_id: str,
        private_values: tuple[str, ...] = (),
    ) -> ProviderResult[T]:
        """Caller supplies one turn ledger, including the HTTP boundary's deadline_at.

        output_type is trusted application code with extra=forbid, not buyer/model input.
        Structured validity is not factual grounding or permission to execute the proposal.
        """
        assert_outside_write_transaction()
        start = budget.clock()
        prior_attempts = budget.provider_attempts
        usages: list[UsageSummary] = []

        def result(
            code: FailureCode | None, proposal: T | None = None, *,
            failure_phase: ProviderFailurePhase | None = None,
            http_status: ProviderHttpStatus = None,
        ) -> ProviderResult[T]:
            state: Literal["available", "unavailable"] = (
                "available" if code is None else "unavailable"
            )

            def sum_usage(values: list[int | None]) -> int | None:
                if len(values) != budget.provider_attempts - prior_attempts:
                    return None
                if not values or any(value is None for value in values):
                    return None
                total = sum(value for value in values if value is not None)
                return total if total <= 10**9 else None

            diagnostic = ProviderDiagnostic(
                request_id=request_id,
                state=state,
                code=code,
                attempts=budget.provider_attempts - prior_attempts,
                failure_phase=failure_phase,
                http_status=http_status,
                elapsed_ms=min(2_147_483_647, max(0, int((budget.clock() - start) * 1000))),
                usage=UsageSummary(
                    input_tokens=sum_usage([usage.input_tokens for usage in usages]),
                    output_tokens=sum_usage([usage.output_tokens for usage in usages]),
                    total_tokens=sum_usage([usage.total_tokens for usage in usages]),
                ),
            )
            if (
                self._readiness is not None
                and not self._stopped
                and diagnostic.attempts > 0
                and code
                not in {
                    "input_too_large",
                    "invalid_schema",
                    "attempt_limit",
                }
            ):
                observation = ProviderObservation(
                    state="ready" if code is None else "unavailable", observed_at=self._utc_now()
                )
                self._readiness.update(
                    lambda snapshot: snapshot.model_copy(update={"provider": observation})
                )
            return ProviderResult(state=state, proposal=proposal, diagnostic=diagnostic)

        if self._stopped or not self._settings.assistant_enabled:
            return result("disabled", failure_phase="admission")
        if not self._settings.provider_configured:
            return result("not_configured", failure_phase="admission")
        if budget.timeouts != self._settings.timeouts:
            # A caller must not enlarge a configured timeout/attempt/tool policy by
            # constructing a ledger with different limits.
            return result("unavailable", failure_phase="admission")
        if len(private_values) > 64 or any(len(value) > 4096 for value in private_values):
            return result("input_too_large", failure_phase="admission")
        if output_type.model_config.get("extra") != "forbid":
            return result("invalid_schema", failure_phase="schema")
        try:
            schema = output_type.model_json_schema()
            key = self._settings.gemini_api_key
            omitted = private_values + ((key.get_secret_value(),) if key is not None else ())
            contents = packet.minimized_json(omitted)
            # Count JSON-string escaping for the trusted schema instruction and user
            # contents, maximal repair, plus the existing provider-framing reserve.
            instruction = output_system_instruction(schema, repair=True)
            budget_bytes = (
                len(json.dumps(contents, ensure_ascii=True, allow_nan=False).encode("utf-8"))
                + len(json.dumps(instruction, ensure_ascii=True, allow_nan=False).encode("utf-8"))
                + 1024
            )
            if budget_bytes > MAX_INPUT_TOKENS:
                return result("input_too_large", failure_phase="schema")
        except (ValueError, TypeError, RecursionError):
            return result("invalid_schema", failure_phase="schema")

        repair = False
        while True:
            try:
                response = await self._attempt(contents, schema, repair, budget)
                if self._stopped:
                    return result("disabled", failure_phase="admission")
                usages.append(response.usage)
                if (
                    response.usage.input_tokens is not None
                    and response.usage.input_tokens > MAX_INPUT_TOKENS
                ):
                    raise ProviderFault("input_too_large", failure_phase="output_validation")
                if len(response.text.encode("utf-8")) > MAX_OUTPUT_BYTES or (
                    response.usage.output_tokens is not None
                    and response.usage.output_tokens > MAX_OUTPUT_TOKENS
                ):
                    raise ProviderFault("output_too_large", failure_phase="output_validation")
                try:
                    decoded = json.loads(
                        response.text,
                        object_pairs_hook=_unique_object,
                        parse_constant=_reject_constant,
                        parse_float=_finite_float,
                    )
                    proposal = output_type.model_validate(decoded, strict=True)
                except (ValueError, TypeError, ValidationError, RecursionError):
                    raise ProviderFault("malformed", failure_phase="output_validation") from None
                if budget.remaining() <= 0:
                    return result("timeout", failure_phase="attempt")
                return result(None, proposal)
            except ProviderFault as fault:
                # Quota/auth/model/oversize/timeout never trigger automatic amplification.
                # Observed HTTP400 is terminal without changing its public failure code.
                # A single malformed-output repair or transient service retry can consume
                # the second shared attempt, with no provider body echoed into the prompt.
                if fault.code not in {"malformed", "unavailable"} or (
                    fault.http_status == 400
                    or budget.provider_attempts >= budget.timeouts.provider_attempts
                    or budget.remaining() <= 0
                    or self._lock.locked()
                ):
                    return result(
                        fault.code, failure_phase=fault.failure_phase, http_status=fault.http_status
                    )
                repair = fault.code == "malformed"
            except ProviderBoundaryFailure as fault:
                # These escaped the transport's old retry mapping; preserve that path.
                return result(
                    "unavailable", failure_phase=fault.failure_phase, http_status=fault.http_status
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                return result("unavailable", failure_phase="adapter")
