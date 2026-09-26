"""Pure eligibility tests; BE05 real repository integration remains a separate gate."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.api.schemas.common import InventoryRef
from app.core.readiness import InventoryObservation
from app.database.store import StoreError
from app.inventory.resource_lineage import lineage_version
from app.inventory.snapshots import ActiveSnapshot
from app.viewings.eligibility import (
    EligibilityIntegrityError,
    EligibilityPolicy,
    observe_eligibility,
    resolve_eligibility,
)
from tests.transactions.viewing_fixtures import GENERATION, RESOURCE, FakeInventory, active_fixture


def test_exact_wire_ref_uses_one_coherent_active_read() -> None:
    active, ref, policy = active_fixture()
    reader = FakeInventory(active)
    wire_ref = InventoryRef.model_validate(ref.model_dump())
    result = observe_eligibility(reader, wire_ref, policy)
    assert reader.calls == 1
    assert result.state == "eligible"
    assert result.ref == ref and result.resource_id == RESOURCE
    assert result.mapping_version == "synthetic-lineage-1"
    assert result.observation == active.observation
    assert active.stage is not None
    assert result.mapping_digest == active.stage.mapping_digest


def test_mapping_and_seller_prose_without_explicit_permission_do_not_grant_eligibility() -> None:
    active, ref, _ = active_fixture()
    assert resolve_eligibility(active, ref, None).state == "unconfigured"
    result = resolve_eligibility(
        active, ref, EligibilityPolicy(version="explicit-empty", eligible_refs=())
    )
    assert result.reason == "NOT_IN_DEMO_ALLOWLIST"
    assert result.resource_id is None


def test_permission_without_reviewed_mapping_does_not_grant_eligibility() -> None:
    active, ref, policy = active_fixture(mapped=False)
    result = resolve_eligibility(active, ref, policy)
    assert result.reason == "REVIEWED_RESOURCE_MISSING"
    assert result.state == "unavailable" and result.resource_id is None


@pytest.mark.parametrize(
    "changed", [{"namespace": "other"}, {"source_id": "707"}, {"source_id": "absent"}]
)
def test_exact_current_reference_does_not_fall_back_to_numeric_id(changed: dict[str, str]) -> None:
    active, ref, policy = active_fixture()
    requested = InventoryRef.model_validate({**ref.model_dump(), **changed})
    result = resolve_eligibility(active, requested, policy)
    assert result.state == "missing" and result.resource_id is None


def test_historical_or_unknown_snapshot_never_retargets_same_source_id() -> None:
    old, old_ref, _ = active_fixture()
    current, current_ref, policy = active_fixture(seed="b", predecessor=old_ref)
    result = resolve_eligibility(current, old_ref, policy)
    assert result.state == "stale" and result.ref == old_ref and result.resource_id is None
    assert current_ref.source_id == old_ref.source_id
    assert old.observation.snapshot_id != current.observation.snapshot_id
    unknown = InventoryRef.model_validate({**current_ref.model_dump(), "snapshot_id": "f" * 64})
    assert resolve_eligibility(current, unknown, policy).state == "stale"


def test_reviewed_successor_retains_same_capacity_resource_in_separate_observations() -> None:
    old, old_ref, old_policy = active_fixture()
    current, current_ref, current_policy = active_fixture(seed="b", predecessor=old_ref)
    before = resolve_eligibility(old, old_ref, old_policy)
    after = resolve_eligibility(current, current_ref, current_policy)
    assert before.resource_id == after.resource_id == RESOURCE
    assert before.ref != after.ref
    assert before.eligibility_version != after.eligibility_version


def test_no_active_inventory_is_unconfigured_not_a_missing_listing() -> None:
    _, ref, policy = active_fixture()
    active = ActiveSnapshot(InventoryObservation(generation=GENERATION, active_revision=0), None)
    result = resolve_eligibility(active, ref, policy)
    assert result.reason == "INVENTORY_NOT_CONFIGURED"


@pytest.mark.parametrize("code", ["STORE_BUSY", "STORE_UNAVAILABLE", "STORE_GENERATION_CHANGED"])
def test_store_failures_propagate_instead_of_becoming_ineligible(code: str) -> None:
    active, ref, policy = active_fixture()

    class BrokenReader(FakeInventory):
        def active(self) -> ActiveSnapshot:
            raise StoreError(code)

    with pytest.raises(StoreError, match=code):
        observe_eligibility(BrokenReader(active), ref, policy)


def test_corrupt_repository_read_does_not_become_missing() -> None:
    active, ref, policy = active_fixture()

    class CorruptReader(FakeInventory):
        def active(self) -> ActiveSnapshot:
            raise ValueError("INVENTORY_IMMUTABLE_STAGE_MISMATCH")

    with pytest.raises(ValueError, match="INVENTORY_IMMUTABLE_STAGE_MISMATCH"):
        observe_eligibility(CorruptReader(active), ref, policy)


def test_incoherent_materialized_stage_fails_closed() -> None:
    active, ref, policy = active_fixture()
    with pytest.raises(EligibilityIntegrityError):
        resolve_eligibility(replace(active, stage=None), ref, policy)
    assert active.stage is not None
    with pytest.raises(EligibilityIntegrityError):
        resolve_eligibility(
            replace(active, stage=replace(active.stage, mapping_digest="0" * 64)), ref, policy
        )


def test_eligibility_version_binds_policy_content_revision_generation_and_lineage() -> None:
    active, ref, policy = active_fixture()
    baseline = resolve_eligibility(active, ref, policy).eligibility_version
    changed_policy = EligibilityPolicy(version="permission-2", eligible_refs=(ref,))
    assert resolve_eligibility(active, ref, changed_policy).eligibility_version != baseline
    empty_same_label = EligibilityPolicy(version=policy.version, eligible_refs=())
    assert resolve_eligibility(active, ref, empty_same_label).eligibility_version != baseline
    for change in ({"active_revision": 2}, {"generation": "30000000-0000-4000-8000-000000000002"}):
        updated = replace(active, observation=active.observation.model_copy(update=change))
        assert resolve_eligibility(updated, ref, policy).eligibility_version != baseline
    assert active.stage is not None
    changed_mappings = (
        active.stage.mappings[0].model_copy(update={"mapping_version": "synthetic-lineage-2"}),
    )
    changed_stage = replace(
        active.stage,
        mappings=changed_mappings,
        mapping_digest=lineage_version(changed_mappings),
    )
    new_lineage = resolve_eligibility(replace(active, stage=changed_stage), ref, policy)
    assert new_lineage.ref == ref and new_lineage.observation == active.observation
    assert new_lineage.mapping_version == "synthetic-lineage-2"
    assert new_lineage.eligibility_version != baseline


def test_duplicate_allowlist_and_bypassed_policy_validation_are_rejected() -> None:
    active, ref, policy = active_fixture()
    with pytest.raises(ValidationError):
        EligibilityPolicy(version="duplicates", eligible_refs=(ref, ref))
    with pytest.raises(ValidationError):
        resolve_eligibility(active, ref, policy.model_copy(update={"version": "invalid version"}))
