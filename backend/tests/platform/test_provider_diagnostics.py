"""Closed core metadata and request-slot races, with no provider/network calls."""

import json
import logging
from dataclasses import asdict
from threading import Event, Thread
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.config import Settings
from app.core.diagnostics import (
    EventDispatcher,
    ProviderMetric,
    ProviderMetricSlot,
    ProviderUsage,
    RequestEvent,
    attach_provider_metric,
    close_provider_metric,
    emit_request_event,
)
from app.core.http import HttpBoundary
from tests.platform.test_configuration import SENTINEL, run_asgi, scope_for

REQUEST_ID = "00000000-0000-4000-8000-000000000001"


def metric(**updates: Any) -> ProviderMetric:
    values: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "state": "available",
        "code": None,
        "attempts": 1,
        "elapsed_ms": 15,
        "usage": ProviderUsage(),
    }
    return ProviderMetric(**{**values, **updates})


def request_event(provider: ProviderMetric | None = None) -> RequestEvent:
    return RequestEvent(
        REQUEST_ID, "post_session_message", "POST", 200, "completed", None, 20, provider=provider
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("request_id", SENTINEL),
        ("model", SENTINEL),
        ("sdk_version", SENTINEL),
        ("adapter_version", SENTINEL),
        ("configuration_version", SENTINEL),
        ("state", SENTINEL),
        ("code", SENTINEL),
        ("failure_phase", SENTINEL),
        ("http_status", SENTINEL),
        ("http_status", True),
        ("http_status", 99),
        ("http_status", 600),
        ("http_status", 503.0),
        ("attempts", -1),
        ("attempts", 3),
        ("attempts", True),
        ("attempts", 1.0),
        ("attempts", "1"),
        ("elapsed_ms", -1),
        ("elapsed_ms", 2_147_483_648),
        ("elapsed_ms", True),
        ("elapsed_ms", float("inf")),
        ("body", SENTINEL),
        ("exception", SENTINEL),
        ("api_key", SENTINEL),
        ("owner_id", REQUEST_ID),
    ],
)
def test_provider_metric_rejects_unknown_secret_and_invalid_fields(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError) as raised:
        metric(**{field: value})
    assert SENTINEL not in str(raised.value)


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens", "total_tokens"])
@pytest.mark.parametrize("value", [-1, 1_000_000_001, True, 1.5, "2", float("nan")])
def test_usage_is_strict_bounded_and_unknown_is_not_zero(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ProviderUsage.model_validate({field: value})


def test_usage_nulls_and_state_code_coherence() -> None:
    assert ProviderUsage().model_dump() == {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }
    assert metric(usage=ProviderUsage(input_tokens=0, total_tokens=10**9)).usage.input_tokens == 0
    for updates in (
        {"state": "available", "code": "timeout"},
        {"state": "unavailable", "code": None},
    ):
        with pytest.raises(ValidationError):
            metric(**updates)
    for code in (
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
    ):
        assert metric(state="unavailable", code=code, attempts=0).code == code
    with pytest.raises(ValidationError):
        ProviderUsage.model_validate({"input_tokens": None, "api_key": SENTINEL})


def test_typed_slot_revalidates_constructed_models_and_rejects_arbitrary_dict() -> None:
    state: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "provider_metric_slot": ProviderMetricSlot(REQUEST_ID),
    }
    with pytest.raises(ValueError, match="TYPED_PROVIDER_METRIC_REQUIRED"):
        attach_provider_metric(state, metric().model_dump())  # type: ignore[arg-type]
    forged = metric().model_copy(update={"attempts": 999})
    with pytest.raises(ValidationError):
        attach_provider_metric(state, forged)
    with pytest.raises(ValidationError):
        attach_provider_metric(state, metric().model_copy(update={"body": SENTINEL}))
    forged_usage = ProviderUsage.model_construct(input_tokens=-1)
    with pytest.raises(ValidationError):
        attach_provider_metric(state, metric().model_copy(update={"usage": forged_usage}))
    with pytest.raises(ValidationError):
        request_event(forged)
    assert close_provider_metric(state, REQUEST_ID) is None


