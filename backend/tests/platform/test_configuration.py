"""F-04 boundaries. Synthetic transport routes do not implement owner authentication."""

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.schemas.capabilities import HealthResult, PublicConfig
from app.api.schemas.common import Envelope, ErrorEnvelope
from app.api.schemas.inventory import SearchRequest
from app.core.config import ConfigurationError, DemoPolicy, Settings, Timeouts, load_settings
from app.core.diagnostics import REQUEST_EVENTS, DiagnosticContext, EventDispatcher, RequestEvent
from app.core.http import HttpBoundary
from app.core.readiness import (
    DependencySnapshot,
    ProviderObservation,
    ReadinessRegistry,
    ReadinessService,
)
from app.database.maintenance import initialize_maintenance_guard, shared_store_lease
from app.database.paths import RuntimeBoundary, reserve_new_store
from app.database.store import Store, StoreError, initialize_store
from app.main import create_app
from tests.support.harness import configured_runtime_boundary, runtime_environment

NOW = datetime(2026, 9, 24, 4, tzinfo=UTC)
SENTINEL = "SYNTHETIC_PRIVATE_CONTACT_COOKIE_PROMPT_NEVER_RETURN"
INERT_BOUNDARY = RuntimeBoundary(Path(r"C:\csa-inert-runtime"), Path(r"C:\csa-inert-runtime"))
PATH = INERT_BOUNDARY.logical_root / "test-stores" / "f04-inert" / "test.sqlite3"
ORIGIN = "http://127.0.0.1:5173"


def synthetic_service(
    settings: Settings,
    snapshot: DependencySnapshot,
    *,
    fault: Exception | None = None,
    writable: bool = True,
) -> ReadinessService:
    def opened(path: Path) -> Store:
        if fault is not None:
            raise fault
        return Store(path, "00000000-0000-4000-8000-000000000001", boundary=INERT_BOUNDARY)

    return ReadinessService(
        settings,
        ReadinessRegistry(snapshot),
        store_opener=opened,
        clock=lambda: NOW,
        can_write=lambda _: writable,
    )


def request(app: ASGIApp, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def run() -> httpx.Response:
        async with (
            asyncio.timeout(3),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
            ) as client,
        ):
            return await client.request(method, path, **kwargs)

    response = asyncio.run(run())
    assert REQUEST_EVENTS.wait_idle(1)
    return response


@pytest.mark.parametrize(
    "invalid",
    [
        {"CSA_ALLOWED_HOSTS": '["*"]'},
        {"CSA_ALLOWED_HOSTS": '["0.0.0.0:8000"]'},
        {"CSA_ALLOWED_HOSTS": '["127.0.0.1:08000"]'},
        {"CSA_ALLOWED_HOSTS": '{"127.0.0.1:8000":true}'},
        {"CSA_ALLOWED_ORIGINS": '["null"]'},
        {"CSA_ALLOWED_ORIGINS": '["http://127.0.0.1:5173/"]'},
        {"CSA_ALLOWED_ORIGINS": '["https://127.0.0.1:5173"]'},
        {"CSA_ALLOWED_ORIGINS": '["http://127.0.0.1:9999"]'},
        {"CSA_PROFILE": "public"},
        {"CSA_PORT": "0"},
        {"CSA_STORE_PATH": "C:\\unapproved\\private.sqlite3"},
        {"CSA_STORE_PATH": "relative.sqlite3"},
        {"CSA_TIMEOUTS_JSON": '{"read_seconds":0}'},
        {"CSA_TIMEOUTS_JSON": '{"read_seconds":6}'},
        {"CSA_TIMEOUTS_JSON": '{"provider_attempts":true}'},
        {"CSA_TIMEOUTS_JSON": '{"operation_seconds":2}'},
        {"CSA_TIMEOUTS_JSON": '{"invented":1}'},
        {"CSA_TIMEOUTS_JSON": "[" * 1500 + "0" + "]" * 1500},
        {"CSA_ASSISTANT_ENABLED": "yes"},
        {"CSA_UNKNOWN_SETTING": SENTINEL},
        {"GEMINI_API_KEY": " " + SENTINEL},
        {"GEMINI_API_KEY": "x" * 4097},
    ],
)
def test_invalid_configuration_is_closed_and_sanitized(invalid: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError) as raised:
        load_settings({**runtime_environment(INERT_BOUNDARY), **invalid})
    assert str(raised.value) == "CONFIGURATION_INVALID"
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True


