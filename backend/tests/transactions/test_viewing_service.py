"""Source-fake integration of pure BE13 logic; never a BE05 acceptance substitute."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from app.api.schemas.viewings import ViewingOptionsRequest
from app.core.config import DemoPolicy
from app.viewings.service import ViewingRulesService
from tests.transactions.viewing_fixtures import NOW, FakeInventory, active_fixture


def test_missing_rules_do_not_read_repository_or_create_options() -> None:
    active, ref, policy = active_fixture()
    reader = FakeInventory(active)
    service = ViewingRulesService(reader, policy=None, eligibility_policy=policy, clock=lambda: NOW)
    result = service.candidates(ViewingOptionsRequest(ref=ref, from_date="2026-09-21"))
    assert result.state == "unconfigured" and result.reason == "RULES_UNAVAILABLE"
    assert result.slots == () and reader.calls == 0


def test_missing_permission_is_explicitly_unconfigured() -> None:
    active, ref, _ = active_fixture()
    reader = FakeInventory(active)
    service = ViewingRulesService(
        reader, policy=DemoPolicy(), eligibility_policy=None, clock=lambda: NOW
    )
    result = service.candidates(ViewingOptionsRequest(ref=ref, from_date="2026-09-21"))
    assert result.state == "unconfigured"
    assert result.reason == "ELIGIBILITY_NOT_CONFIGURED"
    assert result.slots == () and reader.calls == 0


def test_missing_reviewed_mapping_is_unavailable_not_a_permission_rejection() -> None:
    active, ref, policy = active_fixture(mapped=False)
    service = ViewingRulesService(
        FakeInventory(active), policy=DemoPolicy(), eligibility_policy=policy, clock=lambda: NOW
    )
    result = service.candidates(ViewingOptionsRequest(ref=ref, from_date="2026-09-21"))
    assert result.state == "unavailable" and result.reason == "REVIEWED_RESOURCE_MISSING"
    assert result.slots == ()


def test_stale_ref_cannot_receive_calendar_candidates() -> None:
    _, old_ref, _ = active_fixture()
    active, _, policy = active_fixture(seed="b", predecessor=old_ref)
    service = ViewingRulesService(
        FakeInventory(active), policy=DemoPolicy(), eligibility_policy=policy, clock=lambda: NOW
    )
    result = service.candidates(ViewingOptionsRequest(ref=old_ref, from_date="2026-09-21"))
    assert result.state == "ineligible" and result.reason == "REFERENCE_NOT_CURRENT"
    assert result.ref == old_ref and result.slots == ()


def test_one_clock_read_and_one_inventory_read_with_no_capacity_claim() -> None:
    active, ref, policy = active_fixture()
    reader = FakeInventory(active)
    clock_calls: list[int] = []

    def clock() -> datetime:
        clock_calls.append(1)
        return NOW + timedelta(days=len(clock_calls) - 1)

    service = ViewingRulesService(
        reader, policy=DemoPolicy(), eligibility_policy=policy, clock=clock
    )
    request = ViewingOptionsRequest(ref=ref, from_date="2026-09-21", days=7)
    result = service.candidates(request)
    assert result.state == "calendar_candidates" and result.reason == "CAPACITY_NOT_CHECKED"
    assert reader.calls == len(clock_calls) == 1
    assert result.calculated_at == NOW and len(result.slots) == 24
    assert result.capacity_checked is False and result.no_hold is True
    assert active == reader.snapshot


@pytest.mark.parametrize("days", [0, 8, True])
def test_request_validation_bypass_cannot_expand_search_window(days: object) -> None:
    active, ref, policy = active_fixture()
    reader = FakeInventory(active)
    service = ViewingRulesService(
        reader, policy=DemoPolicy(), eligibility_policy=policy, clock=lambda: NOW
    )
    invalid = ViewingOptionsRequest(ref=ref, from_date="2026-09-21").model_copy(
        update={"days": days}
    )
    with pytest.raises(ValidationError):
        service.candidates(invalid)
    assert reader.calls == 0
