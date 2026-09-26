"""Bounded reads and explicit actions over shared owned service boundaries."""

import re
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    ComparisonRequest,
    ComparisonResult,
    HandoffSummary,
    ListingDetail,
    ListingResult,
    ListingSummary,
    SearchCriteria,
    SearchRequest,
    SearchResult,
)
from app.api.schemas.sessions import (
    ClarificationIntent,
    MessageRequest,
    MessageResult,
    NoPendingIntent,
    SessionState,
    TranscriptTurn,
    UnresolvedOperationIntent,
    ViewingReviewIntent,
)
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.inventory.search_policy import normalize_criteria
from app.sessions.service import TurnAdmission
from app.sessions.state import SessionContent

from .action_bridge import ActionClarification, ActionPort, requested_actions
from .answer_assembly import (
    GroundedAnswer,
    assemble_comparison,
    assemble_handoff,
    assemble_search,
)
from .bounded_calls import CallGate
from .budget import BudgetExhausted, TurnBudget
from .collection_bridge import CollectionPort
from .collection_fields import CollectionFieldError, needs_local_private_reply
from .collection_language import CollectionLanguageError, parse_collection_request
from .collection_planner import (
    CollectionObservation,
    collection_result,
    matched_collection_question,
    unresolved_collection_plan,
)
from .conversation_read import retrieve_conversation_sources
from .explicit_field_read import explicit_field_read
from .grounding import GroundingError
from .intent import (
    Clarification,
    CriteriaTransition,
    QuestionRequest,
    ReferenceRequest,
    ResetPatch,
    TurnIntent,
    apply_intent,
    issue,
)
from .interpretation import interpret
from .output_policy import safe_assistant_text
from .provider import GeminiAdapter
from .read_ports import InventoryReadPort, SessionPort, UnconfiguredInventory
from .recalled_values import format_recalled_preferences
from .references import AmbiguousReference, ReferenceResolver, listing_ref, ref_key
from .request_policy import external_source_search, request_routing_eligible
from .result_analysis import analyze_results
from .scope import compose_scope

_LISTING: TypeAdapter[ListingResult] = TypeAdapter(ListingResult)
_SCOPE_CLAUSE = re.compile(
    r"(?:\s+and\s+|[;,]\s*)(?:please\s+)?(?:"
    r"write (?:me )?a poem|"
    r"(?:recommend|assess) (?:a |an )?(?:competitor|competing shopping service)|"
    r"(?:recommend|assess) (?:other|another) car[- ]shopping (?:site|website|service)s?|"
    r"guarantee (?:its |the )?condition"
    r")\s*[.!?]?\s*$",
    re.IGNORECASE,
)


class SearchCriteriaRejected(Exception):
    """I6 rejected normalization before any Inventory read was admitted."""


def _reference_request(request: MessageRequest) -> MessageRequest:
    """Remove only complete recognized trailing non-reference clauses from a read view.

    The original request remains the persistence/provider authority. Residual qualifiers,
    numerals and unknown clause words still reach the existing fail-closed reference guard.
    """
    text = request.text
    for _ in range(3):
        match = _SCOPE_CLAUSE.search(text)
        if match is None:
            break
        text = text[: match.start()]
    if text == request.text or not text.strip():
        return request
    return MessageRequest.model_validate({**request.model_dump(mode="json"), "text": text})


def _scope_topics(text: str, operation: str) -> tuple[str, ...]:
    """Conservative closed English cues; no source text, brand registry or factual authority."""
    topics: list[str] = []
    cues = (
        (
            "competitor",
            r"\b(?:competitors?|competing (?:shopping )?services?|"
            r"(?:other|another) car[- ]shopping (?:site|website|service)s?)\b",
        ),
        (
            "unrelated",
            r"\b(?:write (?:me )?a poem|weather forecast|solve (?:this )?equation|"
            r"ignore (?:all |the |your )?(?:rules|instructions))\b",
        ),
        (
            "unverified_vehicle_claim",
            r"\b(?:accident[- ]free|guaranteed reliable|"
            r"guarantee (?:its |the )?condition)\b",
        ),
        (
            "cash_price",
            r"\b(?:what (?:is|does)|explain)\b.{0,35}\bcash (?:price|asking price)\b",
        ),
        ("mileage", r"\b(?:what (?:is|does)|explain)\b.{0,35}\b(?:mileage|odometer)\b"),
        ("warranty", r"\b(?:what (?:is|does)|explain)\b.{0,35}\bwarranty\b"),
        ("evidence", r"\b(?:what (?:is|does)|explain)\b.{0,35}\b(?:evidence|conflicting)\b"),
    )
    for topic, pattern in cues:
        if re.search(pattern, text, re.IGNORECASE):
            topics.append(topic)
    if not topics and operation == "smalltalk":
        topics.append("greeting" if re.match(r"\s*(?:hello|hi|hey)\b", text, re.I) else "help")
    elif not topics and operation == "unsupported":
        topics.append("unrelated")
    return tuple(topics[:3])


