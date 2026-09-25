"""Bounded intent interpretation; accepted criteria remain authoritative outside prose."""

from collections.abc import MutableMapping
from typing import Any

from app.api.schemas.sessions import ClarificationIntent, MessageRequest, SessionState

from .budget import TurnBudget
from .intent import TurnIntent
from .packet import EvidencePacket
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
) -> ProviderResult[TurnIntent]:
    # Ask only for explicit deltas. Do not serialize raw transcript, profile provenance,
    # pending-operation keys, completion ticket or all prior free-text criteria.
    context = [
        "Explicit durable saves of new quoted soft requirements need one soft_preferences "
        "TextPatch with every exact value and a whole-list verbatim quote plus deferred "
        "preferences. Never substitute current criteria; a proposal is not permission.",
        "Enquiry/viewing: collection, whole-clause quotes; cite a car only when the buyer does. "
        "Contacts stay local. Saved-preference questions use return/session, no patches/deferred "
        "writes.",
    ]
    current_budget = session.criteria.filters.budget
    if current_budget is not None:
        context.append(f"Established budget currency: {current_budget.currency}; basis: cash.")
    pending = session.pending_intent
    if isinstance(pending, ClarificationIntent):
        context.append(pending.question)
    if collection_summary is not None:
        # Reuse a fixed bounded instruction slot; never append a fifth summary.
        context[1] += " " + collection_summary
    packet = EvidencePacket(
        message=request.text,
        session_revision=session.revision,
        selected_ref=session.selected_ref,
        presented_refs=() if request.selected_ref is None else (request.selected_ref,),
        history_summaries=tuple(context),
    )
    return await generate_for_request(
        adapter,
        packet,
        TurnIntent,
        request_state=request_state,
        budget=budget,
        private_values=private_values,
    )
