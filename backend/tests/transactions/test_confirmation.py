"""Confirmation replay, capacity, caller-unit rollback and owned recovery.

These sources have not run under T7. Synthetic ports do not prove real Inventory
activation, HTTP/chat composition, a CSV publisher or the full PDF demonstration.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.schemas.leads import LeadRecord
from app.api.schemas.operations import (
    OperationGenerationUnresolved,
    OperationNotObserved,
    OperationRejected,
    OperationSucceeded,
)
from app.api.schemas.viewings import BookingCoreReceipt, BookingDraft
from app.core.errors import ApiFailure
from app.database.models import ExportState, OperationOutcome
from app.database.store import StoreError
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.leads import repository as lead_repository
from app.leads.service import LeadService
from app.sessions import repository as sessions
from app.viewings import confirmation_repository as repo
from app.viewings.confirmation import ConfirmationEffect
from tests.platform.test_identity import snapshot
from tests.transactions.confirmation_fixtures import ConfirmationHarness, make_confirmation_harness
from tests.transactions.draft_fixtures import confirmation, update
from tests.transactions.lead_fixtures import buyer_values, save_request


@pytest.fixture
def flow() -> ConfirmationHarness:
    return make_confirmation_harness()


def test_atomic_success_at_reviewed_r_then_single_wrapper_advance(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    base = flow.drafts.base
    before = base.service.get(base.context(), draft.session_id)
    result = flow.commit(draft, flow.prepare(draft))
    assert isinstance(result.terminal, OperationSucceeded)
    assert result.replayed is False and result.transition is not None
    assert result.terminal.booking.review.model_dump(mode="json", exclude={"state"}) == (
        draft.review.model_dump(mode="json", exclude={"state"}) if draft.review else None
    )
    assert result.terminal.lead.state == "saved" and result.terminal.csv.state == "pending"
    assert flow.counts() == (1, 1, 1, 1, 1)
    after = base.service.get(base.context(), draft.session_id)
    assert after.revision == before.revision + 1
    assert after.pending_intent.kind == "none" and after.current_draft_id is None
    assert (after.criteria, after.selected_ref, after.active_presentation_id) == (
        before.criteria,
        before.selected_ref,
        before.active_presentation_id,
    )


def test_exact_replay_skips_preparation_after_review_and_appointment_expire(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    first = flow.commit(draft, flow.prepare(draft))
    counters = (
        flow.drafts.inventory.prepares,
        flow.lead_inventory.reads,
        flow.lead_inventory.checks,
    )
    flow.drafts.base.clock.value += timedelta(days=2)
    assert flow.prepare(draft) is None
    replay = flow.commit(draft, None)
    assert replay.terminal == first.terminal and replay.replayed and replay.transition is None
    assert counters == (
        flow.drafts.inventory.prepares,
        flow.lead_inventory.reads,
        flow.lead_inventory.checks,
    )
    assert flow.counts() == (1, 1, 1, 1, 1)


@pytest.mark.parametrize("field", ["draft", "revision", "rules", "generation", "operation_key"])
def test_replay_rejects_changed_material(flow: ConfirmationHarness, field: str) -> None:
    draft = flow.create()
    flow.commit(draft, flow.prepare(draft))
    command = confirmation(draft)
    draft_id = draft.draft_id
    if field == "draft":
        draft_id = str(uuid4())
    elif field == "revision":
        command.expected_draft_revision += 1
    elif field == "rules":
        command.rules_version = "different-rules"
    elif field == "generation":
        command.store_generation = str(uuid4())
    else:
        command.operation_key = "Z" * 43
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        flow.participant.prepare(flow.drafts.base.context(), draft_id=draft_id, command=command)
    assert flow.counts() == (1, 1, 1, 1, 1)


def test_ui_chat_share_fixed_review_key_and_cannot_replace_it(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    first = flow.commit(draft, prepared)
    # Two transport message/action IDs are deliberately absent from the shared material.
    replay = flow.commit(draft, prepared)
    assert replay.terminal == first.terminal and replay.replayed
    replacement = confirmation(draft).model_copy(update={"operation_key": "N" * 43})
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        flow.participant.prepare(
            flow.drafts.base.context(), draft_id=draft.draft_id, command=replacement
        )
    assert flow.counts() == (1, 1, 1, 1, 1)


@pytest.mark.parametrize(
    "offset,expected", [(-30, "succeeded"), (0, "rejected"), (30, "succeeded")]
)
def test_capacity_is_half_open_and_global_across_owners(
    flow: ConfirmationHarness, offset: int, expected: str
) -> None:
    first, second = flow.create(minutes=60), flow.create(who=1, minutes=60 + offset)
    first_prepared, second_prepared = flow.prepare(first), flow.prepare(second, who=1)
    flow.commit(first, first_prepared)
    outcome = flow.commit(second, second_prepared, who=1).terminal
    assert outcome.state == expected
    if isinstance(outcome, OperationRejected):
        assert outcome.rejection_code == "CAPACITY_UNAVAILABLE"
        assert flow.counts() == (1, 2, 1, 1, 1)
    else:
        assert flow.counts() == (2, 2, 2, 2, 2)


@pytest.mark.parametrize(
    "offset,taken",
    [(-31, False), (-30, False), (-15, True), (0, True), (15, True), (30, False)],
)
def test_sql_capacity_handles_general_overlaps(
    flow: ConfirmationHarness, offset: int, taken: bool
) -> None:
    draft = flow.create()
    terminal = flow.commit(draft, flow.prepare(draft)).terminal
    assert isinstance(terminal, OperationSucceeded)
    receipt = terminal.booking
    start = datetime.fromisoformat(receipt.review.starts_at_utc) + timedelta(minutes=offset)
    proposed = BookingCoreReceipt.model_validate(
        {
            **receipt.model_dump(mode="json"),
            "review": {
                **receipt.review.model_dump(mode="json"),
                "starts_at_utc": utc_text(start),
                "ends_at_utc": utc_text(start + timedelta(minutes=30)),
                "local_start": start.astimezone(flow.drafts.service.rules.zone).isoformat(),
            },
        }
    )
    # Tests the interval query independently of the adopted 30-minute start grid.
    assert (
        flow.drafts.base.auth.write(
            flow.drafts.base.context(), lambda unit: repo.capacity_taken(unit, proposed)
        )
        is taken
    )


def test_stable_resource_capacity_survives_inventory_snapshot_change(
    flow: ConfirmationHarness,
) -> None:
    first = flow.create()
    accepted = flow.commit(first, flow.prepare(first)).terminal
    flow.activate_second_snapshot()
    second = flow.create(who=1, snapshot="2" * 64)
    rejected = flow.commit(second, flow.prepare(second, who=1), who=1).terminal
    assert isinstance(accepted, OperationSucceeded) and isinstance(rejected, OperationRejected)
    assert first.ref.snapshot_id != second.ref.snapshot_id
    assert first.review is not None and second.review is not None
    assert first.review.resource_id == second.review.resource_id
    assert rejected.rejection_code == "CAPACITY_UNAVAILABLE"
    assert flow.counts() == (1, 2, 1, 1, 1)


def test_durable_rejection_does_not_turn_into_success_when_capacity_changes(
    flow: ConfirmationHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = flow.create(), flow.create(who=1)
    a, b = flow.prepare(first), flow.prepare(second, who=1)
    flow.commit(first, a)
    rejected = flow.commit(second, b, who=1)
    calls: list[bool] = []

    def now_free(unit: OwnerUnit, accepted: BookingCoreReceipt) -> bool:
        calls.append(True)
        return False

    monkeypatch.setattr(repo, "capacity_taken", now_free)
    replay = flow.commit(second, None, who=1)
    assert isinstance(replay.terminal, OperationRejected)
    assert replay.terminal == rejected.terminal and replay.replayed and calls == []
    assert flow.counts() == (1, 2, 1, 1, 1)


@pytest.mark.parametrize("fault", ["submitted", "outcome", "booking", "lead", "export", "session"])
def test_failure_after_each_effect_rolls_back_everything(
    flow: ConfirmationHarness, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    base = flow.drafts.base
    before = base.service.get(base.context(), draft.session_id)
    targets: dict[str, tuple[Any, str]] = {
        "submitted": (flow.drafts.service, "mark_submitted"),
        "outcome": (repo, "stage_outcome"),
        "booking": (repo, "stage_booking"),
        "lead": (flow.participant.leads, "apply"),
        "export": (lead_repository, "enqueue"),
        "session": (flow.participant, "resolve_session_in_unit"),
    }
    target, name = targets[fault]
    original = getattr(target, name)

    def fail(*args: Any, **kwargs: Any) -> Any:
        original(*args, **kwargs)
        raise StoreError("SYNTHETIC_EFFECT_ROLLBACK")

    monkeypatch.setattr(target, name, fail)
    with pytest.raises(StoreError, match="SYNTHETIC_EFFECT_ROLLBACK"):
        flow.commit(draft, prepared)
    assert flow.counts() == (0, 0, 0, 0, 0)
    assert flow.drafts.service.get(base.context(), draft.draft_id) == draft
    assert base.service.get(base.context(), draft.session_id) == before


def test_read_unit_cannot_apply_or_resolve(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    with pytest.raises(StoreError, match="DRAFT_REQUIRES_CALLER_WRITE_UNIT"):
        flow.drafts.base.auth.read(
            flow.drafts.base.context(write=False), lambda unit: flow.apply(unit, draft, prepared)
        )
    assert flow.counts() == (0, 0, 0, 0, 0)
    result = flow.commit(draft, prepared)
    transition = result.transition
    assert transition is not None
    with pytest.raises(StoreError, match="DRAFT_REQUIRES_CALLER_WRITE_UNIT"):
        flow.drafts.base.auth.read(
            flow.drafts.base.context(write=False),
            lambda unit: flow.participant.resolve_session_in_unit(unit, transition=transition),
        )


def test_intervening_edit_wins_before_submit(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    flow.drafts.service.update(flow.drafts.base.context(), draft.draft_id, update(draft, "suspend"))
    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        flow.commit(draft, prepared)
    assert flow.counts() == (0, 0, 0, 0, 0)


def test_submit_wins_before_edit_and_replay_survives_it(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    first = flow.commit(draft, flow.prepare(draft))
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        flow.drafts.service.update(
            flow.drafts.base.context(), draft.draft_id, update(draft, "suspend")
        )
    assert flow.commit(draft, None).terminal == first.terminal
    assert flow.counts() == (1, 1, 1, 1, 1)


def test_two_prepared_writers_serialize_one_capacity_winner(flow: ConfirmationHarness) -> None:
    drafts = (flow.create(), flow.create(who=1))
    prepared = (flow.prepare(drafts[0]), flow.prepare(drafts[1], who=1))
    contexts = (flow.drafts.base.context(), flow.drafts.base.context(1))
    start = Barrier(2)

    def write(who: int) -> ConfirmationEffect:
        start.wait(timeout=5)
        return flow.drafts.base.auth.write(
            contexts[who], lambda unit: flow.apply(unit, drafts[who], prepared[who])
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write, who) for who in (0, 1)]
        results = [future.result(timeout=20).terminal for future in futures]
    assert sorted(result.state for result in results) == ["rejected", "succeeded"]
    assert flow.counts() == (1, 2, 1, 1, 1)


def test_expired_review_cannot_be_freshly_submitted(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    flow.drafts.base.clock.value += timedelta(minutes=5)
    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        flow.commit(draft, prepared)
    assert flow.counts() == (0, 0, 0, 0, 0)


def test_foreign_owner_cannot_observe_or_apply(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    flow.commit(draft, flow.prepare(draft))
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        flow.prepare(draft, who=1)
    observed = flow.participant.status(
        flow.drafts.base.context(1),
        operation_key=confirmation(draft).operation_key,
        submitted_generation=flow.drafts.base.store.generation,
    )
    assert isinstance(observed, OperationNotObserved) and not observed.definitive_noncommit


@pytest.mark.parametrize("changed_generation", [False, True])
def test_absent_original_operation_is_explicitly_uncertain(
    flow: ConfirmationHarness, changed_generation: bool
) -> None:
    observed = flow.participant.status(
        flow.drafts.base.context(),
        operation_key="U" * 43,
        submitted_generation=(
            str(uuid4()) if changed_generation else flow.drafts.base.store.generation
        ),
    )
    expected = OperationGenerationUnresolved if changed_generation else OperationNotObserved
    assert isinstance(observed, expected)
    assert observed.definitive_noncommit is False and observed.operation_key == "U" * 43


def test_lost_response_recovers_original_terminal_without_new_effect(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    committed = flow.commit(draft, flow.prepare(draft))
    recovered = flow.participant.status(
        flow.drafts.base.context(),
        operation_key=confirmation(draft).operation_key,
        submitted_generation=flow.drafts.base.store.generation,
    )
    assert recovered == committed.terminal
    assert flow.commit(draft, None).terminal == committed.terminal
    assert flow.counts() == (1, 1, 1, 1, 1)


def test_csv_observation_does_not_rewrite_terminal(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    committed = flow.commit(draft, flow.prepare(draft)).terminal
    assert isinstance(committed, OperationSucceeded)

    def repair_metadata(unit: OwnerUnit) -> None:
        projection = unit.db.get(ExportState, 1)
        assert projection is not None
        projection.state, projection.exported_version = "current", projection.canonical_version

    base = flow.drafts.base
    base.auth.write(base.context(), repair_metadata)
    observed = base.auth.read(
        base.context(),
        lambda unit: flow.participant.observe_csv_in_unit(
            unit, generation=base.store.generation, now=utc_text(base.clock.value)
        ),
    )
    assert observed.state == "current" and committed.csv.state == "pending"
    assert flow.commit(draft, None).terminal == committed
    stored = base.store.read(lambda db: db.scalar(select(OperationOutcome.terminal_result_json)))
    assert stored == committed.model_dump(mode="json")


def test_prepared_evidence_and_transition_are_exactly_bound(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    assert prepared is not None
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        flow.commit(draft, replace(prepared, draft_id=str(uuid4())))
    assert flow.counts() == (0, 0, 0, 0, 0)

    def incorrect_transition(unit: OwnerUnit) -> None:
        effect = flow.participant.apply_in_unit(
            unit,
            draft_id=draft.draft_id,
            command=confirmation(draft),
            generation=flow.drafts.base.store.generation,
            now=utc_text(flow.drafts.base.clock.value),
            prepared=prepared,
        )
        assert effect.transition is not None
        flow.participant.resolve_session_in_unit(
            unit,
            transition=replace(
                effect.transition, expected_revision=effect.transition.expected_revision + 1
            ),
        )

    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        flow.drafts.base.auth.write(flow.drafts.base.context(), incorrect_transition)
    assert flow.counts() == (0, 0, 0, 0, 0)


def test_generic_session_protection_is_not_relaxed(flow: ConfirmationHarness) -> None:
    draft = flow.create()

    def check(unit: OwnerUnit) -> None:
        before = sessions.content(unit.session(draft.session_id))
        after = before.model_copy(update={"current_draft_id": None})
        with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
            sessions.protect_operation(before, after)

    flow.drafts.base.auth.read(flow.drafts.base.context(), check)


@pytest.mark.parametrize("spelling", ["Z", ".0Z", ".000000Z"])
def test_equivalent_now_spelling_is_canonical_before_effects(
    flow: ConfirmationHarness, spelling: str
) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    base = flow.drafts.base
    now = base.clock.value.strftime("%Y-%m-%dT%H:%M:%S") + spelling

    def write(unit: OwnerUnit) -> ConfirmationEffect:
        effect = flow.participant.apply_in_unit(
            unit,
            draft_id=draft.draft_id,
            command=confirmation(draft),
            generation=base.store.generation,
            now=now,
            prepared=prepared,
        )
        assert effect.transition is not None
        flow.participant.resolve_session_in_unit(unit, transition=effect.transition)
        unit.session(draft.session_id).revision += 1
        return effect

    effect = base.auth.write(base.context(), write)
    assert effect.terminal.terminal_at == utc_text(base.clock.value)
    assert (
        flow.participant.status(
            base.context(),
            operation_key=confirmation(draft).operation_key,
            submitted_generation=base.store.generation,
        )
        == effect.terminal
    )


def test_missing_original_review_after_generation_change_requires_recovery(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    command = confirmation(draft).model_copy(
        update={
            "review_id": str(uuid4()),
            "operation_key": "R" * 43,
            "store_generation": str(uuid4()),
        }
    )
    with pytest.raises(ApiFailure, match="STORE_GENERATION_CHANGED"):
        flow.participant.prepare(
            flow.drafts.base.context(), draft_id=draft.draft_id, command=command
        )
    assert flow.counts() == (0, 0, 0, 0, 0)


def test_current_generation_fence_precedes_fresh_effects(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    base = flow.drafts.base
    with pytest.raises(ApiFailure, match="STORE_GENERATION_CHANGED"):
        base.auth.write(
            base.context(),
            lambda unit: flow.participant.apply_in_unit(
                unit,
                draft_id=draft.draft_id,
                command=confirmation(draft),
                generation=str(uuid4()),
                now=utc_text(base.clock.value),
                prepared=prepared,
            ),
        )
    assert flow.counts() == (0, 0, 0, 0, 0)


def test_original_status_requires_supplied_original_generation(flow: ConfirmationHarness) -> None:
    draft = flow.create()
    flow.commit(draft, flow.prepare(draft))
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        flow.participant.status(
            flow.drafts.base.context(),
            operation_key=confirmation(draft).operation_key,
            submitted_generation=str(uuid4()),
        )


def test_full_future_interval_is_rechecked_at_submission(flow: ConfirmationHarness) -> None:
    draft = flow.create(minutes=-24 * 60 + 30)
    prepared = flow.prepare(draft)
    flow.drafts.base.clock.value += timedelta(minutes=1)
    with pytest.raises(ApiFailure, match="REVIEW_STALE"):
        flow.commit(draft, prepared)
    assert flow.counts() == (0, 0, 0, 0, 0)


def test_global_projection_exhaustion_rejects_without_partial_lead(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    base = flow.drafts.base
    base.store.write(
        lambda db: db.add(
            ExportState(
                id=1,
                store_generation=base.store.generation,
                canonical_version=2_147_483_647,
                exported_version=None,
                state="pending",
                updated_at=utc_text(base.clock.value),
            )
        )
    )
    outcome = flow.commit(draft, prepared).terminal
    assert isinstance(outcome, OperationRejected) and outcome.rejection_code == "UNSUPPORTED_STATE"
    assert flow.counts() == (0, 1, 0, 0, 0)


def test_confirm_preserves_existing_reviewed_lead_values(flow: ConfirmationHarness) -> None:
    base = flow.drafts.base
    leads = LeadService(base.auth, inventory=flow.lead_inventory)
    values = buyer_values()
    saved = leads.save(base.context(), save_request(flow.drafts.sessions[0], values))
    draft = flow.create()
    outcome = flow.commit(draft, flow.prepare(draft)).terminal
    assert isinstance(outcome, OperationSucceeded)
    assert outcome.lead.lead_id == saved.lead.lead_id
    assert outcome.lead.revision == saved.lead.revision + 1
    current = leads.get(base.context())
    assert isinstance(current, LeadRecord)
    assert current.values == values and current.stage == "viewing_confirmed"
    assert flow.counts() == (1, 1, 1, 1, 2)


def test_status_refreshes_csv_overlay_without_replacing_original_json(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    committed = flow.commit(draft, flow.prepare(draft)).terminal
    assert isinstance(committed, OperationSucceeded)
    base = flow.drafts.base

    def failed(unit: OwnerUnit) -> None:
        state = unit.db.get(ExportState, 1)
        assert state is not None
        state.state = "failed"

    base.auth.write(base.context(), failed)
    result = flow.participant.status(
        base.context(),
        operation_key=confirmation(draft).operation_key,
        submitted_generation=base.store.generation,
    )
    assert isinstance(result, OperationSucceeded) and result.csv.state == "failed"
    assert result.booking == committed.booking and result.lead == committed.lead
    stored = base.store.read(lambda db: db.scalar(select(OperationOutcome.terminal_result_json)))
    assert stored == committed.model_dump(mode="json")


def test_simultaneous_original_key_has_one_effect_and_one_replay(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    context = flow.drafts.base.context()
    start = Barrier(2)

    def write() -> ConfirmationEffect:
        start.wait(timeout=5)
        return flow.drafts.base.auth.write(context, lambda unit: flow.apply(unit, draft, prepared))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(result.replayed for result in results) == [False, True]
    assert results[0].terminal == results[1].terminal
    assert flow.counts() == (1, 1, 1, 1, 1)


def test_simultaneous_edit_and_confirmation_have_one_valid_winner(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    prepared = flow.prepare(draft)
    context = flow.drafts.base.context()
    start = Barrier(2)

    def submit() -> str:
        start.wait(timeout=5)
        try:
            flow.drafts.base.auth.write(context, lambda unit: flow.apply(unit, draft, prepared))
            return "confirmed"
        except ApiFailure as exc:
            assert exc.code == "REVIEW_STALE"
            return "confirm_stale"

    def edit() -> str:
        start.wait(timeout=5)
        try:
            flow.drafts.service.update(context, draft.draft_id, update(draft, "suspend"))
            return "suspended"
        except ApiFailure as exc:
            assert exc.code == "UNSUPPORTED_STATE"
            return "edit_closed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        submit_future, edit_future = pool.submit(submit), pool.submit(edit)
        results = submit_future.result(timeout=20), edit_future.result(timeout=20)
    assert results in {("confirmed", "edit_closed"), ("confirm_stale", "suspended")}
    assert flow.counts() == ((1, 1, 1, 1, 1) if results[0] == "confirmed" else (0, 0, 0, 0, 0))


def test_terminal_replay_survives_parent_session_and_draft_removal(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    committed = flow.commit(draft, flow.prepare(draft)).terminal
    base = flow.drafts.base

    def remove_parents(unit: OwnerUnit) -> None:
        row = unit.draft(draft.draft_id)
        review = unit.review(confirmation(draft).review_id)
        row.active_review_id, review.draft_id = None, None
        unit.db.flush()
        unit.db.delete(row)
        unit.db.flush()
        unit.db.delete(unit.session(draft.session_id))

    base.auth.write(base.context(), remove_parents)
    counters = flow.drafts.inventory.prepares, flow.lead_inventory.reads
    assert flow.prepare(draft) is None
    result = base.auth.read(
        base.context(),
        lambda unit: flow.participant.lookup_in_unit(
            unit,
            draft_id=draft.draft_id,
            command=confirmation(draft),
            generation=base.store.generation,
            now=utc_text(base.clock.value),
        ),
    )
    assert result == committed
    assert counters == (flow.drafts.inventory.prepares, flow.lead_inventory.reads)
    assert flow.counts() == (1, 1, 1, 1, 1)


def test_concurrent_review_replacement_and_confirmation_keep_one_authority(
    flow: ConfirmationHarness,
) -> None:
    draft = flow.create()
    assert draft.review is not None
    original = confirmation(draft)
    prepared = flow.prepare(draft)
    base = flow.drafts.base
    context = base.context()
    before = base.service.get(context, draft.session_id)
    old_review = snapshot(base.store)["booking_reviews"][0]
    replacement = update(draft, "refresh_review")
    start = Barrier(2)

    def submit() -> ConfirmationEffect | str:
        start.wait(timeout=5)
        try:
            return base.auth.write(context, lambda unit: flow.apply(unit, draft, prepared))
        except ApiFailure as exc:
            assert exc.code == "REVIEW_STALE"
            return exc.code

    def refresh() -> BookingDraft | str:
        start.wait(timeout=5)
        try:
            return flow.drafts.service.update(context, draft.draft_id, replacement)
        except ApiFailure as exc:
            assert exc.code == "UNSUPPORTED_STATE"
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        submitted, refreshed = pool.submit(submit), pool.submit(refresh)
        outcome, renewed = submitted.result(timeout=20), refreshed.result(timeout=20)

    after = base.service.get(context, draft.session_id)
    rows = snapshot(base.store)
    retained = next(row for row in rows["booking_reviews"] if row["id"] == original.review_id)
    assert retained["immutable_payload_json"] == old_review["immutable_payload_json"]
    assert retained["operation_key"] == original.operation_key
    assert after.revision == before.revision + 1
    assert len(rows["booking_drafts"]) == 1
    assert confirmation(draft) == original
    if isinstance(outcome, ConfirmationEffect):
        assert renewed == "UNSUPPORTED_STATE"
        assert isinstance(outcome.terminal, OperationSucceeded) and not outcome.replayed
        assert outcome.terminal.operation_key == original.operation_key
        assert outcome.terminal.booking.review.review_id == original.review_id
        assert retained["state"] == "consumed" and len(rows["booking_reviews"]) == 1
        assert after.pending_intent.kind == "none" and after.current_draft_id is None
        assert flow.counts() == (1, 1, 1, 1, 1)
        assert flow.commit(draft, None).terminal == outcome.terminal
    else:
        assert outcome == "REVIEW_STALE" and isinstance(renewed, BookingDraft)
        assert renewed.state == "reviewable" and renewed.review is not None
        assert renewed.revision == draft.revision + 1
        assert renewed.review.review_id != original.review_id
        assert renewed.review.operation_key != original.operation_key
        assert retained["state"] == "invalidated" and len(rows["booking_reviews"]) == 2
        assert after.current_draft_id == renewed.draft_id
        assert after.pending_intent.kind == "viewing_review"
        assert after.pending_intent.review_id == renewed.review.review_id
        assert after.pending_intent.operation_key == renewed.review.operation_key
        assert flow.counts() == (0, 0, 0, 0, 0)
        with pytest.raises(ApiFailure, match="REVIEW_STALE"):
            flow.commit(draft, prepared)
        assert snapshot(base.store) == rows


@pytest.mark.parametrize("terminal_state", ["succeeded", "rejected"])
def test_original_terminal_replay_after_active_source_rules_change(
    flow: ConfirmationHarness,
    terminal_state: str,
) -> None:
    if terminal_state == "rejected":
        blocker = flow.create()
        blocker_result = flow.commit(blocker, flow.prepare(blocker))
        assert isinstance(blocker_result.terminal, OperationSucceeded)
    draft = flow.create(who=1)
    original = confirmation(draft)
    original_json = original.model_dump(mode="json")
    first = flow.commit(draft, flow.prepare(draft, who=1), who=1)
    assert first.terminal.state == terminal_state
    if isinstance(first.terminal, OperationRejected):
        assert first.terminal.rejection_code == "CAPACITY_UNAVAILABLE"
    assert flow.counts() == ((1, 1, 1, 1, 1) if terminal_state == "succeeded" else (1, 2, 1, 1, 1))
    base = flow.drafts.base
    prior = snapshot(base.store)
    flow.activate_second_snapshot()  # Existing explicit synthetic DB activation fixture.
    changed = snapshot(base.store)
    assert changed["active_inventory"][0]["snapshot_id"] != draft.ref.snapshot_id
    assert changed["active_inventory"][0]["revision"] == (
        prior["active_inventory"][0]["revision"] + 1
    )
    assert changed["active_rules"][0]["version"] != original.rules_version
    assert changed["active_rules"][0]["revision"] == prior["active_rules"][0]["revision"] + 1
    assert changed["operation_outcomes"] == prior["operation_outcomes"]
    assert changed["bookings"] == prior["bookings"]
    base.clock.value += timedelta(days=2)
    assert draft.review is not None
    assert datetime.fromisoformat(draft.review.ends_at_utc) < base.clock.value
    context = base.context(1)
    counters = (
        flow.drafts.inventory.prepares,
        flow.lead_inventory.reads,
        flow.lead_inventory.checks,
    )
    assert flow.participant.prepare(context, draft_id=draft.draft_id, command=original) is None
    replay = base.auth.write(
        context,
        lambda unit: flow.participant.apply_in_unit(
            unit,
            draft_id=draft.draft_id,
            command=original,
            generation=base.store.generation,
            now=utc_text(base.clock.value),
            prepared=None,
        ),
    )
    assert replay.replayed and replay.transition is None and replay.terminal == first.terminal
    assert original.model_dump(mode="json") == original_json
    assert confirmation(draft).model_dump(mode="json") == original_json
    assert counters == (
        flow.drafts.inventory.prepares,
        flow.lead_inventory.reads,
        flow.lead_inventory.checks,
    )
    assert snapshot(base.store) == changed


def test_rejected_key_stays_terminal_and_new_review_uses_real_free_capacity(
    flow: ConfirmationHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocker, rejected_draft = flow.create(), flow.create(who=1)
    a, b = flow.prepare(blocker), flow.prepare(rejected_draft, who=1)
    accepted = flow.commit(blocker, a)
    rejected = flow.commit(rejected_draft, b, who=1)
    assert isinstance(accepted.terminal, OperationSucceeded)
    assert isinstance(rejected.terminal, OperationRejected)
    assert rejected.terminal.rejection_code == "CAPACITY_UNAVAILABLE"
    original = confirmation(rejected_draft)
    original_json = original.model_dump(mode="json")
    base = flow.drafts.base
    before = snapshot(base.store)
    real_capacity = repo.capacity_taken
    release_calls: list[bool] = []

    def synthetic_now_free(unit: OwnerUnit, booking: BookingCoreReceipt) -> bool:
        release_calls.append(True)
        return False

    # Retain the existing synthetic capacity-release challenge for original replay.
    # It is not a cancellation or a mutation of the blocker's immutable booking.
    with monkeypatch.context() as release:
        release.setattr(repo, "capacity_taken", synthetic_now_free)
        assert flow.prepare(rejected_draft, who=1) is None
        replay = flow.commit(rejected_draft, None, who=1)
        assert replay.replayed and replay.transition is None
        assert replay.terminal == rejected.terminal and release_calls == []
        assert snapshot(base.store) == before
    assert repo.capacity_taken is real_capacity

    # The original slot stays occupied. A different reviewed interval is actually free.
    blocker_receipt = accepted.terminal.booking
    assert base.auth.write(base.context(1), lambda unit: real_capacity(unit, blocker_receipt))
    fresh = flow.create(who=1, minutes=30)
    assert fresh.review is not None and rejected_draft.review is not None
    assert fresh.draft_id != rejected_draft.draft_id
    assert fresh.review.review_id != original.review_id
    assert fresh.review.operation_key != original.operation_key
    assert fresh.review.resource_id == rejected_draft.review.resource_id
    assert fresh.review.starts_at_utc == rejected_draft.review.ends_at_utc
    assert flow.counts() == (1, 2, 1, 1, 1)
    observed_checks: list[tuple[str, bool]] = []

    def observe_real_capacity(unit: OwnerUnit, booking: BookingCoreReceipt) -> bool:
        taken = real_capacity(unit, booking)
        observed_checks.append((booking.review.operation_key, taken))
        return taken

    with monkeypatch.context() as observe:
        observe.setattr(repo, "capacity_taken", observe_real_capacity)
        fresh_result = flow.commit(fresh, flow.prepare(fresh, who=1), who=1)
    assert observed_checks == [(fresh.review.operation_key, False)]
    assert isinstance(fresh_result.terminal, OperationSucceeded) and not fresh_result.replayed
    assert fresh_result.terminal.operation_key == fresh.review.operation_key
    assert fresh_result.terminal.booking.review.review_id == fresh.review.review_id
    assert fresh_result.terminal.booking.booking_id != blocker_receipt.booking_id
    assert flow.counts() == (2, 3, 2, 2, 2)
    after = snapshot(base.store)
    assert flow.prepare(rejected_draft, who=1) is None
    replay = flow.commit(rejected_draft, None, who=1)
    assert replay.replayed and replay.transition is None and replay.terminal == rejected.terminal
    assert confirmation(rejected_draft).model_dump(mode="json") == original_json
    assert flow.commit(blocker, None).terminal == accepted.terminal
    assert snapshot(base.store) == after
