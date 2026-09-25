"""Preference adapters, authored but not mounted during source-only P10."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import private_read, private_write
from app.api.schemas.common import Envelope, ErrorEnvelope, ResponseMeta
from app.api.schemas.memory import PreferenceCommand, PreferenceRecord
from app.identity.authorization import AuthorizedOwnerContext
from app.memory.service import PreferenceService


def preference_router(service: PreferenceService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["platform"])
    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": ErrorEnvelope}
        for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504)
    }
    private = {
        "x-domain-owner": "platform",
        "x-private": True,
        "x-mutates-state": False,
        "security": [{"OwnerCookie": []}],
    }

    def envelope(
        request: Request, context: AuthorizedOwnerContext, result: PreferenceRecord
    ) -> Envelope[PreferenceRecord]:
        return Envelope(
            data=result,
            meta=ResponseMeta(
                request_id=request.state.request_id,
                store_generation=context.generation,
                identity_context_id=context.context_id,
                entity_revision=result.revision,
            ),
        )

    @router.get(
        "/preferences",
        operation_id="get_preferences",
        response_model=Envelope[PreferenceRecord],
        responses=errors,
        openapi_extra=private,
    )
    def get(
        request: Request, context: Annotated[AuthorizedOwnerContext, Depends(private_read)]
    ) -> Envelope[PreferenceRecord]:
        return envelope(request, context, service.get(context))

    @router.patch(
        "/preferences",
        operation_id="update_preferences",
        response_model=Envelope[PreferenceRecord],
        responses=errors,
        openapi_extra={**private, "x-mutates-state": True},
    )
    def update(
        body: PreferenceCommand,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[PreferenceRecord]:
        return envelope(request, context, service.update(context, body))

    return router
