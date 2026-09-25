"""Owned public routes; deliberately unmounted until real signing/composition validation."""

from typing import Annotated, Any

from fastapi import APIRouter, Path, Request

from app.api.schemas.common import Envelope, ErrorEnvelope, InventoryRef, ResponseMeta
from app.api.schemas.inventory import (
    ComparisonRequest,
    ComparisonResult,
    ListingResult,
    SearchRequest,
    SearchResult,
)
from app.inventory.details_service import InventoryDetailsService
from app.inventory.search_service import InventorySearchService

Namespace = Annotated[str, Path(pattern=r"^[a-z0-9_-]{1,64}$")]
SnapshotId = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]
SourceId = Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]{1,128}$")]


def inventory_router(search: InventorySearchService, details: InventoryDetailsService) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["inventory"])
    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": ErrorEnvelope}
        for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504)
    }
    public = {"x-domain-owner": "inventory", "x-private": False, "x-mutates-state": False}

    @router.post(
        "/inventory/search",
        operation_id="search_inventory",
        response_model=Envelope[SearchResult],
        responses=errors,
        openapi_extra=public,
    )
    def find(body: SearchRequest, request: Request) -> Envelope[SearchResult]:
        result = search.search(body)
        return Envelope(
            data=result,
            meta=ResponseMeta(
                request_id=request.state.request_id,
                inventory_snapshot_id=result.presentation.snapshot_id,
                store_generation=search.reader.store.generation,
            ),
        )

    @router.get(
        "/listings/{namespace}/{snapshot_id}/{source_id}",
        operation_id="get_listing",
        response_model=Envelope[ListingResult],
        responses=errors,
        openapi_extra=public,
    )
    def listing(
        namespace: Namespace, snapshot_id: SnapshotId, source_id: SourceId, request: Request
    ) -> Envelope[ListingResult]:
        result = details.read(
            (InventoryRef(namespace=namespace, snapshot_id=snapshot_id, source_id=source_id),)
        )
        return Envelope(
            data=result.items[0],
            meta=ResponseMeta(
                request_id=request.state.request_id,
                inventory_snapshot_id=result.observation.snapshot_id,
                store_generation=result.observation.generation,
            ),
        )

    @router.post(
        "/comparisons",
        operation_id="compare_listings",
        response_model=Envelope[ComparisonResult],
        responses=errors,
        openapi_extra=public,
    )
    def compare(body: ComparisonRequest, request: Request) -> Envelope[ComparisonResult]:
        result = details.read(tuple(body.refs))
        return Envelope(
            data=ComparisonResult(items=list(result.items)),
            meta=ResponseMeta(
                request_id=request.state.request_id,
                inventory_snapshot_id=result.observation.snapshot_id,
                store_generation=result.observation.generation,
            ),
        )

    return router