def _mixed_selected_read(
    intent: TurnIntent,
    request: MessageRequest,
    session: SessionState,
    *,
    collection_active: bool,
) -> TurnIntent:
    """Keep an explicit UI car read when only a recognized trailing scope clause conflicts."""
    if (
        intent.patches
        or request.selected_ref is None
        or not request_routing_eligible(
            intent,
            request,
            session,
            collection_active=collection_active,
        )
    ):
        return intent
    read = _reference_request(request)
    if read is request:
        return intent
    match = re.fullmatch(
        r"[ ]*show[ ]+(?:me[ ]+)?(?:details[ ]+(?:of|for)[ ]+)?"
        r"(?P<reference>this[ ]+(?:car|listing))[ ]*[.!?]?[ ]*",
        read.text,
        re.IGNORECASE | re.ASCII,
    )
    if match is None:
        return intent
    return TurnIntent(
        operation="detail",
        references=[
            ReferenceRequest(
                source="request",
                quote=match.group("reference"),
            )
        ],
    )


def _apply_answer(result: MessageResult, answer: GroundedAnswer, topics: tuple[str, ...]) -> None:
    composed = compose_scope(answer, topics=topics)
    # Reserve room for fixed hypothetical/action notices without truncating a fact/conflict.
    if len(composed.text) > 11500:
        raise GroundingError("ANSWER_LIMIT")
    result.text, result.evidence = composed.text, list(composed.evidence)
    if composed.handoff_summary is not None:
        result.handoff_summary = composed.handoff_summary


def _content(session: SessionState, criteria: SearchCriteria) -> SessionContent:
    return SessionContent(
        criteria=criteria,
        selected_ref=session.selected_ref,
        active_presentation_id=session.active_presentation_id,
        current_draft_id=session.current_draft_id,
        pending_intent=session.pending_intent,
    )


def _result(admission: TurnAdmission, *, text: str, provider: bool = False) -> MessageResult:
    return MessageResult(
        client_message_id=admission.request.client_message_id,
        session_id=admission.session.session_id,
        turn_revision=admission.session.revision,
        current_revision=admission.session.revision,
        state="answered",
        text=text,
        pending_intent=admission.session.pending_intent,
        persistence="not_saved",
        provider_state="available" if provider else "not_used",
    )


