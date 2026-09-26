"""Authored real-service caller-unit cases; all execution remains separately gated."""

from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.schemas.leads import ContactValue, LeadValues, ReviewedLeadCreation
from app.api.schemas.sessions import ClarificationIntent
from app.core.errors import ApiFailure
from app.database.models import CommandReceipt, ExportState, Message
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.leads import repository as lead_repo
from app.leads.changes import (
    LeadCommandAbsent,
    LeadCommandExpired,
    LeadCommandKnown,
    LeadCommandUnreconciled,
    PreparedLeadChange,
)
from app.sessions.state import SessionContent
from tests.platform.session_cases import answer, ref
from tests.transactions.confirmation_fixtures import make_confirmation_harness
from tests.transactions.conversational_fixtures import begin, facts, finish_in_unit
from tests.transactions.draft_fixtures import DraftHarness, confirmation, make_draft_harness, update
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


@pytest.fixture
def drafts() -> DraftHarness:
    return make_draft_harness()


def test_chat_lead_and_message_commit_together_then_exact_message_replays(leads: LeadHarness) -> None:
    base, service = leads.sessions, leads.service
    admission = begin(base, leads.session_ids[0])
    command = save_request(leads.session_ids[0])
    prepared = service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange) and prepared.references is None

    def commit(unit: OwnerUnit) -> Any:
        initial = unit.session(command.session_id).revision
        result = service.change_in_unit(
            unit, command, submitted_generation=base.store.generation,
            generation=base.store.generation, now=utc_text(base.clock.now()), prepared=prepared,
            source_message_id=admission.message_id,
        )
        assert unit.session(command.session_id).revision == initial
        return finish_in_unit(unit, admission, lead=result, action_id=command.client_action_id)

    result = base.auth.write(base.context(), commit)
    assert result.actions.lead.state == "succeeded"
    assert result.actions.lead.result.lead.values == command.values
    before = facts(base)
    replay = base.service.begin(base.context(), command.session_id, admission.request)
    assert replay.status == "completed" and replay.result == result
    assert facts(base) == before and leads.counts() == (1, 1, 0, 0, 1)
    # Direct UI shares the exact command receipt and does not repeat the effect.
    assert service.save(base.context(), command).replayed
    assert facts(base) == before


@pytest.mark.parametrize("fail_after_message", [False, True])
def test_lead_and_message_roll_back_together(
    leads: LeadHarness, fail_after_message: bool,
) -> None:
    base = leads.sessions
    admission = begin(base, leads.session_ids[0])
    command = save_request(leads.session_ids[0])
    prepared = leads.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange)
    before = facts(base)

    def fail(unit: OwnerUnit) -> None:
        result = leads.service.change_in_unit(
            unit, command, submitted_generation=base.store.generation,
            generation=base.store.generation, now=utc_text(base.clock.now()), prepared=prepared,
            source_message_id=admission.message_id,
        )
        if fail_after_message:
            finish_in_unit(unit, admission, lead=result, action_id=command.client_action_id)
        raise RuntimeError("synthetic later completion failure")

    with pytest.raises(RuntimeError, match="synthetic later"):
        base.auth.write(base.context(), fail)
    assert facts(base) == before


def test_postmutation_projection_limit_aborts_instead_of_partial_rejection(leads: LeadHarness) -> None:
    base = leads.sessions
    admission = begin(base, leads.session_ids[0])
    base.store.write(lambda db: db.add(ExportState(
        id=1, store_generation=base.store.generation, canonical_version=lead_repo.MAX_REVISION,
        exported_version=None, state="pending", updated_at=utc_text(base.clock.now()),
    )))
    command = save_request(leads.session_ids[0])
    prepared = leads.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange)
    before = facts(base)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        base.auth.write(base.context(), lambda unit: leads.service.change_in_unit(
            unit, command, submitted_generation=base.store.generation,
            generation=base.store.generation, now=utc_text(base.clock.now()), prepared=prepared,
            source_message_id=admission.message_id,
        ))
    assert facts(base) == before and leads.counts()[0] == 0