def test_local_profiles_fixed_policy_and_secret_exclusion() -> None:
    http = load_settings({
        **runtime_environment(INERT_BOUNDARY), "GEMINI_API_KEY": SENTINEL,
        "CSA_STORE_PATH": str(PATH),
    })
    https = load_settings({"CSA_PROFILE": "local_https"})
    assert (http.cookie_name, http.cookie_secure) == ("csa_owner", False)
    assert (https.cookie_name, https.cookie_secure) == ("__Host-csa_owner", True)
    assert all(value.startswith("https://") for value in https.allowed_origins)
    assert SENTINEL not in repr(http) + http.model_dump_json()
    assert str(PATH) not in repr(http) + http.model_dump_json()
    assert http.provider_configured is True
    assert load_settings({}).provider_configured is False
    assert http.policy.unresolved_operations_auto_delete is False
    assert http.policy.provider_spend_limit == 0
    with pytest.raises(ValidationError):
        DemoPolicy(capacity=2)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        DemoPolicy(open_weekdays=(6,))
    with pytest.raises(ValidationError):
        http.bind_port = 9000  # type: ignore[misc]  # Exercise the runtime frozen-model guard.


def test_application_construction_performs_no_readiness_probe() -> None:
    settings = Settings(runtime_boundary=INERT_BOUNDARY, store_path=PATH)
    calls: list[Path] = []

    def prohibited(path: Path) -> Store:
        calls.append(path)
        raise AssertionError("STARTUP_MUST_NOT_OPEN_STORE")

    service = ReadinessService(settings, ReadinessRegistry(), store_opener=prohibited)
    app = create_app(settings, readiness=service, event_sink=lambda _: None)
    response = request(app, "GET", "/api/v1/config")
    assert response.status_code == 200
    assert calls == []


@pytest.mark.parametrize(
    "store_fault",
    [None, FileNotFoundError(SENTINEL), PermissionError(SENTINEL), StoreError(SENTINEL)],
)
def test_store_and_provider_states_do_not_erase_inventory(store_fault: Exception | None) -> None:
    settings = Settings(runtime_boundary=INERT_BOUNDARY, store_path=PATH)
    snapshot = DependencySnapshot(
        inventory="ready", active_snapshot_id="a" * 64, viewing="ready", export="unavailable"
    )
    result = synthetic_service(settings, snapshot, fault=store_fault).health()
    assert result.inventory.state == "ready"
    assert result.active_snapshot_id == "a" * 64
    assert result.assistant.state == "unconfigured"
    assert result.store.state == ("ready" if store_fault is None else "unavailable")
    assert result.viewing.state == ("ready" if store_fault is None else "unavailable")
    assert result.export.state == "unavailable"
    assert SENTINEL not in result.model_dump_json()


