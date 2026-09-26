"""Offline failures cross the real SDK, adapter, metric slot and safe logger."""

import asyncio
import json
import logging
import socket
from typing import Any

import httpx
import pytest
from google.genai import errors
from pydantic import SecretStr

from app.assistant import transport as transport_module
from app.assistant.budget import TurnBudget
from app.assistant.provider import GeminiAdapter
from app.assistant.request_diagnostics import generate_for_request
from app.assistant.transport import GoogleGenAITransport
from app.core.config import Settings
from app.core.diagnostics import RequestEvent, close_provider_metric, emit_request_event

from .test_request_diagnostics import REQUEST_ID, Answer, packet, state
from .test_transport import body

SENTINEL = "private-boundary-canary buyer@example.invalid https://private.invalid/?key=secret"
FAKE_KEY = "synthetic-telemetry-test-key"


@pytest.fixture(autouse=True)
def deny_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default HTTPX dispatch is already denied by backend/tests/conftest.py.
    def deny(*args: object, **kwargs: object) -> None:
        raise AssertionError("TELEMETRY_TEST_NETWORK_FORBIDDEN")

    monkeypatch.setattr(socket, "getaddrinfo", deny)


def invoke(
    monkeypatch: pytest.MonkeyPatch, handler: Any, *, factory: Any = None,
) -> tuple[Any, list[httpx.Request], str]:
    calls: list[httpx.Request] = []
    messages: list[str] = []
    monkeypatch.setattr(logging.getLogger("car_shopping.requests"), "info", messages.append)

    def respond(outgoing: httpx.Request) -> httpx.Response:
        calls.append(outgoing)
        return handler(outgoing)

    async def exercise() -> Any:
        settings = Settings(gemini_api_key=SecretStr(FAKE_KEY))
        actual = GoogleGenAITransport(
            settings, transport_factory=factory or (lambda: httpx.MockTransport(respond))
        )
        adapter = GeminiAdapter(settings, actual)
        request_state = state()
        budget = TurnBudget(settings.timeouts, asyncio.get_running_loop().time() + 30)
        try:
            result = await generate_for_request(
                adapter, packet(), Answer, request_state=request_state, budget=budget
            )
            metric = close_provider_metric(request_state, REQUEST_ID)
            assert metric is not None
            assert metric.failure_phase == result.diagnostic.failure_phase
            assert metric.http_status == result.diagnostic.http_status
            assert metric.code == result.diagnostic.code
            assert metric.attempts == result.diagnostic.attempts == budget.provider_attempts
            emit_request_event(RequestEvent(
                request_id=REQUEST_ID, operation="submit_message", method="POST", status=200,
                outcome="completed", error_code=None, duration_ms=1, provider=metric,
            ))
            return result
        finally:
            assert await adapter.close(timeout_seconds=1)

    result = asyncio.run(exercise())
    assert len(messages) == 1
    serialized = messages[0]
    for forbidden in (SENTINEL, FAKE_KEY, "buyer@example.invalid", "private.invalid",
                      "ValueError", "RuntimeError", "ConnectError", "Show Mazda 3"):
        assert forbidden not in serialized
    return result, calls, serialized


@pytest.mark.parametrize(
    "status,code,attempts",
    [(400, "unavailable", 1), (401, "auth", 1), (403, "auth", 1),
     (404, "model_missing", 1), (408, "timeout", 1), (429, "quota", 1),
     (503, "unavailable", 2), (504, "timeout", 1)],
)
def test_actual_http_error_status_reaches_safe_log_with_unchanged_retry_policy(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str, attempts: int,
) -> None:
    result, calls, serialized = invoke(monkeypatch, lambda _: httpx.Response(
        status, json={"error": {"code": status, "message": SENTINEL}},
    ))
    assert result.diagnostic.code == code and result.diagnostic.attempts == attempts
    assert len(calls) == attempts
    logged = json.loads(serialized)["provider"]
    assert logged["failure_phase"] == "http_response" and logged["http_status"] == status


@pytest.mark.parametrize(
    "error_type,code,phase,attempts",
    [(httpx.ConnectError, "unavailable", "http_connect", 2),
     (httpx.ConnectTimeout, "timeout", "http_connect", 1),
     (httpx.ReadTimeout, "timeout", "http_timeout", 1),
     (httpx.WriteTimeout, "timeout", "http_timeout", 1),
     (httpx.PoolTimeout, "timeout", "http_timeout", 1),
     (httpx.RemoteProtocolError, "unavailable", "http_transport", 2)],
)
def test_http_failures_before_response_have_closed_phase_and_no_invented_status(
    monkeypatch: pytest.MonkeyPatch, error_type: Any, code: str, phase: str, attempts: int,
) -> None:
    def fail(outgoing: httpx.Request) -> httpx.Response:
        raise error_type(SENTINEL, request=outgoing)

    result, calls, _ = invoke(monkeypatch, fail)
    assert result.diagnostic.code == code and result.diagnostic.failure_phase == phase
    assert result.diagnostic.http_status is None
    assert result.diagnostic.attempts == attempts and len(calls) == attempts


