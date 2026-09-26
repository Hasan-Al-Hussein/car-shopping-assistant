"""Actual draft/lead/confirmation participants with synthetic Inventory ports only."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.viewings import BookingDraft
from app.database.models import (
    ActiveInventory,
    ActiveRules,
    Booking,
    ExportIntent,
    InventorySnapshot,
    Lead,
    LeadBooking,
    ListingResourceMapping,
    OperationOutcome,
    RuleVersion,
)
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.leads.participant import LeadParticipant
from app.sessions import repository as sessions
from app.sessions.state import canonical
from app.viewings.confirmation import (
    ConfirmationEffect,
    ConfirmationParticipant,
    PreparedConfirmation,
)
from app.viewings.draft_configuration import (
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
)
from app.viewings.eligibility import EligibilityPolicy
from tests.platform.session_cases import ref
from tests.transactions.draft_fixtures import DraftHarness, confirmation, make_draft_harness
from tests.transactions.lead_fixtures import LeadInventoryFake


@dataclass
class ConfirmationHarness:
    drafts: DraftHarness
    participant: ConfirmationParticipant
    lead_inventory: LeadInventoryFake

    def create(
        self, *, who: int = 0, minutes: int = 0, snapshot: str | None = None
    ) -> BookingDraft:
        command = self.drafts.command(who=who)
        assert command.appointment is not None
        command.appointment.starts_at_utc = utc_text(
            datetime.fromisoformat(command.appointment.starts_at_utc) + timedelta(minutes=minutes)
        )
        if snapshot is not None:
            command.ref = ref(snapshot_id=snapshot)
        return self.drafts.service.create(self.drafts.base.context(who), command)

    def prepare(self, draft: BookingDraft, *, who: int = 0) -> PreparedConfirmation | None:
        return self.participant.prepare(
            self.drafts.base.context(who), draft_id=draft.draft_id, command=confirmation(draft)
        )

    def apply(
        self, unit: OwnerUnit, draft: BookingDraft, prepared: PreparedConfirmation | None
    ) -> ConfirmationEffect:
        base = self.drafts.base
        before = unit.session(draft.session_id).revision
        effect = self.participant.apply_in_unit(
            unit,
            draft_id=draft.draft_id,
            command=confirmation(draft),
            generation=base.store.generation,
            now=utc_text(base.clock.value),
            prepared=prepared,
        )
        assert unit.session(draft.session_id).revision == before
        if effect.transition is not None:
            self.participant.resolve_session_in_unit(unit, transition=effect.transition)
            session = unit.session(draft.session_id)
            assert session.revision == before
            session.revision += 1
            sessions.activity(session, utc_text(base.clock.value), 7)
        return effect

    def commit(
        self, draft: BookingDraft, prepared: PreparedConfirmation | None, *, who: int = 0
    ) -> ConfirmationEffect:
        return self.drafts.base.auth.write(
            self.drafts.base.context(who), lambda unit: self.apply(unit, draft, prepared)
        )

    def counts(self) -> tuple[int, ...]:
        return self.drafts.base.store.read(
            lambda db: tuple(
                db.scalar(select(func.count()).select_from(model)) or 0
                for model in (Booking, OperationOutcome, Lead, LeadBooking, ExportIntent)
            )
        )

    def activate_second_snapshot(self) -> None:
        """Synthetic activation only; keep the same stable resource across versioned refs."""
        base = self.drafts.base

        def change(db: Session) -> None:
            active = db.get(ActiveInventory, 1)
            active_rules = db.get(ActiveRules, 1)
            snapshot = db.get(InventorySnapshot, "2" * 64)
            assert active is not None and active_rules is not None and snapshot is not None
            old = db.get(RuleVersion, active_rules.version)
            assert old is not None
            configuration = ViewingConfiguration.model_validate_json(canonical(old.rules_json))
            snapshot.index_version = "e" * 64
            db.flush()
            active.snapshot_id, active.revision = snapshot.snapshot_id, active.revision + 1
            exact = ref(snapshot_id=snapshot.snapshot_id)
            db.add(
                ListingResourceMapping(
                    **exact.model_dump(),
                    resource_id=self.drafts.inventory.resources["12"],
                    mapping_version="synthetic-mapping-1",
                    provenance_json={"synthetic_only": True},
                )
            )
            configuration = configuration.model_copy(
                update={
                    "inventory": configuration.inventory.model_copy(
                        update={
                            "snapshot_id": snapshot.snapshot_id,
                            "active_revision": active.revision,
                        }
                    ),
                    "eligibility": EligibilityPolicy(
                        version="synthetic-permission-2", eligible_refs=(exact,)
                    ),
                },
                deep=True,
            )
            version = configuration_id(configuration)
            db.add(
                RuleVersion(
                    version=version,
                    policy_version=base.settings.policy.version,
                    rules_json=configuration.model_dump(mode="json"),
                    eligibility_version=eligibility_version(configuration),
                    created_at=utc_text(base.clock.value),
                )
            )
            db.flush()
            active_rules.version, active_rules.revision = version, active_rules.revision + 1

        base.store.write(change)


def make_confirmation_harness() -> ConfirmationHarness:
    drafts = make_draft_harness()
    inventory = LeadInventoryFake(drafts.base)
    return ConfirmationHarness(
        drafts,
        ConfirmationParticipant(drafts.service, leads=LeadParticipant(inventory=inventory)),
        inventory,
    )