def test_capabilities_are_independent_and_writeability_is_only_an_observation() -> None:
    settings = Settings(
        runtime_boundary=INERT_BOUNDARY, store_path=PATH, gemini_api_key=SecretStr(SENTINEL)
    )
    fresh = ProviderObservation(state="ready", observed_at=NOW)
    snapshot = DependencySnapshot(provider=fresh, viewing="unconfigured", export="unavailable")
    result = synthetic_service(settings, snapshot).health()
    assert result.inventory.state == "unconfigured"
    assert result.assistant.state == "ready"
    assert result.store.state == "ready"
    assert "writes are checked on submission" in (result.store.reason or "")
    assert result.viewing.state == "unconfigured"
    assert result.export.state == "unavailable"
    readonly = synthetic_service(settings, snapshot, writable=False).health()
    assert readonly.store.state == "degraded"
    assert readonly.assistant.state == "ready"


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        (None, "degraded"),
        (ProviderObservation(state="ready", observed_at=NOW), "ready"),
        (ProviderObservation(state="unavailable", observed_at=NOW), "unavailable"),
        (ProviderObservation(state="ready", observed_at=NOW - timedelta(seconds=61)), "degraded"),
        (ProviderObservation(state="ready", observed_at=NOW + timedelta(seconds=1)), "degraded"),
    ],
)
def test_configured_provider_requires_recent_actual_observation(
    provider: ProviderObservation | None,
    expected: str,
) -> None:
    settings = Settings(gemini_api_key=SecretStr(SENTINEL))
    service = synthetic_service(settings, DependencySnapshot(provider=provider))
    assert service.health().assistant.state == expected
    # Repeated health does not renew an observation or call a provider.
    assert service.registry.snapshot().provider == provider
    assert service.health().assistant.state == expected


def test_invalid_snapshot_cannot_claim_ready_without_exact_identity() -> None:
    with pytest.raises(ValidationError):
        DependencySnapshot(inventory="ready")
    with pytest.raises(ValidationError):
        DependencySnapshot(active_snapshot_id="a" * 64)


def test_public_snapshots_use_frozen_fields_and_no_private_configuration() -> None:
    settings = Settings(
        runtime_boundary=INERT_BOUNDARY, store_path=PATH, gemini_api_key=SecretStr(SENTINEL)
    )
    service = synthetic_service(
        settings, DependencySnapshot(inventory="ready", active_snapshot_id="a" * 64)
    )
    events: list[RequestEvent] = []
    app = create_app(settings, readiness=service, event_sink=events.append)
    config = request(app, "GET", "/api/v1/config", headers={"X-Request-ID": SENTINEL})
    health = request(app, "GET", "/api/v1/health")
    assert config.status_code == health.status_code == 200
    public = Envelope[PublicConfig].model_validate(config.json())
    observed = Envelope[HealthResult].model_validate(health.json())
    assert public.data.limits.body_bytes_max == 65536
    assert public.data.mode == "local_simulated"
    assert set(observed.data.model_dump()) == {
        "service",
        "inventory",
        "store",
        "viewing",
        "export",
        "assistant",
        "active_snapshot_id",
    }
    for response in (config, health):
        assert response.headers["cache-control"] == "no-store"
        request_id = response.json()["meta"]["request_id"]
        assert str(UUID(request_id)) == response.headers["x-request-id"]
        assert response.json()["meta"]["contract_version"] == "1.0.0"
        assert response.json()["meta"]["policy_version"] == "DEMO-POLICY-1"
        assert SENTINEL not in response.text
        assert "AppData" not in response.text
        assert "gemini_api_key" not in response.text
    assert config.headers["x-request-id"] != health.headers["x-request-id"]
    assert len(events) == 2
    assert events[0].snapshot_id is None
    assert events[1].snapshot_id == "a" * 64
    assert all(event.configuration_version == "F04-CONFIG-2" for event in events)
    assert all(event.operation_ref is None for event in events)


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.invalid"},
        {"Host": "127.0.0.1:9999"},
        {"Host": "127.0.0.1:8000.evil.invalid"},
        {"Origin": "null"},
        {"Origin": "http://evil.invalid"},
        {"Origin": ORIGIN + "/"},
    ],
)
def test_exact_transport_boundaries_reject_without_probing(headers: dict[str, str]) -> None:
    app = create_app(Settings(), event_sink=lambda _: None)
    response = request(app, "GET", "/api/v1/health", headers=headers)
    assert response.status_code in {400, 403}
    parsed = ErrorEnvelope.model_validate(response.json())
    assert parsed.error.code in {"HOST_DENIED", "ORIGIN_DENIED"}
    assert response.headers["cache-control"] == "no-store"


