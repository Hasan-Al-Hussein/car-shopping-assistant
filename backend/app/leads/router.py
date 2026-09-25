"""Owned enquiry HTTP adapters; CSV repair follows a committed explicit change."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import private_read, private_write
from app.api.schemas.common import Envelope, ErrorEnvelope, Id, ResponseMeta
from app.api.schemas.leads import (
    LeadRecord,
    LeadSaveRequest,
    LeadSaveResult,
    LeadUpdateRequest,
    NoLead,
)
from app.identity.authorization import AuthorizedOwnerContext
from app.leads import repository
from app.leads.projection import CsvProjector, constrain_observation
from app.leads.service import LeadService


def lead_router(service: LeadService, *, projector: CsvProjector) -> APIRouter:
    settings = service.authorization.identity.settings
    if (projector.store.path, projector.store.boundary) != (
        settings.store_path, settings.runtime_boundary,
    ):
        raise ValueError("LEAD_PROJECTOR_STORE_MISMATCH")
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
        request: Request, context: AuthorizedOwnerContext, revision: int | None,
    ) -> ResponseMeta:
        return ResponseMeta(
            request_id=request.state.request_id, store_generation=context.generation,
            identity_context_id=context.context_id, entity_revision=revision,
        )

    def after_commit(
        context: AuthorizedOwnerContext, result: LeadSaveResult,
    ) -> LeadSaveResult:
        attempt = projector.repair_once()
        observation = service.authorization.read(
            context, lambda unit: repository.projection(
                unit, context.generation, service.authorization.identity.now_text(),
            ),
        )
        # Retain the exact saved/replayed values and revision. Only CSV is current.
        lead = result.lead.model_copy(
            update={"csv": constrain_observation(observation, attempt)}, deep=True,
        )
        return result.model_copy(update={"lead": lead}, deep=True)

    @router.post(
        "/leads", operation_id="save_local_enquiry", status_code=201,
        response_model=Envelope[LeadSaveResult], responses=errors, openapi_extra=mutation,
    )
    def save(
        body: LeadSaveRequest, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[LeadSaveResult]:
        committed = service.save(context, body)
        result = after_commit(context, committed)
        return Envelope(data=result, meta=meta(request, context, result.lead.revision))

    @router.get(
        "/leads/current", operation_id="get_current_local_enquiry",
        response_model=Envelope[LeadRecord | NoLead], responses=errors, openapi_extra=private,
    )
    def current(
        request: Request, context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
    ) -> Envelope[LeadRecord | NoLead]:
        result = service.get(context)
        revision = result.revision if isinstance(result, LeadRecord) else None
        return Envelope(data=result, meta=meta(request, context, revision))

    @router.get(
        "/leads/{lead_id}", operation_id="get_local_enquiry",
        response_model=Envelope[LeadRecord], responses=errors, openapi_extra=private,
    )
    def get(
        lead_id: Id, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_read)],
    ) -> Envelope[LeadRecord]:
        result = service.authorization.read(
            context, lambda unit: repository.record(
                unit, unit.lead(lead_id), context.generation,
                service.authorization.identity.now_text(),
            ),
        )
        return Envelope(data=result, meta=meta(request, context, result.revision))

    @router.patch(
        "/leads/{lead_id}", operation_id="update_local_enquiry",
        response_model=Envelope[LeadSaveResult], responses=errors, openapi_extra=mutation,
    )
    def update(
        lead_id: Id, body: LeadUpdateRequest, request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[LeadSaveResult]:
        committed = service.update(context, lead_id, body)
        result = after_commit(context, committed)
        return Envelope(data=result, meta=meta(request, context, result.lead.revision))

    return router
