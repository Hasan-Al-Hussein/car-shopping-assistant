"""Real owned Store/Inventory/Session/Lead/Draft composition; interpretation is scripted.

Authored source only. This is not actual free AI Studio, UI or CSV-file proof.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.api.schemas.identity import IdentityBootstrapRequest, RecognizedIdentity
from app.api.schemas.leads import BudgetValue, ContactValue, LeadRecord, LeadSaveRequest, LeadValues
from app.api.schemas.sessions import (
    ClarificationIntent, ClarificationReply, MessageRequest, MessageResult,
    SessionCreateRequest, ViewingReviewIntent,
)
from app.assistant.intent import ReferenceRequest, TurnIntent
from app.assistant.service_adapters import AssistantService, BoundedServiceWorker
from app.core.config import Settings
from app.core.errors import ApiFailure
from app.database.models import Booking, BookingDraft, ExportIntent, Lead, Message
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext, OwnerUnit
from app.identity.credentials import decode_token
from app.identity.service import IdentityService
from app.inventory.details_service import InventoryDetailsService
from app.inventory.search_service import InventorySearchService
from app.inventory_gateways import CompactSessionInventory, CompactShortlistInventory
from app.inventory_signing import HmacPublicInventorySigner
from app.leads.service import LeadService
from app.sessions.repository import message_content
from app.sessions.service import SessionService
from app.sessions.state import SessionContent
from app.viewings.drafts import DraftService
from scripts.bootstrap_inventory import BootstrapInputs
from tests.inventory.conftest import inventory_store as inventory_store
from tests.inventory.conftest import inventory_store_path as inventory_store_path
from tests.inventory.test_viewing_adapter import Case
from tests.inventory.test_viewing_adapter import accepted_inputs as accepted_inputs
from tests.inventory.test_viewing_adapter import make_case as make_case
from tests.platform.test_identity import ACK

from .conversation_fakes import ScriptedTransport, adapter, budget, response, state
from .test_service_worker import until


@dataclass
class Clock:
    value: datetime = datetime(2026, 9, 24, 19, 55, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


def proposal(command: str, fields: list[tuple[str, str]] | None = None, reference: ReferenceRequest | None = None) -> TurnIntent:
    return TurnIntent.model_validate({
        "operation": "smalltalk", "scope": "session", "deferred": ["viewing"],
        "collection": {"command": command, "fields": [
            {"field": field, "quote": quote} for field, quote in fields or []
        ]},
        "references": [] if reference is None else [reference.model_dump(mode="json")],
    })


@dataclass
class Harness:
    case: Case
    clock: Clock
    authorization: AuthorizationService
    context: AuthorizedOwnerContext
    sessions: SessionService
    leads: LeadService
    drafts: DraftService
    worker: BoundedServiceWorker
    assistant: AssistantService
    transport: ScriptedTransport
    session_id: str
    last_request: MessageRequest | None = None

    async def read[T](self, call: Callable[[], T]) -> T:
        return await self.worker.run(call, deadline_at=monotonic() + 5)

    async def say(self, text: str, intent: TurnIntent) -> MessageResult:
        current = await self.read(lambda: self.sessions.get(self.context, self.session_id))
        pending = current.pending_intent
        echoed = ClarificationReply(intent_id=pending.intent_id, created_revision=pending.created_revision) if isinstance(pending, ClarificationIntent) else None
        command = MessageRequest(
            client_message_id=str(uuid4()), expected_revision=current.revision,
            text=text, clarification_reply=echoed,
        )
        self.transport.steps.append(response(intent))
        self.last_request = command
        lead = await self.read(lambda: self.leads.get(self.context))
        private = tuple(value.value for value in (lead.values.email, lead.values.phone) if value.state == "provided" and value.value is not None) if isinstance(lead, LeadRecord) else ()
        return await self.assistant.run(
            self.context, self.session_id, command, request_state=state(), budget=budget(), private_values=private,
        )

    async def replay(self, command: MessageRequest) -> MessageResult:
        return await self.assistant.run(
            self.context, self.session_id, command, request_state=state(), budget=budget(),
        )

    def content(self) -> SessionContent:
        return self.authorization.read(
            self.context,
            lambda unit: SessionContent.model_validate(unit.session(self.session_id).state_json),
        )

    def counts(self) -> tuple[int, int, int, int]:
        return self.case.store.read(lambda db: (
            int(db.scalar(select(func.count()).select_from(Lead)) or 0),
            int(db.scalar(select(func.count()).select_from(BookingDraft)) or 0),
            int(db.scalar(select(func.count()).select_from(Booking)) or 0),
            int(db.scalar(select(func.count()).select_from(ExportIntent)) or 0),
        ))

    def retained_action_id(self, client_message_id: str) -> str:
        def read(unit: OwnerUnit) -> str:
            row = unit.db.scalar(select(Message).where(
                Message.owner_id == unit.owner_id, Message.session_id == self.session_id,
                Message.client_message_id == client_message_id,
            ))
            assert row is not None
            retained = message_content(row).collection_command
            assert retained is not None
            return retained.command.client_action_id

        return self.authorization.read(self.context, read)

    def finish(self) -> None:
        asyncio.run(until(lambda: not self.worker.pending))
        assert self.worker.close()
        self.case.gateway.close()


def build(factory: Callable[..., Case], inputs: BootstrapInputs) -> Harness:
    case, clock = factory(), Clock()
    settings = Settings(store_path=case.store.path, runtime_boundary=case.store.boundary, policy=inputs.policy)
    identity = IdentityService(settings, clock=clock)
    owner = identity.bootstrap(IdentityBootstrapRequest.model_validate(ACK), None)
    assert owner.cookie is not None and isinstance(owner.identity, RecognizedIdentity)
    authorization = AuthorizationService(identity)
    context = authorization.authorize_write(decode_token(owner.cookie), owner.identity.context_id, owner.identity.csrf_token)
    signer = HmacPublicInventorySigner(case.store.generation)
    sessions = SessionService(authorization, inventory=CompactSessionInventory(case.reader, signer))
    leads = LeadService(authorization, inventory=CompactShortlistInventory(case.reader))
    drafts = DraftService(authorization, inventory=case.gateway)
    current = sessions.create(context, SessionCreateRequest(client_action_id=str(uuid4())))
    model, transport = adapter()
    worker = BoundedServiceWorker()
    assistant = AssistantService(
        sessions, model, InventorySearchService(case.reader, signer, clock=clock),
        InventoryDetailsService(case.reader), worker, leads=leads, drafts=drafts,
    )
    return Harness(case, clock, authorization, context, sessions, leads, drafts, worker, assistant, transport, current.session_id)


@pytest.mark.parametrize("position,amount,maximum,needs,date_text,expected_date,time_text,expected_utc", [
    (0, "45000", 4500000, "quiet cabin", "tomorrow", "2026-09-25", "14:30", "2026-09-25T10:30:00Z"),
    (1, "62.5k", 6250000, "space for a folding bicycle", "2026-09-26", "2026-09-26", "10 am", "2026-09-26T06:00:00Z"),
])
def test_real_rich_collection_save_review_replay_and_material_correction(
    make_case: Callable[..., Case], accepted_inputs: BootstrapInputs,
    position: int, amount: str, maximum: int, needs: str, date_text: str,
    expected_date: str, time_text: str, expected_utc: str,
) -> None:
    h = build(make_case, accepted_inputs)

    async def exercise() -> None:
        found = await h.say("Show cars", TurnIntent(operation="search"))
        assert found.search is not None and len(found.search.items) > position
        selected = found.search.presentation.ordered_refs[position]
        assert selected.model_dump() in [item.model_dump() for item in accepted_inputs.eligibility.eligible_refs]
        before = await h.read(h.content)
        quote = "the first car" if position == 0 else "the second car"
        await h.say("Prepare a viewing of " + quote, proposal("start_viewing", reference=ReferenceRequest(source="ordinal", position=position, quote=quote)))
        date_clause = "Viewing date: " + date_text
        dated = await h.say(date_clause, proposal("fields", [("local_date", date_clause)]))
        assert "Dubai date: " + expected_date in dated.text
        h.clock.value += timedelta(minutes=10)  # Cross Dubai midnight after the source date.
        time_clause = "Viewing time: " + time_text
        await h.say(time_clause, proposal("fields", [("local_time", time_clause)]))
        budget_clause = "My cash budget is AED " + amount
        needs_clause = f'My requirements are "{needs}"'
        await h.say(budget_clause + "; " + needs_clause, proposal("fields", [("budget", budget_clause), ("requirements", needs_clause)]))
        assert await h.read(h.counts) == (0, 0, 0, 0)
        collected = await h.read(h.content)
        assert collected.criteria == before.criteria and collected.selected_ref == selected
        assert collected.collection is not None and collected.collection.values.local_date == expected_date
        assert collected.collection.values.budget.value is not None
        assert collected.collection.values.budget.value.maximum == maximum
        await h.say("Review my local enquiry", proposal("review_enquiry"))
        saved = await h.say("Save this local enquiry", proposal("save_enquiry"))
        assert saved.actions.lead.state == "succeeded"
        actual_lead = await h.read(lambda: h.leads.get(h.context))
        assert isinstance(actual_lead, LeadRecord)
        assert actual_lead.values.requirements == [needs] and actual_lead.values.selected_refs == [selected]
        assert actual_lead.delivery == "local_only" and actual_lead.csv.state == "pending"
        save_request = h.last_request
        assert save_request is not None
        calls = len(h.transport.requests)
        assert await h.replay(save_request) == saved
        assert len(h.transport.requests) == calls and await h.read(h.counts) == (1, 0, 0, 1)
        prepared = await h.say("Prepare the viewing review", proposal("prepare_viewing"))
        pending = prepared.pending_intent
        assert isinstance(pending, ViewingReviewIntent)
        actual = await h.read(lambda: h.drafts.get(h.context, pending.draft_id))
        assert actual.review is not None and actual.state == "reviewable"
        assert (actual.review.review_id, actual.review.operation_key) == (pending.review_id, pending.operation_key)
        assert datetime.fromisoformat(actual.review.starts_at_utc) == datetime.fromisoformat(expected_utc)
        assert actual.ref == selected
        assert actual.review.lead_change.mode == "preserve_existing"
        assert actual.review.lead_change.lead_id == actual_lead.lead_id
        assert actual.review.lead_change.expected_revision == actual_lead.revision
        session = await h.read(lambda: h.sessions.get(h.context, h.session_id))
        assert session.revision == prepared.current_revision
        review_request = h.last_request
        assert review_request is not None
        calls = len(h.transport.requests)
        assert await h.replay(review_request) == prepared and len(h.transport.requests) == calls
        assert await h.read(h.counts) == (1, 1, 0, 1)
        correction = "Viewing date: 2026-09-28"
        changed = await h.say(correction, proposal("fields", [("local_date", correction)]))
        assert "Temporary viewing details (Dubai): 2026-09-28" in changed.text
        suspended = await h.read(lambda: h.drafts.get(h.context, pending.draft_id))
        assert suspended.state == "suspended" and changed.pending_intent.kind == "none"
        assert suspended.review is None or suspended.review.state != "valid"
        stopped = await h.say("Stop this viewing preparation", proposal("stop_viewing"))
        assert stopped.pending_intent.kind == "none"
        after = await h.read(h.content)
        assert after.collection is None and after.current_draft_id is None
        assert await h.read(h.counts) == (1, 1, 0, 1)

    try:
        asyncio.run(exercise())
    finally:
        h.finish()


def test_real_correction_preserves_form_contacts_and_rejects_unbound_save_language(
    make_case: Callable[..., Case], accepted_inputs: BootstrapInputs,
) -> None:
    h = build(make_case, accepted_inputs)

    async def exercise() -> None:
        seeded = await h.read(lambda: h.leads.save(h.context, LeadSaveRequest(
            client_action_id=str(uuid4()), session_id=h.session_id, intent="save_local_enquiry",
            values=LeadValues(budget=BudgetValue(state="missing"), requirements=[], selected_refs=[],
                              email=ContactValue(state="provided", value="synthetic-form@example.test"), phone=ContactValue(state="declined")),
        )))
        await h.say("Prepare a local enquiry", proposal("start_enquiry"))
        budget_clause, needs_clause = "My cash budget is AED 58000", 'My requirements are "easy parking"'
        await h.say(budget_clause + "; " + needs_clause, proposal("fields", [("budget", budget_clause), ("requirements", needs_clause)]))
        await h.say("Review my local enquiry", proposal("review_enquiry"))
        denied = await h.say("yes", proposal("correct_enquiry"))
        assert denied.actions.lead.state == "not_requested" and denied.pending_intent.kind == "clarification"
        denied = await h.say("Do not update my saved local enquiry", proposal("correct_enquiry"))
        assert denied.actions.lead.state == "not_requested"
        assert await h.read(h.counts) == (1, 0, 0, 1)
        changed = await h.say("Update my saved local enquiry", proposal("correct_enquiry"))
        assert changed.actions.lead.state == "succeeded"
        actual = await h.read(lambda: h.leads.get(h.context))
        assert isinstance(actual, LeadRecord)
        assert actual.lead_id == seeded.lead.lead_id and actual.revision == seeded.lead.revision + 1
        assert actual.values.email == ContactValue(state="provided", value="synthetic-form@example.test")
        assert actual.values.phone == ContactValue(state="declined")
        assert actual.values.requirements == ["easy parking"]
        assert all("synthetic-form@example.test" not in call.contents for call in h.transport.requests)
        assert await h.read(h.counts) == (1, 0, 0, 2)

    try:
        asyncio.run(exercise())
    finally:
        h.finish()


def test_real_retained_command_prevents_same_message_and_new_session_replacement(
    make_case: Callable[..., Case], accepted_inputs: BootstrapInputs, monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = build(make_case, accepted_inputs)

    async def exercise() -> None:
        await h.say("Prepare a local enquiry", proposal("start_enquiry"))
        needs_clause = 'My requirements are "quiet cabin"'
        await h.say(needs_clause, proposal("fields", [("requirements", needs_clause)]))
        await h.say("Review my local enquiry", proposal("review_enquiry"))

        def unavailable(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("SYNTHETIC_PREPARATION_UNAVAILABLE")

        with monkeypatch.context() as patch:
            patch.setattr(h.leads, "prepare_change", unavailable)
            with pytest.raises(RuntimeError, match="SYNTHETIC_PREPARATION"):
                await h.say("Save this local enquiry", proposal("save_enquiry"))
        original = h.last_request
        assert original is not None
        calls = len(h.transport.requests)
        with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
            await h.replay(original)
        assert len(h.transport.requests) == calls and await h.read(h.counts) == (0, 0, 0, 0)
        transcript = await h.read(lambda: h.sessions.transcript(h.context, h.session_id))
        assert transcript.items[-1].state == "pending"
        original_action = await h.read(lambda: h.retained_action_id(original.client_message_id))
        current = await h.read(lambda: h.sessions.create(h.context, SessionCreateRequest(client_action_id=str(uuid4()))))
        h.session_id = current.session_id
        fenced = await h.say("Prepare a local enquiry", proposal("start_enquiry"))
        assert fenced.actions.lead.state == "unresolved"
        assert fenced.actions.lead.client_action_id == original_action
        assert fenced.actions.lead.submitted_store_generation == h.case.store.generation
        assert len(h.transport.requests) == calls + 1 and fenced.provider_state == "available"
        assert await h.read(h.counts) == (0, 0, 0, 0)
        assert (await h.read(h.content)).collection is None

    try:
        asyncio.run(exercise())
    finally:
        h.finish()