class ReadCoordinator:
    """Bind trusted authorization and original-turn persistence through injected facades.

    Concrete service adapters are injected; no default Store or HTTP route is created here.
    Model-requested reads share at most four tool admissions. Begin/get/complete are fixed
    lifecycle steps, timed by the same ledger, not model tools or domain-write permission.
    """

    def __init__(
        self,
        sessions: SessionPort,
        provider: GeminiAdapter,
        inventory: InventoryReadPort | None = None,
        *,
        actions: ActionPort | None = None,
        collection: CollectionPort | None = None,
    ) -> None:
        self.sessions, self.provider = sessions, provider
        self.actions = actions
        self.collection = collection
        self.inventory = inventory if inventory is not None else UnconfiguredInventory()
        self._gate = CallGate()

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
        result = await self._run(
            context,
            session_id,
            request,
            request_state=request_state,
            budget=budget,
            private_values=private_values,
        )
        # Covers completed replays and action/collection delegates as well as read turns.
        return result.model_copy(update={"text": safe_assistant_text(result.text)})

    async def _run(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        request: MessageRequest,
        *,
        request_state: MutableMapping[str, Any],
        budget: TurnBudget,
        private_values: tuple[str, ...] = (),
    ) -> MessageResult:
        request = MessageRequest.model_validate(request.model_dump(mode="json"))
        if not request.text.strip():
            raise ApiFailure("VALIDATION_ERROR")
        if request.explicit_confirmation is not None:
            actions = self.actions
            if actions is None:
                raise ApiFailure("UNSUPPORTED_STATE")
            # Preserve reviewed R. The shared wrapper owns admission, effects and receipt.
            return await self._gate.run(
                lambda: actions.confirm_turn(context, session_id, request),
                budget,
                persistence=True,
            )
        admission = await self._gate.run(
            lambda: self.sessions.begin(context, session_id, request),
            budget,
            persistence=True,
        )
        if admission.status == "completed":
            if admission.result is None:
                raise ApiFailure("INTERNAL_ERROR")
            return admission.result
        if admission.status in {"pending", "interrupted"}:
            raise ApiFailure(
                "OPERATION_UNRESOLVED" if admission.status == "pending" else "UNSUPPORTED_STATE"
            )
        if admission.ticket is None:
            raise ApiFailure("INTERNAL_ERROR")
        # Use the service's validated original request, never a later mutable caller object.
        request, session = admission.request, admission.session
        reply_to = None
        if request.clarification_reply is not None:
            pending, reply = session.pending_intent, request.clarification_reply
            if not isinstance(pending, ClarificationIntent) or (
                pending.intent_id != reply.intent_id
                or pending.created_revision != reply.created_revision
            ):
                # A mismatched/consumed question violates the trusted P9C facade contract.
                raise ApiFailure("UNSUPPORTED_STATE")
            reply_to = pending
        if needs_local_private_reply(request.text, private_values):
            result = _result(
                admission,
                text=(
                    "Keep optional contact details and private documents out of chat. "
                    "Use the local enquiry form for contact details. "
                    "Your preparation and saved values "
                    "have not been changed; contact is optional."
                ),
            )
            return await self._complete(context, admission, result, budget)
        observed = None
        collection_summary = None
        collection_port = self.collection
        if collection_port is not None:
            observed = await self._gate.run(
                lambda: collection_port.observe_collection(context, admission),
                budget,
            )
            stored = observed.snapshot.collection
            if stored is not None and not observed.snapshot.expired:
                collection_summary = (
                    f"Active collection: {stored.purpose}; "
                    f"date {'set' if stored.values.local_date else 'missing'}; "
                    f"time {'set' if stored.values.local_time else 'missing'}."
                )
        recent_turns = await self._gate.run(
            lambda: self.sessions.recent_context(
                context,
                session_id,
                before_revision=session.revision,
            ),
            budget,
        )
        prior_request = ""
        if reply_to is not None:
            for previous in recent_turns:
                answered = previous.assistant_result
                if answered is not None and answered.pending_intent == reply_to:
                    prior_request = previous.user_text
                    break
        proposal = await interpret(
            self.provider,
            request,
            session,
            request_state,
            budget,
            private_values,
            collection_summary=collection_summary,
            recent_turns=recent_turns,
        )
        latest = await self._gate.run(lambda: self.sessions.get(context, session_id), budget)
        if latest.revision != session.revision:
            result = _result(
                admission, text="This earlier turn was superseded by newer session input."
            )
            result.state, result.current_revision = "superseded", latest.revision
            result.provider_state = proposal.state
            return await self._complete(context, admission, result, budget)
        if proposal.proposal is None:
            result = _result(
                admission,
                text=(
                    "Assistant interpretation is unavailable. Your accepted criteria are unchanged."
                ),
            )
            result.state, result.provider_state = "provider_unavailable", "unavailable"
            if reply_to is not None:
                result.text = "Assistant interpretation is unavailable. " + reply_to.question
            # P9C retains the exact question. Failure must neither clear nor replace it.
            return await self._complete(context, admission, result, budget)
        intent = proposal.proposal
        if proposal.state == "available":
            collection_active = observed is not None and (
                observed.snapshot.collection is not None
                or observed.snapshot.unresolved is not None
                or observed.draft is not None
            )
            if external_source_search(
                intent,
                request,
                session,
                collection_active=collection_active,
            ):
                result = _result(
                    admission,
                    text=compose_scope(topics=("unrelated",)).text,
                    provider=True,
                )
                return await self._complete(context, admission, result, budget)
            intent = _mixed_selected_read(
                intent,
                request,
                session,
                collection_active=collection_active,
            )
            intent = explicit_field_read(
                intent,
                request,
                session,
                collection_active=collection_active,
            )
        # A deferred action must not consume a supported read. Explicit collection
        # proposals still require the separate whole-message collection validation.
        if (
            reply_to is not None
            and reply_to.purpose == "search_criteria"
            and intent.collection is not None
        ):
            # A search reply never enters enquiry/viewing validation or mutates its state.
            result = _result(admission, text=reply_to.question, provider=True)
            result.state = "clarification"
            return await self._complete(context, admission, result, budget)
        if intent.collection is not None or (
            intent.operation not in {"search", "detail", "compare", "analyze", "question"}
            and set(intent.deferred).intersection({"viewing", "lead"})
        ):
            return await self._collection_turn(context, admission, intent, observed, budget)
        if set(intent.deferred).intersection({"preferences", "shortlist"}):
            return await self._action_turn(context, admission, intent, budget)
        if (
            intent.operation == "smalltalk"
            and intent.scope == "session"
            and not intent.patches
            and not intent.references
            and not intent.deferred
            and intent.problem is None
            and not collection_summary
            and _scope_topics(request.text, intent.operation) in {("greeting",), ("help",)}
            and (
                observed is None
                or (
                    observed.snapshot.collection is None
                    and observed.snapshot.unresolved is None
                    and observed.draft is None
                )
            )
        ):
            # Replace the generic social/help fallback with a conversational
            # answer. Retain explicit scope refusals and sourced term guidance.
            # This route needs application context, not inventory or an action.
            intent = intent.model_copy(update={
                "operation": "question", "question": QuestionRequest(source="application")
            })
        recall_only = (
            intent.operation == "return"
            and intent.scope == "session"
            and not intent.patches
            and not intent.references
            and not intent.deferred
            and intent.problem is None
        )
        transition = (
            CriteriaTransition(session.criteria, session.criteria, None)
            if recall_only or (intent.operation == "question" and not intent.patches)
            else apply_intent(
                session.criteria,
                intent,
                request.text,
                clarification_targets=tuple(reply_to.targets)
                if reply_to is not None and reply_to.purpose == "search_criteria"
                else (),
                prior_request=prior_request,
            )
        )
        update = _content(session, transition.retained)
        result = _result(admission, text="No domain action has been performed.", provider=True)
        if reply_to is not None and reply_to.purpose != "search_criteria":
            reference_reply = reply_to.purpose == "listing_reference" and (
                intent.operation in {"detail", "compare"}
                and bool(intent.references)
                or intent.operation == "analyze"
                and intent.analysis is not None
                and intent.analysis.scope == "shown"
            )
            independent_analysis = intent.operation in {"analyze", "question"}
            if not reference_reply and not independent_analysis:
                result.state, result.text = "clarification", reply_to.question
                return await self._complete(context, admission, result, budget, update=update)
        if (
            reply_to is not None
            and reply_to.purpose == "search_criteria"
            and intent.operation not in {"analyze", "question"}
        ):
            touched = {patch.field for patch in intent.patches if not isinstance(patch, ResetPatch)}
            if (
                transition.clarification is not None
                or intent.operation != "search"
                or (
                    not set(reply_to.targets) <= touched
                    and not any(isinstance(patch, ResetPatch) for patch in intent.patches)
                )
            ):
                result.state, result.text = "clarification", reply_to.question
                return await self._complete(context, admission, result, budget, update=update)
        # P9C retains the question through admission. Only the validated matched reply
        # bypasses this guard; an ordinary turn cannot skip an unresolved hard condition.
        pending = session.pending_intent
        reset = any(isinstance(patch, ResetPatch) for patch in intent.patches)
        if isinstance(pending, ClarificationIntent) and reply_to is None:
            if reset and transition.clarification is None and pending.purpose == "search_criteria":
                update = SessionContent.model_validate(
                    {
                        **update.model_dump(mode="json"),
                        "pending_intent": NoPendingIntent(kind="none").model_dump(mode="json"),
                    }
                )
                result.pending_intent = update.pending_intent
            elif (
                intent.operation in {"search", "detail", "compare"}
                and pending.purpose == "search_criteria"
            ) or (
                intent.operation in {"detail", "compare"} and pending.purpose == "listing_reference"
            ):
                result.state, result.text = "clarification", pending.question
                return await self._complete(context, admission, result, budget, update=update)
        if transition.clarification is not None:
            update = self._clarification(result, update, transition.clarification)
            return await self._complete(context, admission, result, budget, update=update)
        selection = None
        read_completed = False
        try:
            selection = await self._read(
                context,
                admission,
                intent,
                transition.effective,
                result,
                budget,
                recent_turns=recent_turns,
                request_state=request_state,
                private_values=private_values,
            )
            read_completed = True
        except AmbiguousReference:
            update = self._clarification(result, update, issue("selected_ref", "reference"))
        except SearchCriteriaRejected:
            # Do not persist criteria that the real search contract rejected. A matched
            # reply still owns its exact retained question until a supported read resolves it.
            update = _content(session, session.criteria)
            if isinstance(session.pending_intent, ClarificationIntent):
                result.state, result.text = "clarification", session.pending_intent.question
                result.pending_intent = session.pending_intent
            else:
                patches = [patch for patch in intent.patches if not isinstance(patch, ResetPatch)]
                problem = issue(patches[0].field) if len(patches) == 1 else issue("query")
                update = self._clarification(result, update, problem)
        except (ValidationError, GroundingError):
            result.search, result.comparison, result.handoff_summary = None, None, None
            result.evidence = []
            result.text = (
                "The inventory response could not be verified. "
                "This does not mean there are no matching cars."
            )
        except BudgetExhausted:
            result.text = (
                "This turn reached its bounded read limit. "
                "Please narrow the requested comparison or reference."
            )
        except ApiFailure as error:
            if error.code in {"NOT_FOUND", "PRESENTATION_INVALID", "SNAPSHOT_STALE"}:
                update = self._clarification(result, update, issue("selected_ref", "reference"))
            elif error.code in {
                "STORE_UNAVAILABLE",
                "STORE_BUSY",
                "INTERNAL_ERROR",
                "PROVIDER_TIMEOUT",
            }:
                result.text = (
                    "The inventory read is unavailable. This does not mean there are no "
                    "matching cars; no hard criteria were relaxed."
                )
            else:
                raise
        if (
            reply_to is not None
            and read_completed
            and intent.scope == "session"
            and not (
                intent.operation in {"analyze", "question"}
                and (
                    reply_to.purpose != "listing_reference"
                    or intent.analysis is None
                    or intent.analysis.scope != "shown"
                )
            )
        ):
            # The successful matched read resolves its question only in this ticket's
            # completion. A cancelled/late/unavailable turn leaves retained authority.
            update = SessionContent.model_validate(
                {
                    **update.model_dump(mode="json"),
                    "pending_intent": {"kind": "none"},
                }
            )
            result.pending_intent = update.pending_intent
        if (
            intent.operation == "question"
            and read_completed
            and result.state == "answered"
            and isinstance(session.pending_intent, ClarificationIntent)
            and session.pending_intent.purpose in {"search_criteria", "listing_reference"}
        ):
            # A self-contained answered question replaces a stale read clarification;
            # it never dismisses an action review or changes accepted search filters.
            update = update.model_copy(update={"pending_intent": NoPendingIntent(kind="none")})
            result.pending_intent = update.pending_intent
        if intent.scope == "hypothetical":
            selection = None
            result.text += (
                " These hypothetical criteria have not replaced your accepted search criteria."
            )
        if intent.deferred:
            notice = (
                "Use the current viewing review to submit its explicit confirmation. "
                "This message has not confirmed it."
                if isinstance(session.pending_intent, ViewingReviewIntent)
                else "Check the existing operation status before requesting another action."
                if isinstance(session.pending_intent, UnresolvedOperationIntent)
                else "Continue through the shared viewing/enquiry details and review flow. "
                "No preference, shortlist, enquiry or viewing action was executed."
            )
            problem = Clarification(
                "confirmation",
                notice,
            )
            if result.state != "clarification":
                supported_text = result.text
                update = self._clarification(result, update, problem)
                result.text = supported_text + "\n" + result.text
            else:
                result.text += " No requested domain action was executed."
        if isinstance(session.pending_intent, ViewingReviewIntent | UnresolvedOperationIntent):
            # Preserve an in-progress exact action's car as well as its pending intent.
            selection = None
        return await self._complete(
            context, admission, result, budget, update=update, selection=selection
        )

    async def _collection_turn(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        intent: TurnIntent,
        observed: CollectionObservation | None,
        budget: TurnBudget,
    ) -> MessageResult:
        port = self.collection
        if port is None or observed is None:
            result = collection_result(
                admission,
                "Conversational enquiry preparation is unavailable in this composition; "
                "no action was taken.",
            )
            return await self._complete(context, admission, result, budget)
        if observed.snapshot.unresolved is not None:
            plan = unresolved_collection_plan(admission, observed, provider=True)
            plan.result.text = safe_assistant_text(plan.result.text)
            return await self._gate.run(
                lambda: port.complete_collection(context, admission, plan),
                budget,
                persistence=True,
            )
        try:
            requested = parse_collection_request(
                admission.request.text,
                intent,
                matched_question=matched_collection_question(admission, observed),
            )
            resolved = None
            if requested.reference is not None:
                # Whole-message grammar already accounted for every command/field clause.
                narrowed = MessageRequest.model_validate(
                    {
                        **admission.request.model_dump(mode="json"),
                        "text": requested.reference.quote,
                    }
                )
                resolver = ReferenceResolver(
                    self.sessions,
                    self.inventory,
                    self._gate,
                    context,
                    admission.session,
                    narrowed,
                    budget,
                    [requested.reference],
                )
                resolved = await resolver.resolve(requested.reference)
            plan = await self._gate.run(
                lambda: port.prepare_collection(context, admission, observed, requested, resolved),
                budget,
                tool=True,
            )
        except (
            CollectionLanguageError,
            CollectionFieldError,
            AmbiguousReference,
            ValidationError,
        ) as error:
            # Only extraction/pure planning is in this catch; no participant has been entered.
            text = (
                str(error)
                if isinstance(error, CollectionLanguageError)
                else (
                    "State the exact car, a complete Dubai date/time, or supported cash budget and "
                    "quoted requirements. The earlier preparation is unchanged."
                )
            )
            pending = admission.session.pending_intent
            if isinstance(pending, ClarificationIntent):
                text += " " + pending.question
            result = collection_result(admission, text)
            result.state = "clarification"
            return await self._complete(context, admission, result, budget)
        # Unknown/postmutation failures propagate; the bridge never rewrites success text.
        plan.result.text = safe_assistant_text(plan.result.text)
        return await self._gate.run(
            lambda: port.complete_collection(context, admission, plan),
            budget,
            persistence=True,
        )

    async def _action_turn(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        intent: TurnIntent,
        budget: TurnBudget,
    ) -> MessageResult:
        result = _result(
            admission, text="The requested action is awaiting completion.", provider=True
        )
        update = _content(admission.session, admission.session.criteria)
        actions = self.actions
        pending, reply = admission.session.pending_intent, admission.request.clarification_reply
        if isinstance(pending, ClarificationIntent) and not (
            pending.purpose in {"action_intent", "listing_reference"}
            and reply is not None
            and (reply.intent_id, reply.created_revision)
            == (pending.intent_id, pending.created_revision)
        ):
            # An unsupported action cannot replace an unresolved hard criteria question.
            result.state, result.text = "clarification", pending.question
            return await self._complete(context, admission, result, budget, update=update)
        try:
            requested = requested_actions(admission, intent)
            if requested is None or actions is None:
                raise ActionClarification(
                    "This action is not available in the current composition."
                )
            resolved = None
            if requested.reference is not None:
                # The complete action grammar has validated every original-message clause.
                # Only its exact reference phrase is a read view; persistence keeps the original.
                reference_request = MessageRequest.model_validate(
                    {**admission.request.model_dump(mode="json"), "text": requested.reference.quote}
                )
                resolver = ReferenceResolver(
                    self.sessions,
                    self.inventory,
                    self._gate,
                    context,
                    admission.session,
                    reference_request,
                    budget,
                    [requested.reference],
                )
                resolved = await resolver.resolve(requested.reference)
            plan = await self._gate.run(
                lambda: actions.prepare_actions(context, admission, requested, resolved),
                budget,
                tool=True,
            )
        except ActionClarification as error:
            if isinstance(pending, ClarificationIntent):
                result.state, result.text = "clarification", pending.question
                return await self._complete(context, admission, result, budget, update=update)
            update = self._clarification(result, update, error.problem)
            return await self._complete(context, admission, result, budget, update=update)
        except AmbiguousReference:
            if isinstance(pending, ClarificationIntent):
                result.state, result.text = "clarification", pending.question
                return await self._complete(context, admission, result, budget, update=update)
            update = self._clarification(result, update, issue("selected_ref", "reference"))
            return await self._complete(context, admission, result, budget, update=update)
        # Only a supported, matched action/listing clarification reaches this point.
        update = SessionContent.model_validate(
            {**update.model_dump(mode="json"), "pending_intent": {"kind": "none"}}
        )
        result.pending_intent = update.pending_intent
        # No domain mutation precedes this completion, and no receipt is rewritten afterward.
        return await self._gate.run(
            lambda: actions.complete_actions(context, admission, plan, result, update=update),
            budget,
            persistence=True,
        )

    @staticmethod
    def _clarification(
        result: MessageResult, update: SessionContent, problem: Clarification
    ) -> SessionContent:
        target = problem.target
        purpose: Literal["listing_reference", "action_intent", "viewing_details", "search_criteria"]
        if target == "selected_ref":
            purpose = "listing_reference"
        elif target in {"preference_scope", "confirmation"}:
            purpose = "action_intent"
        elif target == "appointment":
            purpose = "viewing_details"
        else:
            purpose = "search_criteria"
        pending = update.pending_intent
        if not isinstance(pending, ViewingReviewIntent | UnresolvedOperationIntent):
            pending = ClarificationIntent(
                kind="clarification",
                intent_id=str(uuid4()),
                created_revision=result.turn_revision,
                purpose=purpose,
                targets=[target],
                question=problem.question,
            )
        result.state, result.text, result.pending_intent = (
            "clarification",
            problem.question,
            pending,
        )
        return SessionContent.model_validate(
            {**update.model_dump(mode="json"), "pending_intent": pending.model_dump(mode="json")}
        )

    async def _read(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        intent: TurnIntent,
        criteria: SearchCriteria,
        result: MessageResult,
        budget: TurnBudget,
        *,
        recent_turns: tuple[TranscriptTurn, ...] = (),
        request_state: MutableMapping[str, Any] | None = None,
        private_values: tuple[str, ...] = (),
    ) -> InventoryRef | None:
        topics = _scope_topics(admission.request.text, intent.operation)

        def deadline() -> float:
            return min(budget.deadline_at, budget.clock() + 2)

        if intent.operation == "question":
            if intent.collection or intent.deferred:
                raise GroundingError("QUESTION_CANNOT_EXECUTE_ACTION")
            question = intent.question or QuestionRequest(source="inventory")
            sources = await retrieve_conversation_sources(
                question,
                context=context,
                session=admission.session,
                request=admission.request,
                criteria=criteria,
                sessions=self.sessions,
                inventory=self.inventory,
                gate=self._gate,
                budget=budget,
                recent_turns=recent_turns,
            )
            from .grounded_conversation import compose_grounded_answer

            answer = await compose_grounded_answer(
                self.provider,
                admission.request,
                admission.session,
                recent_turns,
                sources.rows,
                scope=sources.scope,
                complete=sources.complete,
                total=sources.total,
                context_note=sources.note,
                request_state=request_state,
                budget=budget,
                private_values=private_values,
            )
            if answer is None:
                result.state, result.provider_state = "provider_unavailable", "unavailable"
                result.text = (
                    "I couldn't finish this answer right now. Your conversation is saved; "
                    "please try again. You can still browse the cars and their listing details."
                )
            else:
                _apply_answer(result, answer, ())
            return None

        if intent.operation == "analyze":
            analysis = intent.analysis
            if (
                analysis is None
                or analysis.quote not in admission.request.text
                or intent.references
                or intent.collection
                or intent.deferred
            ):
                raise AmbiguousReference
            items: tuple[ListingResult | ListingSummary, ...]
            if analysis.scope == "shown":
                presentation = admission.session.active_presentation_id
                if presentation is None or intent.patches:
                    raise AmbiguousReference
                refs = await self._gate.run(
                    lambda: self.sessions.original_refs(
                        context, admission.session.session_id, presentation
                    ),
                    budget,
                    tool=True,
                )
                items = await self._gate.run(
                    lambda: self.inventory.original_batch(refs, deadline_at=deadline()),
                    budget,
                    tool=True,
                )
                label, complete = "the cars I showed you", True
            else:
                if analysis.scope == "inventory" and intent.patches:
                    raise AmbiguousReference
                requested = SearchCriteria() if analysis.scope == "inventory" else criteria
                normalized = normalize_criteria(requested).criteria
                found_items: list[ListingSummary] = []
                cursor = None
                snapshot = None
                total = None
                complete = False
                for _ in range(4):
                    query = SearchRequest(
                        **normalized.model_dump(mode="json"),
                        page_size=50,
                        cursor=cursor,
                        snapshot_id=snapshot,
                        client_request_id=admission.request.client_message_id,
                    )
                    found = await self._gate.run(
                        lambda query=query: self.inventory.search(query, deadline_at=deadline()),
                        budget,
                        tool=True,
                    )
                    found = SearchResult.model_validate(found.model_dump(mode="json"))
                    if (
                        found.applied_criteria != normalized
                        or found.client_request_id != query.client_request_id
                    ):
                        raise GroundingError("ANALYSIS_CRITERIA_MISMATCH")
                    if total is not None and (
                        total != found.supported_total or snapshot != found.presentation.snapshot_id
                    ):
                        raise GroundingError("ANALYSIS_SNAPSHOT_CHANGED")
                    total, snapshot = found.supported_total, found.presentation.snapshot_id
                    found_items.extend(found.items)
                    cursor = found.next_cursor
                    if cursor is None:
                        complete = len(found_items) == total
                        break
                items = tuple(found_items)
                refs = tuple(item.ref for item in found_items)
                label = (
                    "the full supplied inventory"
                    if analysis.scope == "inventory"
                    else "your matching cars"
                )
            answer = analyze_results(
                items,
                expected_refs=refs,
                field=analysis.field,
                operation=analysis.operation,
                scope_label=label,
                complete_scope=complete,
            )
            _apply_answer(result, answer.answer, topics)
            return (
                answer.selected_refs[0]
                if (
                    analysis.scope == "shown"
                    and analysis.operation != "count_known"
                    and len(answer.selected_refs) == 1
                )
                else None
            )
        if intent.operation == "search":
            try:
                search_criteria = normalize_criteria(criteria).criteria
            except ApiFailure as error:
                if error.code != "VALIDATION_ERROR":
                    raise
                raise SearchCriteriaRejected from None
            request = SearchRequest(
                **search_criteria.model_dump(mode="json"),
                client_request_id=admission.request.client_message_id,
            )
            found = await self._gate.run(
                lambda: self.inventory.search(request, deadline_at=deadline()), budget, tool=True
            )
            found = SearchResult.model_validate(found.model_dump(mode="json"))
            if (
                found.applied_criteria != search_criteria
                or found.client_request_id != request.client_request_id
            ):
                raise ApiFailure("INTERNAL_ERROR")
            _apply_answer(result, assemble_search(found, request=request), topics)
            result.search = found
            return None
        if intent.operation in {"detail", "compare"}:
            if (
                len(intent.references) != 1
                and intent.operation == "detail"
                or intent.operation == "compare"
                and not 2 <= len(intent.references) <= 3
            ):
                raise AmbiguousReference
            resolver = ReferenceResolver(
                self.sessions,
                self.inventory,
                self._gate,
                context,
                admission.session,
                _reference_request(admission.request),
                budget,
                intent.references,
            )
            refs = [await resolver.resolve(reference) for reference in intent.references]
            if len({ref_key(ref) for ref in refs}) != len(refs):
                raise AmbiguousReference
            if intent.operation == "compare":
                comparison_request = ComparisonRequest(refs=refs)
                compared = await self._gate.run(
                    lambda: self.inventory.compare(comparison_request, deadline_at=deadline()),
                    budget,
                    tool=True,
                )
                compared = ComparisonResult.model_validate(compared.model_dump(mode="json"))
                if [ref_key(listing_ref(item)) for item in compared.items] != [
                    ref_key(ref) for ref in refs
                ]:
                    raise ApiFailure("INTERNAL_ERROR")
                _apply_answer(
                    result, assemble_comparison(compared, request=comparison_request), topics
                )
                result.comparison = compared
                return None
            detail = await self._gate.run(
                lambda: self.inventory.detail(refs[0], deadline_at=deadline()), budget, tool=True
            )
            detail = _LISTING.validate_python(detail.model_dump(mode="json"))
            if ref_key(listing_ref(detail)) != ref_key(refs[0]):
                raise ApiFailure("INTERNAL_ERROR")
            handoff = HandoffSummary(
                selected_ref=refs[0],
                listing=detail,
                expressed_criteria=criteria,
                fit_reasons=[],
                unresolved_questions=[],
            )
            _apply_answer(
                result,
                assemble_handoff(handoff, expected_ref=refs[0], criteria=criteria),
                topics,
            )
            return (
                refs[0] if isinstance(detail, ListingDetail) and detail.state == "current" else None
            )
        if intent.operation == "return":
            actions = self.actions
            if actions is not None:
                result.text = await self._gate.run(
                    lambda: actions.recall_preferences(context, admission.session),
                    budget,
                    tool=True,
                )
            else:
                result.text = format_recalled_preferences(
                    admission.session.recalled_preferences,
                    session_id=admission.session.session_id,
                    criteria=admission.session.criteria,
                    now=datetime.now(UTC).isoformat(),
                )
        else:
            result.text = compose_scope(topics=topics).text
        return None

    async def _complete(
        self,
        context: AuthorizedOwnerContext,
        admission: TurnAdmission,
        result: MessageResult,
        budget: TurnBudget,
        *,
        update: SessionContent | None = None,
        selection: InventoryRef | None = None,
    ) -> MessageResult:
        ticket = admission.ticket
        if ticket is None:
            raise ApiFailure("INTERNAL_ERROR")
        result.text = safe_assistant_text(result.text)
        # No register/select-before-complete: P9 commits the signed search presentation and
        # exact selection with this ticket, so the turn cannot supersede its own read.
        return await self._gate.run(
            lambda: self.sessions.complete(
                context,
                ticket,
                result,
                update=update,
                presentation=None if result.search is None else result.search.presentation,
                selection=selection,
            ),
            budget,
            persistence=True,
        )