def test_vite_proxy_origin_and_backend_host_are_explicitly_allowed() -> None:
    app = create_app(Settings(), event_sink=lambda _: None)
    response = request(app, "GET", "/api/v1/config", headers={"Origin": ORIGIN})
    assert response.status_code == 200


def test_invalid_json_errors_and_exception_details_are_not_returned_or_logged() -> None:
    events: list[RequestEvent] = []
    app = create_app(Settings(), event_sink=events.append)

    @app.post("/api/v1/inventory/search")
    def search(body: SearchRequest) -> dict[str, bool]:
        raise HTTPException(500, detail=SENTINEL, headers={"X-Private": SENTINEL})

    payloads = [
        ({"unexpected_" + SENTINEL: SENTINEL}, 422),
        ({"client_request_id": "00000000-0000-4000-8000-000000000001"}, 500),
    ]
    for payload, expected in payloads:
        response = request(
            app,
            "POST",
            "/api/v1/inventory/search?contact=" + SENTINEL,
            json=payload,
            headers={"Cookie": SENTINEL, "Authorization": SENTINEL},
        )
        assert response.status_code == expected
        assert SENTINEL not in response.text + str(response.headers)
        ErrorEnvelope.model_validate(response.json())
    malformed = request(
        app,
        "POST",
        "/api/v1/inventory/search",
        content='{"' + SENTINEL,
        headers={"Content-Type": "application/json"},
    )
    assert malformed.status_code == 422
    assert SENTINEL not in malformed.text
    assert all(
        set(asdict(event))
        == {
            "request_id",
            "operation",
            "method",
            "status",
            "outcome",
            "error_code",
            "duration_ms",
            "operation_ref",
            "snapshot_id",
            "contract_version",
            "policy_version",
            "configuration_version",
            "provider",
        }
        for event in events
    )
    assert SENTINEL not in json.dumps([asdict(event) for event in events])
    assert all(event.operation == "search_inventory" for event in events)


def test_raw_internal_exception_and_store_failure_use_safe_error_envelopes() -> None:
    app = create_app(Settings(), event_sink=lambda _: None)

    @app.get("/synthetic-internal")
    def internal() -> None:
        raise RuntimeError(SENTINEL)

    @app.get("/synthetic-store")
    def storage() -> None:
        raise StoreError(SENTINEL)

    for path, status, code in (
        ("/synthetic-internal", 500, "INTERNAL_ERROR"),
        ("/synthetic-store", 503, "STORE_UNAVAILABLE"),
    ):
        response = request(app, "GET", path)
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert SENTINEL not in response.text


def test_response_validation_discards_private_returned_values() -> None:
    events: list[RequestEvent] = []
    app = create_app(Settings(), event_sink=events.append)

    @app.get("/synthetic-response", response_model=PublicConfig)
    def invalid_response() -> dict[str, str]:
        return {"unexpected_" + SENTINEL: SENTINEL}

    response = request(app, "GET", "/synthetic-response")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert SENTINEL not in response.text + json.dumps([asdict(event) for event in events])


@pytest.mark.parametrize("code", ["STORE_BUSY", "STORE_GENERATION_CHANGED"])
@pytest.mark.parametrize("mutates", [False, True])
def test_store_failure_retry_never_invents_replacement_operation(code: str, mutates: bool) -> None:
    app = create_app(Settings(), event_sink=lambda _: None)

    def fault() -> None:
        raise StoreError(code)

    path = (
        "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000001/confirm"
        if mutates
        else "/synthetic-store-read"
    )
    method = "POST" if mutates else "GET"
    app.add_api_route(path, fault, methods=[method])
    response = request(
        app,
        method,
        path,
        headers={"Origin": ORIGIN, "Content-Type": "application/json"},
        content=b"{}" if mutates else b"",
    )
    error = response.json()["error"]
    assert error["code"] == code
    assert response.status_code == (503 if code == "STORE_BUSY" else 409)
    assert error["outcome_state"] == ("unresolved" if mutates else None)
    assert error["retryable"] is (code == "STORE_BUSY")
    assert error["retry_action"] == (
        "none"
        if code == "STORE_GENERATION_CHANGED"
        else "same_operation_only"
        if mutates
        else "read"
    )
    assert error["operation_key"] is None


