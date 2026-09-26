"""Actual composed detail permission, coherent configuration, and read-only behavior."""

from collections.abc import Callable
from datetime import timedelta

import pytest

from app.api.schemas.common import InventoryRef
from app.core.errors import ApiFailure
from app.database.store import StoreError
from app.inventory.extraction import ExtractedCandidate
from app.inventory.snapshots import InventoryRepository
from app.runtime_app import build_composition
from app.viewings.eligibility import EligibilityPolicy
from tests.inventory.snapshot_cases import variant_candidate
from tests.inventory.test_viewing_adapter import NOW, Case, activate, sql
from tests.inventory.test_viewing_adapter import accepted_inputs as accepted_inputs
from tests.inventory.test_viewing_adapter import make_case as make_case
from tests.inventory.viewing_options_cases import business_image, occupy
from tests.platform.runtime_cases import settings_for
from tests.platform.test_identity import call


@pytest.mark.parametrize(
    "configured,member,mapped,expected",
    [
        (True, True, True, "simulated_eligible"),
        (False, True, True, "configuration_missing"),
        (True, False, True, "unavailable"),
        (True, False, False, "unavailable"),
    ],
)
def test_composed_public_detail_observes_permission_without_writes(
    make_case: Callable[..., Case],
    configured: bool,
    member: bool,
    mapped: bool,
    expected: str,
) -> None:
    case = make_case(configured=configured, member=member, mapped=mapped)
    # Listing 4 is the original browser failure; deny-all still applies to it.
    ref = case.ref.model_copy(update={"source_id": "4"}) if mapped else case.ref
    composition = build_composition(settings_for(case.store.path), case.store, clock=lambda: NOW)
    try:
        observation = composition.admit_inventory()
        before = business_image(case)
        before_bytes = case.store.path.read_bytes()
        path = "/api/v1/listings/" + "/".join((ref.namespace, ref.snapshot_id, ref.source_id))
        response = call(composition.app, composition.settings, "GET", path)
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["state"] == "current"
        assert body["data"]["listing"]["ref"] == ref.model_dump()
        assert body["data"]["eligibility"] == expected
        assert body["data"]["eligibility_reason"]
        assert body["meta"]["store_generation"] == observation.generation
        assert body["meta"]["inventory_snapshot_id"] == observation.snapshot_id
        assert "set-cookie" not in response.headers
        assert business_image(case) == before
        assert case.store.path.read_bytes() == before_bytes
    finally:
        assert composition.close()


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_mapping",
        "mapping",
        "resource",
        "configuration",
        "calendar",
        "policy",
        "digest",
        "generation",
        "revision",
        "snapshot",
    ],
)
def test_composed_detail_never_grants_permission_after_dependency_failure(
    make_case: Callable[..., Case],
    mutation: str,
) -> None:
    case = make_case(mapped=mutation != "missing_mapping")
    composition = build_composition(settings_for(case.store.path), case.store, clock=lambda: NOW)
    try:
        composition.admit_inventory()
        if mutation in {"calendar", "policy", "digest", "snapshot"}:
            updates: dict[str, dict[str, object]] = {
                "calendar": {"calendar_version": "wrong-calendar"},
                "policy": {
                    "policy": case.config.policy.model_copy(update={"version": "wrong-policy"})
                },
                "digest": {"mapping_digest": "f" * 64},
                "snapshot": {
                    "inventory": case.config.inventory.model_copy(update={"snapshot_id": "f" * 64}),
                    "eligibility": EligibilityPolicy(version="wrong-snapshot", eligible_refs=()),
                },
            }
            activate(case.store, case.config.model_copy(update=updates[mutation]), 2)
        else:
            mutations = {
                "mapping": "UPDATE listing_resource_mappings SET mapping_version='changed'",
                "resource": "UPDATE vehicle_resources SET mapping_version='changed'",
                "configuration": "UPDATE rule_versions SET rules_json='{}'",
                "generation": (
                    "UPDATE store_metadata "
                    "SET store_generation='12345678-1234-1234-1234-123456789abc'"
                ),
                "revision": "UPDATE active_inventory SET revision=revision+1",
            }
            if mutation in mutations:
                sql(case.store, mutations[mutation])
        before_bytes = case.store.path.read_bytes()
        with pytest.raises((ApiFailure, StoreError)) as failure:
            composition.details.lookup(InventoryRef.model_validate(case.ref.model_dump()))
        code = failure.value.code if isinstance(failure.value, ApiFailure) else str(failure.value)
        assert code in {
            "ELIGIBILITY_UNAVAILABLE",
            "RULES_UNAVAILABLE",
            "STORE_GENERATION_CHANGED",
            "SNAPSHOT_STALE",
            "STORE_UNAVAILABLE",
        }
        assert case.store.path.read_bytes() == before_bytes
    finally:
        assert composition.close()


def test_composed_detail_history_missing_and_full_calendar_remain_read_only(
    make_case: Callable[..., Case],
    snapshot_candidate: ExtractedCandidate,
) -> None:
    case = make_case()
    composition = build_composition(settings_for(case.store.path), case.store, clock=lambda: NOW)
    try:
        composition.admit_inventory()
        occupy(case, NOW, NOW + timedelta(days=30))
        before = business_image(case)
        result = composition.details.lookup(InventoryRef.model_validate(case.ref.model_dump()))
        assert result.state == "current" and result.eligibility == "simulated_eligible"
        missing = InventoryRef.model_validate(
            case.ref.model_copy(update={"source_id": "not-there"}).model_dump()
        )
        assert composition.details.lookup(missing).state == "missing"
        assert business_image(case) == before
        repository = InventoryRepository(case.store, clock=lambda: NOW)
        plan = repository.prepare(
            variant_candidate(snapshot_candidate), policy_version=case.rules.policy.version
        )
        repository.stage(plan)
        observation = repository.activate(plan.candidate.manifest.snapshot_id, expected_revision=1)
        activate(
            case.store,
            case.config.model_copy(
                update={
                    "inventory": observation,
                    "mapping_digest": plan.mapping_digest,
                    "eligibility": EligibilityPolicy(version="history-deny", eligible_refs=()),
                }
            ),
            2,
        )
        composition.admit_inventory()
        composition.reader.admit(case.ref.snapshot_id)
        before = business_image(case)
        historical = composition.details.lookup(InventoryRef.model_validate(case.ref.model_dump()))
        assert historical.state == "historical" and historical.eligibility == "unavailable"
        assert business_image(case) == before
    finally:
        assert composition.close()
