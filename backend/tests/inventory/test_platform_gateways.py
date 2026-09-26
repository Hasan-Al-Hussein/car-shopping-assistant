"""Platform-owned real I5 adapters and owner-service composition; source-only until granted."""

from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, update
from sqlalchemy.orm import Session

from app.api.schemas.identity import IdentityBootstrapRequest
from app.api.schemas.inventory import SearchRequest
from app.api.schemas.memory import MembershipRequest
from app.api.schemas.sessions import PresentationRegisterRequest, SessionCreateRequest
from app.core.config import load_settings
from app.core.errors import ApiFailure
from app.database.models import ListingVersion
from app.database.store import Store
from app.identity.authorization import AuthorizationService, AuthorizedOwnerContext
from app.identity.credentials import decode_token
from app.identity.service import IdentityService
from app.inventory.compact_reader import CompactInventoryReader
from app.inventory.public_projection import map_listing_summary
from app.inventory.references import ImmutableInventoryRef
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage
from app.inventory_gateways import CompactSessionInventory, compose_public_inventory
from app.inventory_signing import HmacPublicInventorySigner
from app.sessions.service import SessionService
from app.shortlist.service import ShortlistService
from tests.inventory.compact_cases import admitted, admitted_pair
from tests.platform.test_identity import ACK, Clock


@dataclass
class OwnerHarness:
    auth: AuthorizationService
    context: AuthorizedOwnerContext
    clock: Clock


def owner(store: Store) -> OwnerHarness:
    clock = Clock()
    settings = load_settings(
        {
            "CSA_STORE_PATH": str(store.path),
            "CSA_RUNTIME_ROOT": str(store.boundary.logical_root),
            "CSA_RUNTIME_PHYSICAL_ROOT": str(store.boundary.physical_root),
        }
    )
    identity = IdentityService(settings, clock=clock.now)
    result = identity.bootstrap(IdentityBootstrapRequest.model_validate(ACK), None)
    assert result.cookie is not None
    auth = AuthorizationService(identity)
    context = auth.authorize_write(
        decode_token(result.cookie), result.identity.context_id, result.identity.csrf_token
    )
    return OwnerHarness(auth, context, clock)


