"""Actual caller-unit services; only Inventory ports are synthetic. Source-only P14."""

from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.api.schemas.memory import CategoryPreference, MembershipRequest
from app.api.schemas.sessions import MessageRequest, MessageResult
from app.core.errors import ApiFailure
from app.database.models import Message
from app.database.store import StoreError
from app.memory.service import PreferenceService
from app.sessions.service import SessionService, ShortlistChange, TurnAdmission
from app.shortlist.inventory import ReferenceBatch
from app.shortlist.service import MembershipRejected
from tests.platform.memory_shortlist_cases import (
    MemoryHarness, failed_commit, make_memory_harness, seed_operational_rows,
)
from tests.platform.session_cases import answer, ref
from tests.platform.test_identity import snapshot
from tests.platform.test_preferences import mode, remember


@pytest.fixture
def h() -> MemoryHarness:
    return make_memory_harness()


def turn(h: MemoryHarness, session_id: str | None = None) -> TurnAdmission:
    base = h.base
    state = base.create() if session_id is None else base.service.get(base.context(), session_id)
    return base.service.begin(base.context(), state.session_id, MessageRequest(
        client_message_id=str(uuid4()), expected_revision=state.revision,
        text="Remember Toyota and save this car to my shortlist.",
    ))


def member(revision: int = 0) -> ShortlistChange:
    return ShortlistChange(ref(), MembershipRequest(
        client_action_id=str(uuid4()), expected_revision=revision,
    ), True)


def complete(h: MemoryHarness, admission: TurnAdmission, **kwargs: Any) -> MessageResult:
    assert admission.ticket is not None
    return h.base.service.complete_action(
        h.base.context(), admission.ticket, answer(admission),
        preference_service=h.preferences, shortlist_service=h.shortlist, **kwargs,
    )


def test_two_effects(h: MemoryHarness) -> None:
    seed_operational_rows(h.base)
    admission = turn(h)
    before = snapshot(h.base.store)
    preference = remember(admission.session.session_id, makes=("Toyota",))
    membership = member()
    saved = complete(h, admission, preference=preference, membership=membership)
    assert saved.persistence == "saved" and saved.current_revision == admission.session.revision
    assert saved.actions.preferences.state == saved.actions.shortlist.state == "succeeded"
    assert saved.actions.preferences.result.entries[0].preference.value == ["Toyota"]
    entry = saved.actions.preferences.result.entries[0]
    assert entry.source_message_id == admission.message_id != admission.request.client_message_id
    assert entry.source_action_id == preference.client_action_id
    assert saved.actions.preferences.result.revision == saved.actions.shortlist.result.current_revision == 1
    assert saved.text == "Your preference update is recorded. This car is on your shortlist."
    transcript = h.base.service.transcript(h.base.context(), admission.session.session_id)
    assert transcript.items[0].assistant_result == saved
    assert h.base.create().recalled_preferences == saved.actions.preferences.result
    assert PreferenceService(h.base.auth).get(h.base.context()) == saved.actions.preferences.result
    after = snapshot(h.base.store)
    for table in ("bookings", "leads", "operation_outcomes", "export_intents"):
        assert after[table] == before[table]


def test_new_values(h: MemoryHarness) -> None:
    admission = turn(h)
    h.preferences.update(h.base.context(), remember(admission.session.session_id))
    preference = remember(admission.session.session_id, 1, ("Toyota", "Mazda"))
    saved = complete(h, admission, preference=preference)
    assert saved.actions.preferences.state == "succeeded"
    assert saved.actions.preferences.result.entries[0].preference.value == ["Toyota", "Mazda"]
    assert saved.actions.preferences.result.entries[0].source_message_id == admission.message_id
    assert admission.session.criteria.filters.makes == []


