"""Actual graph closure with labelled timestamp/navigation fixture perturbations.

These diagnostics tests do not establish a new retention policy or claim that a
user can shorten TTLs or select an obsolete current draft through the public API.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Booking, ConversationSession, Lead
from app.identity.service import utc_text
from app.leads.service import LeadService
from app.operations.retention import RetentionService
from app.sessions import repository as sessions
from app.sessions.state import SessionContent
from tests.operations.backup_fixtures import make_backup_harness
from tests.transactions.confirmation_fixtures import make_confirmation_harness
from tests.transactions.lead_fixtures import LeadInventoryFake, save_request


def test_late_draft_cause_crosses_existing_strong_session_and_counts_one_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_backup_harness(monkeypatch)  # Establish the approved isolated RuntimeBoundary.
    flow = make_confirmation_harness()
    base = flow.drafts.base
    owner_id = base.auth.read(base.context(), lambda unit: unit.owner_id)
    lead_service = LeadService(base.auth, inventory=LeadInventoryFake(base))
    saved = lead_service.save(base.context(), save_request(flow.drafts.sessions[0])).lead
    booked = flow.create()
    terminal = flow.commit(booked, flow.prepare(booked)).terminal
    assert terminal.state == "succeeded"
    before_receipt = base.store.read(lambda db: db.scalar(select(Booking.immutable_receipt_json)))
    base.clock.value += timedelta(days=3)
    # A second real incomplete draft supplies a retained draft cause. The older
    # booked draft is already expired, so it has no independent draft TTL root.
    other = flow.drafts.service.create(base.context(), flow.drafts.command(complete=False))
    assert other.draft_id != booked.draft_id
    expired_at = utc_text(base.clock.now() - timedelta(microseconds=1))

    def graph_case(db: Session) -> None:
        lead = db.get(Lead, saved.lead_id)
        session = db.get(ConversationSession, booked.session_id)
        assert lead is not None and session is not None
        lead.expires_at = expired_at  # Controlled diagnostic threshold, not a production TTL action.
        current = sessions.content(session)
        # Retain a valid typed navigation link to the older real terminal graph.
        # This explicit fixture makes the later cause cross an already visited
        # strong session instead of reaching the booking by a direct draft edge.
        session.state_json = SessionContent.model_validate({
            **current.model_dump(mode="json"), "current_draft_id": booked.draft_id,
            "pending_intent": {"kind": "none"},
        }).model_dump(mode="json")

    base.store.write(graph_case)
    service = RetentionService(base.store, clock=base.clock.now)
    observed = service.inspect(owner_id=owner_id)
    assert observed.protected_expired_leads == 1
    reasons = dict(observed.protected_expired_reasons)
    assert reasons["draft_retained"] == 1
    assert reasons["session_retention_active"] == 1
    assert reasons["booking_retention_active"] == 1
    assert reasons["outcome_replay_active"] == 1
    assert all(count == 1 for count in reasons.values())
    assert "protection_unclassified" not in reasons and "lead_retention_active" not in reasons
    committed = service._commit(observed)
    assert committed.protected_expired_leads == 1
    assert committed.protected_expired_reasons == observed.protected_expired_reasons
    assert base.store.read(lambda db: db.scalar(select(Lead.expires_at))) == expired_at
    assert base.store.read(lambda db: db.scalar(select(Booking.immutable_receipt_json))) == before_receipt
