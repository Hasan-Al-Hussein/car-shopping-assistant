"""Offline A2 slot integration; no routes, provider network, database or logger worker."""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from app.assistant.budget import TurnBudget
from app.assistant.packet import EvidencePacket
from app.assistant.provider import (
    GeminiAdapter,
    ProviderDiagnostic,
    ProviderFault,
    TransportRequest,
    TransportResponse,
    UsageSummary,
)
from app.assistant.request_diagnostics import generate_for_request, record_provider_diagnostic
from app.core.config import Settings
from app.core.diagnostics import (
    ProviderMetric,
    ProviderMetricSlot,
    RequestEvent,
    close_provider_metric,
    emit_request_event,
)

REQUEST_ID = "00000000-0000-0000-0000-000000000001"
OTHER_REQUEST_ID = "00000000-0000-0000-0000-000000000002"
FAKE_KEY = "synthetic-not-a-real-credential"


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str


class ScriptedTransport:
    def __init__(
        self,
        steps: list[TransportResponse | ProviderFault | Callable[[], Awaitable[TransportResponse]]],
    ) -> None:
        self.steps = list(steps)
        self.requests: list[TransportRequest] = []

    async def generate(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        step = self.steps.pop(0)
        if isinstance(step, ProviderFault):
            raise step
        return await step() if callable(step) else step


def state(request_id: str = REQUEST_ID) -> dict[str, Any]:
    return {"request_id": request_id, "provider_metric_slot": ProviderMetricSlot(request_id)}


def settings() -> Settings:
    return Settings(gemini_api_key=SecretStr(FAKE_KEY))


def turn() -> TurnBudget:
    return TurnBudget(settings().timeouts, asyncio.get_running_loop().time() + 30)


def packet() -> EvidencePacket:
    return EvidencePacket(message="Show Mazda 3", session_revision=1)


def response(text: str = "proposal") -> TransportResponse:
    return TransportResponse(json.dumps({"answer": text}))


def diagnostic(**changes: Any) -> ProviderDiagnostic:
    return ProviderDiagnostic(
        request_id=REQUEST_ID,
        state="available",
        code=None,
        attempts=1,
        elapsed_ms=7,
        usage=UsageSummary(input_tokens=10),
    ).model_copy(update=changes)


def test_explicit_mapping_preserves_literals_and_unknown_usage() -> None:
    request_state = state()
    assert record_provider_diagnostic(request_state, diagnostic())
    metric = close_provider_metric(request_state, REQUEST_ID)
    assert type(metric) is ProviderMetric
    assert metric.model_dump() == {
        "request_id": REQUEST_ID,
        "model": "gemini-3.5-flash-lite",
        "sdk_version": "2.25.0",
        "adapter_version": "BE20-ADAPTER-1",
        "configuration_version": "F04-CONFIG-2",
        "state": "available",
        "code": None,
        "attempts": 1,
        "failure_phase": None,
        "http_status": None,
        "elapsed_ms": 7,
        "usage": {"input_tokens": 10, "output_tokens": None, "total_tokens": None},
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"model": "untrusted-model-canary"},
        {"code": "private-error-canary"},
        {"state": "unavailable", "code": None},
        {"attempts": True},
        {"failure_phase": "private-phase-canary"},
        {"http_status": "private-status-canary"},
        {"state": "unavailable", "code": "unavailable", "failure_phase": "http_response",
         "http_status": True},
        {"state": "unavailable", "code": "unavailable", "failure_phase": "sdk_setup",
         "http_status": 503},
        {"failure_phase": "http_response", "http_status": 503},
        {"usage": None},
        {"usage": UsageSummary().model_copy(update={"input_tokens": "private-usage-canary"})},
    ],
)
def test_invalid_metadata_is_omitted_without_logging_raw_validation(
    changes: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    request_state = state()
    assert not record_provider_diagnostic(request_state, diagnostic(**changes))
    assert close_provider_metric(request_state, REQUEST_ID) is None
    assert caplog.records == []


@pytest.mark.parametrize("case", ["missing", "foreign", "closed"])
def test_absent_foreign_and_closed_slots_are_not_enriched(case: str) -> None:
    request_state = state(OTHER_REQUEST_ID if case == "foreign" else REQUEST_ID)
    if case == "missing":
        del request_state["provider_metric_slot"]
    if case == "closed":
        assert close_provider_metric(request_state, REQUEST_ID) is None
    assert not record_provider_diagnostic(request_state, diagnostic())
    assert close_provider_metric(request_state, request_state["request_id"]) is None


def test_attachment_racing_close_never_survives_request_finalization() -> None:
    request_state = state()
    gate = Barrier(2, timeout=2)

    def attach() -> bool:
        gate.wait()
        return record_provider_diagnostic(request_state, diagnostic())

    def close() -> ProviderMetric | None:
        gate.wait()
        return close_provider_metric(request_state, REQUEST_ID)

    with ThreadPoolExecutor(max_workers=2) as executor:
        attached = executor.submit(attach)
        closed = executor.submit(close)
        was_attached, final_metric = attached.result(timeout=3), closed.result(timeout=3)
    assert was_attached == (final_metric is not None)
    assert not record_provider_diagnostic(request_state, diagnostic())
    assert close_provider_metric(request_state, REQUEST_ID) is None


def test_repaired_output_records_only_final_call_metadata_and_safe_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def exercise() -> None:
        private = "buyer@example.invalid private-proposal-canary"
        fake = ScriptedTransport([TransportResponse("private-invalid-canary"), response(private)])
        request_state = state()
        result = await generate_for_request(
            GeminiAdapter(settings(), fake),
            packet(),
            Answer,
            request_state=request_state,
            budget=turn(),
        )
        assert result.proposal == Answer(answer=private)
        metric = close_provider_metric(request_state, REQUEST_ID)
        assert metric is not None and metric.state == "available" and metric.attempts == 2
        assert metric.usage.total_tokens is None and len(fake.requests) == 2
        emitted: list[str] = []
        monkeypatch.setattr(logging.getLogger("car_shopping.requests"), "info", emitted.append)
        emit_request_event(
            RequestEvent(
                request_id=REQUEST_ID,
                operation="assistant",
                method="POST",
                status=200,
                outcome="success",
                error_code=None,
                duration_ms=10,
                provider=metric,
            )
        )
        assert len(emitted) == 1
        serialized = emitted[0]
        for forbidden in (private, "private-invalid-canary", FAKE_KEY, "Show Mazda 3"):
            assert forbidden not in serialized
        assert json.loads(serialized)["provider"]["usage"]["total_tokens"] is None

    asyncio.run(exercise())


def test_normalized_error_replaces_last_invocation_without_inventing_turn_totals() -> None:
    async def exercise() -> None:
        fake = ScriptedTransport([response(), ProviderFault("quota")])
        adapter, request_state, budget = GeminiAdapter(settings(), fake), state(), turn()
        first = await generate_for_request(
            adapter, packet(), Answer, request_state=request_state, budget=budget
        )
        second = await generate_for_request(
            adapter, packet(), Answer, request_state=request_state, budget=budget
        )
        metric = close_provider_metric(request_state, REQUEST_ID)
        assert first.proposal is not None and second.proposal is None
        assert metric is not None and metric.code == "quota" and metric.state == "unavailable"
        assert metric.attempts == 1 and budget.provider_attempts == 2
        assert metric.usage.model_dump() == {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    asyncio.run(exercise())


def test_closed_request_drops_completion_while_provider_call_is_in_flight() -> None:
    async def exercise() -> None:
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed() -> TransportResponse:
            entered.set()
            await release.wait()
            return response()

        request_state = state()
        call = asyncio.create_task(
            generate_for_request(
                GeminiAdapter(settings(), ScriptedTransport([delayed])),
                packet(),
                Answer,
                request_state=request_state,
                budget=turn(),
            )
        )
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert close_provider_metric(request_state, REQUEST_ID) is None
        finally:
            release.set()
        result = await asyncio.wait_for(call, 1)
        assert result.proposal is not None
        assert close_provider_metric(request_state, REQUEST_ID) is None

    asyncio.run(exercise())


def test_caller_cancellation_never_attaches_a_late_transport_result() -> None:
    async def exercise() -> None:
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def stubborn() -> TransportResponse:
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            finally:
                finished.set()
            return response("late-private-canary")

        request_state = state()
        call = asyncio.create_task(
            generate_for_request(
                GeminiAdapter(settings(), ScriptedTransport([stubborn])),
                packet(),
                Answer,
                request_state=request_state,
                budget=turn(),
            )
        )
        try:
            await asyncio.wait_for(entered.wait(), 1)
            call.cancel()
            with pytest.raises(asyncio.CancelledError):
                await call
        finally:
            release.set()
        await asyncio.wait_for(finished.wait(), 1)
        await asyncio.sleep(0)
        # Leave the slot open until the late completion; otherwise closed-slot rejection
        # could hide an incorrect late enrichment by this wrapper.
        assert close_provider_metric(request_state, REQUEST_ID) is None

    asyncio.run(exercise())


@pytest.mark.parametrize("request_state", [{}, {"request_id": REQUEST_ID}, state("invalid")])
def test_wrapper_requires_trusted_request_context_before_provider_call(
    request_state: dict[str, Any],
) -> None:
    async def exercise() -> None:
        fake = ScriptedTransport([])
        with pytest.raises(ValueError, match="^TRUSTED_REQUEST_CONTEXT_REQUIRED$"):
            await generate_for_request(
                GeminiAdapter(settings(), fake),
                packet(),
                Answer,
                request_state=request_state,
                budget=turn(),
            )
        assert not fake.requests

    asyncio.run(exercise())
