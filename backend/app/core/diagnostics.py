"""An allowlist of request facts, with no exception text, URLs or buyer payloads."""

import json
import logging
import re
from collections.abc import Callable, MutableMapping
from dataclasses import asdict, dataclass
from queue import Empty, Full, Queue
from threading import Condition, Event, Lock, Thread
from typing import Annotated, Any, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.common import Id
from app.core.config import CONFIGURATION_VERSION, CONTRACT_VERSION, POLICY_VERSION, FrozenSettings

ProviderFailurePhase = Literal[
    "admission", "schema", "attempt", "transport_setup", "sdk_setup", "sdk_request",
    "http_guard", "http_connect", "http_timeout", "http_transport", "http_response",
    "sdk_response", "output_validation", "cleanup", "adapter",
]
ProviderHttpStatus = Annotated[int | None, Field(ge=100, le=599)]


class ProviderUsage(FrozenSettings):
    model_config = ConfigDict(revalidate_instances="always")

    input_tokens: Annotated[int | None, Field(ge=0, le=10**9)] = None
    output_tokens: Annotated[int | None, Field(ge=0, le=10**9)] = None
    total_tokens: Annotated[int | None, Field(ge=0, le=10**9)] = None


class ProviderMetric(FrozenSettings):
    """Closed internal metadata; core never imports a provider implementation."""

    model_config = ConfigDict(revalidate_instances="always")

    request_id: Id
    model: Literal["gemini-3.5-flash-lite"] = "gemini-3.5-flash-lite"
    sdk_version: Literal["2.25.0"] = "2.25.0"
    adapter_version: Literal["BE20-ADAPTER-1"] = "BE20-ADAPTER-1"
    configuration_version: Literal["F04-CONFIG-2"] = CONFIGURATION_VERSION
    state: Literal["available", "unavailable"]
    code: (
        Literal[
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
        | None
    )
    attempts: Annotated[int, Field(ge=0, le=2)]
    failure_phase: ProviderFailurePhase | None = None
    http_status: ProviderHttpStatus = None
    elapsed_ms: Annotated[int, Field(ge=0, le=2_147_483_647)]
    usage: ProviderUsage

    @model_validator(mode="after")
    def coherent_state(self) -> Self:
        if (self.state == "available") != (self.code is None):
            raise ValueError("INVALID_PROVIDER_METRIC_STATE")
        if self.state == "available" and (
            self.failure_phase is not None or self.http_status is not None
        ):
            raise ValueError("INVALID_PROVIDER_FAILURE_METADATA")
        if self.http_status is not None and self.failure_phase not in {
            "http_timeout", "http_transport", "http_response", "sdk_response", "cleanup",
        }:
            raise ValueError("INVALID_PROVIDER_HTTP_STATUS_PHASE")
        return self


def _checked_metric(metric: ProviderMetric) -> ProviderMetric:
    if type(metric) is not ProviderMetric:
        raise ValueError("TYPED_PROVIDER_METRIC_REQUIRED")
    return ProviderMetric.model_validate(metric)


class ProviderMetricSlot:
    """One bounded metric, atomically closed against late worker completions."""

    def __init__(self, request_id: str) -> None:
        self._request_id = request_id
        self._lock = Lock()
        self._closed = False
        self._metric: ProviderMetric | None = None

    def attach(self, metric: ProviderMetric) -> bool:
        checked = _checked_metric(metric)
        with self._lock:
            if self._closed or checked.request_id != self._request_id:
                return False
            self._metric = checked
            return True

    def close(self, request_id: str) -> ProviderMetric | None:
        with self._lock:
            self._closed = True
            metric, self._metric = self._metric, None
            return metric if request_id == self._request_id else None


def attach_provider_metric(state: MutableMapping[str, Any], metric: ProviderMetric) -> bool:
    """Trusted coordinator only; attach a completed call to its still-open request."""
    checked = _checked_metric(metric)
    slot = state.get("provider_metric_slot")
    if type(slot) is not ProviderMetricSlot or state.get("request_id") != checked.request_id:
        return False
    return slot.attach(checked)


def close_provider_metric(
    state: MutableMapping[str, Any], request_id: str
) -> ProviderMetric | None:
    """Close before the HTTP boundary emits; invalid enrichment is simply omitted."""
    slot = state.get("provider_metric_slot")
    return slot.close(request_id) if type(slot) is ProviderMetricSlot else None


@dataclass(frozen=True)
class DiagnosticContext:
    """Trusted domain enrichment only; never populate from raw request fields."""

    operation_ref: str | None = None
    snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if self.operation_ref is not None and (
            not isinstance(self.operation_ref, str)
            or re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", self.operation_ref
            )
            is None
        ):
            raise ValueError("INVALID_DIAGNOSTIC_REFERENCE")
        if self.snapshot_id is not None and (
            not isinstance(self.snapshot_id, str)
            or re.fullmatch(r"[0-9a-f]{64}", self.snapshot_id) is None
        ):
            raise ValueError("INVALID_DIAGNOSTIC_REFERENCE")


