"""BE11 service source fixtures; actual execution and OS restart remain separate."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.api.schemas.memory import PreferenceCollectionUpdate, PreferencesUpdate
from app.api.schemas.sessions import MessageRequest
from app.core.errors import ApiFailure
from app.database.models import CommandReceipt, Preference
from app.database.store import StoreError
from app.identity.service import utc_text
from app.memory.repository import purge_expired
from app.memory.service import PreferenceService
from tests.platform.memory_shortlist_cases import (
    MemoryHarness,
    failed_commit,
    make_memory_harness,
    seed_operational_rows,
)
from tests.platform.test_identity import snapshot


@pytest.fixture
def harness() -> MemoryHarness:
    return make_memory_harness()


def remember(
    session_id: str, revision: int = 0, makes: tuple[str, ...] = ("Honda",)
) -> PreferencesUpdate:
    return PreferencesUpdate.model_validate(
        dict(
            session_id=session_id,
            expected_revision=revision,
            client_action_id=str(uuid4()),
            scope="durable",
            intent="remember",
            changes=[dict(key="makes", value=list(makes), strength="soft")],
        )
    )


def mode(session_id: str, revision: int, *, enabled: bool) -> PreferenceCollectionUpdate:
    return PreferenceCollectionUpdate(
        session_id=session_id,
        expected_revision=revision,
        client_action_id=str(uuid4()),
        intent="resume_saving" if enabled else "stop_saving",
    )


def test_explicit_memory_new_session_new_service_same_name_isolation(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    command = remember(session.session_id)
    saved = service.update(base.context(), command)
    assert saved.revision == 1 and saved.entries[0].source_action_id == command.client_action_id
    assert saved.entries[0].source_session_id == session.session_id
    assert datetime.fromisoformat(saved.entries[0].expires_at) - datetime.fromisoformat(
        saved.entries[0].confirmed_at
    ) == timedelta(days=30)
    assert base.create().recalled_preferences == saved
    assert PreferenceService(base.auth).get(base.context()) == saved
    assert service.get(base.context(1)).entries == []
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        service.update(base.context(1), remember(session.session_id))
    assert snapshot(base.store) == before


def test_hypothetical_turn_and_current_override_do_not_rewrite_memory(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    saved = service.update(base.context(), remember(session.session_id))
    base.service.begin(
        base.context(),
        session.session_id,
        MessageRequest(
            client_message_id=str(uuid4()),
            expected_revision=0,
            text="For this one hypothetical search, consider Toyota only.",
        ),
    )
    before = snapshot(base.store)
    assert service.recall(base.context(), keys=("makes",), current_keys=("makes",)).entries == []
    assert service.get(base.context()) == saved
    assert snapshot(base.store) == before


@pytest.mark.parametrize(
    "mutation",
    [
        {"scope": "session"},
        {"intent": "hypothetical"},
        {"owner_id": str(uuid4())},
        {"changes": [{"key": "sensitive_profile", "value": ["inferred"], "strength": "hard"}]},
    ],
)
def test_unsafe_or_non_durable_command_revalidated(
    harness: MemoryHarness, mutation: dict[str, object]
) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    command = remember(session.session_id)
    before = snapshot(base.store)
    # model_copy is unchecked; the service boundary must still validate it.
    if "owner_id" in mutation:
        data = command.model_dump()
        data.update(mutation)
        with pytest.raises(ValueError):
            PreferencesUpdate.model_validate(data)
    else:
        with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
            service.update(base.context(), command.model_copy(update=mutation))
    assert snapshot(base.store) == before


def test_per_field_noop_and_clear_preserve_unrelated_provenance(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    command = remember(session.session_id)
    command = PreferencesUpdate.model_validate(
        {
            **command.model_dump(),
            "changes": [
                *command.model_dump()["changes"],
                {
                    "key": "budget",
                    "value": {"maximum": 8_000_000, "currency": "AED"},
                    "strength": "hard",
                },
            ],
        }
    )
    original = service.update(base.context(), command)
    base.clock.value += timedelta(days=1)
    noop = service.update(base.context(), remember(session.session_id, 1))
    assert noop.revision == 2 and noop.entries == original.entries
    changed = service.update(base.context(), remember(session.session_id, 2, ("Toyota",)))
    original_by_key = {entry.preference.key: entry for entry in original.entries}
    changed_by_key = {entry.preference.key: entry for entry in changed.entries}
    assert changed_by_key["budget"] == original_by_key["budget"]
    assert changed_by_key["makes"].confirmed_at != original_by_key["makes"].confirmed_at
    cleared = service.update(base.context(), remember(session.session_id, 3, ()))
    assert cleared.entries == [original_by_key["budget"]]


def test_stop_resume_clear_and_old_retry_do_not_reapply_or_renew(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    command = remember(session.session_id)
    original = service.update(base.context(), command)
    stopped = service.update(base.context(), mode(session.session_id, 1, enabled=False))
    assert stopped.collection_mode == "disabled" and stopped.entries == original.entries
    assert service.update(base.context(), command) == stopped
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        service.update(base.context(), remember(session.session_id, 2, ("Toyota",)))
    mixed = remember(session.session_id, 2, ())
    mixed = PreferencesUpdate.model_validate(
        {
            **mixed.model_dump(),
            "changes": [
                *mixed.model_dump()["changes"],
                {
                    "key": "budget",
                    "value": {"maximum": 9_000_000, "currency": "AED"},
                    "strength": "hard",
                },
            ],
        }
    )
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        service.update(base.context(), mixed)
    assert snapshot(base.store) == before
    cleared = service.update(base.context(), remember(session.session_id, 2, ()))
    assert cleared.entries == [] and cleared.collection_mode == "disabled"
    resumed = service.update(base.context(), mode(session.session_id, 3, enabled=True))
    assert resumed.entries == [] and resumed.revision == 4


def test_repeated_mode_commands_preserve_entry_timestamps(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    original = service.update(base.context(), remember(session.session_id))
    for revision, enabled in enumerate((True, False, False, True), start=1):
        result = service.update(base.context(), mode(session.session_id, revision, enabled=enabled))
        assert result.revision == revision + 1 and result.entries == original.entries


def test_payload_bound_replay_precedes_revision_and_expired_origin_session(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    original = remember(session.session_id)
    service.update(base.context(), original)
    latest = service.update(base.context(), remember(session.session_id, 1, ("Toyota",)))
    base.clock.value += timedelta(days=8)
    before = snapshot(base.store)
    assert service.update(base.context(), original) == latest
    with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
        service.update(base.context(), original.model_copy(update={"expected_revision": 2}))
    assert snapshot(base.store) == before


def test_reconfirmation_state_and_equal_value_remain_truthful(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    service.update(base.context(), remember(session.session_id))
    base.store.write(
        lambda db: db.execute(
            update(Preference).values(applicability="requires_reconfirmation")
        ).close()
    )
    record = service.get(base.context())
    result = service.update(base.context(), remember(session.session_id, 1))
    assert result.entries == record.entries
    assert (
        service.recall(base.context(), keys=("makes",)).entries[0].applicability
        == "requires_reconfirmation"
    )


def test_commit_failure_rolls_back_then_same_command_can_be_reconciled(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.preferences
    seed_operational_rows(base)
    session = base.create()
    command = remember(session.session_id)
    before = snapshot(base.store)
    assert before["bookings"] and before["leads"] and before["operation_outcomes"]
    with failed_commit(), pytest.raises(StoreError, match="SYNTHETIC_COMMIT_FAILURE"):
        service.update(base.context(), command)
    assert snapshot(base.store) == before
    applied = service.update(base.context(), command)
    after = snapshot(base.store)
    assert service.update(base.context(), command) == applied
    assert snapshot(base.store) == after
    untouched = {
        name for name in before if name not in {"preferences", "owners", "command_receipts"}
    }
    assert {name: before[name] for name in untouched} == {name: after[name] for name in untouched}


def test_expiry_cleanup_monotonic_revision_and_expired_receipt_denial(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    command = remember(session.session_id)
    service.update(base.context(), command)
    past = utc_text(base.clock.value - timedelta(seconds=1))
    base.store.write(lambda db: db.execute(update(Preference).values(expires_at=past)).close())
    before = snapshot(base.store)
    assert service.get(base.context()).entries == []
    assert snapshot(base.store) == before
    assert (
        base.auth.write(
            base.context(), lambda unit: purge_expired(unit, now=utc_text(base.clock.value))
        )
        == 1
    )
    assert service.get(base.context()).revision == 2
    # Physical memory removal does not discard the original dedupe authority.
    assert service.update(base.context(), command).entries == []
    base.store.write(
        lambda db: db.execute(
            update(CommandReceipt)
            .where(CommandReceipt.command_kind == "preference.command")
            .values(expires_at=past)
        ).close()
    )
    with pytest.raises(ApiFailure, match="REPLAY_EXPIRED"):
        service.update(base.context(), command)
    fresh = service.update(base.context(), remember(session.session_id, 2))
    assert fresh.revision == 3 and len(fresh.entries) == 1


def test_malformed_retained_value_fails_closed(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.preferences
    session = base.create()
    service.update(base.context(), remember(session.session_id))
    base.store.write(
        lambda db: db.execute(
            update(Preference).values(value_json={"value": ["Honda"], "inferred": True})
        ).close()
    )
    with pytest.raises(StoreError, match="PREFERENCE_STATE_INCOMPATIBLE"):
        service.get(base.context())