def scope_for(method: str, path: str, headers: list[tuple[bytes, bytes]]) -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"127.0.0.1:8000"), *headers],
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 8000),
    }


def run_asgi(
    app: ASGIApp,
    scope: Scope,
    chunks: list[bytes],
) -> list[Message]:
    async def exercise() -> list[Message]:
        messages: list[Message] = []
        pending = list(chunks)

        async def receive() -> Message:
            if pending:
                chunk = pending.pop(0)
                return {"type": "http.request", "body": chunk, "more_body": bool(pending)}
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def send(message: Message) -> None:
            messages.append(message)

        async with asyncio.timeout(3):
            await app(scope, receive, send)
        return messages

    messages = asyncio.run(exercise())
    assert REQUEST_EVENTS.wait_idle(1)
    return messages


@pytest.mark.parametrize(
    ("body", "headers", "status"),
    [
        (b"", [], 200),
        (b"{}", [(b"content-type", b"application/json")], 422),
        (b"hidden", [(b"content-type", b"text/plain")], 422),
    ],
)
def test_bodyless_delete_contract_without_claiming_authentication(
    body: bytes,
    headers: list[tuple[bytes, bytes]],
    status: int,
) -> None:
    calls: list[str] = []

    async def synthetic_handler(scope: Scope, receive: Receive, send: Send) -> None:
        calls.append("transport-only")
        await JSONResponse({"accepted_transport": True})(scope, receive, send)

    # These headers are passed through for later identity/CSRF/domain enforcement.
    base_headers = [
        (b"origin", ORIGIN.encode()),
        (b"x-csrf-token", b"x" * 43),
        (b"x-identity-context", b"00000000-0000-4000-8000-000000000001"),
        (b"x-client-action-id", b"00000000-0000-4000-8000-000000000002"),
        (b"x-expected-revision", b"0"),
    ]
    scope = scope_for(
        "DELETE", "/api/v1/shortlist/synthetic/" + "a" * 64 + "/1", base_headers + headers
    )
    messages = run_asgi(HttpBoundary(synthetic_handler, Settings(), lambda _: None), scope, [body])
    assert messages[0]["status"] == status
    assert calls == (["transport-only"] if status == 200 else [])


@pytest.mark.parametrize("origin", [None, b"null", b"http://evil.invalid", ORIGIN.encode() + b"/"])
def test_mutation_origin_failure_never_dispatches(origin: bytes | None) -> None:
    async def forbidden(scope: Scope, receive: Receive, send: Send) -> None:
        raise AssertionError("MUST_NOT_DISPATCH")

    headers = [] if origin is None else [(b"origin", origin)]
    scope = scope_for("DELETE", "/api/v1/shortlist/synthetic/" + "a" * 64 + "/1", headers)
    messages = run_asgi(HttpBoundary(forbidden, Settings(), lambda _: None), scope, [b""])
    assert messages[0]["status"] == 403


