"""ASGI transport limits, exact local boundaries, deadlines and safe diagnostics."""

import asyncio
import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from starlette.routing import compile_path
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.schemas.capabilities import PublicLimits
from app.api.schemas.common import ErrorCode
from app.api.schemas.routes import ROUTES
from app.core.config import Settings
from app.core.diagnostics import (
    REQUEST_EVENTS,
    DiagnosticContext,
    EventDispatcher,
    ProviderMetricSlot,
    RequestEvent,
    close_provider_metric,
    emit_request_event,
)
from app.core.errors import ERRORS, ApiFailure, error_response


@dataclass(frozen=True)
class RoutePolicy:
    method: str
    pattern: re.Pattern[str]
    operation: str
    mutates: bool
    has_body: bool


POLICIES = tuple(
    RoutePolicy(
        route.method,
        compile_path("/api/v1" + route.path)[0],
        route.operation_id,
        route.mutates,
        route.request is not None,
    )
    for route in ROUTES
)
JSON_CONTENT_TYPE = re.compile(
    rb'application/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?', re.I
)
METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


class Disconnected(Exception):
    pass


def policy_for(scope: Scope) -> RoutePolicy | None:
    for policy in POLICIES:
        if scope["method"] == policy.method and policy.pattern.fullmatch(scope["path"]):
            return policy
    return None


def one_header(scope: Scope, name: bytes) -> bytes | None:
    values = [value for key, value in scope["headers"] if key.lower() == name]
    if len(values) > 1:
        raise ApiFailure("VALIDATION_ERROR")
    return values[0] if values else None


