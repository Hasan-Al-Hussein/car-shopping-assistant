"""P9 owned persistence and race fixtures; injected inventory is not BE06 proof."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.api.schemas.inventory import SearchCriteria, SearchFilters, SearchResult
from app.api.schemas.sessions import (
    ClarificationIntent,
    ClarificationReply,
    MessageRequest,
    NoPendingIntent,
    PresentationRegisterRequest,
    SessionCreateRequest,
    SessionSelectionRequest,
    SessionState,
)
from app.core.errors import ApiFailure
from app.database.models import (
    ActiveInventory,
    CommandReceipt,
    ConversationSession,
    Message,
    Owner,
    OwnerCredential,
    Preference,
    PresentationItem,
    ResultPresentation,
)
from app.database.store import StoreError
from app.identity.service import utc_text
from app.sessions.service import SessionService, TurnTicket
from app.sessions.state import SessionContent
from tests.platform.session_cases import SessionHarness, answer, make_harness, ref
from tests.platform.test_identity import snapshot


@pytest.fixture
def harness() -> SessionHarness:
    return make_harness()


def message(revision: int = 0, text: str = "Show suitable cars") -> MessageRequest:
    return MessageRequest(client_message_id=str(uuid4()), expected_revision=revision, text=text)


def test_new_sessions_preserve_journey_and_other_owner_isolation(harness: SessionHarness) -> None:
    first, second, foreign = harness.create(), harness.create(), harness.create(1)
    assert first.session_id != second.session_id
    assert first.journey_id == second.journey_id != foreign.journey_id
    assert first.revision == second.revision == 0
    before = snapshot(harness.store)
    for target in (foreign.session_id, str(uuid4())):
        with pytest.raises(ApiFailure, match="NOT_FOUND"):
            harness.service.get(harness.context(), target)
    assert snapshot(harness.store) == before


def test_create_replay_and_get_do_not_renew(harness: SessionHarness) -> None:
    command = SessionCreateRequest(client_action_id=str(uuid4()))
    original = harness.service.create(harness.context(), command)
    before = snapshot(harness.store)
    harness.clock.value += timedelta(days=1)
    assert harness.service.create(harness.context(), command) == original
    assert harness.service.get(harness.context(write=False), original.session_id) == original
    assert snapshot(harness.store) == before


def test_begin_deduplicates_original_request_before_revision(harness: SessionHarness) -> None:
    session = harness.create()
    request = message()
    accepted = harness.service.begin(harness.context(), session.session_id, request)
    assert accepted.status == "accepted" and accepted.ticket is not None
    before = snapshot(harness.store)
    retry = harness.service.begin(harness.context(), session.session_id, request)
    assert retry.status == "pending" and retry.ticket is None
    assert retry.message_id == accepted.message_id
    assert snapshot(harness.store) == before
    changed = request.model_copy(update={"text": "Changed payload"})
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        harness.service.begin(harness.context(), session.session_id, changed)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        harness.service.begin(harness.context(), session.session_id, message())
    assert snapshot(harness.store) == before


def test_completed_replay_keeps_original_turn_and_current_revision(harness: SessionHarness) -> None:
    session = harness.create()
    request = message()
    accepted = harness.service.begin(harness.context(), session.session_id, request)
    assert accepted.ticket is not None
    proposal = answer(accepted)
    complete = harness.service.complete(harness.context(), accepted.ticket, proposal)
    assert complete.persistence == "saved" and complete.current_revision == 1
    later = harness.service.begin(harness.context(), session.session_id, message(1))
    before = snapshot(harness.store)
    replay = harness.service.begin(harness.context(), session.session_id, request)
    assert replay.result is not None
    assert replay.result.turn_revision == 1 and replay.result.current_revision == 2
    page = harness.service.transcript(harness.context(write=False), session.session_id)
    assert page.items[0].assistant_result == complete
    assert page.items[1].state == "pending" and later.status == "accepted"
    assert snapshot(harness.store) == before
    assert harness.service.complete(harness.context(), accepted.ticket, proposal) == replay.result
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        harness.service.complete(harness.context(), accepted.ticket, answer(accepted, "Changed"))


def test_late_completion_cannot_replace_new_selection_or_intent(harness: SessionHarness) -> None:
    session = harness.create()
    old = harness.service.begin(harness.context(), session.session_id, message())
    selected = harness.service.select(
        harness.context(),
        session.session_id,
        SessionSelectionRequest(
            expected_revision=1, client_action_id=str(uuid4()), selected_ref=ref("13")
        ),
    )
    assert old.ticket is not None
    update_context = SessionContent(criteria=SearchCriteria(query="obsolete criteria"))
    result = harness.service.complete(
        harness.context(), old.ticket, answer(old), update=update_context
    )
    assert (
        result.state == "superseded" and result.turn_revision == 1 and result.current_revision == 2
    )
    assert harness.service.get(harness.context(), session.session_id) == selected


def test_current_completion_revision_and_clarification_reply_binding(
    harness: SessionHarness,
) -> None:
    session = harness.create()
    first = harness.service.begin(harness.context(), session.session_id, message())
    pending = ClarificationIntent(
        kind="clarification",
        intent_id=str(uuid4()),
        created_revision=2,
        purpose="search_criteria",
        targets=["makes"],
        question="Which make?",
    )
    update_context = SessionContent(criteria=SearchCriteria(query="SUV"), pending_intent=pending)
    result = answer(first).model_copy(update={"state": "clarification", "pending_intent": pending})
    assert first.ticket is not None
    saved = harness.service.complete(harness.context(), first.ticket, result, update=update_context)
    assert saved.current_revision == 2
    before = snapshot(harness.store)
    wrong = message(2).model_copy(
        update={
            "clarification_reply": ClarificationReply(intent_id=str(uuid4()), created_revision=2)
        }
    )
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        harness.service.begin(harness.context(), session.session_id, wrong)
    assert snapshot(harness.store) == before
    correct = message(2).model_copy(
        update={
            "clarification_reply": ClarificationReply(
                intent_id=pending.intent_id, created_revision=2
            )
        }
    )
    accepted = harness.service.begin(harness.context(), session.session_id, correct)
    assert accepted.session.pending_intent == pending and accepted.session.revision == 3
    assert accepted.ticket is not None
    resolved_context = SessionContent(
        criteria=SearchCriteria(query="SUV", filters=SearchFilters(makes=["Honda"]))
    )
    resolved_result = answer(accepted).model_copy(
        update={"pending_intent": NoPendingIntent(kind="none")}
    )
    completed = harness.service.complete(
        harness.context(), accepted.ticket, resolved_result, update=resolved_context
    )
    current = harness.service.get(harness.context(), session.session_id)
    assert completed.current_revision == current.revision == 4
    assert current.pending_intent.kind == "none" and current.criteria.filters.makes == ["Honda"]


def pending_question(harness: SessionHarness) -> tuple[SessionState, ClarificationIntent]:
    session = harness.create()
    first = harness.service.begin(harness.context(), session.session_id, message())
    pending = ClarificationIntent(
        kind="clarification",
        intent_id=str(uuid4()),
        created_revision=2,
        purpose="search_criteria",
        targets=["makes"],
        question="Which make?",
    )
    assert first.ticket is not None
    harness.service.complete(
        harness.context(),
        first.ticket,
        answer(first).model_copy(update={"state": "clarification", "pending_intent": pending}),
        update=SessionContent(criteria=SearchCriteria(query="SUV"), pending_intent=pending),
    )
    return harness.service.get(harness.context(), session.session_id), pending


@pytest.mark.parametrize(
    "interruption", ["cancelled", "crashed", "provider_unavailable", "commit_failure"]
)
def test_clarification_remains_after_reply_interruption(
    harness: SessionHarness, interruption: str
) -> None:
    session, pending = pending_question(harness)
    request = MessageRequest(
        client_message_id=str(uuid4()),
        expected_revision=2,
        text="Honda",
        clarification_reply=ClarificationReply(intent_id=pending.intent_id, created_revision=2),
    )
    accepted = harness.service.begin(harness.context(), session.session_id, request)
    assert accepted.ticket is not None and accepted.session.pending_intent == pending
    service = harness.service
    if interruption == "crashed":
        service = SessionService(
            harness.auth, inventory=harness.inventory, instance_id=str(uuid4())
        )
    elif interruption == "provider_unavailable":
        failure = answer(accepted).model_copy(
            update={"state": "provider_unavailable", "provider_state": "unavailable"}
        )
        completed = service.complete(harness.context(), accepted.ticket, failure)
        assert completed.pending_intent == pending and completed.current_revision == 3
    elif interruption == "commit_failure":
        before = snapshot(harness.store)

        def fail_commit(connection: Connection) -> None:
            if connection.get_execution_options().get("store_write"):
                raise StoreError("SYNTHETIC_COMMIT_FAILURE")

        event.listen(Engine, "commit", fail_commit)
        try:
            with pytest.raises(StoreError, match="SYNTHETIC_COMMIT_FAILURE"):
                service.complete(
                    harness.context(),
                    accepted.ticket,
                    answer(accepted).model_copy(
                        update={"pending_intent": NoPendingIntent(kind="none")}
                    ),
                    update=SessionContent(
                        criteria=SearchCriteria(query="SUV", filters=SearchFilters(makes=["Honda"]))
                    ),
                )
        finally:
            event.remove(Engine, "commit", fail_commit)
        assert snapshot(harness.store) == before
    # "cancelled" intentionally abandons the issued ticket, as a cancelled caller does.
    before = snapshot(harness.store)
    replay = service.begin(harness.context(), session.session_id, request)
    expected = (
        "completed"
        if interruption == "provider_unavailable"
        else "interrupted"
        if interruption == "crashed"
        else "pending"
    )
    assert (
        replay.status == expected
        and replay.ticket is None
        and replay.session.pending_intent == pending
    )
    assert snapshot(harness.store) == before
    # A later different message still receives the unresolved hard-criterion question.
    later = service.begin(harness.context(), session.session_id, message(3, "Show the cars"))
    assert later.session.pending_intent == pending


def test_failed_clarification_completion_cannot_clear_pending_question(
    harness: SessionHarness,
) -> None:
    session, pending = pending_question(harness)
    request = MessageRequest(
        client_message_id=str(uuid4()),
        expected_revision=2,
        text="Honda",
        clarification_reply=ClarificationReply(intent_id=pending.intent_id, created_revision=2),
    )
    accepted = harness.service.begin(harness.context(), session.session_id, request)
    assert accepted.ticket is not None
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        harness.service.complete(
            harness.context(),
            accepted.ticket,
            answer(accepted).model_copy(
                update={
                    "state": "provider_unavailable",
                    "provider_state": "unavailable",
                    "pending_intent": NoPendingIntent(kind="none"),
                }
            ),
            update=SessionContent(),
        )
    assert snapshot(harness.store) == before
    assert harness.service.get(harness.context(), session.session_id).pending_intent == pending


def test_competing_clarification_replies_keep_newer_question_from_late_completion(
    harness: SessionHarness,
) -> None:
    session, pending = pending_question(harness)

    def reply(revision: int, text: str) -> MessageRequest:
        return MessageRequest(
            client_message_id=str(uuid4()),
            expected_revision=revision,
            text=text,
            clarification_reply=ClarificationReply(intent_id=pending.intent_id, created_revision=2),
        )

    old = harness.service.begin(harness.context(), session.session_id, reply(2, "Honda"))
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        harness.service.begin(harness.context(), session.session_id, reply(2, "Toyota"))
    newer = harness.service.begin(harness.context(), session.session_id, reply(3, "Maybe Toyota"))
    assert (
        newer.session.pending_intent == pending
        and old.ticket is not None
        and newer.ticket is not None
    )
    replacement = ClarificationIntent(
        kind="clarification",
        intent_id=str(uuid4()),
        created_revision=5,
        purpose="search_criteria",
        targets=["makes"],
        question="Confirm Toyota as the make?",
    )
    harness.service.complete(
        harness.context(),
        newer.ticket,
        answer(newer).model_copy(update={"state": "clarification", "pending_intent": replacement}),
        update=SessionContent(criteria=SearchCriteria(query="SUV"), pending_intent=replacement),
    )
    late = harness.service.complete(
        harness.context(),
        old.ticket,
        answer(old).model_copy(update={"pending_intent": NoPendingIntent(kind="none")}),
        update=SessionContent(criteria=SearchCriteria(query="obsolete")),
    )
    assert late.state == "superseded" and late.current_revision == 5
    assert harness.service.get(harness.context(), session.session_id).pending_intent == replacement


def test_restart_reopens_state_and_reports_interrupted_without_reexecution(
    harness: SessionHarness,
) -> None:
    session = harness.create()
    request = message()
    admitted = harness.service.begin(harness.context(), session.session_id, request)
    another_service = SessionService(harness.auth, inventory=harness.inventory)
    assert another_service.begin(harness.context(), session.session_id, request).status == "pending"
    restarted = SessionService(harness.auth, inventory=harness.inventory, instance_id=str(uuid4()))
    before = snapshot(harness.store)
    replay = restarted.begin(harness.context(), session.session_id, request)
    assert replay.status == "interrupted" and replay.ticket is None
    assert (
        restarted.transcript(harness.context(), session.session_id).items[0].state == "interrupted"
    )
    assert restarted.get(harness.context(), session.session_id).revision == 1
    assert snapshot(harness.store) == before
    assert admitted.ticket is not None
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        restarted.complete(harness.context(), admitted.ticket, answer(admitted))


def test_ticket_cannot_be_constructed_or_used_for_other_owner(harness: SessionHarness) -> None:
    with pytest.raises(TypeError):
        TurnTicket()
    session = harness.create()
    admitted = harness.service.begin(harness.context(), session.session_id, message())
    assert admitted.ticket is not None
    with pytest.raises(TypeError):
        admitted.ticket._session_id = str(uuid4())
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        harness.service.complete(harness.context(1), admitted.ticket, answer(admitted))
    assert snapshot(harness.store) == before


def test_pages_bind_fixed_boundary_and_restart_key(harness: SessionHarness) -> None:
    session = harness.create()
    for revision in range(3):
        harness.service.begin(
            harness.context(), session.session_id, message(revision, f"Turn {revision}")
        )
    first = harness.service.transcript(harness.context(), session.session_id, page_size=1)
    assert first.next_cursor is not None and first.observed_revision == 3
    harness.service.begin(harness.context(), session.session_id, message(3, "Later turn"))
    restarted = SessionService(harness.auth, instance_id=str(uuid4()))
    rest = restarted.transcript(harness.context(), session.session_id, cursor=first.next_cursor)
    assert [turn.accepted_revision for turn in rest.items] == [2, 3]
    assert rest.next_cursor is None and rest.observed_revision == 3
    assert all(turn.state == "interrupted" for turn in rest.items)


@pytest.mark.parametrize("variant", ["tampered", "different_session", "different_owner"])
def test_cursor_rejects_wrong_binding(harness: SessionHarness, variant: str) -> None:
    session = harness.create()
    for revision in range(2):
        harness.service.begin(harness.context(), session.session_id, message(revision))
    cursor = harness.service.transcript(
        harness.context(), session.session_id, page_size=1
    ).next_cursor
    assert cursor is not None
    target, who = session.session_id, 0
    if variant == "tampered":
        cursor = cursor[:-1] + ("a" if cursor[-1] != "a" else "b")
    else:
        who = int(variant == "different_owner")
        target = harness.create(who).session_id
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
        harness.service.transcript(harness.context(who), target, cursor=cursor)
    assert snapshot(harness.store) == before


def test_presentations_preserve_order_across_paging_and_independent_owners(
    harness: SessionHarness,
) -> None:
    a, b = harness.create(), harness.create(1)
    proof = harness.proof()
    command = PresentationRegisterRequest(
        expected_revision=0, client_action_id=str(uuid4()), presentation=proof
    )
    first = harness.service.register(harness.context(), a.session_id, command)
    other = harness.service.register(harness.context(1), b.session_id, command)
    assert first.active_presentation_id != other.active_presentation_id
    assert first.active_presentation_id != proof.presentation_id
    second = harness.service.register(
        harness.context(),
        a.session_id,
        PresentationRegisterRequest(
            expected_revision=1,
            client_action_id=str(uuid4()),
            presentation=harness.proof(("13", "12")),
        ),
    )
    assert first.active_presentation_id is not None and second.active_presentation_id is not None
    assert (
        harness.service.ordinal(
            harness.context(), a.session_id, first.active_presentation_id, 0
        ).model_dump()
        == ref("12").model_dump()
    )
    assert (
        harness.service.ordinal(
            harness.context(), a.session_id, second.active_presentation_id, 0
        ).model_dump()
        == ref("13").model_dump()
    )
    assert second.criteria == a.criteria
    harness.clock.value += timedelta(minutes=6)
    prepares = harness.inventory.prepares
    assert harness.service.register(harness.context(), a.session_id, command) == second
    assert harness.inventory.prepares == prepares


def test_presentation_refs_return_original_immutable_order_without_current_inventory(
    harness: SessionHarness,
) -> None:
    session = harness.create()
    original = harness.service.register(
        harness.context(),
        session.session_id,
        PresentationRegisterRequest(
            expected_revision=0, client_action_id=str(uuid4()), presentation=harness.proof()
        ),
    )
    assert original.active_presentation_id is not None
    harness.service.register(
        harness.context(),
        session.session_id,
        PresentationRegisterRequest(
            expected_revision=1,
            client_action_id=str(uuid4()),
            presentation=harness.proof(("13", "12")),
        ),
    )
    harness.store.write(lambda db: db.execute(delete(ActiveInventory)).close())
    before, prepares = snapshot(harness.store), harness.inventory.prepares
    view = harness.service.presentation_refs(
        harness.context(write=False), session.session_id, original.active_presentation_id
    )
    assert (
        view.session_id == session.session_id
        and view.presentation_id == original.active_presentation_id
    )
    assert view.snapshot_id == ref().snapshot_id and view.created_revision == 1
    assert view.refs == (ref("12"), ref("13"))
    with pytest.raises((AttributeError, ValueError)):
        view.refs[0].source_id = "13"  # type: ignore[misc]  # Exercise the runtime immutability guard.
    with pytest.raises(AttributeError):
        view.refs = ()  # type: ignore[misc]  # Exercise the frozen dataclass at runtime.
    assert snapshot(harness.store) == before and harness.inventory.prepares == prepares


def test_presentation_refs_empty_and_parent_authority(harness: SessionHarness) -> None:
    session, other = harness.create(), harness.create()
    result = harness.service.register(
        harness.context(),
        session.session_id,
        PresentationRegisterRequest(
            expected_revision=0, client_action_id=str(uuid4()), presentation=harness.proof(())
        ),
    )
    assert result.active_presentation_id is not None
    before = snapshot(harness.store)
    assert (
        harness.service.presentation_refs(
            harness.context(), session.session_id, result.active_presentation_id
        ).refs
        == ()
    )
    for who, target, presentation in (
        (1, session.session_id, result.active_presentation_id),
        (0, other.session_id, result.active_presentation_id),
        (0, session.session_id, str(uuid4())),
    ):
        with pytest.raises(ApiFailure, match="NOT_FOUND"):
            harness.service.presentation_refs(harness.context(who), target, presentation)
    harness.clock.value += timedelta(days=8)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        harness.service.presentation_refs(
            harness.context(), session.session_id, result.active_presentation_id
        )
    assert snapshot(harness.store) == before


@pytest.mark.parametrize("variant", ["gap", "duplicate", "oversized", "future_revision"])
def test_presentation_refs_reject_corrupt_original_order(
    harness: SessionHarness, variant: str
) -> None:
    session = harness.create()
    result = harness.service.register(
        harness.context(),
        session.session_id,
        PresentationRegisterRequest(
            expected_revision=0, client_action_id=str(uuid4()), presentation=harness.proof()
        ),
    )
    presentation = result.active_presentation_id
    assert presentation is not None

    def corrupt(db: Session) -> None:
        if variant == "future_revision":
            db.execute(
                update(ResultPresentation)
                .where(ResultPresentation.id == presentation)
                .values(created_revision=99)
            )
        elif variant == "gap":
            db.execute(
                update(PresentationItem)
                .where(
                    PresentationItem.presentation_id == presentation, PresentationItem.ordinal == 1
                )
                .values(ordinal=2)
            )
        elif variant == "duplicate":
            db.execute(
                update(PresentationItem)
                .where(
                    PresentationItem.presentation_id == presentation, PresentationItem.ordinal == 1
                )
                .values(source_id="12")
            )
        else:
            for ordinal in range(2, 51):
                db.add(
                    PresentationItem(
                        presentation_id=presentation, ordinal=ordinal, **ref().model_dump()
                    )
                )

    harness.store.write(corrupt)
    before = snapshot(harness.store)
    with pytest.raises(StoreError, match="SESSION_PRESENTATION_INCOMPATIBLE"):
        harness.service.presentation_refs(harness.context(), session.session_id, presentation)
    assert snapshot(harness.store) == before


@pytest.mark.parametrize("variant", ["signature", "expired_at_write", "activation", "missing_ref"])
def test_new_presentation_admission_fails_atomically(harness: SessionHarness, variant: str) -> None:
    session = harness.create()
    proof = harness.proof(("99",) if variant == "missing_ref" else ("12",))
    if variant == "signature":
        proof = proof.model_copy(update={"signature": "x" * 43})
    if variant == "expired_at_write":
        harness.inventory.after_prepare = lambda: setattr(
            harness.clock, "value", harness.clock.value + timedelta(minutes=6)
        )
    if variant == "activation":
        harness.inventory.after_prepare = lambda: harness.store.write(
            lambda db: mutate_activation(db)
        )
    command = PresentationRegisterRequest(
        expected_revision=0, client_action_id=str(uuid4()), presentation=proof
    )
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure):
        harness.service.register(harness.context(), session.session_id, command)
    assert harness.service.get(harness.context(), session.session_id).revision == 0
    assert harness.store.read(lambda db: len(db.scalars(select(Message)).all())) == 0
    after = snapshot(harness.store)
    assert {key: value for key, value in before.items() if key != "active_inventory"} == {
        key: value for key, value in after.items() if key != "active_inventory"
    }


def mutate_activation(db: object) -> None:
    from sqlalchemy.orm import Session

    assert isinstance(db, Session)
    db.execute(update(ActiveInventory).values(revision=2))


def test_empty_presentation_and_changed_payload_conflict(harness: SessionHarness) -> None:
    session = harness.create()
    command = PresentationRegisterRequest(
        expected_revision=0, client_action_id=str(uuid4()), presentation=harness.proof(())
    )
    saved = harness.service.register(harness.context(), session.session_id, command)
    assert saved.active_presentation_id is not None
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        harness.service.ordinal(
            harness.context(), session.session_id, saved.active_presentation_id, 0
        )
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        harness.service.register(
            harness.context(),
            session.session_id,
            command.model_copy(update={"presentation": harness.proof()}),
        )


def test_selection_replay_cannot_undo_newer_selection(harness: SessionHarness) -> None:
    session = harness.create()
    original = SessionSelectionRequest(
        expected_revision=0, client_action_id=str(uuid4()), selected_ref=ref()
    )
    harness.service.select(harness.context(), session.session_id, original)
    current = harness.service.select(
        harness.context(),
        session.session_id,
        SessionSelectionRequest(
            expected_revision=1, client_action_id=str(uuid4()), selected_ref=ref("13")
        ),
    )
    before = snapshot(harness.store)
    assert harness.service.select(harness.context(), session.session_id, original) == current
    assert snapshot(harness.store) == before


def test_expired_session_is_not_revived_or_deleted(harness: SessionHarness) -> None:
    session = harness.create()
    request = message()
    admitted = harness.service.begin(harness.context(), session.session_id, request)
    harness.clock.value += timedelta(days=7)
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        harness.service.get(harness.context(), session.session_id)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        harness.service.begin(harness.context(), session.session_id, request)
    assert admitted.ticket is not None
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        harness.service.complete(harness.context(), admitted.ticket, answer(admitted))
    assert snapshot(harness.store) == before


def test_completion_failure_rolls_back_without_saved_claim(harness: SessionHarness) -> None:
    session = harness.create()
    admitted = harness.service.begin(harness.context(), session.session_id, message())
    assert admitted.ticket is not None
    before = snapshot(harness.store)
    bad = SessionContent(current_draft_id=str(uuid4()))
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        harness.service.complete(harness.context(), admitted.ticket, answer(admitted), update=bad)
    assert snapshot(harness.store) == before


def test_recall_reads_real_typed_entries_without_reconfirmation(harness: SessionHarness) -> None:
    session = harness.create()

    def seed(unit: object) -> None:
        from app.identity.authorization import OwnerUnit

        assert isinstance(unit, OwnerUnit)
        unit.db.add(
            Preference(
                owner_id=unit.owner_id,
                key="makes",
                value_json={"value": ["Honda"]},
                strength="soft",
                source_session_reference=session.session_id,
                source_action_id=str(uuid4()),
                source_message_reference=None,
                confirmed_at=utc_text(harness.clock.value),
                expires_at=utc_text(harness.clock.value + timedelta(days=30)),
                applicability="confirmed",
            )
        )
        owner = unit.db.get(Owner, unit.owner_id)
        assert owner is not None
        owner.preference_revision = 1

    harness.auth.write(harness.context(), seed)
    before = snapshot(harness.store)
    record = harness.service.get(harness.context(), session.session_id).recalled_preferences
    assert record.revision == 1 and record.entries[0].preference.value == ["Honda"]
    assert snapshot(harness.store) == before
    assert harness.create().recalled_preferences == record
    assert harness.create(1).recalled_preferences.entries == []


def test_missing_live_gateway_fails_closed(harness: SessionHarness) -> None:
    session = harness.create()
    service = SessionService(harness.auth)
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        service.select(
            harness.context(),
            session.session_id,
            SessionSelectionRequest(
                expected_revision=0, client_action_id=str(uuid4()), selected_ref=ref()
            ),
        )
    assert snapshot(harness.store) == before


def test_two_simultaneous_tabs_accept_one_expected_revision(harness: SessionHarness) -> None:
    session = harness.create()
    contexts = (harness.context(), harness.context())
    barrier = Barrier(2, timeout=5)

    def submit(index: int) -> str:
        barrier.wait()
        try:
            return harness.service.begin(contexts[index], session.session_id, message()).status
        except ApiFailure as failure:
            return failure.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, (0, 1)))
    assert sorted(results) == ["REVISION_CONFLICT", "accepted"]
    assert harness.service.get(harness.context(), session.session_id).revision == 1
    assert len(harness.service.transcript(harness.context(), session.session_id).items) == 1


def test_write_commit_failure_never_returns_saved_result(harness: SessionHarness) -> None:
    session = harness.create()
    accepted = harness.service.begin(harness.context(), session.session_id, message())
    assert accepted.ticket is not None
    before = snapshot(harness.store)

    def fail_commit(connection: Connection) -> None:
        if connection.get_execution_options().get("store_write"):
            raise StoreError("SYNTHETIC_COMMIT_FAILURE")

    event.listen(Engine, "commit", fail_commit)
    try:
        with pytest.raises(StoreError, match="SYNTHETIC_COMMIT_FAILURE"):
            harness.service.complete(harness.context(), accepted.ticket, answer(accepted))
    finally:
        event.remove(Engine, "commit", fail_commit)
    assert snapshot(harness.store) == before
    replay = harness.service.begin(harness.context(), session.session_id, accepted.request)
    assert replay.status == "pending" and replay.result is None and replay.ticket is None


def test_foreign_presentation_and_nonmember_selection_roll_back(harness: SessionHarness) -> None:
    local, foreign = harness.create(), harness.create(1)
    proof = harness.proof(("12",))
    owned = harness.service.register(
        harness.context(),
        local.session_id,
        PresentationRegisterRequest(
            expected_revision=0, client_action_id=str(uuid4()), presentation=proof
        ),
    )
    other = harness.service.register(
        harness.context(1),
        foreign.session_id,
        PresentationRegisterRequest(
            expected_revision=0, client_action_id=str(uuid4()), presentation=proof
        ),
    )
    before = snapshot(harness.store)
    for presentation_id, selected_ref, error in (
        (other.active_presentation_id, ref(), "NOT_FOUND"),
        (owned.active_presentation_id, ref("13"), "PRESENTATION_INVALID"),
    ):
        with pytest.raises(ApiFailure, match=error):
            harness.service.select(
                harness.context(),
                local.session_id,
                SessionSelectionRequest(
                    expected_revision=1,
                    client_action_id=str(uuid4()),
                    selected_ref=selected_ref,
                    presentation_id=presentation_id,
                ),
            )
    assert snapshot(harness.store) == before


def test_completion_does_not_renew_and_expired_create_receipt_never_recreates(
    harness: SessionHarness,
) -> None:
    command = SessionCreateRequest(client_action_id=str(uuid4()))
    session = harness.service.create(harness.context(), command)
    accepted = harness.service.begin(harness.context(), session.session_id, message())
    assert accepted.ticket is not None
    before = harness.store.read(
        lambda db: db.scalar(
            select(ConversationSession.expires_at).where(
                ConversationSession.id == session.session_id
            )
        )
    )
    harness.clock.value += timedelta(days=1)
    harness.service.complete(harness.context(), accepted.ticket, answer(accepted))
    assert (
        harness.store.read(
            lambda db: db.scalar(
                select(ConversationSession.expires_at).where(
                    ConversationSession.id == session.session_id
                )
            )
        )
        == before
    )
    harness.store.write(
        lambda db: expire_receipt(db, command.client_action_id, utc_text(harness.clock.value))
    )
    before_rows = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="REPLAY_EXPIRED"):
        harness.service.create(harness.context(), command)
    assert snapshot(harness.store) == before_rows


def expire_receipt(db: Session, action_id: str, instant: str) -> None:
    db.execute(
        update(CommandReceipt)
        .where(CommandReceipt.client_action_id == action_id)
        .values(expires_at=instant)
    )


def test_own_turn_can_atomically_record_search_then_select_ordinal(harness: SessionHarness) -> None:
    session = harness.create()
    search = harness.service.begin(harness.context(), session.session_id, message())
    assert search.ticket is not None
    proof = harness.proof(("13", "12"))
    proposal = answer(search)
    first_result = harness.service.complete(
        harness.context(),
        search.ticket,
        proposal,
        presentation=proof,
        update=SessionContent(criteria=SearchCriteria(query="Honda")),
    )
    assert first_result.state == "answered" and first_result.turn_revision == 1
    assert first_result.current_revision == 2
    current = harness.service.get(harness.context(), session.session_id)
    assert current.active_presentation_id is not None
    first_ref = harness.service.ordinal(
        harness.context(), session.session_id, current.active_presentation_id, 0
    )
    assert first_ref.model_dump() == ref("13").model_dump()
    second = harness.service.begin(
        harness.context(), session.session_id, message(2, "The first one")
    )
    assert second.ticket is not None
    selected = harness.service.complete(
        harness.context(), second.ticket, answer(second), selection=first_ref
    )
    assert selected.state == "answered" and selected.current_revision == 4
    latest = harness.service.get(harness.context(), session.session_id)
    assert (
        latest.selected_ref == first_ref
        and latest.active_presentation_id == current.active_presentation_id
    )
    before = snapshot(harness.store)
    harness.clock.value += timedelta(minutes=6)
    replay = harness.service.complete(
        harness.context(),
        search.ticket,
        proposal,
        presentation=proof,
        update=SessionContent(criteria=SearchCriteria(query="Honda")),
    )
    assert replay.turn_revision == 1 and replay.current_revision == 4
    assert snapshot(harness.store) == before


def test_late_turn_cannot_register_its_search_after_newer_turn(harness: SessionHarness) -> None:
    session = harness.create()
    old = harness.service.begin(harness.context(), session.session_id, message())
    assert old.ticket is not None
    harness.service.begin(harness.context(), session.session_id, message(1, "Newer topic"))
    before = harness.inventory.prepares
    late = harness.service.complete(
        harness.context(), old.ticket, answer(old), presentation=harness.proof(), selection=ref()
    )
    assert late.state == "superseded" and late.current_revision == 2
    assert harness.inventory.prepares == before
    assert harness.store.read(lambda db: len(db.scalars(select(ResultPresentation)).all())) == 0
    assert harness.service.get(harness.context(), session.session_id).selected_ref is None


def test_stored_foreign_context_pointer_is_denied_without_repair(harness: SessionHarness) -> None:
    local, foreign = harness.create(), harness.create(1)
    other = harness.service.register(
        harness.context(1),
        foreign.session_id,
        PresentationRegisterRequest(
            expected_revision=0, client_action_id=str(uuid4()), presentation=harness.proof()
        ),
    )
    assert other.active_presentation_id is not None
    invalid = SessionContent(active_presentation_id=other.active_presentation_id)

    def corrupt(db: Session) -> None:
        db.execute(
            update(ConversationSession)
            .where(ConversationSession.id == local.session_id)
            .values(state_json=invalid.model_dump(mode="json"))
        )

    harness.store.write(corrupt)
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        harness.service.get(harness.context(), local.session_id)
    assert snapshot(harness.store) == before


def test_malformed_stored_turn_fails_without_fabricated_answer(harness: SessionHarness) -> None:
    session = harness.create()
    admitted = harness.service.begin(harness.context(), session.session_id, message())

    def corrupt(db: Session) -> None:
        db.execute(
            update(Message)
            .where(Message.id == admitted.message_id)
            .values(result_json={"version": "invalid"})
        )

    harness.store.write(corrupt)
    before = snapshot(harness.store)
    with pytest.raises(StoreError, match="SESSION_STATE_INCOMPATIBLE"):
        harness.service.transcript(harness.context(), session.session_id)
    assert snapshot(harness.store) == before


def test_revoked_credential_cannot_complete_accepted_ticket(harness: SessionHarness) -> None:
    context = harness.context()
    session = harness.create()
    admitted = harness.service.begin(context, session.session_id, message())
    assert admitted.ticket is not None

    def revoke(db: Session) -> None:
        db.execute(
            update(OwnerCredential)
            .where(OwnerCredential.context_id == context.context_id)
            .values(revoked_at=utc_text(harness.clock.value))
        )

    harness.store.write(revoke)
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
        harness.service.complete(context, admitted.ticket, answer(admitted))
    assert snapshot(harness.store) == before


def test_current_completion_accepts_proof_and_member_selection_together(
    harness: SessionHarness,
) -> None:
    session = harness.create()
    admitted = harness.service.begin(harness.context(), session.session_id, message())
    assert admitted.ticket is not None
    completed = harness.service.complete(
        harness.context(),
        admitted.ticket,
        answer(admitted),
        presentation=harness.proof(),
        selection=ref("13"),
    )
    assert completed.state == "answered" and completed.current_revision == 2
    state = harness.service.get(harness.context(), session.session_id)
    assert (
        state.selected_ref is not None and state.selected_ref.model_dump() == ref("13").model_dump()
    )
    assert state.active_presentation_id is not None


def test_completion_automatically_records_search_results_own_proof(harness: SessionHarness) -> None:
    session = harness.create()
    admitted = harness.service.begin(harness.context(), session.session_id, message())
    assert admitted.ticket is not None
    criteria = SearchCriteria(query="Unsupported search")
    search = SearchResult(
        client_request_id=str(uuid4()),
        state="no_supported_matches",
        items=[],
        supported_total=0,
        next_cursor=None,
        presentation=harness.proof(()),
        applied_criteria=criteria,
        evidence_coverage=[],
    )
    proposed = answer(admitted).model_copy(update={"search": search})
    completed = harness.service.complete(
        harness.context(), admitted.ticket, proposed, update=SessionContent(criteria=criteria)
    )
    assert completed.state == "answered" and completed.current_revision == 2
    assert completed.search == search
    current = harness.service.get(harness.context(), session.session_id)
    assert current.active_presentation_id is not None and current.criteria == criteria


def test_simultaneous_identical_message_has_one_ticket_and_one_record(
    harness: SessionHarness,
) -> None:
    session = harness.create()
    request = message()
    contexts = (harness.context(), harness.context())
    barrier = Barrier(2, timeout=5)

    def submit(index: int) -> tuple[str, bool]:
        barrier.wait()
        admitted = harness.service.begin(contexts[index], session.session_id, request)
        return admitted.status, admitted.ticket is not None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, (0, 1)))
    assert sorted(results) == [("accepted", True), ("pending", False)]
    assert len(harness.service.transcript(harness.context(), session.session_id).items) == 1
