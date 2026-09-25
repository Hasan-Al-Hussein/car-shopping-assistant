"""Tiny A3 contract fakes; no authorization, SQLite, signature or retrieval proof."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import SecretStr

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    ComparisonRequest,
    ComparisonResult,
    ListingDetail,
    ListingResult,
    PresentationProof,
    SearchCriteria,
    SearchRequest,
    SearchResult,
)
from app.api.schemas.sessions import MessageRequest, MessageResult, SessionState
from app.assistant.budget import TurnBudget
from app.assistant.intent import TurnIntent
from app.assistant.provider import (
    GeminiAdapter,
    ProviderFault,
    TransportRequest,
    TransportResponse,
)
from app.assistant.references import ref_key
from app.core.config import Settings
from app.core.diagnostics import ProviderMetricSlot
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.sessions.service import TurnAdmission, TurnTicket
from app.sessions.state import SessionContent

CONTEXT = cast(AuthorizedOwnerContext, object())
SNAPSHOT = "a" * 64


def ref(source: str) -> InventoryRef:
    return InventoryRef(namespace="synthetic", snapshot_id=SNAPSHOT, source_id=source)


def listing(source: str, make: str | None = "Honda") -> ListingDetail:
    unknown = {"status": "unknown", "reason": "not_stated"}
    fact = (
        unknown
        if make is None
        else {
            "status": "known",
            "value": make,
            "evidence": [
                {
                    "evidence_id": str(uuid4()),
                    "workbook_sha256": "b" * 64,
                    "sheet": "synthetic",
                    "cell": "A2",
                    "raw_text": make,
                    "span_start": 0,
                    "span_end": len(make),
                    "extraction_version": "test-1",
                    "category": "structured_source",
                    "review_status": "not_reviewed",
                }
            ],
        }
    )
    return ListingDetail.model_validate(
        {
            "state": "current",
            "listing": {
                "ref": ref(source).model_dump(),
                "title": "Synthetic fixture car",
                "make": fact,
                "model": unknown,
                "trim": unknown,
                "year": unknown,
                "cash_price": unknown,
                "mileage_km": unknown,
                "photo": {"state": "missing", "url": None, "alt": "No fixture photograph"},
            },
            "description": "",
            "fuel_type": unknown,
            "body_type": unknown,
            "transmission": unknown,
            "location": unknown,
            "warranty": unknown,
            "service_history": unknown,
            "eligibility": "configuration_missing",
            "eligibility_reason": "Synthetic read-only fixture",
        }
    )


def session(**changes: Any) -> SessionState:
    return SessionState.model_validate(
        {
            "session_id": str(uuid4()),
            "journey_id": str(uuid4()),
            "revision": 0,
            "criteria": {},
            "selected_ref": None,
            "active_presentation_id": None,
            "current_draft_id": None,
            "pending_intent": {"kind": "none"},
            "recalled_preferences": {
                "entries": [],
                "revision": 0,
                "collection_mode": "explicit_save",
            },
            **changes,
        }
    )


def request(current: SessionState, text: str, **changes: Any) -> MessageRequest:
    return MessageRequest.model_validate(
        {
            "client_message_id": str(uuid4()),
            "expected_revision": current.revision,
            "text": text,
            **changes,
        }
    )


def state() -> dict[str, Any]:
    request_id = str(uuid4())
    return {"request_id": request_id, "provider_metric_slot": ProviderMetricSlot(request_id)}


def budget() -> TurnBudget:
    return TurnBudget(Settings().timeouts, asyncio.get_running_loop().time() + 30)


Step = TransportResponse | ProviderFault | Callable[[], Awaitable[TransportResponse]]


class ScriptedTransport:
    def __init__(self, *steps: Step) -> None:
        self.steps = list(steps)
        self.requests: list[TransportRequest] = []

    async def generate(self, value: TransportRequest) -> TransportResponse:
        self.requests.append(value)
        step = self.steps.pop(0)
        if isinstance(step, ProviderFault):
            raise step
        return await step() if callable(step) else step


def response(intent: TurnIntent) -> TransportResponse:
    return TransportResponse(intent.model_dump_json())


def adapter(*intents: TurnIntent) -> tuple[GeminiAdapter, ScriptedTransport]:
    transport = ScriptedTransport(*(response(intent) for intent in intents))
    return provider(transport), transport


def provider(transport: ScriptedTransport) -> GeminiAdapter:
    return GeminiAdapter(
        Settings(gemini_api_key=SecretStr("synthetic-never-a-live-key")), transport
    )


@dataclass
class FakeTurn:
    admission: TurnAdmission
    result: MessageResult | None = None
    status: Literal["pending", "interrupted"] = "pending"


class FakeSessions:
    """Model only original admission/replay/currentness and atomic completion shape."""

    def __init__(self, current: SessionState | None = None) -> None:
        self.current = current or session()
        self.turns: dict[str, FakeTurn] = {}
        self.tickets: dict[TurnTicket, FakeTurn] = {}
        self.presentations: dict[str, tuple[InventoryRef, ...]] = {}
        self.completions: list[tuple[PresentationProof | None, InventoryRef | None]] = []
        self.reads: list[str] = []
        self.lifecycle: list[str] = []

    async def begin(
        self, context: AuthorizedOwnerContext, session_id: str, value: MessageRequest
    ) -> TurnAdmission:
        self.lifecycle.append("begin")
        existing = self.turns.get(value.client_message_id)
        if existing is not None:
            if existing.admission.request != value:
                raise ApiFailure("IDEMPOTENCY_CONFLICT")
            replay = existing.result
            if replay is not None:
                replay = replay.model_copy(update={"current_revision": self.current.revision})
            return TurnAdmission(
                "completed" if replay is not None else existing.status,
                existing.admission.message_id,
                existing.admission.session,
                existing.admission.request,
                result=replay,
            )
        if value.expected_revision != self.current.revision:
            raise ApiFailure("REVISION_CONFLICT")
        changed = self.current.model_dump(mode="json")
        changed["revision"] += 1
        if value.clarification_reply is not None:
            pending = self.current.pending_intent
            if pending.kind != "clarification" or (
                pending.intent_id != value.clarification_reply.intent_id
                or pending.created_revision != value.clarification_reply.created_revision
            ):
                raise ApiFailure("REVISION_CONFLICT")
            # P9C validates a reply but retains its question until current completion.
        if value.selected_ref is not None:
            changed["selected_ref"] = value.selected_ref.model_dump(mode="json")
        if value.presentation_id is not None:
            changed["active_presentation_id"] = value.presentation_id
        self.current = SessionState.model_validate(changed)
        ticket = object.__new__(TurnTicket)  # Fake identity only; never given to the real service.
        accepted = TurnAdmission(
            "accepted",
            str(uuid4()),
            self.current.model_copy(deep=True),
            value.model_copy(deep=True),
            ticket=ticket,
        )
        turn = FakeTurn(accepted)
        self.turns[value.client_message_id] = self.tickets[ticket] = turn
        return accepted

    async def get(self, context: AuthorizedOwnerContext, session_id: str) -> SessionState:
        self.lifecycle.append("get")
        return self.current.model_copy(deep=True)

    async def original_refs(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str
    ) -> tuple[InventoryRef, ...]:
        self.reads.append("original_refs")
        return self.presentations[presentation_id]

    async def ordinal(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str, ordinal: int
    ) -> InventoryRef:
        self.reads.append("ordinal")
        refs = self.presentations[presentation_id]
        if ordinal >= len(refs):
            raise ApiFailure("NOT_FOUND")
        return refs[ordinal]

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
        self.lifecycle.append("complete")
        turn = self.tickets[ticket]
        assert result.client_message_id == turn.admission.request.client_message_id
        assert result.turn_revision == turn.admission.session.revision
        self.completions.append((presentation, selection))
        if self.current.revision != result.turn_revision:
            saved = result.model_copy(
                update={
                    "state": "superseded",
                    "current_revision": self.current.revision,
                    "persistence": "saved",
                }
            )
        else:
            if (
                self.current.pending_intent.kind == "clarification"
                and result.state == "provider_unavailable"
            ):
                after = self.current.pending_intent if update is None else update.pending_intent
                if after != self.current.pending_intent:
                    raise ApiFailure("UNSUPPORTED_STATE")
            changed = self.current.model_dump(mode="json")
            if update is not None:
                assert update.selected_ref == turn.admission.session.selected_ref
                assert (
                    update.active_presentation_id == turn.admission.session.active_presentation_id
                )
                changed.update(update.model_dump(mode="json", exclude={"version", "collection"}))
            if presentation is not None:
                self.presentations[presentation.presentation_id] = tuple(presentation.ordered_refs)
                changed["active_presentation_id"] = presentation.presentation_id
            if selection is not None:
                changed["selected_ref"] = selection.model_dump(mode="json")
            if changed != self.current.model_dump(mode="json"):
                changed["revision"] += 1
            next_state = SessionState.model_validate(changed)
            assert result.pending_intent == next_state.pending_intent
            self.current = next_state
            saved = result.model_copy(
                update={
                    "persistence": "saved",
                    "current_revision": self.current.revision,
                }
            )
        turn.result = MessageResult.model_validate(saved.model_dump(mode="json"))
        return turn.result


class FakeInventory:
    """Fixed DTO answers, deliberately not a search implementation."""

    def __init__(self, *items: ListingDetail) -> None:
        self.items = items or (listing("one"),)
        self.by_ref = {ref_key(item.listing.ref): item for item in self.items}
        self.calls: list[str] = []
        self.searches: list[SearchRequest] = []
        self.deadlines: list[float] = []

    async def search(self, value: SearchRequest, *, deadline_at: float) -> SearchResult:
        self.calls.append("search")
        self.searches.append(value)
        self.deadlines.append(deadline_at)
        criteria = SearchCriteria.model_validate(
            value.model_dump(
                mode="json",
                exclude={"snapshot_id", "page_size", "cursor", "client_request_id"},
            )
        )
        return SearchResult(
            client_request_id=value.client_request_id,
            state="matches",
            items=[item.listing for item in self.items],
            supported_total=len(self.items),
            next_cursor=None,
            applied_criteria=criteria,
            evidence_coverage=[],
            presentation=PresentationProof(
                presentation_id=str(uuid4()),
                snapshot_id=SNAPSHOT,
                ordered_refs=[item.listing.ref for item in self.items],
                criteria_hash="c" * 64,
                issued_at="2026-09-24T00:00:00Z",
                expires_at="2026-09-24T00:10:00Z",
                signature="s" * 43,
            ),
        )

    async def detail(self, value: InventoryRef, *, deadline_at: float) -> ListingResult:
        self.calls.append("detail")
        self.deadlines.append(deadline_at)
        return self.by_ref[ref_key(value)]

    async def compare(self, value: ComparisonRequest, *, deadline_at: float) -> ComparisonResult:
        self.calls.append("compare")
        self.deadlines.append(deadline_at)
        return ComparisonResult(items=[self.by_ref[ref_key(item)] for item in value.refs])

    async def original_batch(
        self, refs: tuple[InventoryRef, ...], *, deadline_at: float
    ) -> tuple[ListingResult, ...]:
        self.calls.append("original_batch")
        self.deadlines.append(deadline_at)
        return tuple(self.by_ref[ref_key(item)] for item in refs)