class HttpBoundary:
    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        event_sink: Callable[[RequestEvent], None] = emit_request_event,
        event_dispatcher: EventDispatcher = REQUEST_EVENTS,
    ) -> None:
        self.app = app
        self.settings = settings
        self.event_sink = event_sink
        self.event_dispatcher = event_dispatcher

    def _check_origin_host(self, scope: Scope, mutates: bool) -> None:
        host = one_header(scope, b"host")
        if host is None or host not in {
            value.encode("ascii") for value in self.settings.allowed_hosts
        }:
            raise ApiFailure("HOST_DENIED")
        if scope.get("scheme") != self.settings.scheme:
            raise ApiFailure("HOST_DENIED")
        # Forwarded headers never grant authority; the intended server binds 127.0.0.1.
        client = scope.get("client")
        if client is None or client[0] != "127.0.0.1":
            raise ApiFailure("HOST_DENIED")
        origin = one_header(scope, b"origin")
        if origin is None:
            if mutates:
                raise ApiFailure("ORIGIN_DENIED")
        elif origin not in {value.encode("ascii") for value in self.settings.allowed_origins}:
            raise ApiFailure("ORIGIN_DENIED")

    async def _read_body(self, scope: Scope, receive: Receive, has_body: bool) -> bytes:
        maximum = PublicLimits().body_bytes_max
        content_length = one_header(scope, b"content-length")
        transfer_encoding = one_header(scope, b"transfer-encoding")
        if transfer_encoding not in (None, b"chunked"):
            raise ApiFailure("VALIDATION_ERROR")
        if content_length is not None:
            if (
                not content_length.isdigit()
                or len(content_length) > 10
                or transfer_encoding is not None
            ):
                raise ApiFailure("VALIDATION_ERROR")
            if int(content_length) > maximum:
                raise ApiFailure("INPUT_TOO_LARGE")
        if one_header(scope, b"content-encoding") not in (None, b"identity"):
            raise ApiFailure("UNSUPPORTED_CONTENT_TYPE")
        content_type = one_header(scope, b"content-type")
        if has_body and (content_type is None or not JSON_CONTENT_TYPE.fullmatch(content_type)):
            raise ApiFailure("UNSUPPORTED_CONTENT_TYPE")
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise Disconnected
            if message["type"] != "http.request":
                raise ApiFailure("VALIDATION_ERROR")
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > maximum:
                raise ApiFailure("INPUT_TOO_LARGE")
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if content_length is not None and len(body) != int(content_length):
            raise ApiFailure("VALIDATION_ERROR")
        if body and not has_body:
            raise ApiFailure("VALIDATION_ERROR")
        if body and (content_type is None or not JSON_CONTENT_TYPE.fullmatch(content_type)):
            raise ApiFailure("UNSUPPORTED_CONTENT_TYPE")
        return bytes(body)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = monotonic()
        request_id = str(uuid4())
        policy = policy_for(scope)
        method = scope["method"] if scope["method"] in METHODS else "OTHER"
        mutates = policy.mutates if policy is not None else method not in {"GET", "HEAD", "OPTIONS"}
        operation = policy.operation if policy is not None else "unmatched"
        timeout = (
            self.settings.timeouts.confirmation_seconds
            if operation == "confirm_booking_draft"
            else self.settings.timeouts.operation_seconds
            if mutates
            else self.settings.timeouts.read_seconds
        )
        state = scope.setdefault("state", {})
        state.update(
            request_id=request_id,
            mutates=mutates,
            safe_error_code=None,
            deadline_at=started + timeout,
            provider_metric_slot=ProviderMetricSlot(request_id),
        )
        response_started = False
        dispatched = False
        status = 500
        outcome = "failed"

        async def guarded_send(message: Message) -> None:
            nonlocal response_started, status
            if message["type"] == "http.response.start":
                if response_started:
                    raise RuntimeError("RESPONSE_ALREADY_STARTED")
                response_started = True
                status = message["status"]
                message = dict(message)
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in {b"cache-control", b"x-request-id"}
                ]
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"x-request-id", request_id.encode("ascii")),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        async def failure(code: ErrorCode, *, response_status: int | None = None) -> None:
            state["safe_error_code"] = code
            if not response_started:
                response = error_response(
                    code,
                    request_id,
                    mutates=mutates and dispatched,
                    status=response_status,
                    uncertain=mutates and dispatched,
                )
                await response(scope, receive, guarded_send)

        budget = asyncio.timeout(timeout)
        try:
            async with budget:
                self._check_origin_host(scope, mutates)
                body = await self._read_body(scope, receive, policy.has_body if policy else False)
                delivered = False

                async def replay_receive() -> Message:
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    return await receive()

                dispatched = True
                await self.app(scope, replay_receive, guarded_send)
                outcome = "failed" if status >= 500 else "denied" if status >= 400 else "completed"
        except ApiFailure as exc:
            await failure(exc.code)
            outcome = "denied"
        except TimeoutError:
            # A timed-out thread may still finish. Never assert rollback or issue a new key.
            await failure("INTERNAL_ERROR", response_status=504 if budget.expired() else 500)
            outcome = "deadline" if budget.expired() else "failed"
        except Disconnected:
            status = 499
            outcome = "disconnected"
        except asyncio.CancelledError:
            status = 499 if not response_started else status
            outcome = "cancelled"
            raise
        except Exception:
            await failure("INTERNAL_ERROR")
            outcome = "failed"
        finally:
            provider_metric = close_provider_metric(state, request_id)
            context = state.get("diagnostic_context")
            if not isinstance(context, DiagnosticContext):
                context = DiagnosticContext()
            code = state.get("safe_error_code")
            event = RequestEvent(
                request_id=request_id,
                operation=operation,
                method=method,
                status=status,
                outcome=outcome,
                error_code=code if isinstance(code, str) and code in ERRORS else None,
                duration_ms=max(0, round((monotonic() - started) * 1000)),
                operation_ref=context.operation_ref,
                snapshot_id=context.snapshot_id,
                provider=provider_metric,
            )
            # Best effort enqueue only: a slow/failed sink cannot block the event loop.
            with suppress(Exception):
                self.event_dispatcher.submit(event, self.event_sink)
