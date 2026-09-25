"""Frozen viewing routes over injected services; GET never publishes or repairs."""

from typing import Annotated, Any, Protocol

from fastapi import APIRouter, Depends, Query, Request, Response
from starlette.responses import JSONResponse

from app.api.dependencies import private_read, private_write
from app.api.schemas.common import ApiError, Envelope, ErrorEnvelope, Id, OpaqueKey, ResponseMeta
from app.api.schemas.operations import OperationRejected, OperationStatus, OperationSucceeded
from app.api.schemas.viewings import (
    BookingDraft,
    BookingDraftCreate,
    BookingDraftUpdate,
    BookingReceipt,
    ConfirmRequest,
    ViewingOptions,
    ViewingOptionsRequest,
)
from app.core.diagnostics import DiagnosticContext
from app.core.errors import ERRORS
from app.identity.authorization import AuthorizedOwnerContext
from app.viewings.application import ConfirmationObservationUnavailable, ViewingApplication


class ViewingOptionsReader(Protocol):
    """Requires actual capacity-observed options, never unverified calendar candidates."""

    def options(self, request: ViewingOptionsRequest) -> ViewingOptions: ...


def viewing_router(application: ViewingApplication, *, options: ViewingOptionsReader) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["transactions"])
    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": ErrorEnvelope}
        for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504)
    }
    private = {
        "x-domain-owner": "transactions", "x-private": True, "x-mutates-state": False,
        "security": [{"OwnerCookie": []}],
    }
    mutation = {**private, "x-mutates-state": True}

    def meta(
        request: Request, context: AuthorizedOwnerContext, *, revision: int | None = None,
        snapshot: str | None = None, operation_ref: str | None = None,
    ) -> ResponseMeta:
        request.state.diagnostic_context = DiagnosticContext(
            snapshot_id=snapshot, operation_ref=operation_ref,
        )
        return ResponseMeta(
            request_id=request.state.request_id, store_generation=context.generation,
            identity_context_id=context.context_id, entity_revision=revision,
            inventory_snapshot_id=snapshot,
        )

    def draft_envelope(
        request: Request, context: AuthorizedOwnerContext, result: BookingDraft,
    ) -> Envelope[BookingDraft]:
        return Envelope(data=result, meta=meta(
            request, context, revision=result.revision, snapshot=result.ref.snapshot_id,
        ))

    @router.post(
        "/viewing-options", operation_id="get_viewing_options",
        response_model=Envelope[ViewingOptions], responses=errors,
        openapi_extra={**private, "x-private": False, "security": []},
    )
    def available(body: ViewingOptionsRequest, request: Request) -> Envelope[ViewingOptions]:
        result = options.options(body)
        request.state.diagnostic_context = DiagnosticContext(snapshot_id=result.ref.snapshot_id)
        return Envelope(data=result, meta=ResponseMeta(
            request_id=request.state.request_id, inventory_snapshot_id=result.ref.snapshot_id,
        ))

    @router.post(
        "/booking-drafts", operation_id="create_booking_draft", status_code=201,
        response_model=Envelope[BookingDraft], responses=errors, openapi_extra=mutation,
    )
    def create(
        body: BookingDraftCreate, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[BookingDraft]:
        return draft_envelope(request, context, application.drafts.create(context, body))

    @router.get(
        "/booking-drafts/{draft_id}", operation_id="get_booking_draft",
        response_model=Envelope[BookingDraft], responses=errors, openapi_extra=private,
    )
    def get(
        draft_id: Id, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
    ) -> Envelope[BookingDraft]:
        return draft_envelope(request, context, application.drafts.get(context, draft_id))

    @router.patch(
        "/booking-drafts/{draft_id}", operation_id="update_booking_draft",
        response_model=Envelope[BookingDraft], responses=errors, openapi_extra=mutation,
    )
    def update(
        draft_id: Id, body: BookingDraftUpdate, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[BookingDraft]:
        return draft_envelope(request, context, application.drafts.update(context, draft_id, body))

    @router.post(
        "/booking-drafts/{draft_id}/confirm", operation_id="confirm_booking_draft",
        response_model=Envelope[OperationStatus],
        responses={**errors, 409: {"model": ErrorEnvelope | Envelope[OperationRejected]}},
        openapi_extra=mutation,
    )
    def confirm(
        draft_id: Id, body: ConfirmRequest, request: Request, response: Response,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[OperationStatus] | JSONResponse:
        try:
            result = application.confirm(context, draft_id, body)
        except ConfirmationObservationUnavailable as exc:
            terminal = exc.terminal
            meta(request, context, snapshot=terminal.booking.review.ref.snapshot_id,
                 operation_ref=terminal.review_id)
            request.state.safe_error_code = "STORE_UNAVAILABLE"
            return JSONResponse(status_code=503, content=ErrorEnvelope(error=ApiError(
                code="STORE_UNAVAILABLE", message=ERRORS["STORE_UNAVAILABLE"].message,
                request_id=request.state.request_id, retryable=True, retry_action="read",
                operation_key=terminal.operation_key, outcome_state="succeeded",
            )).model_dump(mode="json"))
        if isinstance(result, OperationRejected):
            response.status_code = 409
        snapshot = (
            result.booking.review.ref.snapshot_id if isinstance(result, OperationSucceeded) else None
        )
        return Envelope(data=result, meta=meta(
            request, context, snapshot=snapshot, operation_ref=result.review_id,
        ))

    @router.get(
        "/operations/{operation_key}", operation_id="get_operation",
        response_model=Envelope[OperationStatus], responses=errors, openapi_extra=private,
    )
    def status(
        operation_key: OpaqueKey, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
        submitted_store_generation: Annotated[Id | None, Query()] = None,
    ) -> Envelope[OperationStatus]:
        result = application.status(context, operation_key, submitted_store_generation)
        snapshot = (
            result.booking.review.ref.snapshot_id if isinstance(result, OperationSucceeded) else None
        )
        reference = (
            result.review_id if isinstance(result, OperationSucceeded | OperationRejected) else None
        )
        return Envelope(data=result, meta=meta(
            request, context, snapshot=snapshot, operation_ref=reference,
        ))

    @router.get(
        "/bookings/{booking_id}", operation_id="get_booking",
        response_model=Envelope[BookingReceipt], responses=errors, openapi_extra=private,
    )
    def booking(
        booking_id: Id, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
    ) -> Envelope[BookingReceipt]:
        result = application.booking(context, booking_id)
        return Envelope(data=result, meta=meta(
            request, context, snapshot=result.review.ref.snapshot_id,
            operation_ref=result.review.review_id,
        ))

    return router