@pytest.mark.parametrize(
    ("chunks", "headers", "expected"),
    [
        ([b"x" * 32768, b"x" * 32769], [(b"content-type", b"application/json")], 413),
        ([b"{}"], [(b"content-type", b"text/plain")], 415),
        ([b"{}"], [(b"content-type", b"application/json"), (b"content-length", b"65537")], 413),
        ([b"{}"], [(b"content-type", b"application/json"), (b"content-length", b"1")], 422),
        (
            [b"{}"],
            [
                (b"content-type", b"application/json"),
                (b"content-length", b"2"),
                (b"content-length", b"2"),
            ],
            422,
        ),
    ],
)
def test_preparse_body_limits_fail_without_downstream_dispatch(
    chunks: list[bytes],
    headers: list[tuple[bytes, bytes]],
    expected: int,
) -> None:
    called = False

    async def forbidden(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal called
        called = True

    scope = scope_for("POST", "/api/v1/inventory/search", headers)
    messages = run_asgi(HttpBoundary(forbidden, Settings(), lambda _: None), scope, chunks)
    assert messages[0]["status"] == expected
    assert called is False


def test_exact_body_byte_limit_is_accepted_for_a_public_post_read() -> None:
    received: list[bytes] = []

    async def handler(scope: Scope, receive: Receive, send: Send) -> None:
        received.append((await receive())["body"])
        await JSONResponse({"accepted_transport": True})(scope, receive, send)

    body = b" " * 65534 + b"{}"
    scope = scope_for("POST", "/api/v1/inventory/search", [(b"content-type", b"application/json")])
    messages = run_asgi(
        HttpBoundary(handler, Settings(), lambda _: None), scope, [body[:32768], body[32768:]]
    )
    assert messages[0]["status"] == 200
    assert received == [body]


@pytest.mark.parametrize(
    "change",
    ["duplicate_host", "duplicate_origin", "remote_client", "wrong_scheme", "forwarded_host"],
)
def test_ambiguous_or_forwarded_authority_is_not_trusted(change: str) -> None:
    called = False

    async def forbidden(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal called
        called = True

    scope = scope_for("GET", "/api/v1/health", [])
    if change == "duplicate_host":
        scope["headers"].append((b"host", b"127.0.0.1:8000"))
    elif change == "duplicate_origin":
        scope["headers"].extend([(b"origin", ORIGIN.encode()), (b"origin", ORIGIN.encode())])
    elif change == "remote_client":
        scope["client"] = ("192.0.2.1", 1234)
    elif change == "wrong_scheme":
        scope["scheme"] = "https"
    else:
        scope["headers"] = [(b"host", b"evil.invalid"), (b"x-forwarded-host", b"127.0.0.1:8000")]
    messages = run_asgi(HttpBoundary(forbidden, Settings(), lambda _: None), scope, [b""])
    assert messages[0]["status"] in {400, 422}
    assert called is False


def test_diagnostic_sink_failure_does_not_replay_or_change_a_response() -> None:
    def broken_sink(event: RequestEvent) -> None:
        raise RuntimeError(SENTINEL)

    response = request(create_app(Settings(), event_sink=broken_sink), "GET", "/api/v1/config")
    assert response.status_code == 200
    assert SENTINEL not in response.text


def test_diagnostics_use_only_trusted_validated_context() -> None:
    operation_ref = "00000000-0000-4000-8000-000000000001"
    trusted = DiagnosticContext(operation_ref=operation_ref, snapshot_id="b" * 64)
    for value in (SENTINEL, "x" * 43):
        with pytest.raises(ValueError, match="^INVALID_DIAGNOSTIC_REFERENCE$"):
            DiagnosticContext(operation_ref=value)
        with pytest.raises(ValueError, match="^INVALID_DIAGNOSTIC_REFERENCE$"):
            DiagnosticContext(snapshot_id=value)
    events: list[RequestEvent] = []
    for context in (trusted, {"operation_ref": SENTINEL, "snapshot_id": SENTINEL}):

        async def handler(
            scope: Scope, receive: Receive, send: Send, context: object = context
        ) -> None:
            scope["state"]["diagnostic_context"] = context
            scope["state"]["safe_error_code"] = SENTINEL
            await JSONResponse({"ok": True})(scope, receive, send)

        boundary = HttpBoundary(handler, Settings(), events.append)
        run_asgi(
            boundary,
            scope_for("GET", "/api/v1/health", [(b"x-operation-ref", SENTINEL.encode())]),
            [b""],
        )
    assert events[0].operation_ref == operation_ref
    assert events[0].snapshot_id == "b" * 64
    assert events[1].operation_ref is events[1].snapshot_id is None
    assert all(event.error_code is None for event in events)
    assert all(
        event.contract_version == "1.0.0" and event.policy_version == "DEMO-POLICY-1"
        for event in events
    )
    assert SENTINEL not in json.dumps([asdict(event) for event in events])


def test_blocked_diagnostic_sink_and_full_queue_do_not_block_other_requests() -> None:
    entered, release = Event(), Event()
    dispatcher = EventDispatcher(capacity=1)
    seen: list[RequestEvent] = []

    def stalled(event: RequestEvent) -> None:
        entered.set()
        if not release.wait(5):
            raise AssertionError("TEST_SINK_RELEASE_REQUIRED")
        seen.append(event)

    async def handler(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"ok": True})(scope, receive, send)

    boundary = HttpBoundary(handler, Settings(), stalled, dispatcher)
    try:
        first = run_asgi(boundary, scope_for("GET", "/api/v1/health", []), [b""])
        assert first[0]["status"] == 200
        assert entered.wait(1)

        # Same event loop serves concurrent requests while the only consumer is blocked.
        async def concurrent() -> list[httpx.Response]:
            async with (
                asyncio.timeout(1),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=boundary), base_url="http://127.0.0.1:8000"
                ) as client,
            ):
                return list(await asyncio.gather(*[client.get("/api/v1/config") for _ in range(4)]))

        assert all(response.status_code == 200 for response in asyncio.run(concurrent()))
        assert seen == []
        # Exactly one event is queued; additional events are dropped without waiting.
        event = RequestEvent(str(uuid4()), "get_health", "GET", 200, "completed", None, 0)
        assert dispatcher.submit(event, stalled) is False
    finally:
        release.set()
        assert dispatcher.wait_idle(2)
        assert dispatcher.close(1)
    assert len(seen) == 2
    assert dispatcher.submit(event, stalled) is False


