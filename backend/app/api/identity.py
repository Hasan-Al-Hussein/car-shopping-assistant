"""Three explicit identity routes; no other private-resource authority is mounted."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, Request, Response
from starlette.responses import JSONResponse

from app.api.schemas.common import EmptyResult, Envelope, ErrorEnvelope, Id, OpaqueKey, ResponseMeta
from app.api.schemas.identity import (
    IdentityBootstrapRequest,
    IdentityEndRequest,
    IdentityResult,
    RecognizedIdentity,
)
from app.core.config import Settings
from app.core.errors import ApiFailure, error_response
from app.core.http import one_header
from app.identity.credentials import decode_token
from app.identity.service import IdentityService


class AmbiguousCookie(ApiFailure):
    """No candidate may be cleared when parsing cannot identify one safely."""

    def __init__(self) -> None:
        super().__init__("IDENTITY_REQUIRED")


def credential_cookie(request: Request, settings: Settings) -> bytes | None:
    headers = [value for name, value in request.scope["headers"] if name.lower() == b"cookie"]
    if not headers:
        return None
    if len(headers) != 1 or len(headers[0]) > 8192:
        raise AmbiguousCookie()
    name = settings.cookie_name.encode("ascii")
    values: list[tuple[bytes, bool]] = []
    for part in headers[0].split(b";"):
        key, separator, value = part.strip().partition(b"=")
        if key.strip() == name:
            values.append((value, key == name and bool(separator)))
    if not values:
        return None
    if len(values) != 1:
        raise AmbiguousCookie()
    value, well_formed = values[0]
    if not well_formed:
        raise ApiFailure("IDENTITY_REQUIRED")
    try:
        return decode_token(value.decode("ascii"))
    except (UnicodeError, ValueError):
        raise ApiFailure("IDENTITY_REQUIRED") from None


def clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.cookie_name, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


def identity_router(service: IdentityService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["platform"])
    settings = service.settings
    errors: dict[int | str, dict[str, Any]] = {
        status: {"model": ErrorEnvelope}
        for status in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504)
    }
    public = {"x-domain-owner": "platform", "x-private": False, "security": []}

    @router.get(
        "/identity",
        operation_id="get_identity",
        response_model=Envelope[IdentityResult],
        responses=errors,
        openapi_extra={**public, "x-mutates-state": False},
    )
    def current(request: Request) -> Envelope[IdentityResult]:
        observation = service.current(credential_cookie(request, settings))
        context_id = (
            observation.identity.context_id
            if isinstance(observation.identity, RecognizedIdentity)
            else None
        )
        return Envelope(
            data=observation.identity,
            meta=ResponseMeta(
                request_id=request.state.request_id,
                store_generation=observation.generation,
                identity_context_id=context_id,
            ),
        )

    @router.post(
        "/identity/bootstrap",
        operation_id="bootstrap_identity",
        status_code=201,
        response_model=Envelope[RecognizedIdentity],
        responses={
            **errors,
            200: {"model": Envelope[RecognizedIdentity], "description": "Existing valid identity"},
        },
        openapi_extra={**public, "x-mutates-state": True},
    )
    def bootstrap(
        body: IdentityBootstrapRequest,
        request: Request,
        response: Response,
        origin: Annotated[str, Header(alias="Origin")],
    ) -> Envelope[RecognizedIdentity] | JSONResponse:
        try:
            outcome = service.bootstrap(body, credential_cookie(request, settings))
        except ApiFailure as exc:
            if exc.code != "IDENTITY_REQUIRED" or isinstance(exc, AmbiguousCookie):
                raise
            # An explicit acknowledged attempt may discard an invalid browser credential.
            # It never creates a replacement in that response or clears on store failure.
            request.state.safe_error_code = exc.code
            denied = error_response(exc.code, request.state.request_id)
            clear_cookie(denied, settings)
            return denied
        if outcome.cookie is None:
            response.status_code = 200
        else:
            response.set_cookie(
                settings.cookie_name,
                outcome.cookie,
                max_age=settings.policy.owner_cookie_days * 24 * 60 * 60,
                expires=datetime.fromisoformat(outcome.identity.expires_at.replace("Z", "+00:00")),
                path="/",
                httponly=True,
                secure=settings.cookie_secure,
                samesite="lax",
            )
        return Envelope(
            data=outcome.identity,
            meta=ResponseMeta(
                request_id=request.state.request_id,
                store_generation=outcome.generation,
                identity_context_id=outcome.identity.context_id,
            ),
        )

    @router.post(
        "/identity/end",
        operation_id="end_identity",
        response_model=Envelope[EmptyResult],
        responses=errors,
        openapi_extra={
            "x-domain-owner": "platform",
            "x-private": True,
            "x-mutates-state": True,
            "security": [{"OwnerCookie": []}],
        },
    )
    def end(
        body: IdentityEndRequest,
        request: Request,
        response: Response,
        identity_context: Annotated[Id, Header(alias="X-Identity-Context")],
        csrf: Annotated[OpaqueKey, Header(alias="X-CSRF-Token")],
        origin: Annotated[str, Header(alias="Origin")],
    ) -> Envelope[EmptyResult]:
        # FastAPI validates the frozen shape; reject ambiguity before comparing authority.
        one_header(request.scope, b"x-identity-context")
        one_header(request.scope, b"x-csrf-token")
        outcome = service.end(credential_cookie(request, settings), identity_context, csrf)
        clear_cookie(response, settings)
        return Envelope(
            data=EmptyResult(state="ended"),
            meta=ResponseMeta(
                request_id=request.state.request_id,
                store_generation=outcome.generation,
                identity_context_id=outcome.context_id,
            ),
        )

    return router
