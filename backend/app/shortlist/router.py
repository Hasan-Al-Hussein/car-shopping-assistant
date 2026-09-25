"""Shortlist transport, deliberately unmounted until validated composition."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request

from app.api.dependencies import (
    DeleteCommandHeaders,
    delete_command_headers,
    private_read,
    private_write,
)
from app.api.schemas.common import Envelope, ErrorEnvelope, InventoryRef, ResponseMeta
from app.api.schemas.memory import MembershipRequest, MembershipResult, ShortlistResult
from app.identity.authorization import AuthorizedOwnerContext
from app.shortlist.service import ShortlistService

Namespace = Annotated[str, Path(pattern=r"^[a-z0-9_-]{1,64}$")]
SnapshotId = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]
SourceId = Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]{1,128}$")]


def shortlist_router(service: ShortlistService) -> APIRouter:
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

    def meta(request: Request, context: AuthorizedOwnerContext, revision: int) -> ResponseMeta:
        return ResponseMeta(
            request_id=request.state.request_id,
            store_generation=context.generation,
            identity_context_id=context.context_id,
            entity_revision=revision,
        )

    def reference(namespace: str, snapshot_id: str, source_id: str) -> InventoryRef:
        # Apply exactly the frozen path constraints without accepting an owner ID.
        return InventoryRef(namespace=namespace, snapshot_id=snapshot_id, source_id=source_id)

    @router.get(
        "/shortlist",
        operation_id="get_shortlist",
        response_model=Envelope[ShortlistResult],
        responses=errors,
        openapi_extra=private,
    )
    def get(
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
        page_size: Annotated[int, Query(ge=1, le=50)] = 20,
        cursor: Annotated[str | None, Query(max_length=2048)] = None,
    ) -> Envelope[ShortlistResult]:
        result = service.get(context, page_size=page_size, cursor=cursor)
        return Envelope(data=result, meta=meta(request, context, result.revision))

    @router.put(
        "/shortlist/{namespace}/{snapshot_id}/{source_id}",
        operation_id="add_shortlist_membership",
        response_model=Envelope[MembershipResult],
        responses=errors,
        openapi_extra={**private, "x-mutates-state": True},
    )
    def put(
        namespace: Namespace,
        snapshot_id: SnapshotId,
        source_id: SourceId,
        body: MembershipRequest,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[MembershipResult]:
        result = service.put(context, reference(namespace, snapshot_id, source_id), body)
        return Envelope(data=result, meta=meta(request, context, result.current_revision))

    @router.delete(
        "/shortlist/{namespace}/{snapshot_id}/{source_id}",
        operation_id="remove_shortlist_membership",
        response_model=Envelope[MembershipResult],
        responses=errors,
        openapi_extra={**private, "x-mutates-state": True},
    )
    def delete(
        namespace: Namespace,
        snapshot_id: SnapshotId,
        source_id: SourceId,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
        headers: Annotated[DeleteCommandHeaders, Depends(delete_command_headers)],
    ) -> Envelope[MembershipResult]:
        result = service.delete(
            context,
            reference(namespace, snapshot_id, source_id),
            MembershipRequest(
                client_action_id=headers.client_action_id,
                expected_revision=headers.expected_revision,
            ),
        )
        return Envelope(data=result, meta=meta(request, context, result.current_revision))

    return router