def test_shared_signer_search_session_registration_and_rotation_preserve_owned_history(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    services = compose_public_inventory(reader)
    buyer = owner(inventory_store)
    services.search.clock = buyer.clock.now
    assert services.search.signer is services.signer is services.sessions.signer
    search = services.search.search(SearchRequest(client_request_id=str(uuid4()), page_size=2))
    service = SessionService(buyer.auth, inventory=services.sessions)
    created = service.create(buyer.context, SessionCreateRequest(client_action_id=str(uuid4())))
    command = PresentationRegisterRequest(
        expected_revision=0, client_action_id=str(uuid4()), presentation=search.presentation
    )
    saved = service.register(buyer.context, created.session_id, command)
    assert saved.active_presentation_id is not None
    expected = tuple(
        ImmutableInventoryRef.model_validate(item.ref.model_dump()) for item in search.items
    )
    assert (
        service.presentation_refs(
            buyer.context, created.session_id, saved.active_presentation_id
        ).refs
        == expected
    )
    # Same generation, fresh process-style composition: old public MACs no longer verify.
    replacement = compose_public_inventory(reader)
    service.inventory = replacement.sessions
    with pytest.raises(ApiFailure, match="PRESENTATION_INVALID"):
        replacement.sessions.verify(search.presentation, now=buyer.clock.now())
    buyer.clock.value += timedelta(minutes=31)
    assert service.register(buyer.context, created.session_id, command) == saved
    assert (
        service.presentation_refs(
            buyer.context, created.session_id, saved.active_presentation_id
        ).refs
        == expected
    )


def test_real_empty_presentation_still_rechecks_snapshot_identity(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    services = compose_public_inventory(reader)
    buyer = owner(inventory_store)
    proof = services.signer.sign_presentation(
        snapshot_id=snapshot_plan.index.snapshot_id,
        ordered_refs=(),
        criteria_hash="a" * 64,
        now=buyer.clock.now(),
    )
    service = SessionService(buyer.auth, inventory=services.sessions)
    created = service.create(buyer.context, SessionCreateRequest(client_action_id=str(uuid4())))
    result = service.register(
        buyer.context,
        created.session_id,
        PresentationRegisterRequest(
            expected_revision=0, client_action_id=str(uuid4()), presentation=proof
        ),
    )
    assert result.active_presentation_id is not None
    assert (
        service.presentation_refs(
            buyer.context, created.session_id, result.active_presentation_id
        ).refs
        == ()
    )
    prepared = services.sessions.prepare((), snapshot_id=snapshot_plan.index.snapshot_id)
    reader.invalidate()
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        inventory_store.write(lambda db: services.sessions.recheck(db, prepared))


def test_real_shortlist_current_historical_missing_and_same_unit_recheck(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, old = admitted_pair(inventory_store, snapshot_plan, second_plan)
    services = compose_public_inventory(reader)
    buyer = owner(inventory_store)
    service = ShortlistService(buyer.auth, inventory=services.shortlist)
    first = snapshot_plan.candidate.manifest.reference("12")

    def no_listing_hydration(*args: object, **kwargs: object) -> None:
        raise AssertionError("LISTING_JSON_HYDRATED_DURING_OWNER_ADMISSION")

    event.listen(ListingVersion, "load", no_listing_hydration)
    try:
        service.put(
            buyer.context,
            first,
            MembershipRequest(expected_revision=0, client_action_id=str(uuid4())),
        )
    finally:
        event.remove(ListingVersion, "load", no_listing_hydration)
    InventoryRepository(inventory_store).activate(
        second_plan.index.snapshot_id, expected_revision=old.active_revision
    )
    current = second_plan.candidate.manifest.reference("12")
    missing = second_plan.candidate.manifest.reference("not-present")
    batch = services.shortlist.read((current, first, missing))
    assert tuple(item.state for item in batch.items) == ("current", "historical", "missing")
    assert tuple(item.ref for item in batch.items) == (current, first, missing)
    assert batch.items[2].listing is None
    expected = next(row for row in snapshot_plan.candidate.listings if row.ref == first)
    assert batch.items[1].listing == map_listing_summary(expected)
    saved = service.get(buyer.context)
    assert len(saved.items) == 1 and saved.items[0].state == "historical"
    assert saved.items[0].ref.model_dump() == first.model_dump()
    assert saved.items[0].listing == batch.items[1].listing
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        services.sessions.prepare((missing,), snapshot_id=second_plan.index.snapshot_id)
    with pytest.raises(ApiFailure, match="NOT_FOUND"):
        services.sessions.prepare((first,), snapshot_id=second_plan.index.snapshot_id)

    # Opening another Store unit or mapping/full stage reconstruction is prohibited here.
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("NESTED_STORE_OR_PROJECTION_INSIDE_RECHECK")

    with monkeypatch.context() as patch:
        patch.setattr("app.database.store.Store.read", forbidden)
        patch.setattr("app.inventory_gateways.map_listing_summary", forbidden)
        patch.setattr("app.inventory.compact_reader.load_stage_set", forbidden)
        inventory_store.write(lambda db: services.shortlist.recheck(db, batch))


@pytest.mark.parametrize("consumer", ["session", "shortlist"])
def test_real_recheck_rejects_changed_persisted_projection_and_rolls_back(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    consumer: str,
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    services = compose_public_inventory(reader)
    ref = snapshot_plan.candidate.manifest.reference("12")
    session_admission = services.sessions.prepare((ref,), snapshot_id=ref.snapshot_id)
    shortlist_batch = services.shortlist.read((ref,))
    original = inventory_store.path.read_bytes()

    def corrupt_and_recheck(db: Session) -> None:
        # Same existing unit, unchanged row counts and active tuple.
        db.execute(
            update(ListingVersion)
            .where(
                ListingVersion.snapshot_id == ref.snapshot_id,
                ListingVersion.source_id == ref.source_id,
            )
            .values(normalized_json={"changed_projection": True})
        )
        if consumer == "session":
            services.sessions.recheck(db, session_admission)
        else:
            services.shortlist.recheck(db, shortlist_batch)

    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        inventory_store.write(corrupt_and_recheck)
    assert inventory_store.path.read_bytes() == original


def test_pointer_race_and_swapped_exact_identity_fail_closed(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
) -> None:
    reader, before = admitted_pair(inventory_store, snapshot_plan, second_plan)
    services = compose_public_inventory(reader)
    first, other = (snapshot_plan.candidate.manifest.reference(source) for source in ("12", "13"))
    prepared = services.sessions.prepare((first,), snapshot_id=first.snapshot_id)
    changed = replace(prepared, refs=(other,))
    with pytest.raises(ApiFailure, match="STORE_UNAVAILABLE"):
        inventory_store.write(lambda db: services.sessions.recheck(db, changed))
    InventoryRepository(inventory_store).activate(
        second_plan.index.snapshot_id, expected_revision=before.active_revision
    )
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        inventory_store.write(lambda db: services.sessions.recheck(db, prepared))


def test_generation_composition_rejects_foreign_signer(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    reader, _ = admitted(inventory_store, snapshot_plan)
    with pytest.raises(ValueError, match="PUBLIC_SIGNER_STORE_GENERATION_MISMATCH"):
        CompactSessionInventory(reader, HmacPublicInventorySigner(str(uuid4())))
    replacement = replace(inventory_store, generation=str(uuid4()))
    rotated = compose_public_inventory(CompactInventoryReader(replacement))
    assert rotated.signer.generation == replacement.generation
    assert rotated.search.signer is rotated.sessions.signer is rotated.signer