def test_stalled_request_body_expires_before_domain_dispatch() -> None:
    called = False

    async def handler(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal called
        called = True

    events: list[RequestEvent] = []
    settings = Settings(timeouts=Timeouts(read_seconds=1))
    messages = run_asgi(
        HttpBoundary(handler, settings, events.append), scope_for("GET", "/api/v1/health", []), []
    )
    assert messages[0]["status"] == 504
    assert called is False
    assert events[0].outcome == "deadline"


def test_health_deadline_returns_while_sync_store_worker_is_still_running() -> None:
    entered, release, finished = Event(), Event(), Event()

    def slow_open(path: Path) -> Store:
        entered.set()
        try:
            if not release.wait(5):
                raise AssertionError("TEST_WORKER_RELEASE_REQUIRED")
            return Store(path, "00000000-0000-4000-8000-000000000001", boundary=INERT_BOUNDARY)
        finally:
            finished.set()

    settings = Settings(
        runtime_boundary=INERT_BOUNDARY, store_path=PATH, timeouts=Timeouts(read_seconds=1)
    )
    service = ReadinessService(
        settings, ReadinessRegistry(), store_opener=slow_open, can_write=lambda _: True
    )
    app = create_app(settings, readiness=service, event_sink=lambda _: None)
    try:
        response = request(app, "GET", "/api/v1/health")
        assert entered.is_set()
        assert response.status_code == 504
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert finished.is_set() is False
    finally:
        release.set()
        assert finished.wait(2)


@pytest.mark.parametrize("mutates", [False, True])
def test_deadline_does_not_call_a_local_timeout_a_provider_failure_or_a_rollback(
    mutates: bool,
) -> None:
    async def blocked(scope: Scope, receive: Receive, send: Send) -> None:
        await asyncio.Event().wait()

    settings = Settings(timeouts=Timeouts(read_seconds=1, confirmation_seconds=1))
    events: list[RequestEvent] = []
    path = (
        "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000001/confirm"
        if mutates
        else "/api/v1/health"
    )
    headers = (
        [(b"origin", ORIGIN.encode()), (b"content-type", b"application/json")] if mutates else []
    )
    scope = scope_for("POST" if mutates else "GET", path, headers)
    messages = run_asgi(
        HttpBoundary(blocked, settings, events.append), scope, [b"{}" if mutates else b""]
    )
    assert messages[0]["status"] == 504
    result = json.loads(messages[1]["body"])["error"]
    assert result["code"] == "INTERNAL_ERROR"
    assert result["outcome_state"] == ("unresolved" if mutates else None)
    assert result["retry_action"] == ("same_operation_only" if mutates else "none")
    assert events[0].outcome == "deadline"


def test_failure_after_response_start_does_not_send_a_second_response() -> None:
    async def partially_sent(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b'{"partial":', "more_body": True})
        raise RuntimeError(SENTINEL)

    events: list[RequestEvent] = []
    messages = run_asgi(
        HttpBoundary(partially_sent, Settings(), events.append),
        scope_for("GET", "/api/v1/health", []),
        [b""],
    )
    assert len([message for message in messages if message["type"] == "http.response.start"]) == 1
    assert events[0].outcome == "failed"
    assert events[0].error_code == "INTERNAL_ERROR"
    assert SENTINEL not in json.dumps([asdict(event) for event in events])


