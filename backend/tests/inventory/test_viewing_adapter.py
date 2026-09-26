"""Authored I8 proof obligations; apply and execute only under a later grant.

Real Store fixtures use the accepted 100-record candidate and reviewed mappings.
Only the named fixtures activate configurations, never production construction.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from app.core.config import VIEWING_VENUE
from app.core.errors import ApiFailure
from app.core.readiness import ReadinessRegistry
from app.database.models import ActiveRules, RuleVersion
from app.database.store import Store, StoreError
from app.inventory import compact_reader, viewing_adapter
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.references import ImmutableInventoryRef
from app.inventory.snapshots import InventoryRepository
from app.inventory.viewing_adapter import CompactViewingInventory
from app.viewings.draft_admission import PreparedViewing
from app.viewings.draft_configuration import (
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
)
from app.viewings.eligibility import EligibilityPolicy
from app.viewings.scheduling import ViewingRules
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from scripts.bootstrap_inventory import BootstrapInputs, load_inputs

NOW = datetime(2026, 9, 24, 4, tzinfo=UTC)
PREPARED = TypeAdapter(PreparedViewing)


@dataclass
class Clock:
    value: float = 100.0

    def __call__(self) -> float:
        return self.value


@dataclass
class Case:
    store: Store
    reader: CompactInventoryReader
    rules: ViewingRules
    config: ViewingConfiguration
    ref: ImmutableInventoryRef
    gateway: CompactViewingInventory
    clock: Clock


def activate(store: Store, config: ViewingConfiguration, revision: int) -> None:
    """Explicit test-operator fixture; not called by the adapter or application."""

    def write(db: Session) -> None:
        version = configuration_id(config)
        if db.get(RuleVersion, version) is None:
            db.add(
                RuleVersion(
                    version=version,
                    policy_version=config.policy.version,
                    eligibility_version=eligibility_version(config),
                    rules_json=config.model_dump(mode="json"),
                    created_at="2026-09-24T04:00:00.000000Z",
                )
            )
            db.flush()
        active = db.get(ActiveRules, 1)
        if active is None:
            db.add(ActiveRules(id=1, version=version, revision=revision))
        else:
            active.version, active.revision = version, revision

    store.write(write)


@pytest.fixture(scope="session")
def accepted_inputs() -> BootstrapInputs:
    return load_inputs()


@pytest.fixture
def make_case(inventory_store: Store, accepted_inputs: BootstrapInputs) -> Callable[..., Case]:
    def build(
        *,
        configured: bool = True,
        member: bool = True,
        mapped: bool = True,
        capacity: int = 256,
    ) -> Case:
        selected = accepted_inputs.mappings[0].ref
        mappings = tuple(
            item for item in accepted_inputs.mappings if mapped or item.ref != selected
        )
        repository = InventoryRepository(inventory_store, clock=lambda: NOW)
        plan = repository.prepare(
            accepted_inputs.candidate,
            policy_version=accepted_inputs.policy.version,
            mappings=mappings,
        )
        repository.stage(plan)
        observation = repository.activate(plan.candidate.manifest.snapshot_id, expected_revision=0)
        rules = ViewingRules(accepted_inputs.policy)
        config = ViewingConfiguration(
            format="viewing-configuration-1",
            calendar_version=rules.version,
            policy=accepted_inputs.policy,
            venue_label=VIEWING_VENUE,
            eligibility=(
                accepted_inputs.eligibility
                if member
                else EligibilityPolicy(version="test-deny-all", eligible_refs=())
            ),
            inventory=observation,
            mapping_digest=plan.mapping_digest,
        )
        if configured:
            activate(inventory_store, config, 1)
        reader = CompactInventoryReader(inventory_store)
        reader.refresh(ReadinessRegistry())
        clock = Clock()
        gateway = CompactViewingInventory(
            reader, rules=rules, capacity=capacity, monotonic_clock=clock
        )
        return Case(inventory_store, reader, rules, config, selected, gateway, clock)

    return build


def sql(store: Store, statement: str, parameters: tuple[object, ...] = ()) -> None:
    def write(db: Session) -> None:
        db.connection().exec_driver_sql(statement, parameters)

    store.write(write)


def test_real_prepare_deserialized_and_fresh_authority_recheck_in_read_and_write(
    make_case: Callable[..., Case],
    accepted_inputs: BootstrapInputs,
) -> None:
    case = make_case()
    original = case.gateway.prepare(case.ref)
    restored = PREPARED.validate_json(PREPARED.dump_json(original))
    fresh = case.gateway.prepare(case.ref)
    assert original.identity != fresh.identity
    assert len(original.identity) == 2
    assert original.identity[0] == "viewing-admission-1"
    assert original.generation == case.store.generation
    assert original.ref == case.ref
    assert original.active_revision == 1
    assert original.configuration_version == configuration_id(case.config)
    assert original.configuration_revision == 1
    assert original.eligibility_version == eligibility_version(case.config)
    assert original.resource_id == accepted_inputs.mappings[0].resource_id
    assert original.mapping_version == accepted_inputs.mappings[0].mapping_version

    def recheck(db: Session) -> None:
        case.gateway.recheck(db, restored)
        case.gateway.recheck(db, fresh)
        case.gateway.recheck(db, original)

    case.store.read(recheck)
    case.store.write(recheck)
    assert replace(fresh, identity=original.identity) == original


@pytest.mark.parametrize("member", [False, True])
def test_explicit_membership_and_missing_mapping_never_default_to_permission(
    make_case: Callable[..., Case],
    member: bool,
) -> None:
    case = make_case(member=member, mapped=False)
    with pytest.raises(ApiFailure) as failure:
        case.gateway.prepare(case.ref)
    assert failure.value.code == "ELIGIBILITY_UNAVAILABLE"


def test_no_active_configuration_is_not_implicitly_activated(
    make_case: Callable[..., Case],
) -> None:
    case = make_case(configured=False)
    with pytest.raises(ApiFailure) as failure:
        case.gateway.prepare(case.ref)
    assert failure.value.code == "RULES_UNAVAILABLE"
    assert case.store.read(lambda db: db.get(ActiveRules, 1) is None)


@pytest.mark.parametrize("change", ["missing", "historical"])
def test_missing_or_noncurrent_exact_reference_is_closed(
    make_case: Callable[..., Case],
    change: str,
) -> None:
    case = make_case()
    data = case.ref.model_dump()
    data["source_id" if change == "missing" else "snapshot_id"] = (
        "999" if change == "missing" else "f" * 64
    )
    with pytest.raises(ApiFailure):
        case.gateway.prepare(ImmutableInventoryRef.model_validate(data))


@pytest.mark.parametrize("mutation", ["mapping", "resource", "projection", "active", "stage"])
def test_actual_token_recheck_rejects_changed_persisted_inventory(
    make_case: Callable[..., Case],
    mutation: str,
) -> None:
    case = make_case()
    prepared = case.gateway.prepare(case.ref)
    exact = (case.ref.namespace, case.ref.snapshot_id, case.ref.source_id)
    if mutation == "mapping":
        sql(
            case.store,
            "UPDATE listing_resource_mappings SET mapping_version='changed' "
            "WHERE namespace=? AND snapshot_id=? AND source_id=?",
            exact,
        )
    elif mutation == "resource":
        sql(
            case.store,
            "UPDATE vehicle_resources SET mapping_version='changed' WHERE id=?",
            (prepared.resource_id,),
        )
    elif mutation == "projection":
        sql(
            case.store,
            "UPDATE listing_versions SET normalized_json='{}' "
            "WHERE namespace=? AND snapshot_id=? AND source_id=?",
            exact,
        )
    elif mutation == "active":
        sql(case.store, "UPDATE active_inventory SET revision=revision+1 WHERE id=1")
    else:
        sql(
            case.store,
            "UPDATE inventory_snapshot_payloads "
            "SET payload_json=json_set(payload_json,'$.mapping_digest',?) WHERE snapshot_id=?",
            ("0" * 64, case.ref.snapshot_id),
        )
    with pytest.raises(ApiFailure):
        case.store.write(lambda db: case.gateway.recheck(db, prepared))


@pytest.mark.parametrize(
    "mutation", ["material", "oversized", "eligibility_column", "reactivation"]
)
def test_config_content_columns_and_a_b_a_revision_are_rechecked(
    make_case: Callable[..., Case],
    mutation: str,
) -> None:
    case = make_case()
    prepared = case.gateway.prepare(case.ref)
    if mutation == "reactivation":
        denied = case.config.model_copy(
            update={"eligibility": EligibilityPolicy(version="test-deny-all", eligible_refs=())}
        )
        activate(case.store, denied, 2)
        activate(case.store, case.config, 3)
    elif mutation == "eligibility_column":
        sql(
            case.store,
            "UPDATE rule_versions SET eligibility_version='changed' WHERE version=?",
            (prepared.configuration_version,),
        )
    else:
        raw = "{}" if mutation == "material" else " " * 65_537
        sql(
            case.store,
            "UPDATE rule_versions SET rules_json=? WHERE version=?",
            (raw, prepared.configuration_version),
        )
    with pytest.raises(ApiFailure) as failure:
        case.store.read(lambda db: case.gateway.recheck(db, prepared))
    assert failure.value.code == "RULES_UNAVAILABLE"


def test_configuration_mapping_digest_must_match_audited_stage(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    changed = case.config.model_copy(update={"mapping_digest": "0" * 64})
    activate(case.store, changed, 2)
    with pytest.raises(ApiFailure) as failure:
        case.gateway.prepare(case.ref)
    assert failure.value.code == "RULES_UNAVAILABLE"


def test_expiry_never_renews_and_new_preparation_cannot_revive_old_handle(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    old = case.gateway.prepare(case.ref)
    case.clock.value = 399.0
    case.store.read(lambda db: case.gateway.recheck(db, old))
    fresh = case.gateway.prepare(case.ref)
    case.clock.value = 400.0
    with Session() as db, pytest.raises(ApiFailure):
        case.gateway.recheck(db, old)
    case.store.read(lambda db: case.gateway.recheck(db, fresh))


def test_eviction_release_reconstruction_and_forged_material_cannot_mint_authority(
    make_case: Callable[..., Case],
) -> None:
    case = make_case(capacity=1)
    old = case.gateway.prepare(case.ref)
    current = case.gateway.prepare(case.ref)
    other = CompactViewingInventory(case.reader, rules=case.rules, monotonic_clock=case.clock)
    rejected = (
        old,
        replace(current, resource_id=str(uuid4())),
        replace(current, active_revision=True),
        replace(current, identity=("viewing-admission-1", "0" * 64)),
    )
    with Session() as db:
        for value in rejected:
            with pytest.raises(ApiFailure):
                case.gateway.recheck(db, value)
        with pytest.raises(ApiFailure):
            other.recheck(db, PREPARED.validate_json(PREPARED.dump_json(current)))
    case.store.read(lambda db: case.gateway.recheck(db, current))
    case.gateway.release(current)
    case.gateway.release(current)
    with Session() as db, pytest.raises(ApiFailure):
        case.gateway.recheck(db, current)


@pytest.mark.parametrize("revocation", ["reader", "adapter", "close", "process"])
def test_revoked_closed_or_other_process_authority_is_unavailable(
    make_case: Callable[..., Case],
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
) -> None:
    case = make_case()
    prepared = case.gateway.prepare(case.ref)
    if revocation == "reader":
        case.reader.invalidate()
    elif revocation == "adapter":
        case.gateway.invalidate()
    elif revocation == "close":
        case.gateway.close()
        with pytest.raises(ApiFailure):
            case.gateway.prepare(case.ref)
    else:
        original = os.getpid()
        monkeypatch.setattr(os, "getpid", lambda: original + 1)
    with pytest.raises(ApiFailure):
        case.store.read(lambda db: case.gateway.recheck(db, prepared))


def test_write_recheck_uses_original_session_without_store_or_stage_decode(
    make_case: Callable[..., Case],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = make_case()
    prepared = case.gateway.prepare(case.ref)
    original = case.reader.recheck_identity
    sessions: list[Session] = []

    def checked(
        db: Session,
        token: tuple[str, ...],
        *,
        expected_refs: tuple[ImmutableInventoryRef, ...],
    ) -> None:
        sessions.append(db)
        assert db.connection().get_execution_options()["store_write"] is True
        assert token[0] == "inventory-read-1" and token != prepared.identity
        assert expected_refs == (prepared.ref,)
        original(db, token, expected_refs=expected_refs)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("nested Store/read preparation/full stage decode inside WRITE")

    def write(db: Session) -> None:
        with monkeypatch.context() as patch:
            patch.setattr(case.reader, "recheck_identity", checked)
            patch.setattr(Store, "read", forbidden)
            patch.setattr(Store, "write", forbidden)
            patch.setattr(case.reader, "read_refs", forbidden)
            patch.setattr(compact_reader, "load_stage_set", forbidden)
            patch.setattr(viewing_adapter, "_stage_mapping_digest", forbidden)
            case.gateway.recheck(db, prepared)
        assert sessions == [db]

    case.store.write(write)


def test_invalidation_during_actual_sql_recheck_is_not_lost(
    make_case: Callable[..., Case],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = make_case()
    prepared = case.gateway.prepare(case.ref)
    monkeypatch.setattr(case.reader, "_checkpoint", lambda phase: case.gateway.invalidate())
    with pytest.raises(ApiFailure):
        case.store.read(lambda db: case.gateway.recheck(db, prepared))


@pytest.mark.parametrize("interleaving", ["reader", "adapter", "expiry"])
def test_prepare_rejects_revocation_or_expiry_after_actual_reference_read(
    make_case: Callable[..., Case],
    monkeypatch: pytest.MonkeyPatch,
    interleaving: str,
) -> None:
    case = make_case()
    original = case.reader.read_refs

    def read(
        refs: tuple[ImmutableInventoryRef, ...],
        *,
        expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        batch = original(refs, expected_snapshot_id=expected_snapshot_id)
        if interleaving == "reader":
            case.reader.invalidate()
        elif interleaving == "adapter":
            case.gateway.invalidate()
        else:
            case.clock.value = 400.0
        return batch

    monkeypatch.setattr(case.reader, "read_refs", read)
    with pytest.raises(ApiFailure) as failure:
        case.gateway.prepare(case.ref)
    assert failure.value.code == "ELIGIBILITY_UNAVAILABLE"


def test_prepare_uses_configuration_current_after_actual_reference_read(
    make_case: Callable[..., Case],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = make_case()
    original = case.reader.read_refs
    denied = case.config.model_copy(
        update={"eligibility": EligibilityPolicy(version="test-deny-all", eligible_refs=())}
    )

    def read(
        refs: tuple[ImmutableInventoryRef, ...],
        *,
        expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        batch = original(refs, expected_snapshot_id=expected_snapshot_id)
        # The actual first READ has finished; this separate operator unit changes
        # configuration before the adapter's coherent capture READ begins.
        activate(case.store, denied, 2)
        return batch

    monkeypatch.setattr(case.reader, "read_refs", read)
    with pytest.raises(ApiFailure) as failure:
        case.gateway.prepare(case.ref)
    assert failure.value.code == "ELIGIBILITY_UNAVAILABLE"


@pytest.mark.parametrize("bad_time", [99.0, float("nan"), float("inf")])
def test_clock_regression_or_nonfinite_value_revokes_previous_authority(
    make_case: Callable[..., Case],
    bad_time: float,
) -> None:
    case = make_case()
    prepared = case.gateway.prepare(case.ref)
    case.clock.value = bad_time
    with Session() as db, pytest.raises(ApiFailure):
        case.gateway.recheck(db, prepared)
    case.clock.value = 100.0
    with pytest.raises(ApiFailure):
        case.store.read(lambda db: case.gateway.recheck(db, prepared))
    fresh = case.gateway.prepare(case.ref)
    assert fresh.identity != prepared.identity
    case.store.read(lambda db: case.gateway.recheck(db, fresh))


def test_prepare_does_not_implicitly_admit_a_new_compact_reader(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    cold_reader = CompactInventoryReader(case.store)
    gateway = CompactViewingInventory(cold_reader, rules=case.rules, monotonic_clock=case.clock)
    with pytest.raises(ApiFailure) as failure:
        gateway.prepare(case.ref)
    assert failure.value.code == "ELIGIBILITY_UNAVAILABLE"


def test_prepare_is_forbidden_inside_write(make_case: Callable[..., Case]) -> None:
    case = make_case()
    with pytest.raises(StoreError, match="EXTERNAL_WORK_INSIDE_WRITE_TRANSACTION"):
        case.store.write(lambda db: case.gateway.prepare(case.ref))


@pytest.mark.parametrize("capacity,lifetime", [(0, 300), (257, 300), (1, 301), (1, float("nan"))])
def test_bounds_rejected_without_runtime_io(capacity: int, lifetime: float) -> None:
    with pytest.raises(ValueError, match="VIEWING_ADMISSION_BOUNDS_INVALID"):
        CompactViewingInventory(
            cast(CompactInventoryReader, object()),
            rules=cast(ViewingRules, object()),
            capacity=capacity,
            lifetime_seconds=lifetime,
        )
