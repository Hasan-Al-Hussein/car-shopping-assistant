"""Synthetic real-Store drafts; this adapter is not real Inventory/config activation proof."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.viewings import (
    AppointmentSelection,
    BookingDraft,
    BookingDraftCreate,
    BookingDraftUpdate,
    ConfirmRequest,
)
from app.core.config import VIEWING_VENUE
from app.core.readiness import InventoryObservation
from app.database.models import (
    ActiveInventory,
    ActiveRules,
    Booking,
    BookingReview,
    ExportIntent,
    InventorySnapshot,
    InventoryStorageProfile,
    Lead,
    ListingResourceMapping,
    OperationOutcome,
    RuleVersion,
    VehicleResource,
)
from app.database.models import (
    BookingDraft as DraftRow,
)
from app.database.store import StoreError, assert_outside_write_transaction
from app.identity.service import utc_text
from app.inventory.references import ImmutableInventoryRef
from app.viewings.draft_admission import PreparedViewing
from app.viewings.draft_configuration import (
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
    load_configuration,
)
from app.viewings.drafts import DraftService
from app.viewings.eligibility import EligibilityPolicy
from app.viewings.scheduling import ViewingRules
from tests.platform.session_cases import SessionHarness, make_harness, ref


class SyntheticDraftInventory:
    def __init__(self, harness: SessionHarness, resources: dict[str, str]) -> None:
        self.harness, self.resources = harness, resources
        self.prepares = 0
        self.after_prepare: Callable[[], None] | None = None
        self.fail_recheck = False

    def prepare(self, exact: ImmutableInventoryRef) -> PreparedViewing:
        assert_outside_write_transaction()
        self.prepares += 1

        def read(db: Session) -> PreparedViewing:
            active = db.get(ActiveInventory, 1)
            config = db.get(ActiveRules, 1)
            assert active is not None and config is not None
            profile = db.get(InventoryStorageProfile, 1)
            assert profile is not None
            observation = InventoryObservation.model_validate(
                dict(
                    generation=self.harness.store.generation,
                    active_revision=active.revision,
                    snapshot_id=active.snapshot_id,
                    index_version=active.index_version,
                    mode=profile.mode,
                )
            )
            material = load_configuration(
                db,
                config.version,
                rules=ViewingRules(self.harness.settings.policy),
                observation=observation,
                namespace=exact.namespace,
            )
            if exact.source_id not in self.resources:
                raise StoreError("SYNTHETIC_REF_UNAVAILABLE")
            return PreparedViewing(
                self.harness.store.generation,
                exact,
                active.revision,
                active.index_version,
                self.resources[exact.source_id],
                "synthetic-mapping-1",
                eligibility_version(material),
                config.version,
                config.revision,
                ("synthetic-reviewed-identity-1",),
            )

        value = self.harness.store.read(read)
        if self.after_prepare is not None:
            self.after_prepare()
        return value

    def recheck(self, db: Session, prepared: PreparedViewing) -> None:
        if self.fail_recheck or prepared.identity != ("synthetic-reviewed-identity-1",):
            raise StoreError("SYNTHETIC_INTEGRITY_UNAVAILABLE")
        assert db.in_transaction()


@dataclass
class DraftHarness:
    base: SessionHarness
    service: DraftService
    inventory: SyntheticDraftInventory
    sessions: tuple[str, str]

    def command(self, *, complete: bool = True, who: int = 0) -> BookingDraftCreate:
        revision = self.base.service.get(self.base.context(who), self.sessions[who]).revision
        return BookingDraftCreate(
            client_action_id=str(uuid4()),
            session_id=self.sessions[who],
            expected_session_revision=revision,
            ref=ref(),
            appointment=self.appointment() if complete else None,
        )

    def appointment(self) -> AppointmentSelection:
        return AppointmentSelection(
            starts_at_utc=utc_text(self.base.clock.value + timedelta(days=1))
        )

    def counts(self) -> tuple[int, ...]:
        return self.base.store.read(
            lambda db: tuple(
                db.scalar(select(func.count()).select_from(model)) or 0
                for model in (
                    DraftRow,
                    BookingReview,
                    Booking,
                    Lead,
                    ExportIntent,
                    OperationOutcome,
                )
            )
        )


def make_draft_harness() -> DraftHarness:
    base = make_harness()
    sessions = (base.create(0).session_id, base.create(1).session_id)
    resources = {source: str(uuid4()) for source in ("12", "13")}
    rules = ViewingRules(base.settings.policy)

    def seed(db: Session) -> None:
        active = db.get(ActiveInventory, 1)
        snapshot = db.get(InventorySnapshot, ref().snapshot_id)
        assert active is not None and snapshot is not None
        db.delete(active)
        db.flush()
        snapshot.index_version = "e" * 64
        db.flush()
        db.add(
            ActiveInventory(id=1, snapshot_id=ref().snapshot_id, index_version="e" * 64, revision=1)
        )
        profile = db.get(InventoryStorageProfile, 1)
        assert profile is not None
        for resource in resources.values():
            db.add(
                VehicleResource(
                    id=resource,
                    mapping_version="synthetic-mapping-1",
                    created_at=utc_text(base.clock.value),
                )
            )
        db.flush()
        for source, resource in resources.items():
            db.add(
                ListingResourceMapping(
                    **ref(source).model_dump(),
                    resource_id=resource,
                    mapping_version="synthetic-mapping-1",
                    provenance_json={"synthetic_only": True},
                )
            )
        configuration = ViewingConfiguration(
            format="viewing-configuration-1",
            calendar_version=rules.version,
            policy=base.settings.policy,
            venue_label=VIEWING_VENUE,
            eligibility=EligibilityPolicy(
                version="synthetic-permission-1", eligible_refs=(ref(), ref("13"))
            ),
            inventory=InventoryObservation.model_validate(
                dict(
                    generation=base.store.generation,
                    active_revision=1,
                    snapshot_id=ref().snapshot_id,
                    index_version="e" * 64,
                    mode=profile.mode,
                )
            ),
            mapping_digest="f" * 64,
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
        db.add(ActiveRules(id=1, version=version, revision=1))

    base.store.write(seed)
    inventory = SyntheticDraftInventory(base, resources)
    return DraftHarness(base, DraftService(base.auth, inventory=inventory), inventory, sessions)


def update(draft: BookingDraft, intent: str, **changes: object) -> BookingDraftUpdate:
    return BookingDraftUpdate.model_validate(
        dict(
            client_action_id=str(uuid4()),
            expected_revision=draft.revision,
            intent=intent,
            **changes,
        )
    )


def confirmation(draft: BookingDraft) -> ConfirmRequest:
    review = draft.review
    assert review is not None
    return ConfirmRequest(
        review_id=review.review_id,
        expected_draft_revision=draft.revision,
        operation_key=review.operation_key,
        rules_version=review.rules_version,
        store_generation=review.store_generation,
        confirmation="confirm_simulated_viewing",
    )
