"""Real shared participants with retained chat uncertainty; synthetic Inventory only."""

from typing import Any
from uuid import uuid4

import pytest

from app.api.schemas.leads import ContactValue, LeadRecord, LeadSaveRequest, LeadUpdateRequest, LeadValues
from app.api.schemas.viewings import BookingDraftCreate
from app.core.errors import ApiFailure
from app.identity.authorization import OwnerUnit
from app.leads.changes import PreparedLeadChange
from app.leads.service import LeadService
from app.sessions.collection import CollectionValues, LeadBinding
from app.sessions.service import LeadChange
from tests.platform.collection_cases import begin, collect
from tests.platform.session_cases import SessionHarness, answer, ref
from tests.platform.test_identity import snapshot
from tests.transactions.draft_fixtures import make_draft_harness, update
from tests.transactions.lead_fixtures import correction, make_lead_harness, save_request


def retain_enquiry(
    base: SessionHarness, session_id: str, leads: LeadService, monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = leads.get(base.context())
    values = CollectionValues() if not isinstance(current, LeadRecord) else CollectionValues(
        budget=current.values.budget, requirements=current.values.requirements,
        requirements_state="provided" if current.values.requirements else "missing",
        ref=current.values.selected_refs[0] if current.values.selected_refs else None,
    )
    binding = None if not isinstance(current, LeadRecord) else LeadBinding(
        lead_id=current.lead_id, revision=current.revision,
    )
    collect(base, session_id, values, ask="save", binding=binding)
    admission = begin(base, session_id, "Save these exact local enquiry values")
    assert admission.ticket is not None
    command: LeadSaveRequest | LeadUpdateRequest
    if isinstance(current, LeadRecord):
        command = correction(session_id, current.revision, current.values)
    else:
        command = save_request(session_id, LeadValues(
            budget=values.budget, requirements=values.requirements, selected_refs=[],
            email=ContactValue(state="missing"), phone=ContactValue(state="missing"),
        ))

    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("SYNTHETIC_RETAINED_COMMAND")

    with monkeypatch.context() as patched:
        patched.setattr(leads, "prepare_change", unavailable)
        with pytest.raises(RuntimeError, match="RETAINED_COMMAND"):
            base.service.complete_action(base.context(), admission.ticket, answer(admission),
                lead=LeadChange(command, None if binding is None else binding.lead_id), lead_service=leads)
    retained = base.service.read_collection(base.context(), admission.ticket).unresolved
    assert retained is not None and retained.command == command


def test_fence_blocks_fresh_form_save_update_but_allows_owned_receipt_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = make_lead_harness()
    base = h.sessions
    first_command = save_request(h.session_ids[0])
    first = h.service.save(base.context(), first_command)
    pending_session = base.create().session_id
    retain_enquiry(base, pending_session, h.service, monkeypatch)
    another_session = base.create().session_id
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
        h.service.save(base.context(), save_request(another_session))
    with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
        h.service.update(base.context(), first.lead.lead_id,
            correction(another_session, first.lead.revision, first.lead.values))
    assert snapshot(base.store) == before
    replay = h.service.save(base.context(), first_command)
    assert replay.replayed and replay.lead.lead_id == first.lead.lead_id
    assert snapshot(base.store) == before
    # Uncertainty belongs to the owner, not every buyer in this Store.
    foreign = h.service.save(base.context(1), save_request(h.session_ids[1]))
    assert not foreign.replayed and foreign.lead.lead_id != first.lead.lead_id


def test_new_fence_between_form_preparation_and_application_aborts_whole_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = make_lead_harness()
    base = h.sessions
    first = h.service.save(base.context(), save_request(h.session_ids[0]))
    form = correction(h.session_ids[0], first.lead.revision, first.lead.values)
    context = base.context()
    prepared = h.service.prepare_change(context, form, lead_id=first.lead.lead_id,
        submitted_generation=context.generation)
    assert isinstance(prepared, PreparedLeadChange)
    retain_enquiry(base, base.create().session_id, h.service, monkeypatch)
    before = snapshot(base.store)

    def apply(unit: OwnerUnit) -> object:
        return h.service.change_in_unit(unit, form, lead_id=first.lead.lead_id,
            submitted_generation=context.generation, generation=context.generation,
            now=base.auth.identity.now_text(), prepared=prepared)

    with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
        base.auth.write(context, apply)
    assert snapshot(base.store) == before


@pytest.mark.parametrize("intent", ["edit", "refresh_review", "suspend", "discard"])
def test_fence_blocks_new_draft_effects_but_prior_create_receipt_replays(
    intent: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = make_draft_harness()
    base = h.base
    original_command = h.command()
    original = h.service.create(base.context(), original_command)
    other_session = base.create().session_id
    retain_enquiry(base, other_session, LeadService(base.auth), monkeypatch)
    another_session = base.create()
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
        h.service.create(base.context(), BookingDraftCreate(
            client_action_id=str(uuid4()), session_id=another_session.session_id,
            expected_session_revision=another_session.revision, ref=ref(), appointment=h.appointment(),
        ))
    changes = {"ref": ref("13")} if intent == "edit" else {}
    with pytest.raises(ApiFailure, match="OPERATION_UNRESOLVED"):
        h.service.update(base.context(), original.draft_id, update(original, intent, **changes))
    assert snapshot(base.store) == before
    replay = h.service.create(base.context(), original_command)
    assert replay.draft_id == original.draft_id and replay.revision == original.revision
    assert snapshot(base.store) == before
