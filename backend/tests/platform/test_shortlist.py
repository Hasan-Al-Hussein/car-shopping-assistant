"""BE12 deterministic source fixtures with a strictly synthetic exact-ref port."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.schemas.memory import MembershipRequest
from app.api.schemas.operations import OperationRejected
from app.core.errors import ApiFailure
from app.database.models import (
    ActiveInventory,
    BookingReview,
    CommandReceipt,
    ListingVersion,
    OperationOutcome,
    Owner,
    ShortlistMembership,
)
from app.database.store import StoreError
from app.identity.service import utc_text
from app.shortlist.inventory import key
from app.shortlist.repository import purge_expired
from app.shortlist.service import ShortlistService
from tests.platform.memory_shortlist_cases import (
    MemoryHarness,
    failed_commit,
    make_memory_harness,
    seed_operational_rows,
)
from tests.platform.session_cases import ref
from tests.platform.test_identity import snapshot
from tests.platform.test_preferences import mode


@pytest.fixture
def harness() -> MemoryHarness:
    return make_memory_harness()


def command(revision: int = 0) -> MembershipRequest:
    return MembershipRequest(expected_revision=revision, client_action_id=str(uuid4()))


def test_repeat_put_delete_and_older_replay_are_current_truth(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.shortlist
    original = command()
    first = service.put(base.context(), ref(), original)
    before = snapshot(base.store)
    base.clock.value += timedelta(days=1)
    noop = service.put(base.context(), ref(), command(1))
    assert first.changed_at_apply and not noop.changed_at_apply and noop.current_revision == 2
    assert snapshot(base.store)["shortlist_memberships"] == before["shortlist_memberships"]
    removed = service.delete(base.context(), ref(), command(2))
    repeated = service.delete(base.context(), ref(), command(3))
    assert removed.changed_at_apply and not repeated.changed_at_apply and not repeated.saved
    before = snapshot(base.store)
    replay = service.put(base.context(), ref(), original)
    assert (
        replay.replayed
        and replay.applied_revision == 1
        and replay.current_revision == 4
        and not replay.saved
    )
    assert snapshot(base.store) == before


def test_shared_namespace_rejects_changed_method_ref_or_revision(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.shortlist
    original = command()
    service.put(base.context(), ref(), original)
    before = snapshot(base.store)
    for operation, target, body in (
        (service.delete, ref(), original),
        (service.put, ref("13"), original),
        (service.put, ref(), original.model_copy(update={"expected_revision": 1})),
    ):
        with pytest.raises(ApiFailure, match="IDEMPOTENCY_CONFLICT"):
            operation(base.context(), target, body)
    with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
        service.delete(base.context(), ref(), command())
    assert snapshot(base.store) == before


def test_same_name_owner_and_recreated_service_are_independent(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.shortlist
    service.put(base.context(), ref(), command())
    saved = service.get(base.context())
    assert saved.total == 1 and saved.items[0].ref.model_dump() == ref().model_dump()
    assert service.get(base.context(1)).items == []
    assert not service.delete(base.context(1), ref(), command()).changed_at_apply
    assert ShortlistService(base.auth, inventory=harness.inventory).get(base.context()) == saved
    assert base.create().selected_ref is None  # Shortlist does not select/comparison/book.


def test_stop_saving_blocks_fresh_put_but_allows_delete_and_replay(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.shortlist
    session = base.create()
    original = command()
    service.put(base.context(), ref(), original)
    harness.preferences.update(base.context(), mode(session.session_id, 0, enabled=False))
    before = snapshot(base.store)
    assert service.put(base.context(), ref(), original).replayed
    with pytest.raises(ApiFailure, match="UNSUPPORTED_STATE"):
        service.put(base.context(), ref(), command(1))
    assert snapshot(base.store) == before
    assert not service.delete(base.context(), ref(), command(1)).saved


def test_historical_reused_id_and_missing_refs_never_retarget(harness: MemoryHarness) -> None:
    base, service = harness.base, harness.shortlist
    original = command()
    service.put(base.context(), ref(), original)
    base.store.write(
        lambda db: db.execute(
            update(ActiveInventory).values(snapshot_id="2" * 64, revision=2)
        ).close()
    )
    historical = service.get(base.context()).items[0]
    assert historical.state == "historical" and historical.ref.snapshot_id == "1" * 64
    assert historical.listing is not None and historical.listing.title == "Synthetic 1/12"
    assert service.put(base.context(), ref(), original).reference_state == "historical"
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        service.put(base.context(), ref(), command(1))
    service.put(base.context(), ref(snapshot_id="2" * 64), command(1))
    harness.inventory.missing.add(key(ref()))
    values = service.get(base.context()).items
    assert {item.state for item in values} == {"current", "missing"}
    missing = next(item for item in values if item.state == "missing")
    assert missing.ref.snapshot_id == "1" * 64 and missing.listing is None
    assert service.delete(base.context(), ref(), command(2)).reference_state == "missing"
    assert service.get(base.context()).items[0].ref.snapshot_id == "2" * 64


def seed_many(harness: MemoryHarness, count: int = 55) -> None:
    base = harness.base
    owner_id = base.auth.read(base.context(), lambda unit: unit.owner_id)
    now, expires = utc_text(base.clock.value), utc_text(base.clock.value + timedelta(days=30))

    def write(db: Session) -> None:
        template = db.get(ListingVersion, key(ref()))
        assert template is not None
        buyer = db.get(Owner, owner_id)
        assert buyer is not None
        buyer.shortlist_revision = 1
        for number in range(count):
            exact = ref("extra-" + str(number).zfill(3))
            db.add(
                ListingVersion(
                    **exact.model_dump(),
                    source_row=number + 100,
                    original_json=template.original_json,
                    normalized_json=template.normalized_json,
                )
            )
            db.flush()
            db.add(
                ShortlistMembership(
                    owner_id=owner_id,
                    **exact.model_dump(),
                    added_at=now,
                    updated_at=now,
                    expires_at=expires,
                )
            )

    base.store.write(write)


def test_more_than_fifty_stable_ties_and_truthful_total_bounded_batches(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.shortlist
    seed_many(harness)
    before = snapshot(base.store)
    first = service.get(base.context(), page_size=50)
    assert len(first.items) == 50 and first.total == 55 and first.next_cursor is not None
    rest = service.get(base.context(), page_size=50, cursor=first.next_cursor)
    assert len(rest.items) == 5 and rest.total == 55 and rest.next_cursor is None
    assert [item.ref.source_id for item in first.items + rest.items] == [
        f"extra-{i:03d}" for i in range(55)
    ]
    assert harness.inventory.batches == [50, 5]
    assert snapshot(base.store) == before


@pytest.mark.parametrize("variant", ["tamper", "owner", "revision", "expiry"])
def test_cursor_rejects_invalid_binding_or_expired_set(
    harness: MemoryHarness, variant: str
) -> None:
    base, service = harness.base, harness.shortlist
    seed_many(harness, 3)
    if variant == "expiry":
        base.store.write(
            lambda db: db.execute(
                update(ShortlistMembership).values(
                    expires_at=utc_text(base.clock.value + timedelta(hours=1))
                )
            ).close()
        )
    cursor = service.get(base.context(), page_size=1).next_cursor
    assert cursor is not None
    who, expected = 0, "VALIDATION_ERROR"
    if variant == "tamper":
        cursor = cursor[:-1] + ("a" if cursor[-1] != "a" else "b")
    elif variant == "owner":
        who = 1
    elif variant == "revision":
        service.delete(base.context(), ref("extra-000"), command(1))
        expected = "REVISION_CONFLICT"
    else:
        base.clock.value += timedelta(hours=1)
        expected = "REVISION_CONFLICT"
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match=expected):
        service.get(base.context(who), cursor=cursor)
    assert snapshot(base.store) == before


@pytest.mark.parametrize("variant", ["activation", "listing_identity", "stop_mode", "expiry"])
def test_prepare_races_rechecked_without_partial_effect(
    harness: MemoryHarness, variant: str
) -> None:
    base, service = harness.base, harness.shortlist
    session = base.create()
    if variant == "expiry":
        service.put(base.context(), ref(), command())
        base.store.write(
            lambda db: db.execute(
                update(ShortlistMembership).values(
                    expires_at=utc_text(base.clock.value + timedelta(hours=1))
                )
            ).close()
        )
        harness.inventory.after_read = lambda: setattr(
            base.clock, "value", base.clock.value + timedelta(hours=1)
        )
        with pytest.raises(ApiFailure, match="REVISION_CONFLICT"):
            service.get(base.context())
        return
    failure: type[Exception]
    if variant == "activation":
        harness.inventory.after_read = lambda: base.store.write(
            lambda db: db.execute(update(ActiveInventory).values(revision=2)).close()
        )
        failure, code = ApiFailure, "SNAPSHOT_STALE"
    elif variant == "listing_identity":
        harness.inventory.after_read = lambda: base.store.write(
            lambda db: db.execute(
                update(ListingVersion)
                .where(ListingVersion.snapshot_id == ref().snapshot_id)
                .values(normalized_json={"changed": True})
            ).close()
        )
        failure, code = StoreError, "SYNTHETIC_IDENTITY_CHANGED"
    else:

        def stop_saving() -> None:
            harness.preferences.update(base.context(), mode(session.session_id, 0, enabled=False))

        harness.inventory.after_read = stop_saving
        failure, code = ApiFailure, "UNSUPPORTED_STATE"
    with pytest.raises(failure, match=code):
        service.put(base.context(), ref(), command())
    assert (
        base.store.read(lambda db: db.scalar(select(ShortlistMembership.owner_id).limit(1))) is None
    )
    assert service.get(base.context()).revision == 0


@pytest.mark.parametrize("same_id", [False, True])
def test_two_tabs_serialize_commands_without_duplicate_membership(
    harness: MemoryHarness, same_id: bool
) -> None:
    base, service = harness.base, harness.shortlist
    barrier, original = Barrier(2, timeout=5), command()
    bodies = (original, original if same_id else command())
    contexts = (base.context(), base.context())

    def synchronize() -> None:
        barrier.wait()

    harness.inventory.after_read = synchronize

    def submit(index: int) -> str:
        try:
            result = service.put(contexts[index], ref(), bodies[index])
            return "replayed" if result.replayed else "applied"
        except ApiFailure as error:
            return error.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, (0, 1)))
    finally:
        harness.inventory.after_read = None
    assert sorted(results) == (
        ["applied", "replayed"] if same_id else ["REVISION_CONFLICT", "applied"]
    )
    assert service.get(base.context()).total == 1
    assert service.get(base.context()).revision == 1


def test_commit_failure_lost_response_and_no_operational_side_effect(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.shortlist
    seed_operational_rows(base)
    original = command()
    before = snapshot(base.store)
    assert before["bookings"] and before["leads"] and before["operation_outcomes"]
    with failed_commit(), pytest.raises(StoreError, match="SYNTHETIC_COMMIT_FAILURE"):
        service.put(base.context(), ref(), original)
    assert snapshot(base.store) == before
    service.put(base.context(), ref(), original)  # Caller may lose this response.
    after = snapshot(base.store)
    result = service.put(base.context(), ref(), original)
    assert result.replayed and result.saved and result.applied_revision == 1
    assert snapshot(base.store) == after
    untouched = {
        name
        for name in before
        if name not in {"owners", "shortlist_memberships", "command_receipts"}
    }
    assert {name: before[name] for name in untouched} == {name: after[name] for name in untouched}


@pytest.mark.parametrize("protected", [False, True])
def test_expiry_hidden_cleanup_protects_parentless_unresolved_review(
    harness: MemoryHarness, protected: bool
) -> None:
    base, service = harness.base, harness.shortlist
    original = command()
    service.put(base.context(), ref(), original)
    now, past = utc_text(base.clock.value), utc_text(base.clock.value - timedelta(seconds=1))
    owner_id = base.auth.read(base.context(), lambda unit: unit.owner_id)

    def expire(db: Session) -> None:
        db.execute(update(ShortlistMembership).values(expires_at=past)).close()
        if protected:
            db.add(
                BookingReview(
                    id=str(uuid4()),
                    owner_id=owner_id,
                    draft_id=None,
                    draft_revision=0,
                    operation_key="p" * 43,
                    payload_hash="f" * 64,
                    immutable_payload_json={"malformed_unresolved": True},
                    store_generation=base.store.generation,
                    issued_at=past,
                    expires_at=now,
                    state="submitted",
                )
            )

    base.store.write(expire)
    before = snapshot(base.store)
    assert service.get(base.context()).items == []
    assert not service.put(base.context(), ref(), original).saved
    assert snapshot(base.store) == before
    removed = base.auth.write(base.context(), lambda unit: purge_expired(unit, now=now))
    assert removed == int(not protected)
    after = snapshot(base.store)
    assert after["booking_reviews"] == before["booking_reviews"]
    assert after["command_receipts"] == before["command_receipts"]
    assert service.get(base.context()).revision == (1 if protected else 2)
    if protected:
        service.delete(base.context(), ref(), command(1))
        assert snapshot(base.store)["booking_reviews"] == before["booking_reviews"]


def test_unavailable_gateway_never_fakes_saved_or_empty_existing_state(
    harness: MemoryHarness,
) -> None:
    base = harness.base
    service = ShortlistService(base.auth)
    assert service.get(base.context()).items == []
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        service.put(base.context(), ref(), command())
    harness.shortlist.put(base.context(), ref(), command())
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        service.get(base.context())


@pytest.mark.parametrize("well_formed_terminal", [False, True])
def test_cleanup_requires_trusted_proof_not_just_matching_outcome(
    harness: MemoryHarness, well_formed_terminal: bool
) -> None:
    base, service = harness.base, harness.shortlist
    service.put(base.context(), ref(), command())
    owner_id = base.auth.read(base.context(), lambda unit: unit.owner_id)
    review_id, operation_key = str(uuid4()), "t" * 43
    now, past, future = (
        utc_text(base.clock.value),
        utc_text(base.clock.value - timedelta(seconds=1)),
        utc_text(base.clock.value + timedelta(days=90)),
    )
    terminal = OperationRejected.model_validate(
        dict(
            state="rejected",
            operation_key=operation_key,
            review_id=review_id,
            original_store_generation=base.store.generation,
            terminal_at=now,
            replay_valid_until=future,
            rejection_code="UNSUPPORTED_STATE",
            booking={"state": "not_created"},
            lead={"state": "not_requested"},
            csv={"state": "not_requested"},
        )
    )

    def seed(db: Session) -> None:
        db.execute(update(ShortlistMembership).values(expires_at=past)).close()
        db.add(
            BookingReview(
                id=review_id,
                owner_id=owner_id,
                draft_id=None,
                draft_revision=0,
                operation_key=operation_key,
                payload_hash="f" * 64,
                immutable_payload_json={"unverified": True},
                store_generation=base.store.generation,
                issued_at=past,
                expires_at=now,
                state="consumed",
            )
        )
        db.flush()
        db.add(
            OperationOutcome(
                id=str(uuid4()),
                owner_id=owner_id,
                review_id=review_id,
                operation_key=operation_key,
                payload_hash="f" * 64,
                store_generation=base.store.generation,
                terminal_state="REJECTED",
                terminal_at=now,
                replay_valid_until=future,
                terminal_result_json=terminal.model_dump(mode="json")
                if well_formed_terminal
                else {"malformed": True},
            )
        )

    base.store.write(seed)
    before = snapshot(base.store)
    assert base.auth.write(base.context(), lambda unit: purge_expired(unit, now=now)) == 0
    assert snapshot(base.store) == before


def test_expired_shortlist_receipt_cannot_become_fresh_after_cleanup(
    harness: MemoryHarness,
) -> None:
    base, service = harness.base, harness.shortlist
    original = command()
    service.put(base.context(), ref(), original)
    past, now = utc_text(base.clock.value - timedelta(seconds=1)), utc_text(base.clock.value)

    def expire(db: Session) -> None:
        db.execute(update(ShortlistMembership).values(expires_at=past)).close()
        db.execute(
            update(CommandReceipt)
            .where(CommandReceipt.command_kind == "shortlist.membership")
            .values(expires_at=past)
        ).close()

    base.store.write(expire)
    assert base.auth.write(base.context(), lambda unit: purge_expired(unit, now=now)) == 1
    before = snapshot(base.store)
    with pytest.raises(ApiFailure, match="REPLAY_EXPIRED"):
        service.put(base.context(), ref(), original)
    assert snapshot(base.store) == before
