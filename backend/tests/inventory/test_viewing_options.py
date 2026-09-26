"""I11 obligations, authored only: real I5/configuration/SQLite reads, synthetic bookings."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.api.schemas.viewings import ViewingOptionsRequest
from app.core.errors import ApiFailure
from app.core.readiness import ReadinessRegistry
from app.database.store import Store, StoreError
from app.identity.service import utc_text
from app.inventory import viewing_options
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.references import ImmutableInventoryRef
from app.inventory.snapshots import InventoryRepository
from app.inventory.viewing_options import CompactViewingOptions
from app.viewings.draft_configuration import configuration_id, eligibility_version
from app.viewings.eligibility import EligibilityPolicy
from app.viewings.scheduling import ViewingRules
from scripts.bootstrap_inventory import BootstrapInputs
from tests.inventory.snapshot_cases import variant_candidate
from tests.inventory.test_viewing_adapter import NOW, Case, activate, sql
from tests.inventory.test_viewing_adapter import accepted_inputs as accepted_inputs
from tests.inventory.test_viewing_adapter import make_case as make_case
from tests.inventory.viewing_options_cases import business_image, occupy

START = datetime(2026, 9, 25, 4, tzinfo=UTC)


def request(case: Case, *, days: int = 1, start: str = "2026-09-25") -> ViewingOptionsRequest:
    return ViewingOptionsRequest.model_validate({
        "ref": case.ref.model_dump(), "from_date": start, "days": days,
    })


def reader(case: Case) -> CompactViewingOptions:
    return CompactViewingOptions(case.reader, rules=case.rules, clock=lambda: NOW)


def test_real_versions_single_clock_capacity_query_and_no_writes(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    statements: list[str] = []
    traced = CompactInventoryReader(replace(case.store, trace=statements.append))
    traced.refresh(ReadinessRegistry())
    calls: list[bool] = []

    def clock() -> datetime:
        calls.append(True)
        return NOW

    service = CompactViewingOptions(traced, rules=case.rules, clock=clock)
    before = business_image(case)
    statements.clear()
    result = service.options(request(case, days=7))
    assert calls == [True]
    assert result.state == "available" and len(result.slots) == 24 and result.no_hold is True
    assert result.rules_version == configuration_id(case.config)
    assert result.rules_version != case.rules.version
    assert result.eligibility_version == eligibility_version(case.config)
    assert result.calculated_at == utc_text(NOW)
    assert result.slots[0].starts_at_utc == utc_text(START)
    assert result.slots[-1].ends_at_utc == utc_text(START + timedelta(hours=12))
    queries = [statement for statement in statements if statement.startswith("WITH candidates(")]
    assert len(queries) == 1 and "NOT EXISTS" in queries[0] and "LIMIT 24" in queries[0]
    assert all(word not in queries[0] for word in ("owner_id", "snapshot_id", "expires_at"))
    assert not any(statement.lstrip().upper().startswith((
        "INSERT ", "UPDATE ", "DELETE ", "REPLACE ", "BEGIN IMMEDIATE",
    )) for statement in statements)
    assert business_image(case) == before
    assert set(result.model_dump()) == {
        "ref", "state", "rules_version", "eligibility_version", "calculated_at", "no_hold", "slots",
    }


@pytest.mark.parametrize("offset,taken", [(-31, False), (-30, False), (-15, True),
                                        (0, True), (15, True), (30, False)])
def test_actual_durable_foreign_booking_uses_half_open_capacity_despite_expired_retention(
    make_case: Callable[..., Case], offset: int, taken: bool,
) -> None:
    case = make_case()
    start = START + timedelta(minutes=offset)
    occupy(case, start, start + timedelta(minutes=30))
    before = business_image(case)
    result = reader(case).options(request(case))
    assert (utc_text(START) not in [slot.starts_at_utc for slot in result.slots]) is taken
    assert business_image(case) == before


def test_other_resource_does_not_block_but_another_listing_for_same_resource_does(
    make_case: Callable[..., Case], accepted_inputs: BootstrapInputs,
) -> None:
    case = make_case()
    other = next(item for item in accepted_inputs.mappings if item.ref != case.ref)
    own = next(item for item in accepted_inputs.mappings if item.ref == case.ref)
    occupy(case, START, START + timedelta(minutes=30),
           resource_id=other.resource_id, ref=other.ref)
    assert reader(case).options(request(case)).slots[0].starts_at_utc == utc_text(START)
    occupy(case, START, START + timedelta(minutes=30),
           resource_id=own.resource_id, ref=other.ref)
    assert reader(case).options(request(case)).slots[0].starts_at_utc == utc_text(
        START + timedelta(minutes=30)
    )


def test_full_first_day_does_not_hide_next_day_and_full_window_has_no_slots(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    occupy(case, START, START + timedelta(hours=12))
    result = reader(case).options(request(case, days=2))
    assert result.state == "available" and len(result.slots) == 24
    assert result.slots[0].starts_at_utc == utc_text(START + timedelta(days=1))
    occupy(case, START + timedelta(days=1), START + timedelta(days=1, hours=12))
    result = reader(case).options(request(case, days=2))
    assert result.state == "no_valid_slots" and result.slots == []
    assert result.rules_version == configuration_id(case.config) and result.no_hold


def test_no_hold_next_read_observes_booking_and_read_gap_uses_latest_capacity(
    make_case: Callable[..., Case], monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = make_case()
    service = reader(case)
    assert service.options(request(case)).slots[0].starts_at_utc == utc_text(START)
    original = case.reader.read_refs
    observed: list[bool] = []

    def interleaved(
        refs: tuple[ImmutableInventoryRef, ...], *, expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        batch = original(refs, expected_snapshot_id=expected_snapshot_id)
        mapping = batch.items[0].mapping
        assert mapping is not None
        occupy(case, START, START + timedelta(minutes=30), resource_id=mapping.resource_id)
        observed.append(True)
        return batch

    monkeypatch.setattr(case.reader, "read_refs", interleaved)
    result = service.options(request(case))
    assert observed == [True]
    assert result.slots[0].starts_at_utc == utc_text(START + timedelta(minutes=30))


@pytest.mark.parametrize("absent", ["configuration", "policy"])
def test_genuinely_unconfigured_is_not_implicitly_activated(
    make_case: Callable[..., Case], absent: str,
) -> None:
    case = make_case(configured=absent != "configuration")
    before = business_image(case)
    service = CompactViewingOptions(
        case.reader, rules=None if absent == "policy" else case.rules, clock=lambda: NOW,
    )
    result = service.options(request(case))
    assert result.state == "unconfigured" and result.slots == []
    assert result.rules_version is None and result.eligibility_version is None
    assert business_image(case) == before


def test_no_active_inventory_is_unconfigured(
    inventory_store: Store, accepted_inputs: BootstrapInputs,
) -> None:
    compact = CompactInventoryReader(inventory_store)
    compact.refresh(ReadinessRegistry())
    result = CompactViewingOptions(
        compact, rules=ViewingRules(accepted_inputs.policy), clock=lambda: NOW,
    ).options(ViewingOptionsRequest.model_validate({
        "ref": accepted_inputs.mappings[0].ref.model_dump(), "from_date": "2026-09-25",
    }))
    assert result.state == "unconfigured" and result.no_hold and result.slots == []


def test_healthy_deny_all_precedes_missing_mapping(
    make_case: Callable[..., Case],
) -> None:
    case = make_case(member=False, mapped=False)
    result = reader(case).options(request(case))
    assert result.state == "ineligible" and result.slots == []
    assert result.rules_version == configuration_id(case.config)
    assert result.eligibility_version == eligibility_version(case.config)


def test_eligible_missing_mapping_is_error_not_ordinary_ineligibility(
    make_case: Callable[..., Case],
) -> None:
    case = make_case(mapped=False)
    with pytest.raises(ApiFailure, match="ELIGIBILITY_UNAVAILABLE"):
        reader(case).options(request(case))


@pytest.mark.parametrize("field,value,code", [
    ("snapshot_id", "f" * 64, "SNAPSHOT_STALE"),
    ("source_id", "does-not-exist", "NOT_FOUND"),
])
def test_stale_and_absent_refs_use_closed_existing_errors(
    make_case: Callable[..., Case], field: str, value: str, code: str,
) -> None:
    case = make_case()
    command = request(case).model_dump()
    command["ref"][field] = value
    with pytest.raises(ApiFailure, match=code):
        reader(case).options(ViewingOptionsRequest.model_validate(command))


def test_bad_configuration_remains_unavailable_even_when_calendar_is_empty(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    sql(case.store, "UPDATE rule_versions SET rules_json='{}'")
    with pytest.raises(ApiFailure, match="RULES_UNAVAILABLE"):
        reader(case).options(request(case, start="2026-09-27"))


@pytest.mark.parametrize("mutation", ["inventory", "mapping", "configuration", "revoke"])
def test_read_gap_rechecks_original_inventory_and_current_configuration(
    make_case: Callable[..., Case], monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    case = make_case()
    original = case.reader.read_refs
    newer = case.config.model_copy(update={
        "eligibility": EligibilityPolicy(version="i11-deny", eligible_refs=()),
    })
    changed: list[bool] = []

    def interleaved(
        refs: tuple[ImmutableInventoryRef, ...], *, expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        batch = original(refs, expected_snapshot_id=expected_snapshot_id)
        if mutation == "inventory":
            sql(case.store, "UPDATE active_inventory SET revision=revision+1")
        elif mutation == "mapping":
            sql(case.store, "UPDATE listing_resource_mappings SET mapping_version='changed'")
        elif mutation == "configuration":
            activate(case.store, newer, 2)
        else:
            case.reader.invalidate()
        changed.append(True)
        return batch

    monkeypatch.setattr(case.reader, "read_refs", interleaved)
    if mutation == "configuration":
        result = reader(case).options(request(case))
        assert result.state == "ineligible" and result.rules_version == configuration_id(newer)
        assert result.eligibility_version == eligibility_version(newer)
    else:
        with pytest.raises(ApiFailure, match="ELIGIBILITY_UNAVAILABLE"):
            reader(case).options(request(case))
    assert changed == [True]


@pytest.mark.parametrize("error", ["STORE_BUSY", "STORE_UNAVAILABLE", "STORE_GENERATION_CHANGED"])
def test_capacity_failure_propagates_without_returning_empty_availability(
    make_case: Callable[..., Case], monkeypatch: pytest.MonkeyPatch, error: str,
) -> None:
    case = make_case()
    reached: list[bool] = []

    def fail(db: Session, resource_id: str, candidates: object) -> list[object]:
        assert db.in_transaction()
        reached.append(True)
        raise StoreError(error)

    monkeypatch.setattr(viewing_options, "_free_slots", fail)
    with pytest.raises(StoreError, match=error):
        reader(case).options(request(case))
    assert reached == [True]


@pytest.mark.parametrize("start", ["2026-09-27", "2026-08-01", "2026-11-01"])
def test_closed_past_and_beyond_horizon_windows_have_no_valid_slots(
    make_case: Callable[..., Case], start: str,
) -> None:
    case = make_case()
    result = reader(case).options(request(case, start=start))
    assert result.state == "no_valid_slots" and result.slots == [] and result.no_hold


def test_request_bypass_and_overflow_are_validation_errors(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    service = reader(case)
    for command in (
        request(case).model_copy(update={"days": True}),
        request(case, start="9999-12-31", days=2),
    ):
        with pytest.raises(ApiFailure, match="VALIDATION_ERROR"):
            service.options(command)


def test_bad_clock_does_not_return_business_availability(
    make_case: Callable[..., Case],
) -> None:
    case = make_case()
    service = CompactViewingOptions(case.reader, rules=case.rules,
                                    clock=lambda: datetime(2026, 9, 24))
    with pytest.raises(ApiFailure, match="RULES_UNAVAILABLE"):
        service.options(request(case))


def test_cold_reader_never_self_admits(
    make_case: Callable[..., Case], monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = make_case()
    cold = CompactInventoryReader(case.store)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("PUBLIC_OPTIONS_MUST_NOT_ADMIT")

    monkeypatch.setattr(cold, "admit", forbidden)
    monkeypatch.setattr(cold, "refresh", forbidden)
    before = business_image(case)
    with pytest.raises(ApiFailure, match="ELIGIBILITY_UNAVAILABLE"):
        CompactViewingOptions(cold, rules=case.rules, clock=lambda: NOW).options(request(case))
    assert business_image(case) == before


def test_changed_batch_stamp_cannot_authorize_capacity_read(
    make_case: Callable[..., Case], monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = make_case()
    original = case.reader.read_refs
    changed: list[bool] = []

    def altered(
        refs: tuple[ImmutableInventoryRef, ...], *, expected_snapshot_id: str | None = None,
    ) -> CompactBatch:
        batch = original(refs, expected_snapshot_id=expected_snapshot_id)
        changed.append(True)
        return replace(batch, stamp="0" * 64)

    monkeypatch.setattr(case.reader, "read_refs", altered)
    with pytest.raises(ApiFailure, match="ELIGIBILITY_UNAVAILABLE"):
        reader(case).options(request(case))
    assert changed == [True]


def test_retained_history_requires_its_own_admission_before_stale_classification(
    make_case: Callable[..., Case], accepted_inputs: BootstrapInputs,
) -> None:
    case = make_case()
    repository = InventoryRepository(case.store, clock=lambda: NOW)
    # A genuine staged second snapshot, explicitly synthetic and deny-all; no
    # resource lineage or vehicle identity is inferred for its changed records.
    plan = repository.prepare(
        variant_candidate(accepted_inputs.candidate), policy_version=case.rules.policy.version,
    )
    repository.stage(plan)
    observation = repository.activate(plan.candidate.manifest.snapshot_id, expected_revision=1)
    current_config = case.config.model_copy(update={
        "inventory": observation, "mapping_digest": plan.mapping_digest,
        "eligibility": EligibilityPolicy(version="i11-history-deny", eligible_refs=()),
    })
    activate(case.store, current_config, 2)
    compact = CompactInventoryReader(case.store)
    compact.refresh(ReadinessRegistry())
    service = CompactViewingOptions(compact, rules=case.rules, clock=lambda: NOW)
    before = business_image(case)
    with pytest.raises(ApiFailure, match="ELIGIBILITY_UNAVAILABLE"):
        service.options(request(case))
    compact.admit(case.ref.snapshot_id)  # Explicit fixture/operator action only.
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        service.options(request(case))
    assert business_image(case) == before
