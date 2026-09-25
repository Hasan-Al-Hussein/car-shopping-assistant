"""Private-route dependencies; canonical cookie parsing and F04 remain authoritative."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, Request

from app.api.identity import credential_cookie
from app.api.schemas.common import Id, OpaqueKey
from app.core.http import one_header
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext


def authorization_service(request: Request) -> AuthorizationService:
    service = request.app.state.authorization
    if not isinstance(service, AuthorizationService):
        raise RuntimeError("AUTHORIZATION_SERVICE_REQUIRED")
    return service


def private_read(
    request: Request,
    identity_context: Annotated[Id, Header(alias="X-Identity-Context")],
) -> AuthorizedOwnerContext:
    one_header(request.scope, b"x-identity-context")
    service = authorization_service(request)
    return service.authorize_read(
        credential_cookie(request, service.identity.settings), identity_context
    )


def private_write(
    request: Request,
    identity_context: Annotated[Id, Header(alias="X-Identity-Context")],
    csrf_token: Annotated[OpaqueKey, Header(alias="X-CSRF-Token")],
    origin: Annotated[str, Header(alias="Origin")],
) -> AuthorizedOwnerContext:
    one_header(request.scope, b"x-identity-context")
    one_header(request.scope, b"x-csrf-token")
    one_header(request.scope, b"origin")
    service = authorization_service(request)
    return service.authorize_write(
        credential_cookie(request, service.identity.settings), identity_context, csrf_token
    )


@dataclass(frozen=True)
class DeleteCommandHeaders:
    client_action_id: str
    expected_revision: int


def delete_command_headers(
    request: Request,
    client_action_id: Annotated[Id, Header(alias="X-Client-Action-ID")],
    expected_revision: Annotated[int, Header(alias="X-Expected-Revision", ge=0, le=2_147_483_647)],
) -> DeleteCommandHeaders:
    """Bodyless shortlist DELETE also requires Depends(private_write)."""
    one_header(request.scope, b"x-client-action-id")
    one_header(request.scope, b"x-expected-revision")
    return DeleteCommandHeaders(client_action_id, expected_revision)