@pytest.mark.parametrize("where", ["sdk_setup", "sdk_request"])
def test_sdk_setup_and_request_validation_fail_before_http_without_changing_repair(
    monkeypatch: pytest.MonkeyPatch, where: str,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise ValueError(SENTINEL)

    if where == "sdk_setup":
        monkeypatch.setattr(transport_module.genai, "Client", fail)
    else:
        monkeypatch.setattr(transport_module.types, "GenerateContentConfig", fail)
    result, calls, _ = invoke(monkeypatch, lambda _: httpx.Response(200, json=body()))
    assert result.diagnostic.code == "malformed" and result.diagnostic.failure_phase == where
    assert result.diagnostic.http_status is None and result.diagnostic.attempts == 2
    assert calls == []


def test_sdk_api_error_without_observed_response_does_not_invent_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise errors.APIError(503, {"message": SENTINEL})

    monkeypatch.setattr(transport_module.genai, "Client", fail)
    result, calls, _ = invoke(monkeypatch, lambda _: httpx.Response(200, json=body()))
    assert result.diagnostic.code == "unavailable"
    assert result.diagnostic.failure_phase == "sdk_setup"
    assert result.diagnostic.http_status is None and result.diagnostic.attempts == 2
    assert calls == []


@pytest.mark.parametrize(
    "case,code,phase,attempts",
    [("invalid_json", "malformed", "sdk_response", 2),
     ("missing_candidates", "malformed", "sdk_response", 2),
     ("prompt_block", "unavailable", "sdk_response", 2),
     ("oversize", "output_too_large", "http_response", 1),
     ("redirect", "unavailable", "http_response", 2)],
)
def test_response_failures_keep_observed_status_and_closed_boundary(
    monkeypatch: pytest.MonkeyPatch, case: str, code: str, phase: str, attempts: int,
) -> None:
    def respond(_: httpx.Request) -> httpx.Response:
        if case == "invalid_json":
            return httpx.Response(200, content=SENTINEL)
        if case == "missing_candidates":
            return httpx.Response(200, json=body(candidates=[]))
        if case == "prompt_block":
            return httpx.Response(200, json=body(promptFeedback={"blockReason": "SAFETY"}))
        if case == "oversize":
            return httpx.Response(200, content=b"x" * 65537)
        return httpx.Response(307, headers={"Location": "https://private.invalid/"})

    result, calls, _ = invoke(monkeypatch, respond)
    assert result.diagnostic.code == code and result.diagnostic.failure_phase == phase
    assert result.diagnostic.http_status == (307 if case == "redirect" else 200)
    assert result.diagnostic.attempts == attempts and len(calls) == attempts


def test_stream_timeout_preserves_status_already_received(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> Any:
            yield b'{"candidates":'
            raise httpx.ReadTimeout(SENTINEL)

    result, calls, _ = invoke(
        monkeypatch, lambda outgoing: httpx.Response(200, stream=FailingStream(), request=outgoing)
    )
    assert result.diagnostic.code == "timeout"
    assert result.diagnostic.failure_phase == "http_timeout"
    assert result.diagnostic.http_status == 200 and len(calls) == 1


def test_transport_setup_exception_remains_nonretry_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factories: list[bool] = []

    def fail() -> Any:
        factories.append(True)
        raise ValueError(SENTINEL)

    result, calls, _ = invoke(monkeypatch, None, factory=fail)
    assert result.diagnostic.code == "unavailable"
    assert result.diagnostic.failure_phase == "transport_setup"
    assert result.diagnostic.http_status is None and result.diagnostic.attempts == 1
    assert factories == [True] and calls == []


@pytest.mark.parametrize("status", [200, 503])
@pytest.mark.parametrize("close_boundary", ["sdk", "httpx"])
def test_cleanup_failure_overrides_success_or_mapped_fault_without_retry(
    monkeypatch: pytest.MonkeyPatch, status: int, close_boundary: str,
) -> None:
    calls: list[bool] = []
    closed: list[str] = []

    def respond(outgoing: httpx.Request) -> httpx.Response:
        calls.append(True)
        return httpx.Response(status, json=body(), request=outgoing)

    class ClosingTransport(httpx.MockTransport):
        async def aclose(self) -> None:
            await super().aclose()
            closed.append("httpx")
            if close_boundary == "httpx":
                raise RuntimeError(SENTINEL)

    if close_boundary == "sdk":
        original_close = transport_module.genai.Client.close

        def fail_close(client: Any) -> None:
            original_close(client)
            closed.append("sdk")
            raise RuntimeError(SENTINEL)

        monkeypatch.setattr(transport_module.genai.Client, "close", fail_close)
    result, _, _ = invoke(monkeypatch, None, factory=lambda: ClosingTransport(respond))
    assert result.diagnostic.code == "unavailable" and result.diagnostic.attempts == 1
    assert result.diagnostic.failure_phase == "cleanup" and result.diagnostic.http_status == status
    assert len(calls) == 1 and "httpx" in closed
    if close_boundary == "sdk":
        assert closed[0] == "sdk"


@pytest.mark.parametrize("final", ["connected_failure", "success", "invalid_model_json"])
def test_final_attempt_metadata_never_retains_prior_response_failure(
    monkeypatch: pytest.MonkeyPatch, final: str,
) -> None:
    count = 0

    def respond(outgoing: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(503, json={"error": {"code": 503, "message": SENTINEL}})
        if final == "connected_failure":
            raise httpx.ConnectError(SENTINEL, request=outgoing)
        if final == "invalid_model_json":
            return httpx.Response(200, json=body(candidates=[{
                "finishReason": "STOP", "content": {"parts": [{"text": SENTINEL}]},
            }]))
        return httpx.Response(200, json=body())

    result, calls, _ = invoke(monkeypatch, respond)
    assert result.diagnostic.attempts == 2 and len(calls) == 2
    assert result.diagnostic.http_status is None
    if final == "connected_failure":
        assert result.diagnostic.code == "unavailable"
        assert result.diagnostic.failure_phase == "http_connect"
    elif final == "invalid_model_json":
        assert result.diagnostic.code == "malformed"
        assert result.diagnostic.failure_phase == "output_validation"
    else:
        assert result.proposal == Answer(answer="ok")
        assert result.diagnostic.code is None and result.diagnostic.failure_phase is None
