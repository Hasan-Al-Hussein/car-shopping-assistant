"""The frozen message endpoint over the application-owned Assistant services."""

from time import monotonic
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from starlette.responses import JSONResponse

from app.api.dependencies import private_write
from app.api.schemas.common import ApiError, Envelope, ErrorEnvelope, Id, ResponseMeta
from app.api.schemas.operations import OperationSucceeded
from app.api.schemas.sessions import MessageRequest, MessageResult
from app.assistant.budget import TurnBudget
from app.assistant.service_adapters import AssistantService, BoundedServiceWorker
from app.core.config import Settings
from app.core.diagnostics import DiagnosticContext
from app.core.errors import ERRORS, ApiFailure
from app.database.models import Owner
from app.database.store import StoreError
from app.identity.authorization import AuthorizedOwnerContext, OwnerUnit
from app.leads import repository as lead_repository
from app.leads.projection import CsvProjector
from app.leads.service import LeadService
from app.sessions.repository import live_session

_RESPONSE_RESERVE_SECONDS = 0.25


def assistant_router(
    service: AssistantService,
    *,
    settings: Settings,
    worker: BoundedServiceWorker,
    leads: LeadService,
    projector: CsvProjector,
) -> APIRouter:
    if leads.authorization.identity.settings != settings or (
        projector.store.path,
        projector.store.boundary,
    ) != (settings.store_path, settings.runtime_boundary):
        raise ValueError("ASSISTANT_COMPOSITION_MISMATCH")
    router = APIRouter(prefix="/api/v1", tags=["assistant"])
    errors: dict[int | str, dict[str, Any]] = {
        code: {"model": ErrorEnvelope}
        for code in (400, 401, 403, 404, 409, 413, 415, 422, 429, 500, 503, 504)
    }

    def private_values(context: AuthorizedOwnerContext, session_id: str) -> tuple[str, ...]:
        def read(unit: OwnerUnit) -> tuple[str, ...]:
            now = leads.authorization.identity.now_text()
            session = live_session(unit, session_id, now)
            owner = unit.db.get(Owner, unit.owner_id)
            if owner is None:
                raise StoreError("ASSISTANT_OWNER_UNAVAILABLE")
            values = [] if owner.display_name is None else [owner.display_name]
            current = unit.lead_for_journey(session.journey_id)
            if current is not None:
                # Retained expired contacts still need redaction. Their presence
                # grants no current lead authority and does not block other chat.
                contacts = lead_repository.values(current)
                values.extend(
                    item.value
                    for item in (contacts.email, contacts.phone)
                    if item.state == "provided" and item.value is not None
                )
            return tuple(values)

        return leads.authorization.read(context, read)

    @router.post(
        "/sessions/{session_id}/messages",
        operation_id="submit_message",
        response_model=Envelope[MessageResult],
        responses=errors,
        openapi_extra={
            "x-domain-owner": "assistant",
            "x-private": True,
            "x-mutates-state": True,
            "security": [{"OwnerCookie": []}],
        },
    )
    async def submit(
        session_id: Id,
        body: MessageRequest,
        request: Request,
        context: Annotated[AuthorizedOwnerContext, Depends(private_write)],
    ) -> Envelope[MessageResult] | JSONResponse:
        state = request.scope["state"]
        budget = TurnBudget(settings.timeouts, state["deadline_at"])
        try:
            # Failed owner/private reads never fall back to unregistered provider input.
            omitted = await worker.run(
                lambda: private_values(context, session_id), deadline_at=budget.deadline_at
            )
            result = await service.run(
                context,
                session_id,
                body,
                request_state=state,
                budget=budget,
                private_values=omitted,
            )
        except ApiFailure as exc:
            if exc.code != "OPERATION_UNRESOLVED":
                raise
            state["safe_error_code"] = exc.code
            explicit = body.explicit_confirmation
            # The client retains its original message/action identity and reads it;
            # an uncertain/pending result never authorizes a fresh message/key retry.
            return JSONResponse(
                status_code=409,
                content=ErrorEnvelope(
                    error=ApiError(
                        code=exc.code,
                        message=ERRORS[exc.code].message,
                        request_id=state["request_id"],
                        retryable=True,
                        retry_action="read",
                        outcome_state="unresolved",
                        operation_key=None if explicit is None else explicit.operation_key,
                    )
                ).model_dump(mode="json"),
            )
        if result.persistence == "saved" and (
            result.actions.lead.state == "succeeded"
            or isinstance(result.operation, OperationSucceeded)
        ):
            repair_deadline = min(
                budget.deadline_at - _RESPONSE_RESERVE_SECONDS,
                monotonic() + settings.timeouts.read_seconds,
            )
            try:
                # A separate postcommit attempt can repair CSV. The original typed
                # message receipt and its accepted CSV observation remain immutable.
                if repair_deadline > monotonic():
                    await worker.run(
                        projector.repair_once, deadline_at=repair_deadline, persistence=True
                    )
            except Exception:
                # Canonical success is already proven. GET lead/operation exposes
                # current CSV status; no canonical retry or response rewrite occurs.
                pass
        snapshot = result.search.presentation.snapshot_id if result.search is not None else None
        operation_ref = None
        if isinstance(result.operation, OperationSucceeded):
            snapshot = result.operation.booking.review.ref.snapshot_id
            operation_ref = result.operation.review_id
        state["diagnostic_context"] = DiagnosticContext(
            snapshot_id=snapshot, operation_ref=operation_ref
        )
        return Envelope(
            data=result,
            meta=ResponseMeta(
                request_id=state["request_id"],
                store_generation=context.generation,
                identity_context_id=context.context_id,
                entity_revision=result.current_revision,
                inventory_snapshot_id=snapshot,
            ),
        )

    return router
