"""Bounded intent interpretation; accepted criteria remain authoritative outside prose."""

from collections.abc import MutableMapping
from typing import Any

from app.api.schemas.inventory import KnownFact
from app.api.schemas.sessions import (
    ClarificationIntent,
    MessageRequest,
    SessionState,
    TranscriptTurn,
)

from .budget import TurnBudget
from .intent import TurnIntent
from .packet import ConversationMessage, EvidencePacket
from .provider import GeminiAdapter, ProviderResult
from .request_diagnostics import generate_for_request


async def interpret(
    adapter: GeminiAdapter,
    request: MessageRequest,
    session: SessionState,
    request_state: MutableMapping[str, Any],
    budget: TurnBudget,
    private_values: tuple[str, ...],
    collection_summary: str | None = None,
    recent_turns: tuple[TranscriptTurn, ...] = (),
) -> ProviderResult[TurnIntent]:
    # Bounded owned conversational context, minimized before upload. No identity,
    # action credentials, source descriptions, or private form fields are serialized.
    context = [
        "Explicit durable saves of new quoted soft requirements need one soft_preferences "
        "TextPatch with every exact value and a whole-list verbatim quote plus deferred "
        "preferences. Never substitute current criteria; a proposal is not permission.",
        "Recall uses return/session, no patches. Use conversation history and accepted criteria. "
        "Browse without a questionnaire; cite a car only when the buyer does. Shopping budgets "
        "and search clarification replies use search patches, never collection. Only explicit "
        "enquiry/viewing preparation uses collection. Use question for natural inventory "
        "questions and follow-ups; do not request arbitrary missing criteria.",
    ]
    current_budget = session.criteria.filters.budget
    if current_budget is not None:
        context.append(f"Established budget currency: {current_budget.currency}; basis: cash.")
    pending = session.pending_intent
    if isinstance(pending, ClarificationIntent):
        matched = request.clarification_reply is not None
        context.append(
            f"Pending {pending.purpose}; targets={','.join(pending.targets)}; "
            f"reply_to_question={matched}. {pending.question} "
            "Resolve from the answer and preceding user request. "
            "Search answers use search patches; "
            "Preserve prior currency, payment basis and bounds. A bare purchase budget is "
            "an inclusive maximum only when no earlier stricter bound was stated."
        )
    if collection_summary is not None:
        # Reuse a fixed bounded instruction slot; never append a fifth summary.
        context[1] = context[1][:300] + " " + collection_summary
    conversation = []
    for turn in recent_turns[-6:]:
        conversation.append(ConversationMessage(role="user", text=turn.user_text[:2000]))
        answer = turn.assistant_result
        if answer is None:
            continue
        text = answer.text[:900]
        if answer.search is not None:
            rows = []
            for index, car in enumerate(answer.search.items[:20], 1):
                values = []
                for name in ("make", "model", "year", "cash_price", "mileage_km"):
                    fact = getattr(car, name)
                    value = str(fact.value) if isinstance(fact, KnownFact) else fact.status
                    values.append(f"{name}={value}")
                rows.append(f"{index}. " + "; ".join(values))
            text = (
                f"Displayed search: {answer.search.supported_total} matches; "
                f"{len(answer.search.items)} shown in original order.\n" + "\n".join(rows)
            )
        conversation.append(ConversationMessage(role="assistant", text=text[:2000] or "No answer."))
    while len(conversation) > 2 and sum(len(item.text) for item in conversation) > 6000:
        del conversation[:2]
    packet = EvidencePacket(
        message=request.text,
        session_revision=session.revision,
        selected_ref=session.selected_ref,
        presented_refs=() if request.selected_ref is None else (request.selected_ref,),
        history_summaries=tuple(item[:400] for item in context),
        conversation=tuple(conversation),
        accepted_criteria=session.criteria.model_dump_json(),
    )
    return await generate_for_request(
        adapter,
        packet,
        TurnIntent,
        request_state=request_state,
        budget=budget,
        private_values=private_values,
    )
