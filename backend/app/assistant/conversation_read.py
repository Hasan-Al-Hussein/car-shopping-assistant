"""Bounded, source-bound retrieval for open-ended conversational questions."""

from dataclasses import dataclass

from app.api.schemas.inventory import (
    ListingDetail,
    ListingSummary,
    SearchCriteria,
    SearchRequest,
    SearchResult,
)
from app.api.schemas.sessions import MessageRequest, SessionState, TranscriptTurn
from app.identity.authorization import AuthorizedOwnerContext
from app.inventory.search_policy import normalize_criteria

from .bounded_calls import CallGate
from .budget import TurnBudget
from .grounding import GroundingError, key
from .intent import QuestionRequest
from .read_ports import InventoryReadPort, SessionPort
from .references import AmbiguousReference


@dataclass(frozen=True)
class ConversationSources:
    rows: tuple[ListingSummary | ListingDetail, ...]
    scope: str
    complete: bool
    total: int | None
    note: str = ""


APP_FACTS = (
    "This app searches the supplied car inventory, displays original listing details, "
    "compares up to three cars, and keeps a shortlist. It supports conversation history "
    "and explicitly saved preferences across sessions. Viewing/test-drive bookings are "
    "simulated, Monday to Saturday 08:00–20:00 Dubai time, with a review before confirmation. "
    "Enquiries collect the buyer's budget and needs and save qualified leads to a local CSV. "
    "Contact details are optional and entered in the local enquiry form, not chat. "
    "There is no verified live stock, inspection, finance approval or real seller booking."
)


async def retrieve_conversation_sources(
    question: QuestionRequest,
    *,
    context: AuthorizedOwnerContext,
    session: SessionState,
    request: MessageRequest,
    criteria: SearchCriteria,
    sessions: SessionPort,
    inventory: InventoryReadPort,
    gate: CallGate,
    budget: TurnBudget,
    recent_turns: tuple[TranscriptTurn, ...] = (),
) -> ConversationSources:
    def deadline() -> float:
        return min(budget.deadline_at, budget.clock() + 5)

    source = question.source
    context_note = ""
    if source == "application":
        return ConversationSources((), "application", True, None, APP_FACTS)
    if source in {"shown", "selected"}:
        # Public citations can contain truncated aggregate evidence, not a displayed set.
        # Re-read the complete inventory and use history to resolve natural-answer followups.
        latest_answer = next(
            (
                turn.assistant_result
                for turn in reversed(recent_turns)
                if turn.assistant_result is not None and turn.assistant_result.state == "answered"
            ),
            None,
        )
        natural_answer = latest_answer is not None and latest_answer.search is None
        if natural_answer and request.selected_ref is None:
            recovered = await retrieve_conversation_sources(
                question.model_copy(update={"source": "inventory"}), context=context,
                session=session, request=request, criteria=criteria, sessions=sessions,
                inventory=inventory, gate=gate, budget=budget, recent_turns=recent_turns,
            )
            return ConversationSources(recovered.rows, "inventory", recovered.complete,
                                       recovered.total, "Use the conversation to resolve the cars "
                                       "being discussed. This corpus includes the full inventory, "
                                       "not just those cars. Do not substitute an unrelated car.")
        if source == "selected":
            selected = request.selected_ref or session.selected_ref
            if selected is None:
                raise AmbiguousReference
            else:
                refs = (selected,)
        else:
            if session.active_presentation_id is None:
                raise AmbiguousReference
            else:
                refs = await gate.run(
                    lambda: sessions.original_refs(
                        context, session.session_id, session.active_presentation_id
                    ),
                    budget,
                    tool=True,
                )
        details = await gate.run(
            lambda: inventory.original_batch(refs, deadline_at=deadline()),
            budget,
            tool=True,
        )
        if len(details) != len(refs):
            raise GroundingError("CONVERSATION_REFERENCE_COUNT")
        rows = []
        for ref, detail in zip(refs, details, strict=True):
            actual_ref = detail.listing.ref if isinstance(detail, ListingDetail) else detail.ref
            if key(ref) != key(actual_ref):
                raise GroundingError("CONVERSATION_REFERENCE_MISMATCH")
            if isinstance(detail, ListingDetail):
                rows.append(detail)
        return ConversationSources(
            tuple(rows),
            source,
            len(rows) == len(refs),
            len(refs),
            context_note,
        )

    normalized = normalize_criteria(
        SearchCriteria() if source == "inventory" else criteria
    ).criteria
    summaries: list[ListingSummary] = []
    cursor = None
    snapshot = None
    total = None
    complete = False
    for _ in range(2):
        query = SearchRequest(
            **normalized.model_dump(mode="json"),
            page_size=50,
            cursor=cursor,
            snapshot_id=snapshot,
            client_request_id=request.client_message_id,
        )
        found = await gate.run(
            lambda query=query: inventory.search(query, deadline_at=deadline()), budget, tool=True
        )
        found = SearchResult.model_validate(found.model_dump(mode="json"))
        if (
            found.applied_criteria != normalized
            or found.client_request_id != query.client_request_id
        ):
            raise GroundingError("CONVERSATION_CRITERIA_MISMATCH")
        if total is not None and (
            total != found.supported_total or snapshot != found.presentation.snapshot_id
        ):
            raise GroundingError("CONVERSATION_SNAPSHOT_CHANGED")
        total, snapshot = found.supported_total, found.presentation.snapshot_id
        summaries.extend(found.items)
        cursor = found.next_cursor
        if cursor is None:
            complete = len(summaries) == total
            break
    if len({key(row.ref) for row in summaries}) != len(summaries):
        raise GroundingError("CONVERSATION_DUPLICATE_ROWS")
    if not question.include_descriptions:
        return ConversationSources(tuple(summaries), source, complete, total)
    enriched: list[ListingSummary | ListingDetail] = []
    for offset in range(0, len(summaries), 50):
        batch = summaries[offset : offset + 50]
        refs = tuple(row.ref for row in batch)
        details = await gate.run(
            lambda refs=refs: inventory.original_batch(refs, deadline_at=deadline()),
            budget, tool=True,
        )
        if len(details) != len(batch):
            raise GroundingError("CONVERSATION_REFERENCE_COUNT")
        for summary, detail in zip(batch, details, strict=True):
            actual_ref = detail.listing.ref if isinstance(detail, ListingDetail) else detail.ref
            if key(summary.ref) != key(actual_ref):
                raise GroundingError("CONVERSATION_REFERENCE_MISMATCH")
            enriched.append(detail if isinstance(detail, ListingDetail) else summary)
    return ConversationSources(tuple(enriched), source, complete, total)