def test_exact_replay(h: MemoryHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    admission, membership = turn(h), member()
    preference = remember(admission.session.session_id)
    saved = complete(h, admission, preference=preference, membership=membership)
    h.base.clock.value += timedelta(minutes=1)
    newer = turn(h, admission.session.session_id)
    before = snapshot(h.base.store)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("REPLAY_CALLED_PARTICIPANT")

    monkeypatch.setattr(h.preferences, "update_in_unit", forbidden)
    monkeypatch.setattr(h.shortlist, "prepare_change", forbidden)
    monkeypatch.setattr(h.shortlist, "change_in_unit", forbidden)
    replay = complete(h, admission, preference=preference, membership=membership)
    assert replay == saved.model_copy(update={"current_revision": newer.session.revision})
    assert snapshot(h.base.store) == before
    changed = preference.model_copy(update={"expected_revision": 1})
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        complete(h, admission, preference=changed, membership=membership)
    assert snapshot(h.base.store) == before


@pytest.mark.parametrize("kind", ["late", "owner", "issuer", "epoch"])
def test_ticket_denials(h: MemoryHarness, kind: str) -> None:
    admission = turn(h)
    assert admission.ticket is not None
    if kind == "late":
        turn(h, admission.session.session_id)
    if kind == "epoch":
        def replace_epoch(db: Session) -> None:
            row = db.get(Message, admission.message_id)
            assert row is not None
            row.result_json = {**row.result_json, "worker_epoch": str(uuid4())}
        h.base.store.write(replace_epoch)
    before, batches = snapshot(h.base.store), list(h.inventory.batches)
    service = SessionService(h.base.auth) if kind == "issuer" else h.base.service
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT|UNSUPPORTED_STATE"):
        service.complete_action(
            h.base.context(1 if kind == "owner" else 0), admission.ticket, answer(admission),
            membership=member(), shortlist_service=h.shortlist,
        )
    assert snapshot(h.base.store) == before and h.inventory.batches == batches


@pytest.mark.parametrize("domain", ["preference", "shortlist"])
def test_revision_outcome(h: MemoryHarness, domain: str) -> None:
    admission, membership = turn(h), member()
    preference = remember(admission.session.session_id)
    if domain == "preference":
        h.preferences.update(h.base.context(), remember(admission.session.session_id, makes=("Mazda",)))
    else:
        h.shortlist.put(h.base.context(), ref(), MembershipRequest(
            client_action_id=str(uuid4()), expected_revision=0,
        ))
    saved = complete(h, admission, preference=preference, membership=membership)
    rejected = saved.actions.preferences if domain == "preference" else saved.actions.shortlist
    successful = saved.actions.shortlist if domain == "preference" else saved.actions.preferences
    assert rejected.state == "rejected" and rejected.code == "REVISION_CONFLICT"
    assert successful.state == "succeeded" and saved.persistence == "saved"
    assert h.preferences.get(h.base.context()).revision == 1
    assert h.shortlist.get(h.base.context()).revision == 1


@pytest.mark.parametrize("failure", ["after", "commit"])
def test_atomic_rollback(h: MemoryHarness, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    admission, membership = turn(h), member()
    preference = remember(admission.session.session_id)
    before = snapshot(h.base.store)
    original = h.shortlist.change_in_unit

    def after_effect(*args: Any, **kwargs: Any) -> Any:
        original(*args, **kwargs)
        # Same allowlisted string, but NOT the proven precondition exception type.
        raise ApiFailure("VALIDATION_ERROR")

    if failure == "after":
        monkeypatch.setattr(h.shortlist, "change_in_unit", after_effect)
        with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
            complete(h, admission, preference=preference, membership=membership)
        monkeypatch.setattr(h.shortlist, "change_in_unit", original)
    else:
        with failed_commit(), pytest.raises(StoreError, match="SYNTHETIC_COMMIT_FAILURE"):
            complete(h, admission, preference=preference, membership=membership)
    assert snapshot(h.base.store) == before
    saved = complete(h, admission, preference=preference, membership=membership)
    assert saved.actions.preferences.state == saved.actions.shortlist.state == "succeeded"
    assert h.preferences.get(h.base.context()).revision == h.shortlist.get(h.base.context()).revision == 1


def test_denial_receipt_race(h: MemoryHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    admission, membership = turn(h), member()
    h.preferences.update(h.base.context(), mode(admission.session.session_id, 0, enabled=False))
    prepare = h.shortlist.prepare_change

    def racing(*args: Any, **kwargs: Any) -> ReferenceBatch:
        try:
            return prepare(*args, **kwargs)
        except MembershipRejected:
            h.preferences.update(h.base.context(), mode(admission.session.session_id, 1, enabled=True))
            monkeypatch.setattr(h.shortlist, "prepare_change", prepare)
            h.shortlist.put(h.base.context(), membership.ref, membership.command)
            raise

    monkeypatch.setattr(h.shortlist, "prepare_change", racing)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        complete(h, admission, membership=membership)
    transcript = h.base.service.transcript(h.base.context(), admission.session.session_id)
    assert transcript.items[0].state == "pending"
    saved = complete(h, admission, membership=membership)
    assert saved.actions.shortlist.state == "succeeded" and saved.actions.shortlist.result.replayed
    assert saved.actions.shortlist.result.current_revision == 1


def test_copied_command(h: MemoryHarness) -> None:
    admission, membership = turn(h), member()
    preference = remember(admission.session.session_id, makes=("Toyota",))
    change = preference.changes[0]
    assert isinstance(change, CategoryPreference)
    h.inventory.after_read = lambda: change.value.append("Honda")
    saved = complete(h, admission, preference=preference, membership=membership)
    assert saved.actions.preferences.state == "succeeded"
    assert saved.actions.preferences.result.entries[0].preference.value == ["Toyota"]


def test_current_membership_ack(h: MemoryHarness) -> None:
    admission, membership = turn(h), member()
    h.shortlist.put(h.base.context(), membership.ref, membership.command)
    h.shortlist.delete(h.base.context(), membership.ref, MembershipRequest(
        client_action_id=str(uuid4()), expected_revision=1,
    ))
    saved = complete(h, admission, membership=membership)
    assert saved.actions.shortlist.state == "succeeded"
    assert saved.actions.shortlist.result.replayed and not saved.actions.shortlist.result.saved
    assert saved.text == "This car is not on your shortlist."


def test_noop_provenance(h: MemoryHarness) -> None:
    first = turn(h)
    saved = complete(h, first, preference=remember(first.session.session_id))
    assert saved.actions.preferences.state == "succeeded"
    second = turn(h, first.session.session_id)
    h.base.clock.value += timedelta(minutes=1)
    later = complete(h, second, preference=remember(second.session.session_id, 1))
    assert later.actions.preferences.state == "succeeded"
    assert later.actions.preferences.result.entries == saved.actions.preferences.result.entries
    assert later.actions.preferences.result.revision == 2


def test_provenance_parent(h: MemoryHarness) -> None:
    first, other = turn(h), turn(h)
    before = snapshot(h.base.store)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        h.base.auth.write(h.base.context(), lambda unit: h.preferences.update_in_unit(
            unit, remember(first.session.session_id), source_message_id=other.message_id,
        ))
    assert snapshot(h.base.store) == before
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        h.base.auth.read(h.base.context(), lambda unit: h.preferences.update_in_unit(
            unit, remember(first.session.session_id), source_message_id=first.message_id,
        ))
    assert snapshot(h.base.store) == before


def test_batch_target(h: MemoryHarness) -> None:
    admission, membership = turn(h), member()
    wrong = h.shortlist.prepare_change(h.base.context(), ref("13"), membership.command, desired=True)
    before = snapshot(h.base.store)
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        h.base.auth.write(h.base.context(), lambda unit: h.shortlist.change_in_unit(
            unit, membership.ref, membership.command, desired=True,
            generation=h.base.store.generation, prepared=wrong,
        ))
    assert snapshot(h.base.store) == before


def test_combined_mode_rejected(h: MemoryHarness) -> None:
    admission = turn(h)
    before = snapshot(h.base.store)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        complete(h, admission, preference=mode(admission.session.session_id, 0, enabled=False), membership=member())
    assert snapshot(h.base.store) == before

def test_late_during_prepare(h: MemoryHarness) -> None:
    admission, membership = turn(h), member()
    preference = remember(admission.session.session_id)
    raced: list[dict[str, list[dict[str, Any]]]] = []
    def newer_turn() -> None:
        h.inventory.after_read = None
        turn(h, admission.session.session_id)
        raced.append(snapshot(h.base.store))
    h.inventory.after_read = newer_turn
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        complete(h, admission, preference=preference, membership=membership)
    assert len(raced) == 1 and snapshot(h.base.store) == raced[0]
    assert h.preferences.get(h.base.context()).revision == 0
    assert h.shortlist.get(h.base.context()).revision == 0


def test_denial_cleared(h: MemoryHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    admission, membership = turn(h), member()
    h.preferences.update(h.base.context(), mode(admission.session.session_id, 0, enabled=False))
    prepare = h.shortlist.prepare_change
    raced: list[dict[str, list[dict[str, Any]]]] = []
    def resume(*args: Any, **kwargs: Any) -> ReferenceBatch:
        try:
            return prepare(*args, **kwargs)
        except MembershipRejected:
            monkeypatch.setattr(h.shortlist, "prepare_change", prepare)
            h.preferences.update(h.base.context(), mode(admission.session.session_id, 1, enabled=True))
            raced.append(snapshot(h.base.store))
            raise
    monkeypatch.setattr(h.shortlist, "prepare_change", resume)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        complete(h, admission, membership=membership)
    assert len(raced) == 1 and snapshot(h.base.store) == raced[0]
    saved = complete(h, admission, membership=membership)
    assert saved.actions.shortlist.state == "succeeded"
    assert not saved.actions.shortlist.result.replayed and saved.actions.shortlist.result.current_revision == 1