"""Application entrypoint. Importing it never opens a store or calls a provider."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request

from app.api.identity import identity_router
from app.api.schemas.capabilities import HealthResult, PublicConfig
from app.api.schemas.common import Envelope, ErrorEnvelope, ResponseMeta
from app.api.schemas.openapi_security import install_owner_cookie_schema
from app.core.config import CONTRACT_VERSION, Settings, load_settings
from app.core.diagnostics import (
    DiagnosticContext,
    RequestEvent,
    emit_request_event,
    prepare_request_logging,
)
from app.core.errors import install_error_handlers
from app.core.http import HttpBoundary
from app.core.readiness import ReadinessRegistry, ReadinessService
from app.identity.authorization import AuthorizationService
from app.identity.service import IdentityService
from app.sessions.inventory import SessionInventory
from app.sessions.router import session_router
from app.sessions.service import SessionService


def create_app(
    settings: Settings | None = None,
    *,
    registry: ReadinessRegistry | None = None,
    readiness: ReadinessService | None = None,
    identity: IdentityService | None = None,
    session_inventory: SessionInventory | None = None,
    event_sink: Callable[[RequestEvent], None] = emit_request_event,
) -> FastAPI:
    if readiness is not None and registry is not None:
        raise ValueError("USE_READINESS_OR_REGISTRY")
    configured = settings if settings is not None else load_settings()
    observations = registry if registry is not None else ReadinessRegistry()
    service = readiness if readiness is not None else ReadinessService(configured, observations)
    if service.settings != configured:
        raise ValueError("READINESS_SETTINGS_MISMATCH")
    identities = identity if identity is not None else IdentityService(configured)
    if identities.settings != configured:
        raise ValueError("IDENTITY_SETTINGS_MISMATCH")
    prepare_request_logging()
    application = FastAPI(
        title="Car Shopping Assistant",
        version=CONTRACT_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    install_owner_cookie_schema(application)
    application.state.settings = configured
    application.state.readiness = service
    application.state.identity = identities
    application.state.authorization = AuthorizationService(identities)
    sessions = SessionService(application.state.authorization, inventory=session_inventory)
    application.state.sessions = sessions
    application.add_middleware(HttpBoundary, settings=configured, event_sink=event_sink)
    install_error_handlers(application)
    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": ErrorEnvelope}
        for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504)
    }
    metadata = {
        "x-domain-owner": "platform",
        "x-mutates-state": False,
        "x-private": False,
        "security": [],
    }

    @application.get(
        "/api/v1/health",
        operation_id="get_health",
        response_model=Envelope[HealthResult],
        responses=errors,
        openapi_extra=metadata,
        tags=["platform"],
    )
    def health(request: Request) -> Envelope[HealthResult]:
        observed = service.health()
        request.state.diagnostic_context = DiagnosticContext(
            snapshot_id=observed.active_snapshot_id
        )
        return Envelope(data=observed, meta=ResponseMeta(request_id=request.state.request_id))

    @application.get(
        "/api/v1/config",
        operation_id="get_config",
        response_model=Envelope[PublicConfig],
        responses=errors,
        openapi_extra=metadata,
        tags=["platform"],
    )
    def public_config(request: Request) -> Envelope[PublicConfig]:
        return Envelope(
            data=configured.public_config(), meta=ResponseMeta(request_id=request.state.request_id)
        )

    application.include_router(identity_router(identities))
    application.include_router(session_router(sessions))
    return application


app = create_app()


if __name__ == "__main__":
    from app.runtime_app import main

    main()
