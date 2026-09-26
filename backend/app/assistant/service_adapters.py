"""Explicit real-service composition with one shared, non-queuing synchronous worker.

Caller timeouts do not stop a thread or establish rollback. The worker owns its capacity
until the concurrent Future settles, independently of an abandoned/closed event loop.
Create one worker for the application composition, never one per request or timeout.
"""

import asyncio
from collections.abc import Callable, MutableMapping
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from math import isfinite
from threading import Lock
from time import monotonic
from typing import Any

from app.api.schemas.common import ErrorCode, InventoryRef
from app.api.schemas.inventory import (
    ComparisonRequest,
    ComparisonResult,
    ListingResult,
    PresentationProof,
    SearchRequest,
    SearchResult,
)
from app.api.schemas.memory import MembershipRequest, PreferencesUpdate
from app.api.schemas.sessions import MessageRequest, MessageResult, SessionState, TranscriptTurn
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.inventory.details_service import InventoryDetailsService
from app.inventory.search_service import InventorySearchService
from app.leads.service import LeadService
from app.memory.service import PreferenceService
from app.sessions.service import SessionService, ShortlistChange, TurnAdmission, TurnTicket
from app.sessions.state import SessionContent
from app.shortlist.service import ShortlistService
from app.viewings.confirmation import ConfirmationParticipant
from app.viewings.drafts import DraftService

from .action_bridge import ActionBridge, PreparedActions, RequestedActions
from .budget import TurnBudget
from .collection_bridge import CollectionBridge
from .collection_language import CollectionRequest
from .collection_planner import CollectionObservation, CollectionPlan
from .coordinator import ReadCoordinator
from .provider import GeminiAdapter