def test_matching_request_only_and_close_refuses_late_completion() -> None:
    state: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "provider_metric_slot": ProviderMetricSlot(REQUEST_ID),
    }
    assert not attach_provider_metric(state, metric(request_id=str(uuid4())))
    final = metric(state="unavailable", code="timeout", attempts=2)
    assert attach_provider_metric(state, final)
    assert close_provider_metric(state, REQUEST_ID) == final
    assert not attach_provider_metric(state, metric())
    assert close_provider_metric(state, REQUEST_ID) is None
    assert not attach_provider_metric({"request_id": REQUEST_ID}, metric())
    with pytest.raises(ValueError, match="PROVIDER_REQUEST_MISMATCH"):
        request_event(metric(request_id=str(uuid4())))


def test_close_wins_against_a_worker_already_holding_the_slot_reference() -> None:
    entered, release = Event(), Event()
    slot = ProviderMetricSlot(REQUEST_ID)

    class PausedState(dict[str, Any]):
        def get(self, key: str, default: Any = None) -> Any:
            result = super().get(key, default)
            if key == "request_id":
                entered.set()
                assert release.wait(2)
            return result

    state = PausedState(request_id=REQUEST_ID, provider_metric_slot=slot)
    accepted: list[bool] = []
    worker = Thread(target=lambda: accepted.append(attach_provider_metric(state, metric())))
    worker.start()
    try:
        assert entered.wait(2)
        assert close_provider_metric(state, REQUEST_ID) is None
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()
    assert accepted == [False]
    assert slot.close(REQUEST_ID) is None


def test_log_emission_preserves_old_shape_and_exact_safe_provider_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[str] = []
    monkeypatch.setattr(logging.getLogger("car_shopping.requests"), "info", messages.append)
    plain = request_event()
    emit_request_event(plain)
    expected = asdict(plain)
    expected.pop("provider")
    assert json.loads(messages.pop()) == expected
    enriched = metric()
    dispatcher = EventDispatcher(capacity=1)
    try:
        assert dispatcher.submit(request_event(enriched), emit_request_event)
        assert dispatcher.wait_idle(2)
    finally:
        assert dispatcher.close(1)
    payload = json.loads(messages.pop())
    assert payload["provider"] == enriched.model_dump(mode="json")
    assert set(payload["provider"]) == {
        "request_id",
        "model",
        "sdk_version",
        "adapter_version",
        "configuration_version",
        "state",
        "code",
        "attempts",
        "failure_phase",
        "http_status",
        "elapsed_ms",
        "usage",
    }
    assert payload["provider"]["usage"] == {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }
    assert SENTINEL not in json.dumps(payload)


@pytest.mark.parametrize("enrichment", ["valid", "foreign", "raw_dict"])
def test_http_boundary_consumes_only_typed_same_request_metric(enrichment: str) -> None:
    events: list[RequestEvent] = []
    states: list[dict[str, Any]] = []

    async def handler(scope: Scope, receive: Receive, send: Send) -> None:
        state = scope["state"]
        states.append(state)
        if enrichment == "raw_dict":
            state["provider_metric"] = {"body": SENTINEL}
        else:
            value = metric(request_id=state["request_id"] if enrichment == "valid" else REQUEST_ID)
            assert attach_provider_metric(state, value) is (enrichment == "valid")
        await JSONResponse({"ok": True})(scope, receive, send)

    boundary = HttpBoundary(handler, Settings(), events.append)
    run_asgi(boundary, scope_for("GET", "/api/v1/health", []), [b""])
    assert len(events) == 1
    assert (events[0].provider is not None) is (enrichment == "valid")
    if events[0].provider is not None:
        assert events[0].provider.request_id == events[0].request_id
    assert not attach_provider_metric(states[0], metric(request_id=states[0]["request_id"]))
