"""Real owned session routes; Assistant owns POST messages and its coordinator."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import private_read, private_write
from app.api.schemas.common import Envelope, ErrorEnvelope, Id, ResponseMeta
from app.api.schemas.sessions import (
    PresentationRegisterRequest,
    SessionCreateRequest,
    SessionSelectionRequest,
    SessionState,
    TranscriptPage,
)
from app.identity.authorization import AuthorizedOwnerContext
from app.sessions.service import SessionService


def session_router(service: SessionService) -> APIRouter:
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
    mutation = {**private, "x-mutates-state": True}

    def envelope(
        request: Request, context: AuthorizedOwnerContext, state: SessionState
    ) -> Envelope[SessionState]:
        return Envelope(
            data=state,
            meta=ResponseMeta(
                request_id=request.state.request_id,
                store_generation=context.generation,
                identity_context_id=context.context_id,
                entity_revision=state.revision,
            ),
        )

    @router.post(
        "/sessions",
        operation_id="create_session",
        status_code=201,
        response_model=Envelope[SessionState],
        responses=errors,
        openapi_extra=mutation,
    )
    def create(
        body: SessionCreateRequest,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[SessionState]:
        return envelope(request, context, service.create(context, body))

    @router.get(
        "/sessions/{session_id}",
        operation_id="get_session",
        response_model=Envelope[SessionState],
        responses=errors,
        openapi_extra=private,
    )
    def get(
        session_id: Id,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
    ) -> Envelope[SessionState]:
        return envelope(request, context, service.get(context, session_id))

    @router.get(
        "/sessions/{session_id}/messages",
        operation_id="get_session_messages",
        response_model=Envelope[TranscriptPage],
        responses=errors,
        openapi_extra=private,
    )
    def transcript(
        session_id: Id,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
        page_size: Annotated[int, Query(ge=1, le=50)] = 20,
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ) -> Envelope[TranscriptPage]:
        page = service.transcript(context, session_id, page_size=page_size, cursor=cursor)
        return Envelope(
            data=page,
            meta=ResponseMeta(
                request_id=request.state.request_id,
                store_generation=context.generation,
                identity_context_id=context.context_id,
                entity_revision=page.observed_revision,
            ),
        )

    @router.post(
        "/sessions/{session_id}/presentations",
        operation_id="register_presentation",
        response_model=Envelope[SessionState],
        responses=errors,
        openapi_extra=mutation,
    )
    def register(
        session_id: Id,
        body: PresentationRegisterRequest,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[SessionState]:
        return envelope(request, context, service.register(context, session_id, body))

    @router.patch(
        "/sessions/{session_id}/selection",
        operation_id="select_session_listing",
        response_model=Envelope[SessionState],
        responses=errors,
        openapi_extra=mutation,
    )
    def select(
        session_id: Id,
        body: SessionSelectionRequest,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[SessionState]:
        return envelope(request, context, service.select(context, session_id, body))

    return router