@pytest.mark.parametrize("tamper", ["none", "message", "owner", "command", "generation"])
def test_prepared_lead_binding_is_required_and_exact(leads: LeadHarness, tamper: str) -> None:
    base = leads.sessions
    admission = begin(base, leads.session_ids[0])
    command = save_request(leads.session_ids[0])
    prepared = leads.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange)
    changes = {
        "message": {"source_message_id": str(uuid4())},
        "owner": {"owner_id": str(uuid4())},
        "command": {"command_json": b"{}"},
        "generation": {"submitted_store_generation": str(uuid4())},
    }
    candidate = None if tamper == "none" else replace(
        prepared, envelope=replace(prepared.envelope, **changes[tamper])
    )
    before = facts(base)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        base.auth.write(base.context(), lambda unit: leads.service.change_in_unit(
            unit, command, submitted_generation=base.store.generation,
            generation=base.store.generation, now=utc_text(base.clock.now()), prepared=candidate,
            source_message_id=admission.message_id,
        ))
    assert facts(base) == before


def test_superseded_message_cannot_apply_prepared_lead(leads: LeadHarness) -> None:
    base = leads.sessions
    admission = begin(base, leads.session_ids[0])
    command = save_request(leads.session_ids[0])
    prepared = leads.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange)
    begin(base, leads.session_ids[0])
    before = facts(base)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        base.auth.write(base.context(), lambda unit: leads.service.change_in_unit(
            unit, command, submitted_generation=base.store.generation,
            generation=base.store.generation, now=utc_text(base.clock.now()), prepared=prepared,
            source_message_id=admission.message_id,
        ))
    assert facts(base) == before


@pytest.mark.parametrize("field", ["email", "phone"])
def test_chat_cannot_create_provided_contacts(leads: LeadHarness, field: str) -> None:
    base = leads.sessions
    admission = begin(base, leads.session_ids[0])
    values = buyer_values().model_dump(mode="json")
    values[field] = {"state": "provided", "value": "synthetic-form-only"}
    before = facts(base)
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        leads.service.prepare_change(
            base.context(), save_request(leads.session_ids[0], LeadValues.model_validate(values)),
            submitted_generation=base.store.generation, source_message_id=admission.message_id,
        )
    assert facts(base) == before


@pytest.mark.parametrize("erase", [False, True])
def test_noncontact_chat_correction_preserves_form_contact(leads: LeadHarness, erase: bool) -> None:
    base = leads.sessions
    values = buyer_values()
    values.email = ContactValue(state="provided", value="synthetic@example.invalid")
    saved = leads.service.save(base.context(), save_request(leads.session_ids[0], values)).lead
    admission = begin(base, leads.session_ids[0])
    revised = saved.values.model_copy(deep=True)
    revised.requirements = ["An explicit new non-contact requirement"]
    if erase:
        revised.email = ContactValue(state="missing")
    command = correction(leads.session_ids[0], saved.revision, revised)
    before = facts(base)
    if erase:
        with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
            leads.service.prepare_change(
                base.context(), command, lead_id=saved.lead_id,
                submitted_generation=base.store.generation, source_message_id=admission.message_id,
            )
        assert facts(base) == before
        return
    prepared = leads.service.prepare_change(
        base.context(), command, lead_id=saved.lead_id,
        submitted_generation=base.store.generation, source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange)
    result = base.auth.write(base.context(), lambda unit: leads.service.change_in_unit(
        unit, command, lead_id=saved.lead_id, submitted_generation=base.store.generation,
        generation=base.store.generation, now=utc_text(base.clock.now()), prepared=prepared,
        source_message_id=admission.message_id,
    ))
    assert result.lead.values.email == saved.values.email
    assert result.lead.values.requirements == revised.requirements