def test_unmounted_private_routes_do_not_establish_identity_and_all_errors_are_no_store() -> None:
    app = create_app(Settings(), event_sink=lambda _: None)
    for path in ("/api/v1/not-an-endpoint", "/openapi.json", "/docs"):
        response = request(app, "GET", path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
        assert response.headers["cache-control"] == "no-store"
        assert "set-cookie" not in response.headers


def test_real_missing_store_probe_never_creates_a_file_or_directory() -> None:
    boundary = configured_runtime_boundary()
    path = (
        boundary.logical_root / "test-stores" / ("f04-missing-" + str(uuid4())) / "missing.sqlite3"
    )
    assert not path.parent.exists()
    result = ReadinessService(
        Settings(store_path=path, runtime_boundary=boundary), ReadinessRegistry()
    ).health()
    assert result.store.state == "unavailable"
    assert not path.parent.exists()


def test_real_corrupt_store_probe_preserves_bytes_and_does_not_repair() -> None:
    boundary = configured_runtime_boundary()
    path = (
        boundary.logical_root / "test-stores" / ("f04-corrupt-" + str(uuid4())) / "corrupt.sqlite3"
    )
    physical = reserve_new_store(path, boundary=boundary)
    initialize_maintenance_guard(path, boundary=boundary)
    with shared_store_lease(path, boundary=boundary):
        physical.write_bytes(b"synthetic corrupt sqlite input")
    before = hashlib.sha256(physical.read_bytes()).hexdigest()
    result = ReadinessService(
        Settings(store_path=path, runtime_boundary=boundary), ReadinessRegistry()
    ).health()
    assert result.store.state == "unavailable"
    assert hashlib.sha256(physical.read_bytes()).hexdigest() == before
    assert sorted(item.name for item in physical.parent.iterdir()) == [
        "corrupt.sqlite3", "corrupt.sqlite3.maintenance.lock",
    ]


def test_real_healthy_store_probe_performs_only_read_validation() -> None:
    boundary = configured_runtime_boundary()
    path = boundary.logical_root / "test-stores" / ("f04-ready-" + str(uuid4())) / "ready.sqlite3"
    # Explicit disposable test setup, never application startup.
    store = initialize_store(path, boundary=boundary)
    before = hashlib.sha256(store.path.read_bytes()).hexdigest()
    service = ReadinessService(
        Settings(store_path=path, runtime_boundary=boundary), ReadinessRegistry()
    )
    for _ in range(2):
        result = service.health()
        assert result.store.state == "ready"
    assert hashlib.sha256(store.path.read_bytes()).hexdigest() == before
    assert sorted(item.name for item in store.path.parent.iterdir()) == [
        "ready.sqlite3", "ready.sqlite3.maintenance.lock",
    ]