class BoundedServiceWorker:
    """One submitted call total, no waiting queue and no replacement after abandonment."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="assistant-service")
        self._state = Lock()
        self._busy = False
        self._closed = False

    @property
    def pending(self) -> bool:
        with self._state:
            return self._busy

    def close(self) -> bool:
        """Stop admission; return False while a call remains live, without claiming cleanup.

        The composition must retain this instance and call close again after settlement.
        A successful close joins the executor; a pending close never waits for the call.
        """
        with self._state:
            self._closed = True
            pending = self._busy
        self._executor.shutdown(wait=not pending, cancel_futures=False)
        return not pending

    async def run[T](
        self,
        call: Callable[[], T],
        *,
        deadline_at: float,
        persistence: bool = False,
    ) -> T:
        code: ErrorCode = "OPERATION_UNRESOLVED" if persistence else "PROVIDER_TIMEOUT"
        if not isfinite(deadline_at) or monotonic() >= deadline_at:
            raise ApiFailure(code)

        def invoke() -> T:
            # Admission does not renew the caller's frozen deadline.
            if monotonic() >= deadline_at:
                raise ApiFailure(code)
            return call()

        with self._state:
            if self._closed:
                raise ApiFailure("OPERATION_UNRESOLVED" if persistence else "STORE_UNAVAILABLE")
            if self._busy:
                raise ApiFailure("OPERATION_UNRESOLVED" if persistence else "STORE_BUSY")
            self._busy = True
            try:
                future = self._executor.submit(invoke)
            except BaseException:
                self._busy = False
                raise

        def settled(completed: Future[T]) -> None:
            # Callback registration is outside the lock: an already finished future invokes
            # it inline. Neither releasing capacity nor observing failure needs an event loop.
            try:
                if not completed.cancelled():
                    completed.exception()
            finally:
                with self._state:
                    self._busy = False

        future.add_done_callback(settled)
        observed = asyncio.wrap_future(future)

        def consume(completed: asyncio.Future[T]) -> None:
            if not completed.cancelled():
                completed.exception()

        observed.add_done_callback(consume)
        try:
            value = await asyncio.wait_for(
                asyncio.shield(observed), max(0.0, deadline_at - monotonic())
            )
        except TimeoutError:
            raise ApiFailure(code) from None
        if monotonic() >= deadline_at:
            raise ApiFailure(code)
        return value


class SessionServiceAdapter:
    """Per-turn facade over the same service/issuer and the shared application worker.

    SessionService has no cooperative cancellation seam once executing. A late begin can
    persist a pending original message; a late complete can persist its exact answer. This
    adapter never re-begins, invents a ticket or issues a substitute completion on timeout.
    """

    def __init__(
        self,
        service: SessionService,
        worker: BoundedServiceWorker,
        budget: TurnBudget,
        *,
        actions: ActionBridge | None = None,
        collection: CollectionBridge | None = None,
    ) -> None:
        if budget.clock is not monotonic:
            raise ValueError("SERVICE_BUDGET_REQUIRES_MONOTONIC_CLOCK")
        self._service, self._worker = service, worker
        if actions is not None and actions.sessions is not service:
            raise ValueError("ACTION_BRIDGE_REQUIRES_SAME_SESSION_SERVICE")
        self._actions = actions
        if collection is not None and collection.sessions is not service:
            raise ValueError("COLLECTION_BRIDGE_REQUIRES_SAME_SESSION_SERVICE")
        self._collection = collection
        self._deadline_at = budget.deadline_at
        self._read_seconds = budget.timeouts.read_seconds

    async def _call[T](self, call: Callable[[], T], *, persistence: bool = False) -> T:
        deadline = min(self._deadline_at, monotonic() + self._read_seconds)
        return await self._worker.run(call, deadline_at=deadline, persistence=persistence)

    def _action_bridge(self) -> ActionBridge:
        if self._actions is None:
            raise ApiFailure("UNSUPPORTED_STATE")
        return self._actions

    @staticmethod
    def _admission(admission: TurnAdmission) -> TurnAdmission:
        # Copy payloads, retain original process-local ticket/owner/generation authority.
        return replace(
            admission,
            session=SessionState.model_validate(admission.session.model_dump(mode="json")),
            request=MessageRequest.model_validate(admission.request.model_dump(mode="json")),
            result=None
            if admission.result is None
            else MessageResult.model_validate(admission.result.model_dump(mode="json")),
        )

    async def prepare_actions(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        requested: RequestedActions,
        resolved_ref: InventoryRef | None,
    ) -> PreparedActions:
        bridge, copied = self._action_bridge(), self._admission(admission)
        reference = (
            None
            if resolved_ref is None
            else InventoryRef.model_validate(resolved_ref.model_dump(mode="json"))
        )
        return await self._call(lambda: bridge.prepare(context, copied, requested, reference))

    def _collection_bridge(self) -> CollectionBridge:
        if self._collection is None:
            raise ApiFailure("UNSUPPORTED_STATE")
        return self._collection

    async def observe_collection(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
    ) -> CollectionObservation:
        bridge, copied = self._collection_bridge(), self._admission(admission)
        return await self._call(lambda: bridge.observe(context, copied))

    async def prepare_collection(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        observed: CollectionObservation,
        requested: CollectionRequest,
        resolved_ref: InventoryRef | None,
    ) -> CollectionPlan:
        bridge, copied = self._collection_bridge(), self._admission(admission)
        # These are detached data only: no ticket/capability/ORM object is copied.
        snapshot, language = deepcopy(observed), deepcopy(requested)
        reference = (
            None
            if resolved_ref is None
            else InventoryRef.model_validate(resolved_ref.model_dump(mode="json"))
        )
        return await self._call(
            lambda: bridge.prepare(context, copied, snapshot, language, reference)
        )

    async def complete_collection(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        plan: CollectionPlan,
    ) -> MessageResult:
        bridge, copied, copied_plan = (
            self._collection_bridge(),
            self._admission(admission),
            deepcopy(plan),
        )
        return await self._call(
            lambda: bridge.complete(context, copied, copied_plan), persistence=True
        )

    async def complete_actions(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        plan: PreparedActions,
        result: MessageResult,
        *,
        update: SessionContent | None = None,
    ) -> MessageResult:
        bridge, copied = self._action_bridge(), self._admission(admission)
        membership = plan.membership
        copied_plan = replace(
            plan,
            preference=None
            if plan.preference is None
            else PreferencesUpdate.model_validate(plan.preference.model_dump(mode="json")),
            membership=None
            if membership is None
            else ShortlistChange(
                ref=InventoryRef.model_validate(membership.ref.model_dump(mode="json")),
                command=MembershipRequest.model_validate(
                    membership.command.model_dump(mode="json")
                ),
                desired=membership.desired,
            ),
        )
        copied_result = MessageResult.model_validate(result.model_dump(mode="json"))
        copied_update = (
            None
            if update is None
            else SessionContent.model_validate(update.model_dump(mode="json"))
        )
        return await self._call(
            lambda: bridge.complete(
                context, copied, copied_plan, copied_result, update=copied_update
            ),
            persistence=True,
        )

    async def confirm_turn(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        request: MessageRequest,
    ) -> MessageResult:
        bridge = self._action_bridge()
        copied = MessageRequest.model_validate(request.model_dump(mode="json"))
        return await self._call(
            lambda: bridge.confirm(context, session_id, copied), persistence=True
        )

    async def recall_preferences(
        self,
        context: AuthorizedOwnerContext,
        session: SessionState,
    ) -> str:
        bridge = self._action_bridge()
        copied = SessionState.model_validate(session.model_dump(mode="json"))
        return await self._call(lambda: bridge.recall(context, copied))

    async def begin(
        self, context: AuthorizedOwnerContext, session_id: str, request: MessageRequest
    ) -> TurnAdmission:
        copied = MessageRequest.model_validate(request.model_dump(mode="json"))
        return await self._call(
            lambda: self._service.begin(context, session_id, copied), persistence=True
        )

    async def get(self, context: AuthorizedOwnerContext, session_id: str) -> SessionState:
        return await self._call(lambda: self._service.get(context, session_id))

    async def recent_context(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        *,
        before_revision: int,
    ) -> tuple[TranscriptTurn, ...]:
        return await self._call(
            lambda: self._service.recent_context(
                context,
                session_id,
                before_revision=before_revision,
            )
        )

    async def ordinal(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str, ordinal: int
    ) -> InventoryRef:
        return await self._call(
            lambda: self._service.ordinal(context, session_id, presentation_id, ordinal)
        )

    async def original_refs(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str
    ) -> tuple[InventoryRef, ...]:
        owned = await self._call(
            lambda: self._service.presentation_refs(context, session_id, presentation_id)
        )
        return tuple(InventoryRef.model_validate(ref.model_dump(mode="json")) for ref in owned.refs)

    async def complete(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
        result: MessageResult,
        *,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
    ) -> MessageResult:
        copied_result = MessageResult.model_validate(result.model_dump(mode="json"))
        copied_update = (
            None
            if update is None
            else SessionContent.model_validate(update.model_dump(mode="json"))
        )
        copied_proof = (
            None
            if presentation is None
            else PresentationProof.model_validate(presentation.model_dump(mode="json"))
        )
        copied_selection = (
            None
            if selection is None
            else InventoryRef.model_validate(selection.model_dump(mode="json"))
        )
        return await self._call(
            lambda: self._service.complete(
                context,
                ticket,
                copied_result,
                update=copied_update,
                presentation=copied_proof,
                selection=copied_selection,
            ),
            persistence=True,
        )


class InventoryServiceAdapter:
    """Use I6 public projections directly; never reconstruct or cache source facts."""

    def __init__(
        self,
        search: InventorySearchService,
        details: InventoryDetailsService,
        worker: BoundedServiceWorker,
    ) -> None:
        self._search, self._details, self._worker = search, details, worker

    async def search(self, request: SearchRequest, *, deadline_at: float) -> SearchResult:
        copied = SearchRequest.model_validate(request.model_dump(mode="json"))
        return await self._worker.run(
            lambda: self._search.search(copied, deadline_at=deadline_at), deadline_at=deadline_at
        )

    async def detail(self, ref: InventoryRef, *, deadline_at: float) -> ListingResult:
        copied = InventoryRef.model_validate(ref.model_dump(mode="json"))
        return await self._worker.run(
            lambda: self._details.lookup(copied, deadline_at=deadline_at), deadline_at=deadline_at
        )

    async def compare(self, request: ComparisonRequest, *, deadline_at: float) -> ComparisonResult:
        copied = ComparisonRequest.model_validate(request.model_dump(mode="json"))
        return await self._worker.run(
            lambda: self._details.compare(copied, deadline_at=deadline_at), deadline_at=deadline_at
        )

    async def original_batch(
        self, refs: tuple[InventoryRef, ...], *, deadline_at: float
    ) -> tuple[ListingResult, ...]:
        if type(refs) is not tuple or not 0 <= len(refs) <= 50:
            raise ApiFailure("VALIDATION_ERROR")
        copied = tuple(InventoryRef.model_validate(ref.model_dump(mode="json")) for ref in refs)
        return await self._worker.run(
            lambda: self._details.original_batch(copied, deadline_at=deadline_at),
            deadline_at=deadline_at,
        )


class AssistantService:
    """Unmounted composition. The application supplies and owns every concrete service."""

    def __init__(
        self,
        sessions: SessionService,
        provider: GeminiAdapter,
        search: InventorySearchService,
        details: InventoryDetailsService,
        worker: BoundedServiceWorker,
        *,
        preferences: PreferenceService | None = None,
        shortlist: ShortlistService | None = None,
        confirmation: ConfirmationParticipant | None = None,
        leads: LeadService | None = None,
        drafts: DraftService | None = None,
    ) -> None:
        self._sessions, self._provider, self._worker = sessions, provider, worker
        self._inventory = InventoryServiceAdapter(search, details, worker)
        if (leads is None) != (drafts is None):
            raise ValueError("COLLECTION_REQUIRES_BOTH_SHARED_DOMAIN_SERVICES")
        self._collection = (
            CollectionBridge(sessions, leads, drafts, drafts.rules)
            if leads is not None and drafts is not None
            else None
        )
        self._actions = (
            ActionBridge(
                sessions, preferences=preferences, shortlist=shortlist, confirmation=confirmation
            )
            if any(item is not None for item in (preferences, shortlist, confirmation))
            else None
        )

    async def run(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        request: MessageRequest,
        *,
        request_state: MutableMapping[str, Any],
        budget: TurnBudget,
        private_values: tuple[str, ...] = (),
    ) -> MessageResult:
        sessions = SessionServiceAdapter(
            self._sessions, self._worker, budget, actions=self._actions, collection=self._collection
        )
        coordinator = ReadCoordinator(
            sessions,
            self._provider,
            self._inventory,
            actions=sessions if self._actions is not None else None,
            collection=sessions if self._collection is not None else None,
        )
        return await coordinator.run(
            context,
            session_id,
            request,
            request_state=request_state,
            budget=budget,
            private_values=private_values,
        )