def test_exact_lead_proof_survives_csv_failure_and_source_message_deletion(leads: LeadHarness) -> None:
    base = leads.sessions
    admission = begin(base, leads.session_ids[0])
    command = save_request(leads.session_ids[0])
    prepared = leads.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange)
    saved = base.auth.write(base.context(), lambda unit: leads.service.change_in_unit(
        unit, command, submitted_generation=base.store.generation,
        generation=base.store.generation, now=utc_text(base.clock.now()), prepared=prepared,
        source_message_id=admission.message_id,
    ))

    def remove(db: Session) -> None:
        db.execute(delete(Message).where(Message.id == admission.message_id))
        db.execute(delete(ExportState))

    base.store.write(remove)
    observation = base.auth.read(base.context(), lambda unit: leads.service.lookup_change_in_unit(
        unit, command, submitted_generation=base.store.generation,
        observed_generation=base.store.generation, now=utc_text(base.clock.now()),
        source_message_id=admission.message_id,
    ))
    assert isinstance(observation, LeadCommandKnown)
    assert observation.accepted == saved.lead and observation.csv_basis == "receipt_snapshot"
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        base.auth.read(base.context(), lambda unit: leads.service.lookup_change_in_unit(
            unit, command, submitted_generation=base.store.generation,
            observed_generation=base.store.generation, now=utc_text(base.clock.now()),
            source_message_id=str(uuid4()),
        ))


def test_lead_absence_expiry_and_historical_generation_never_authorize_new_key(leads: LeadHarness) -> None:
    base = leads.sessions
    command = save_request(leads.session_ids[0])

    def observe(generation: str) -> Any:
        return base.auth.read(base.context(), lambda unit: leads.service.lookup_change_in_unit(
            unit, command, submitted_generation=generation, observed_generation=base.store.generation,
            now=utc_text(base.clock.now()),
        ))

    absent = observe(base.store.generation)
    assert isinstance(absent, LeadCommandAbsent) and not absent.definitive_noncommit
    old = str(uuid4())
    assert isinstance(observe(old), LeadCommandUnreconciled)
    leads.service.save(base.context(), command)

    def historical(db: Session) -> None:
        row = db.scalar(select(CommandReceipt).where(CommandReceipt.client_action_id == command.client_action_id))
        assert row is not None
        value = dict(row.result_json)
        value["store_generation"] = old
        lead = dict(value["lead"])
        lead["csv"] = {**lead["csv"], "store_generation": old}
        value["lead"] = lead
        row.result_json = value

    base.store.write(historical)  # Synthetic receipt metadata, not actual restore/credential proof.
    known = observe(old)
    assert isinstance(known, LeadCommandKnown) and known.generation_relation == "historical_generation"
    before = facts(base)
    with pytest.raises(ApiFailure, match="STORE_GENERATION_CHANGED"):
        base.auth.write(base.context(), lambda unit: leads.service.change_in_unit(
            unit, command, submitted_generation=old, generation=base.store.generation,
            now=utc_text(base.clock.now()), prepared=None,
        ))
    assert facts(base) == before
    # Move only the observation time so credential expiry cannot mask this branch.
    expired = base.auth.read(base.context(), lambda unit: leads.service.lookup_change_in_unit(
        unit, command, submitted_generation=old, observed_generation=base.store.generation,
        now=utc_text(base.clock.now() + timedelta(days=91)),
    ))
    assert isinstance(expired, LeadCommandExpired) and not hasattr(expired, "accepted")


def test_chat_draft_binds_final_revision_and_ui_observes_same_review(drafts: DraftHarness) -> None:
    base = drafts.base
    admission = begin(base, drafts.sessions[0])
    command = drafts.command()
    prepared = drafts.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert prepared is not None

    def commit(unit: OwnerUnit) -> Any:
        row = unit.session(command.session_id)
        accepted = row.revision
        effect = drafts.service.change_in_unit(
            unit, command, generation=base.store.generation, submitted_generation=base.store.generation,
            now=utc_text(base.clock.now()), prepared=prepared, final_session_revision=accepted + 1,
            source_message_id=admission.message_id,
        )
        assert row.revision == accepted and effect.transition is not None
        drafts.service.resolve_session_in_unit(unit, transition=effect.transition)
        assert row.revision == accepted
        row.revision = effect.transition.final_revision
        viewed = drafts.service.observe_changed_in_unit(
            unit, effect=effect, generation=base.store.generation, now=utc_text(base.clock.now()),
        )
        message = finish_in_unit(unit, admission)
        return viewed, message

    viewed, message = base.auth.write(base.context(), commit)
    assert viewed.state == "reviewable" and viewed.review is not None
    assert isinstance(viewed.review.lead_change, ReviewedLeadCreation)
    assert viewed.review.lead_change.source_session_revision == message.current_revision
    assert message.turn_revision == admission.session.revision
    assert message.current_revision == message.turn_revision + 1
    assert drafts.service.get(base.context(), viewed.draft_id) == viewed
    before = facts(base)
    assert drafts.service.create(base.context(), command) == viewed
    replay = base.service.begin(base.context(), command.session_id, admission.request)
    assert replay.status == "completed" and replay.result == message
    assert facts(base) == before


