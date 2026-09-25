"""Concrete collection facade; only Platform completes messages and business effects."""

from dataclasses import replace
from typing import Protocol

from app.api.schemas.common import InventoryRef
from app.api.schemas.sessions import MessageResult
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.leads.service import LeadService
from app.sessions.service import SessionService, TurnAdmission
from app.viewings.drafts import DraftService
from app.viewings.scheduling import ViewingRules

from .collection_language import CollectionRequest
from .collection_planner import CollectionObservation, CollectionPlan, plan_collection


class CollectionBridge:
    def __init__(
        self, sessions: SessionService, leads: LeadService, drafts: DraftService,
        rules: ViewingRules,
    ) -> None:
        if leads.authorization is not sessions.authorization or drafts.authorization is not sessions.authorization:
            raise ValueError("COLLECTION_REQUIRES_SHARED_AUTHORIZATION")
        self.sessions, self.leads, self.drafts, self.rules = sessions, leads, drafts, rules

    def observe(self, context: AuthorizedOwnerContext, admission: TurnAdmission) -> CollectionObservation:
        if admission.status != "accepted" or admission.ticket is None:
            raise ApiFailure("UNSUPPORTED_STATE")
        return CollectionObservation(self.sessions.read_collection(context, admission.ticket), None, None)

    def prepare(
        self, context: AuthorizedOwnerContext, admission: TurnAdmission,
        observed: CollectionObservation, requested: CollectionRequest,
        resolved_ref: InventoryRef | None,
    ) -> CollectionPlan:
        if observed.snapshot.unresolved is not None:
            return plan_collection(admission, observed, requested, resolved_ref=resolved_ref, rules=self.rules)
        lead = self.leads.get(context) if requested.command in {
            "review_enquiry", "save_enquiry", "correct_enquiry", "prepare_viewing", "refresh_viewing",
        } else None
        draft = (
            self.drafts.get(context, admission.session.current_draft_id)
            if admission.session.current_draft_id is not None else None
        )
        return plan_collection(
            admission, replace(observed, lead=lead, draft=draft), requested,
            resolved_ref=resolved_ref, rules=self.rules,
        )

    def complete(
        self, context: AuthorizedOwnerContext, admission: TurnAdmission, plan: CollectionPlan,
    ) -> MessageResult:
        if admission.ticket is None or (
            plan.result.session_id, plan.result.client_message_id, plan.result.turn_revision
        ) != (
            admission.session.session_id, admission.request.client_message_id, admission.session.revision
        ):
            raise ApiFailure("VALIDATION_ERROR")
        if plan.lead is not None or plan.draft is not None:
            if any(value["state"] != "not_requested" for value in plan.result.actions.model_dump().values()):
                raise ApiFailure("VALIDATION_ERROR")
            return self.sessions.complete_action(
                context, admission.ticket, plan.result, update=plan.update,
                selection=plan.selection,
                collection_update=plan.collection_update, lead=plan.lead, draft=plan.draft,
                lead_service=self.leads, draft_service=self.drafts,
            )
        return self.sessions.complete(
            context, admission.ticket, plan.result, update=plan.update,
            selection=plan.selection,
            collection_update=plan.collection_update,
        )


class CollectionPort(Protocol):
    async def observe_collection(
        self, context: AuthorizedOwnerContext, admission: TurnAdmission,
    ) -> CollectionObservation: ...

    async def prepare_collection(
        self, context: AuthorizedOwnerContext, admission: TurnAdmission,
        observed: CollectionObservation, requested: CollectionRequest, resolved_ref: InventoryRef | None,
    ) -> CollectionPlan: ...

    async def complete_collection(
        self, context: AuthorizedOwnerContext, admission: TurnAdmission, plan: CollectionPlan,
    ) -> MessageResult: ...