@dataclass(frozen=True)
class RequestEvent:
    request_id: str
    operation: str
    method: str
    status: int
    outcome: str
    error_code: str | None
    duration_ms: int
    operation_ref: str | None = None
    snapshot_id: str | None = None
    contract_version: str = CONTRACT_VERSION
    policy_version: str = POLICY_VERSION
    configuration_version: str = CONFIGURATION_VERSION
    provider: ProviderMetric | None = None

    def __post_init__(self) -> None:
        if self.provider is not None:
            checked = _checked_metric(self.provider)
            if checked.request_id != self.request_id:
                raise ValueError("PROVIDER_REQUEST_MISMATCH")
            object.__setattr__(self, "provider", checked)


class EventDispatcher:
    """Bounded best-effort telemetry; one lazy daemon worker for the process."""

    def __init__(self, capacity: int = 128) -> None:
        if capacity < 1 or capacity > 128:
            raise ValueError("INVALID_DIAGNOSTIC_CAPACITY")
        self._queue: Queue[tuple[RequestEvent, Callable[[RequestEvent], None]]] = Queue(capacity)
        self._lock = Lock()
        self._idle = Condition(self._lock)
        self._pending = 0
        self._stopped = Event()
        self._worker: Thread | None = None

    def submit(self, event: RequestEvent, sink: Callable[[RequestEvent], None]) -> bool:
        # No consumer I/O on this path. Saturation drops the new event, never a request.
        with self._lock:
            if self._stopped.is_set():
                return False
            if self._worker is None:
                worker = Thread(target=self._run, name="csa-diagnostics", daemon=True)
                try:
                    worker.start()
                except RuntimeError:
                    return False
                self._worker = worker
            try:
                self._queue.put_nowait((event, sink))
            except Full:
                return False
            self._pending += 1
            return True

    def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                event, sink = self._queue.get(timeout=0.1)
            except Empty:
                continue
            try:
                sink(event)
            except Exception:
                # No recursive logging, retries, replacement threads or response changes.
                pass
            finally:
                self._queue.task_done()
                with self._idle:
                    self._pending -= 1
                    self._idle.notify_all()

    def wait_idle(self, timeout: float) -> bool:
        """Bounded operator/test drain; never called from the request path."""
        with self._idle:
            return self._idle.wait_for(lambda: self._pending == 0, timeout=max(0, timeout))

    def close(self, timeout: float = 0.1) -> bool:
        """Stop accepting events; a blocked sink cannot be forcibly cancelled."""
        with self._lock:
            self._stopped.set()
            worker = self._worker
        if worker is not None:
            worker.join(timeout=max(0, min(timeout, 1)))
        return worker is None or not worker.is_alive()


# Construction performs no I/O and starts no thread. All app instances share one
# bounded worker; a stuck sink cannot spawn an unbounded population of replacements.
REQUEST_EVENTS = EventDispatcher()


def prepare_request_logging() -> None:
    # Uvicorn's default access line contains the raw URL/query. The launcher must also
    # use --no-access-log, including when logging is configured after app construction.
    logging.getLogger("uvicorn.access").disabled = True
    logger = logging.getLogger("car_shopping.requests")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


def emit_request_event(event: RequestEvent) -> None:
    payload = asdict(event)
    if event.provider is None:
        # Preserve the original event wire/log shape when there is no enrichment.
        del payload["provider"]
    else:
        checked = _checked_metric(event.provider)
        if checked.request_id != event.request_id:
            raise ValueError("PROVIDER_REQUEST_MISMATCH")
        payload["provider"] = checked.model_dump(mode="json")
    logging.getLogger("car_shopping.requests").info(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    )