@pytest.mark.parametrize("failure", ["wrong_final", "early_observe", "after_message"])
def test_draft_review_transition_and_message_fail_atomically(
    drafts: DraftHarness, failure: str,
) -> None:
    base = drafts.base
    admission = begin(base, drafts.sessions[0])
    command = drafts.command()
    prepared = drafts.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert prepared is not None
    before = facts(base)

    def fail(unit: OwnerUnit) -> None:
        row = unit.session(command.session_id)
        effect = drafts.service.change_in_unit(
            unit, command, generation=base.store.generation, submitted_generation=base.store.generation,
            now=utc_text(base.clock.now()), prepared=prepared,
            final_session_revision=row.revision if failure == "wrong_final" else row.revision + 1,
            source_message_id=admission.message_id,
        )
        if failure == "early_observe":
            drafts.service.observe_changed_in_unit(
                unit, effect=effect, generation=base.store.generation, now=utc_text(base.clock.now()),
            )
        assert effect.transition is not None
        drafts.service.resolve_session_in_unit(unit, transition=effect.transition)
        row.revision = effect.transition.final_revision
        finish_in_unit(unit, admission)
        raise RuntimeError("synthetic later draft completion failure")

    if failure == "after_message":
        with pytest.raises(RuntimeError, match="synthetic later draft completion failure"):
            base.auth.write(base.context(), fail)
    else:
        code = "REVISION_CONFLICT" if failure == "wrong_final" else "REVIEW_STALE"
        with pytest.raises(ApiFailure, match=code):
            base.auth.write(base.context(), fail)
    assert facts(base) == before


