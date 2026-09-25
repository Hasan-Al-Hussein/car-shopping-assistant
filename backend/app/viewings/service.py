"""Read-only calendar candidates. Capacity and confirmation belong to later cards."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.api.schemas.viewings import ViewingOptionsRequest
from app.core.config import DemoPolicy
from app.inventory.references import ImmutableInventoryRef
from app.viewings.eligibility import (
    ActiveInventoryReader,
    EligibilityPolicy,
    EligibilityResult,
    observe_eligibility,
)
from app.viewings.scheduling import ViewingRules, ZonedInterval, utc_instant


@dataclass(frozen=True)
class CalendarCandidates:
    """Internal result, deliberately not the wire's capacity-observed available state."""

    ref: ImmutableInventoryRef
    state: Literal[
        "calendar_candidates", "no_valid_slots", "ineligible", "unconfigured", "unavailable"
    ]
    reason: str
    calculated_at: datetime
    rules_version: str | None
    eligibility: EligibilityResult | None
    slots: tuple[ZonedInterval, ...] = ()
    no_hold: Literal[True] = True
    capacity_checked: Literal[False] = False


class ViewingRulesService:
    def __init__(
        self,
        reader: ActiveInventoryReader,
        *,
        policy: DemoPolicy | None,
        eligibility_policy: EligibilityPolicy | None,
        clock: Callable[[], datetime],
    ) -> None:
        self._reader = reader
        self._rules = ViewingRules(policy) if policy is not None else None
        self._eligibility_policy = (
            EligibilityPolicy.model_validate(eligibility_policy.model_dump(mode="python"))
            if eligibility_policy is not None
            else None
        )
        self._clock = clock

    def candidates(self, request: ViewingOptionsRequest) -> CalendarCandidates:
        """Capture the trusted clock once and make at most one coherent inventory read.

        The returned candidates still need a later read of occupied intervals and
        atomic revalidation at confirmation. This method cannot hold capacity.
        """
        selected = ViewingOptionsRequest.model_validate(request.model_dump(mode="python"))
        ref = ImmutableInventoryRef.model_validate(selected.ref.model_dump(mode="python"))
        now = utc_instant(self._clock())
        rules = self._rules
        if rules is None:
            return CalendarCandidates(ref, "unconfigured", "RULES_UNAVAILABLE", now, None, None)
        if self._eligibility_policy is None:
            return CalendarCandidates(
                ref, "unconfigured", "ELIGIBILITY_NOT_CONFIGURED", now, rules.version, None
            )
        eligibility = observe_eligibility(self._reader, ref, self._eligibility_policy)
        if eligibility.state != "eligible":
            state: Literal["unconfigured", "ineligible", "unavailable"]
            if eligibility.state == "unconfigured":
                state = "unconfigured"
            elif eligibility.state == "unavailable":
                state = "unavailable"
            else:
                state = "ineligible"
            return CalendarCandidates(
                ref, state, eligibility.reason, now, rules.version, eligibility
            )
        slots = rules.candidate_slots(selected.from_date, days=selected.days, now=now)
        return CalendarCandidates(
            ref,
            "calendar_candidates" if slots else "no_valid_slots",
            "CAPACITY_NOT_CHECKED" if slots else "NO_CALENDAR_MATCH",
            now,
            rules.version,
            eligibility,
            slots,
        )
