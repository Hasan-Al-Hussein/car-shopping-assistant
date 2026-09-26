"""BE17 source cases: real authorization/Store, synthetic users and Inventory port."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.leads import BudgetValue, ContactValue, LeadRecord, NoLead
from app.core.errors import ApiFailure
from app.database.models import (
    ActiveInventory,
    CommandReceipt,
    ConversationSession,
    ExportState,
    Lead,
)
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.leads import repository as repo
from app.leads.service import LeadService
from tests.platform.session_cases import ref
from tests.transactions.lead_fixtures import (
    LeadHarness,
    buyer_values,
    correction,
    make_lead_harness,
    save_request,
)


@pytest.fixture
def leads() -> LeadHarness:
    return make_lead_harness()


def test_get_empty_is_observational(leads: LeadHarness) -> None:
    before = leads.counts()
    context = leads.sessions.context(write=False)
    assert leads.service.get(context) == NoLead(state="not_created")
    assert leads.service.get(context) == NoLead(state="not_created")
    assert leads.counts() == before == (0, 0, 0, 0, 0)
    assert leads.inventory.reads == 0
    assert leads.sessions.store.read(lambda db: db.get(ExportState, 1) is None)


@pytest.mark.parametrize("budget_state", ["missing", "declined", "provided"])
def test_explicit_partial_save_preserves_states_and_zero(
    leads: LeadHarness,
    budget_state: str,
) -> None:
    supplied = buyer_values()
    supplied.budget = BudgetValue.model_validate(
        {
            "state": budget_state,
            "value": {"minimum": 0, "maximum": 0, "currency": "AED", "basis": "cash"}
            if budget_state == "provided"
            else None,
        }
    )
    supplied.email = ContactValue(state="provided", value="=synthetic@example.invalid\nعربي")
    result = leads.service.save(
        leads.sessions.context(), save_request(leads.session_ids[0], supplied)
    )
    assert result.lead.values == supplied
    assert result.lead.stage == "interested" and result.lead.booking_ids == []
    assert result.lead.delivery == "local_only" and not result.replayed
    assert result.lead.csv.state == "pending"
    assert result.lead.revision == result.lead.csv.canonical_version == 1
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_new_command_is_create_only_across_new_sessions(leads: LeadHarness) -> None:
    command = save_request(leads.session_ids[0])
    first = leads.service.save(leads.sessions.context(), command)
    new_session = leads.sessions.create(0)
    with pytest.raises(ApiFailure, match="LEAD_EXISTS"):
        leads.service.save(leads.sessions.context(), save_request(new_session.session_id))
    assert new_session.journey_id == first.lead.journey_id
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_corrections_same_lead_and_stale_tab_rejected(leads: LeadHarness) -> None:
    context = leads.sessions.context()
    first = leads.service.save(context, save_request(leads.session_ids[0]))
    new_session = leads.sessions.create(0)
    supplied = buyer_values()
    supplied.email = ContactValue(state="declined")
    supplied.requirements = ["Corrected explicit buyer need"]
    change = correction(new_session.session_id, first.lead.revision, supplied)
    second = leads.service.update(context, first.lead.lead_id, change)
    assert second.lead.lead_id == first.lead.lead_id
    assert second.lead.revision == 2 and second.lead.values == supplied
    with pytest.raises(ApiFailure, match="LEAD_REVISION_CONFLICT"):
        leads.service.update(
            context, first.lead.lead_id, correction(new_session.session_id, 1, buyer_values())
        )
    assert leads.counts() == (1, 2, 0, 0, 2)

    def provenance(unit: OwnerUnit) -> tuple[str, str]:
        row = unit.lead(first.lead.lead_id)
        return row.source_session_reference, row.created_at

    original, created = leads.sessions.auth.read(context, provenance)
    assert original == leads.session_ids[0]
    assert created == first.lead.updated_at


def test_replay_original_facts_after_later_correction_with_current_csv(leads: LeadHarness) -> None:
    context = leads.sessions.context()
    command = save_request(leads.session_ids[0])
    first = leads.service.save(context, command)
    supplied = buyer_values()
    supplied.requirements = ["Second accepted revision"]
    change = correction(leads.session_ids[0], 1, supplied)
    leads.service.update(context, first.lead.lead_id, change)
    before = leads.counts()
    replay = leads.service.save(context, command)
    assert replay.replayed and replay.lead.revision == 1
    assert replay.lead.values == first.lead.values
    assert replay.lead.csv.canonical_version == 2
    current = leads.service.get(context)
    assert isinstance(current, LeadRecord) and current.revision == 2
    assert leads.service.update(context, first.lead.lead_id, change).replayed
    assert leads.counts() == before


@pytest.mark.parametrize("changed", ["values", "session", "kind"])
def test_reused_action_payload_conflicts(leads: LeadHarness, changed: str) -> None:
    context = leads.sessions.context()
    command = save_request(leads.session_ids[0])
    first = leads.service.save(context, command)
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        if changed == "kind":
            update = correction(command.session_id, 1, command.values)
            update.client_action_id = command.client_action_id
            leads.service.update(context, first.lead.lead_id, update)
        else:
            retry = command.model_copy(deep=True)
            if changed == "values":
                retry.values.requirements.append("Different payload")
            else:
                retry.session_id = leads.session_ids[1]
            leads.service.save(context, retry)
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_owned_reads_and_payload_bound_commands_do_not_cross_buyers(leads: LeadHarness) -> None:
    command = save_request(leads.session_ids[0])
    first = leads.service.save(leads.sessions.context(0), command)
    other = leads.sessions.context(1)
    assert leads.service.get(other) == NoLead(state="not_created")
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        leads.service.save(other, command)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        leads.service.update(
            other, first.lead.lead_id, correction(leads.session_ids[1], 1, buyer_values())
        )
    independent = save_request(leads.session_ids[1])
    independent.client_action_id = command.client_action_id
    second = leads.service.save(other, independent)
    assert second.lead.lead_id != first.lead.lead_id
    assert second.lead.revision == 1 and second.lead.csv.canonical_version == 2
    assert leads.counts() == (2, 2, 0, 0, 2)


def test_read_authority_cannot_capture(leads: LeadHarness) -> None:
    with pytest.raises(ApiFailure, match="CSRF_DENIED"):
        leads.service.save(leads.sessions.context(write=False), save_request(leads.session_ids[0]))
    assert leads.counts() == (0, 0, 0, 0, 0)


def test_session_expiry_does_not_expire_lead_read_or_exact_replay(leads: LeadHarness) -> None:
    command = save_request(leads.session_ids[0])
    first = leads.service.save(leads.sessions.context(), command)
    leads.sessions.clock.value += timedelta(days=8)
    context = leads.sessions.context()
    assert leads.service.get(context) == first.lead.model_copy(
        update={
            "csv": first.lead.csv.model_copy(
                update={"observed_at": utc_text(leads.sessions.clock.value)}
            ),
        }
    )
    assert leads.service.save(context, command).replayed
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        leads.service.update(
            context, first.lead.lead_id, correction(command.session_id, 1, buyer_values())
        )
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_read_and_replay_survive_origin_session_deletion(leads: LeadHarness) -> None:
    command = save_request(leads.session_ids[0])
    first = leads.service.save(leads.sessions.context(), command)

    def remove(db: Session) -> None:
        session = db.get(ConversationSession, command.session_id)
        assert session is not None
        db.delete(session)

    leads.sessions.store.write(remove)
    assert leads.service.save(leads.sessions.context(), command).replayed
    assert isinstance(leads.service.get(leads.sessions.context()), LeadRecord)
    assert first.lead.values == buyer_values()


def test_expired_receipt_and_restore_generation_never_reapply(leads: LeadHarness) -> None:
    command = save_request(leads.session_ids[0])
    leads.service.save(leads.sessions.context(), command)

    def mutate(db: Session, *, generation: bool) -> None:
        row = db.scalar(select(CommandReceipt).where(CommandReceipt.command_kind == repo.KIND))
        assert row is not None
        if generation:
            row.result_json = {**row.result_json, "store_generation": str(uuid4())}
        else:
            row.expires_at = utc_text(leads.sessions.clock.value)

    leads.sessions.store.write(lambda db: mutate(db, generation=True))
    with pytest.raises(ApiFailure, match="STORE_GENERATION_CHANGED"):
        leads.service.save(leads.sessions.context(), command)
    leads.sessions.store.write(lambda db: mutate(db, generation=False))
    with pytest.raises(ApiFailure, match="REPLAY_EXPIRED"):
        leads.service.save(leads.sessions.context(), command)
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_inventory_unavailable_does_not_masquerade_as_missing_or_write(leads: LeadHarness) -> None:
    supplied = buyer_values()
    supplied.selected_refs = [ref()]
    service = LeadService(leads.sessions.auth)
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        service.save(leads.sessions.context(), save_request(leads.session_ids[0], supplied))
    assert leads.counts() == (0, 0, 0, 0, 0)


def test_exact_reference_preparation_rechecks_inside_write(leads: LeadHarness) -> None:
    supplied = buyer_values()
    supplied.selected_refs = [ref()]
    command = save_request(leads.session_ids[0], supplied)
    result = leads.service.save(leads.sessions.context(), command)
    assert [item.model_dump() for item in result.lead.values.selected_refs] == [ref().model_dump()]
    assert leads.inventory.reads == leads.inventory.checks == 1
    leads.service.inventory = None
    assert leads.service.save(leads.sessions.context(), command).replayed
    assert leads.inventory.reads == 1


def test_inventory_activation_race_rolls_back_capture(leads: LeadHarness) -> None:
    def switch() -> None:
        def write(db: Session) -> None:
            active = db.get(ActiveInventory, 1)
            assert active is not None
            active.revision += 1

        leads.sessions.store.write(write)

    leads.inventory.after_read = switch
    supplied = buyer_values()
    supplied.selected_refs = [ref()]
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0], supplied))
    assert leads.counts() == (0, 0, 0, 0, 0)


def test_failure_after_lead_and_intent_rolls_back_both(
    leads: LeadHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise StoreError("SYNTHETIC_RECEIPT_FAILURE")

    monkeypatch.setattr(repo, "remember", fail)
    with pytest.raises(StoreError, match="SYNTHETIC_RECEIPT_FAILURE"):
        leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0]))
    assert leads.counts() == (0, 0, 0, 0, 0)
    assert leads.sessions.store.read(lambda db: db.get(ExportState, 1) is None)


@pytest.mark.parametrize("fault", ["missing", "generation", "false_current"])
def test_projection_failure_does_not_create_or_repair_on_read(
    leads: LeadHarness, fault: str
) -> None:
    leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0]))

    def damage(db: Session) -> None:
        state = db.get(ExportState, 1)
        assert state is not None
        if fault == "missing":
            db.delete(state)
        elif fault == "generation":
            state.store_generation = str(uuid4())
        else:
            state.state = "current"

    leads.sessions.store.write(damage)
    with pytest.raises(StoreError):
        leads.service.get(leads.sessions.context(write=False))
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_supplied_values_are_detached_before_inventory_callback(leads: LeadHarness) -> None:
    supplied = buyer_values()
    supplied.selected_refs = [ref()]
    command = save_request(leads.session_ids[0], supplied)
    leads.inventory.after_read = lambda: command.values.requirements.append("Late mutation")
    result = leads.service.save(leads.sessions.context(), command)
    assert "Late mutation" not in result.lead.values.requirements


def test_unverified_or_implicit_intent_is_rejected_without_coercion(leads: LeadHarness) -> None:
    command = save_request(leads.session_ids[0])
    for tampered in (
        command.model_copy(update={"intent": "save_shortlist"}),
        command.model_copy(
            update={
                "values": command.values.model_copy(
                    update={
                        "phone": ContactValue(state="missing").model_copy(
                            update={"state": "unverified", "value": "seller text"}
                        ),
                    }
                )
            }
        ),
    ):
        with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
            leads.service.save(leads.sessions.context(), tampered)
    assert leads.counts() == (0, 0, 0, 0, 0)


def test_expired_canonical_row_is_not_empty_or_overwritten(leads: LeadHarness) -> None:
    result = leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0]))

    def expire(db: Session) -> None:
        row = db.get(Lead, result.lead.lead_id)
        assert row is not None
        row.expires_at = utc_text(leads.sessions.clock.value)

    leads.sessions.store.write(expire)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        leads.service.get(leads.sessions.context())
    with pytest.raises(ApiFailure, match="LEAD_EXISTS"):
        leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0]))
    assert leads.counts() == (1, 1, 0, 0, 1)


@pytest.mark.parametrize("empty_state", ["current", "pending"])
def test_first_capture_advances_initialized_empty_projection(
    leads: LeadHarness,
    empty_state: str,
) -> None:
    leads.sessions.store.write(
        lambda db: db.add(
            ExportState(
                id=1,
                store_generation=leads.sessions.store.generation,
                canonical_version=0,
                exported_version=0 if empty_state == "current" else None,
                state=empty_state,
                updated_at=utc_text(leads.sessions.clock.value),
            )
        )
    )
    assert leads.service.get(leads.sessions.context()) == NoLead(state="not_created")
    result = leads.service.save(leads.sessions.context(), save_request(leads.session_ids[0]))
    assert result.lead.csv.state == "pending" and result.lead.csv.canonical_version == 1
    assert result.lead.csv.exported_version == (0 if empty_state == "current" else None)
    assert leads.counts() == (1, 1, 0, 0, 1)


def test_new_revision_renews_lead_but_never_old_receipt_or_replay(leads: LeadHarness) -> None:
    original_time = leads.sessions.clock.value
    command = save_request(leads.session_ids[0])
    first = leads.service.save(leads.sessions.context(), command)
    leads.sessions.clock.value += timedelta(days=1)
    update = correction(command.session_id, 1, buyer_values())
    second = leads.service.update(leads.sessions.context(), first.lead.lead_id, update)
    assert second.lead.revision == 2 and second.lead.values == first.lead.values
    assert second.lead.expires_at == utc_text(original_time + timedelta(days=91))

    def receipt_expiries(db: Session) -> list[str]:
        return list(
            db.scalars(
                select(CommandReceipt.expires_at)
                .where(
                    CommandReceipt.command_kind == repo.KIND,
                )
                .order_by(CommandReceipt.created_at)
            )
        )

    assert leads.sessions.store.read(receipt_expiries) == [
        utc_text(original_time + timedelta(days=90)),
        utc_text(original_time + timedelta(days=91)),
    ]
    leads.sessions.clock.value += timedelta(minutes=2)
    replay = leads.service.save(leads.sessions.context(), command)
    assert replay.lead.expires_at == first.lead.expires_at
    current = leads.service.get(leads.sessions.context())
    assert isinstance(current, LeadRecord) and current.expires_at == second.lead.expires_at
    assert leads.sessions.store.read(receipt_expiries)[0] == first.lead.expires_at
