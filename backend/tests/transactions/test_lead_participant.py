"""Caller-unit atomicity cases; staged bookings are not BE15 acceptance evidence."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.schemas.leads import LeadRecord, ReviewedExistingLead, ReviewedLeadCreation
from app.core.errors import ApiFailure
from app.database.models import ActiveInventory, Booking, ConversationSession, ExportState
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.leads.participant import ParticipatingLead
from app.shortlist.inventory import prepare
from tests.platform.session_cases import ref
from tests.transactions.lead_fixtures import (
    LeadHarness,
    buyer_values,
    correction,
    make_lead_harness,
    save_request,
    staged_booking,
)


@pytest.fixture
def leads() -> LeadHarness:
    return make_lead_harness()


def creation(leads: LeadHarness) -> ReviewedLeadCreation:
    def read(db: Session) -> int:
        row = db.get(ConversationSession, leads.session_ids[0])
        assert row is not None
        return row.revision

    revision = leads.sessions.store.read(read)
    return ReviewedLeadCreation(
        mode="create_from_review",
        values=buyer_values(),
        source_session_revision=revision,
    )


def test_participant_creates_lead_link_and_outbox_only_with_actual_booking(
    leads: LeadHarness,
) -> None:
    change = creation(leads)

    def write(unit: OwnerUnit) -> ParticipatingLead:
        accepted = staged_booking(leads, unit, change)
        return leads.participant.apply(
            unit,
            accepted=accepted,
            generation=leads.sessions.store.generation,
            now=utc_text(leads.sessions.clock.value),
            retention_days=90,
        )

    result = leads.sessions.auth.write(leads.sessions.context(), write)
    assert result.lead.state == "saved" and result.lead.revision == 1
    assert result.csv.state == "pending" and result.csv.canonical_version == 1
    current = leads.service.get(leads.sessions.context())
    assert isinstance(current, LeadRecord)
    assert current.stage == "viewing_confirmed" and len(current.booking_ids) == 1
    assert current.values == change.values and current.delivery == "local_only"
    assert leads.counts() == (1, 1, 1, 1, 0)


def test_caller_failure_after_participation_rolls_everything_back(leads: LeadHarness) -> None:
    change = creation(leads)

    def write(unit: OwnerUnit) -> None:
        accepted = staged_booking(leads, unit, change)
        provisional = leads.participant.apply(
            unit,
            accepted=accepted,
            generation=leads.sessions.store.generation,
            now=utc_text(leads.sessions.clock.value),
            retention_days=90,
        )
        assert provisional.lead.state == "saved"
        raise StoreError("SYNTHETIC_CALLER_FAILURE_AFTER_PARTICIPANT")

    with pytest.raises(StoreError, match="SYNTHETIC_CALLER_FAILURE"):
        leads.sessions.auth.write(leads.sessions.context(), write)
    assert leads.counts() == (0, 0, 0, 0, 0)
    assert leads.sessions.store.read(lambda db: db.get(ExportState, 1) is None)


def test_participant_never_commits_its_session(
    leads: LeadHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_commit(self: Session) -> None:
        raise AssertionError("PARTICIPANT_MUST_NOT_COMMIT")

    monkeypatch.setattr(Session, "commit", forbidden_commit)
    change = creation(leads)

    def write(unit: OwnerUnit) -> ParticipatingLead:
        accepted = staged_booking(leads, unit, change)
        return leads.participant.apply(
            unit,
            accepted=accepted,
            generation=leads.sessions.store.generation,
            now=utc_text(leads.sessions.clock.value),
            retention_days=90,
        )

    leads.sessions.auth.write(leads.sessions.context(), write)
    assert leads.counts() == (1, 1, 1, 1, 0)


def test_preserve_existing_advances_only_stage_link_revision(leads: LeadHarness) -> None:
    initial = leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0]))
    change = ReviewedExistingLead(
        mode="preserve_existing",
        lead_id=initial.lead.lead_id,
        expected_revision=1,
    )

    def write(unit: OwnerUnit) -> ParticipatingLead:
        accepted = staged_booking(leads, unit, change)
        return leads.participant.apply(
            unit,
            accepted=accepted,
            generation=leads.sessions.store.generation,
            now=utc_text(leads.sessions.clock.value),
            retention_days=90,
        )

    result = leads.sessions.auth.write(leads.sessions.context(), write)
    assert result.lead.lead_id == initial.lead.lead_id and result.lead.revision == 2
    current = leads.service.get(leads.sessions.context())
    assert isinstance(current, LeadRecord) and current.values == initial.lead.values
    assert current.stage == "viewing_confirmed"
    corrected = leads.service.update(
        leads.sessions.context(),
        current.lead_id,
        correction(leads.session_ids[0], 2, buyer_values()),
    )
    assert corrected.lead.stage == "viewing_confirmed"
    assert corrected.lead.booking_ids == current.booking_ids
    assert result.lead.revision == 2  # Accepted participation facts do not follow later edits.
    assert leads.counts() == (1, 3, 1, 1, 2)


@pytest.mark.parametrize("race", ["lead_created", "session_changed", "lead_corrected"])
def test_stale_review_has_no_participant_or_booking_effect(leads: LeadHarness, race: str) -> None:
    change: ReviewedLeadCreation | ReviewedExistingLead = creation(leads)
    if race in {"lead_created", "lead_corrected"}:
        initial = leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0]))
        if race == "lead_corrected":
            change = ReviewedExistingLead(
                mode="preserve_existing",
                lead_id=initial.lead.lead_id,
                expected_revision=1,
            )
            leads.service.update(
                leads.sessions.context(),
                initial.lead.lead_id,
                correction(leads.session_ids[0], 1, buyer_values()),
            )
    else:

        def advance(db: Session) -> None:
            row = db.get(ConversationSession, leads.session_ids[0])
            assert row is not None
            row.revision += 1

        leads.sessions.store.write(advance)
    before = leads.counts()

    def write(unit: OwnerUnit) -> ParticipatingLead:
        accepted = staged_booking(leads, unit, change)
        return leads.participant.apply(
            unit,
            accepted=accepted,
            generation=leads.sessions.store.generation,
            now=utc_text(leads.sessions.clock.value),
            retention_days=90,
        )

    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        leads.sessions.auth.write(leads.sessions.context(), write)
    assert leads.counts() == before


def test_second_participation_is_not_an_operation_replay(leads: LeadHarness) -> None:
    change = creation(leads)

    def write(unit: OwnerUnit) -> None:
        accepted = staged_booking(leads, unit, change)
        for _ in range(2):
            leads.participant.apply(
                unit,
                accepted=accepted,
                generation=leads.sessions.store.generation,
                now=utc_text(leads.sessions.clock.value),
                retention_days=90,
            )

    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        leads.sessions.auth.write(leads.sessions.context(), write)
    assert leads.counts() == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("fault", ["absent_booking", "receipt", "generation", "foreign_session"])
def test_untrusted_accepted_context_cannot_raise_stage(leads: LeadHarness, fault: str) -> None:
    change = creation(leads)

    def write(unit: OwnerUnit) -> ParticipatingLead:
        accepted = staged_booking(
            leads,
            unit,
            change,
            session_id=leads.session_ids[1] if fault == "foreign_session" else None,
        )
        generation = leads.sessions.store.generation
        if fault == "absent_booking":
            row = unit.db.get(Booking, accepted.booking_id)
            assert row is not None
            unit.db.delete(row)
            unit.db.flush()
        elif fault == "receipt":
            accepted.review.lead_change = ReviewedLeadCreation(
                mode="create_from_review",
                values=buyer_values(),
                source_session_revision=999,
            )
        elif fault == "generation":
            generation = str(uuid4())
        return leads.participant.apply(
            unit,
            accepted=accepted,
            generation=generation,
            now=utc_text(leads.sessions.clock.value),
            retention_days=90,
        )

    with pytest.raises((ApiFailure, StoreError)):
        leads.sessions.auth.write(leads.sessions.context(), write)
    assert leads.counts() == (0, 0, 0, 0, 0)


def test_read_unit_rejects_participation_before_effects(leads: LeadHarness) -> None:
    change = creation(leads)
    accepted = leads.sessions.auth.write(
        leads.sessions.context(),
        lambda unit: staged_booking(leads, unit, change),
    )
    with pytest.raises(StoreError, match="LEAD_REQUIRES_CALLER_WRITE_UNIT"):
        leads.sessions.auth.read(
            leads.sessions.context(write=False),
            lambda unit: leads.participant.apply(
                unit,
                accepted=accepted,
                generation=leads.sessions.store.generation,
                now=utc_text(leads.sessions.clock.value),
                retention_days=90,
            ),
        )
    assert leads.counts() == (0, 0, 0, 1, 0)


@pytest.mark.parametrize("mode", ["valid", "mismatch", "stale", "missing"])
def test_participant_prepared_refs_are_required_and_rechecked(
    leads: LeadHarness,
    mode: str,
) -> None:
    change = creation(leads)
    change.values.selected_refs = [ref()]
    prepared = prepare(
        leads.inventory,
        (ref("13") if mode == "mismatch" else ref(),),
        leads.sessions.store.generation,
    )
    if mode == "stale":

        def advance(db: Session) -> None:
            active = db.get(ActiveInventory, 1)
            assert active is not None
            active.revision += 1

        leads.sessions.store.write(advance)

    def write(unit: OwnerUnit) -> ParticipatingLead:
        accepted = staged_booking(leads, unit, change)
        return leads.participant.apply(
            unit,
            accepted=accepted,
            generation=leads.sessions.store.generation,
            now=utc_text(leads.sessions.clock.value),
            retention_days=90,
            prepared=None if mode == "missing" else prepared,
        )

    if mode == "valid":
        leads.sessions.auth.write(leads.sessions.context(), write)
        current = leads.service.get(leads.sessions.context())
        assert isinstance(current, LeadRecord)
        assert [item.model_dump() for item in current.values.selected_refs] == [ref().model_dump()]
        assert leads.inventory.checks == 1
        assert leads.counts() == (1, 1, 1, 1, 0)
    else:
        with pytest.raises(ApiFailure):
            leads.sessions.auth.write(leads.sessions.context(), write)
        assert leads.counts() == (0, 0, 0, 0, 0)