def test_repeated_suspend_can_keep_chat_completion_revision(drafts: DraftHarness) -> None:
    base = drafts.base
    initial = drafts.service.create(base.context(), drafts.command())
    suspended = drafts.service.update(base.context(), initial.draft_id, update(initial, "suspend"))
    admission = begin(base, drafts.sessions[0])
    command = update(suspended, "suspend")
    prepared = drafts.service.prepare_change(
        base.context(), command, draft_id=initial.draft_id, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert prepared is not None and prepared.viewing is None

    def commit(unit: OwnerUnit) -> Any:
        row = unit.session(drafts.sessions[0])
        effect = drafts.service.change_in_unit(
            unit, command, draft_id=initial.draft_id, generation=base.store.generation,
            submitted_generation=base.store.generation, now=utc_text(base.clock.now()),
            prepared=prepared, final_session_revision=row.revision,
            source_message_id=admission.message_id,
        )
        assert effect.transition is not None
        drafts.service.resolve_session_in_unit(unit, transition=effect.transition)
        viewed = drafts.service.observe_changed_in_unit(
            unit, effect=effect, generation=base.store.generation, now=utc_text(base.clock.now()),
        )
        return viewed, finish_in_unit(unit, admission)

    viewed, message = base.auth.write(base.context(), commit)
    assert viewed.state == "suspended" and viewed.revision == suspended.revision + 1
    assert message.current_revision == message.turn_revision


def test_question_without_platform_authority_remains_strict(drafts: DraftHarness) -> None:
    base = drafts.base
    admission = begin(base, drafts.sessions[0])
    question = ClarificationIntent(
        kind="clarification", intent_id=str(uuid4()), created_revision=admission.session.revision + 1,
        purpose="viewing_details", targets=["appointment"], question="Which appointment?",
    )
    content = SessionContent(pending_intent=question)
    assert admission.ticket is not None
    base.service.complete(
        base.context(), admission.ticket,
        answer(admission).model_copy(update={"state": "clarification", "pending_intent": question}),
        update=content,
    )
    before = facts(base)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        drafts.service.prepare_change(
            base.context(), drafts.command(), submitted_generation=base.store.generation,
        )
    assert facts(base) == before
    # Positive opaque-authority proof requires Platform's actual collection module.


def test_draft_old_generation_and_changed_message_binding_fail(drafts: DraftHarness) -> None:
    base = drafts.base
    command = drafts.command()
    saved = drafts.service.create(base.context(), command)
    before = facts(base)
    with pytest.raises(ApiFailure, match="STORE_GENERATION_CHANGED"):
        drafts.service.prepare_change(base.context(), command, submitted_generation=str(uuid4()))
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        base.auth.read(base.context(), lambda unit: drafts.service.lookup_change_in_unit(
            unit, command, generation=base.store.generation, submitted_generation=base.store.generation,
            now=utc_text(base.clock.now()), source_message_id=str(uuid4()),
        ))
    assert facts(base) == before
    assert drafts.service.get(base.context(), saved.draft_id) == saved


@pytest.mark.parametrize(
    ("tamper", "code"),
    [
        ("before_revision", "REVISION_CONFLICT"),
        ("before_pending_json", "REVISION_CONFLICT"),
        ("after_pending_json", "REVIEW_STALE"),
        ("final_revision", "REVIEW_STALE"),
        ("owner_id", "NOT_FOUND"),
    ],
)
def test_draft_transition_tampering_rolls_back_domain_and_message(
    drafts: DraftHarness, tamper: str, code: str,
) -> None:
    base = drafts.base
    admission = begin(base, drafts.sessions[0])
    command = drafts.command()
    prepared = drafts.service.prepare_change(
        base.context(), command, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert prepared is not None
    before = facts(base)

    def fail(unit: OwnerUnit) -> None:
        row = unit.session(command.session_id)
        effect = drafts.service.change_in_unit(
            unit, command, generation=base.store.generation, submitted_generation=base.store.generation,
            now=utc_text(base.clock.now()), prepared=prepared, final_session_revision=row.revision + 1,
            source_message_id=admission.message_id,
        )
        assert effect.transition is not None
        changes = {
            "before_revision": row.revision + 1,
            "before_pending_json": b"{}",
            "after_pending_json": b"{}",
            "final_revision": row.revision,
            "owner_id": str(uuid4()),
        }
        drafts.service.resolve_session_in_unit(
            unit, transition=replace(effect.transition, **{tamper: changes[tamper]}),
        )
        pytest.fail("Altered transition was accepted")

    with pytest.raises(ApiFailure, match=code):
        base.auth.write(base.context(), fail)
    assert facts(base) == before


@pytest.mark.parametrize("intent", ["edit", "refresh_review", "suspend", "discard"])
def test_chat_draft_correction_and_stop_share_ui_rules(drafts: DraftHarness, intent: str) -> None:
    base = drafts.base
    first = drafts.service.create(base.context(), drafts.command())
    assert first.review is not None
    admission = begin(base, drafts.sessions[0])
    command = update(first, intent, **({"ref": ref("13").model_dump()} if intent == "edit" else {}))
    prepares = drafts.inventory.prepares
    prepared = drafts.service.prepare_change(
        base.context(), command, draft_id=first.draft_id, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert prepared is not None
    needs_inventory = intent in {"edit", "refresh_review"}
    assert (prepared.viewing is not None) is needs_inventory
    assert drafts.inventory.prepares == prepares + int(needs_inventory)

    def commit(unit: OwnerUnit) -> Any:
        row = unit.session(first.session_id)
        effect = drafts.service.change_in_unit(
            unit, command, draft_id=first.draft_id, generation=base.store.generation,
            submitted_generation=base.store.generation, now=utc_text(base.clock.now()),
            prepared=prepared, final_session_revision=row.revision + 1,
            source_message_id=admission.message_id,
        )
        assert effect.transition is not None
        drafts.service.resolve_session_in_unit(unit, transition=effect.transition)
        row.revision = effect.transition.final_revision
        result = drafts.service.observe_changed_in_unit(
            unit, effect=effect, generation=base.store.generation, now=utc_text(base.clock.now()),
        )
        return result, finish_in_unit(unit, admission)

    changed, message = base.auth.write(base.context(), commit)
    assert changed.revision == first.revision + 1
    if needs_inventory:
        assert changed.review is not None and changed.state == "reviewable"
        assert changed.review.operation_key != first.review.operation_key
        assert changed.ref.source_id == ("13" if intent == "edit" else "12")
        assert isinstance(changed.review.lead_change, ReviewedLeadCreation)
        assert changed.review.lead_change.source_session_revision == message.current_revision
    else:
        assert changed.review is None and changed.state == ("suspended" if intent == "suspend" else "discarded")
    observed = base.service.get(base.context(), first.session_id)
    assert observed.current_draft_id == (None if intent == "discard" else first.draft_id)
    before = facts(base)
    assert drafts.service.update(base.context(), first.draft_id, command) == changed
    assert facts(base) == before
    assert drafts.counts()[2:] == (0, 0, 0, 0)  # No booking, lead, export intent or outcome.


@pytest.mark.parametrize("intent", ["edit", "suspend", "discard"])
@pytest.mark.parametrize("terminal", [False, True], ids=["submitted_unknown", "terminal_success"])
def test_prepared_draft_cannot_replace_submitted_or_terminal_authority(
    intent: str, terminal: bool,
) -> None:
    flow = make_confirmation_harness()
    drafts, base = flow.drafts, flow.drafts.base
    first = flow.create()
    command = update(first, intent, **({"ref": ref("13").model_dump()} if intent == "edit" else {}))
    prepared = drafts.service.prepare_change(
        base.context(), command, draft_id=first.draft_id, submitted_generation=base.store.generation,
    )
    assert prepared is not None
    if terminal:
        accepted = flow.commit(first, flow.prepare(first))
        assert accepted.terminal.state == "succeeded"
        assert accepted.terminal.booking.state == "confirmed_simulated"
    else:
        base.auth.write(base.context(), lambda unit: drafts.service.mark_submitted(
            unit, first.draft_id, confirmation(first), generation=base.store.generation,
            now=utc_text(base.clock.now()),
        ))
    before = facts(base)
    revision = base.service.get(base.context(), first.session_id).revision
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE" if terminal else "OPERATION_UNRESOLVED"):
        base.auth.write(base.context(), lambda unit: drafts.service.change_in_unit(
            unit, command, draft_id=first.draft_id, generation=base.store.generation,
            submitted_generation=base.store.generation, now=utc_text(base.clock.now()),
            prepared=prepared, final_session_revision=revision + 1,
        ))
    assert facts(base) == before


@pytest.mark.parametrize("contact_changed", [False, True])
def test_prepared_chat_correction_cannot_overwrite_a_later_form_edit(
    leads: LeadHarness, contact_changed: bool,
) -> None:
    base = leads.sessions
    saved = leads.service.save(base.context(), save_request(leads.session_ids[0])).lead
    admission = begin(base, leads.session_ids[0])
    proposed = saved.values.model_copy(deep=True)
    proposed.requirements = ["Chat correction prepared before the later form edit"]
    command = correction(leads.session_ids[0], saved.revision, proposed)
    prepared = leads.service.prepare_change(
        base.context(), command, lead_id=saved.lead_id, submitted_generation=base.store.generation,
        source_message_id=admission.message_id,
    )
    assert isinstance(prepared, PreparedLeadChange)
    form_values = saved.values.model_copy(deep=True)
    form_values.requirements = ["Newer explicit form requirements"]
    if contact_changed:
        form_values.email = ContactValue(state="provided", value="form-new@example.invalid")
    latest = leads.service.update(
        base.context(), saved.lead_id, correction(leads.session_ids[0], saved.revision, form_values),
    )
    before = facts(base)
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR" if contact_changed else "LEAD_REVISION_CONFLICT"):
        base.auth.write(base.context(), lambda unit: leads.service.change_in_unit(
            unit, command, lead_id=saved.lead_id, submitted_generation=base.store.generation,
            generation=base.store.generation, now=utc_text(base.clock.now()), prepared=prepared,
            source_message_id=admission.message_id,
        ))
    assert facts(base) == before
    assert leads.service.get(base.context()) == latest.lead
