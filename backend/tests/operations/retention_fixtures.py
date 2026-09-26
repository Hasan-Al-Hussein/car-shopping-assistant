"""Actual disposable Store/domain fixtures; synthetic pending-command material is labelled."""

from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.leads import LeadRecord
from app.database import models as m
from app.database.paths import RuntimeBoundary
from app.operations.retention import RetentionService
from app.sessions import repository as sessions
from app.sessions.collection import RetainedCollectionCommand
from app.sessions.state import StoredMessage, canonical, fingerprint
from tests.transactions.conversational_fixtures import begin
from tests.transactions.lead_fixtures import correction, save_request
from tests.transactions.projection_fixtures import ProjectionHarness, make_projection_harness


@dataclass
class RetentionHarness:
    projection: ProjectionHarness
    service: RetentionService
    owners: tuple[str, str]

    def facts(self) -> tuple[tuple[dict[str, Any], ...], ...]:
        def read(db: Session) -> tuple[tuple[dict[str, Any], ...], ...]:
            return tuple(
                tuple(
                    dict(row)
                    for row in db.execute(
                        select(model.__table__).order_by(*model.__table__.primary_key)
                    ).mappings()
                )
                for model in (
                    m.Owner,
                    m.OwnerCredential,
                    m.Journey,
                    m.ConversationSession,
                    m.Message,
                    m.ResultPresentation,
                    m.PresentationItem,
                    m.Preference,
                    m.PreferenceSetting,
                    m.ShortlistMembership,
                    m.CommandReceipt,
                    m.BookingDraft,
                    m.BookingReview,
                    m.OperationOutcome,
                    m.Booking,
                    m.Lead,
                    m.LeadBooking,
                    m.ExportIntent,
                    m.ExportState,
                )
            )

        return self.projection.store.read(read)

    def unresolved_lead_command(
        self,
        *,
        existing: bool = True,
        saved_lead: LeadRecord | None = None,
    ) -> tuple[str, str]:
        """Actual typed pending record, not proof of A9's user-authority wrapper."""
        leads = self.projection.leads
        base = leads.sessions
        saved = (
            saved_lead if saved_lead is not None else self.projection.save() if existing else None
        )
        admission = begin(base, leads.session_ids[0])
        command = (
            save_request(leads.session_ids[0])
            if saved is None
            else correction(
                leads.session_ids[0],
                saved.revision,
                saved.values,
            )
        )
        lead_id = None if saved is None else saved.lead_id
        material = {
            "kind": "session-collection-completion-1",
            "command": command.model_dump(mode="json"),
            "lead_id": lead_id,
            "draft_id": None,
        }
        completion = canonical(material).decode("utf-8")
        retained = RetainedCollectionCommand(
            kind="lead",
            source_message_id=admission.message_id,
            session_id=leads.session_ids[0],
            submitted_store_generation=base.store.generation,
            request_hash=fingerprint(admission.request.model_dump(mode="json")),
            command_hash=fingerprint(
                {"lead_id": lead_id, "command": command.model_dump(mode="json")}
            ),
            command=command,
            lead_id=lead_id,
            completion_json=completion,
            completion_hash=fingerprint(material),
        )

        def retain(db: Session) -> None:
            row = db.get(m.Message, admission.message_id)
            assert row is not None
            current = sessions.message_content(row)
            row.result_json = StoredMessage.model_validate(
                {
                    **current.model_dump(mode="json"),
                    "collection_command": retained.model_dump(mode="json"),
                }
            ).model_dump(mode="json")

        base.store.write(retain)
        return admission.message_id, command.client_action_id


def make_retention_harness(
    monkeypatch: pytest.MonkeyPatch,
    *,
    boundary: RuntimeBoundary | None = None,
) -> RetentionHarness:
    projection = make_projection_harness(monkeypatch, boundary=boundary)
    base = projection.leads.sessions
    owners = tuple(base.auth.read(base.context(who), lambda unit: unit.owner_id) for who in (0, 1))
    return RetentionHarness(
        projection, RetentionService(projection.store, clock=base.clock.now), (owners[0], owners[1])
    )
