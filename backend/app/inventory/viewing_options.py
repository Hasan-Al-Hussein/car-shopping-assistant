"""Public simulated options: coherent inventory/configuration and global capacity.

This read observes free intervals, creates no hold and grants no action authority.
Confirmation must independently recheck current rules, eligibility and capacity.
"""

import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.schemas.common import InventoryRef
from app.api.schemas.viewings import ViewingOptions, ViewingOptionsRequest, ViewingSlot
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.database.store import assert_outside_write_transaction
from app.identity.service import utc_text
from app.inventory.compact_reader import CompactInventoryReader, CompactReference
from app.inventory.public_projection import ListingEligibility
from app.inventory.references import ImmutableInventoryRef
from app.inventory.staging_plan import STAGING_POLICY_VERSION
from app.viewings.draft_configuration import (
    ViewingConfiguration,
    eligibility_version,
    load_configuration,
)
from app.viewings.scheduling import MAX_CANDIDATES, SchedulingError, ViewingRules, utc_instant


def utc_now() -> datetime:
    return datetime.now(UTC)


def _configuration(
    db: Session, observation: InventoryObservation, rules: ViewingRules
) -> tuple[str, ViewingConfiguration] | None:
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT m.store_generation,a.snapshot_id,a.revision,a.index_version,p.mode,"
            "s.namespace,s.index_version FROM store_metadata m "
            "LEFT JOIN active_inventory a ON a.id=1 "
            "LEFT JOIN inventory_storage_profile p ON p.id=1 "
            "LEFT JOIN inventory_snapshots s ON s.snapshot_id=a.snapshot_id WHERE m.id=1"
        )
        .first()
    )
    if row is None or row[0] != observation.generation:
        raise ApiFailure("STORE_GENERATION_CHANGED")
    if observation.snapshot_id is None:
        if any(value is not None for value in (row[1], row[2], row[3], row[5], row[6])):
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
        return None
    if (
        type(row[2]) is not int
        or tuple(row[1:5])
        != (
            observation.snapshot_id,
            observation.active_revision,
            observation.index_version,
            observation.mode,
        )
        or type(row[5]) is not str
        or row[6] != observation.index_version
    ):
        raise ApiFailure("SNAPSHOT_STALE")
    namespace: str = row[5]
    pointers = (
        db.connection()
        .exec_driver_sql(
            "SELECT id,CASE WHEN typeof(version)='text' "
            "AND length(CAST(version AS BLOB)) BETWEEN 1 AND 200 THEN version END,revision "
            "FROM active_rules ORDER BY id LIMIT 2"
        )
        .all()
    )
    if not pointers:
        return None
    if (
        len(pointers) != 1
        or pointers[0][0] != 1
        or type(pointers[0][1]) is not str
        or type(pointers[0][2]) is not int
        or not 0 <= pointers[0][2] <= 2_147_483_647
    ):
        raise ApiFailure("RULES_UNAVAILABLE")
    version: str = pointers[0][1]
    config = load_configuration(
        db, version, rules=rules, observation=observation, namespace=namespace
    )
    # The preceding I5 recheck authenticates this complete stage in the same unit.
    # Only its bounded digest crosses into application memory, never the full stage.
    stage = (
        db.connection()
        .exec_driver_sql(
            "SELECT serialization_version,CASE WHEN json_valid(payload_json) THEN "
            "CASE WHEN json_type(payload_json,'$.mapping_digest')='text' "
            "AND length(json_extract(payload_json,'$.mapping_digest'))=64 "
            "THEN json_extract(payload_json,'$.mapping_digest') END END "
            "FROM inventory_snapshot_payloads WHERE snapshot_id=?",
            (observation.snapshot_id,),
        )
        .first()
    )
    if (
        stage is None
        or stage[0] != STAGING_POLICY_VERSION
        or type(stage[1]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", stage[1]) is None
        or stage[1] != config.mapping_digest
    ):
        raise ApiFailure("RULES_UNAVAILABLE")
    return version, config


def _resource(db: Session, item: CompactReference) -> str:
    mapping = item.mapping
    if mapping is None or type(item.resource_version) is not str:
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT m.resource_id,m.mapping_version,r.mapping_version "
            "FROM listing_resource_mappings m "
            "JOIN vehicle_resources r ON r.id=m.resource_id "
            "WHERE m.namespace=? AND m.snapshot_id=? AND m.source_id=?",
            (item.ref.namespace, item.ref.snapshot_id, item.ref.source_id),
        )
        .first()
    )
    if row is None or tuple(row) != (
        mapping.resource_id,
        mapping.mapping_version,
        item.resource_version,
    ):
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    return mapping.resource_id


class CompactPublicEligibility:
    """Informational permission inside the detail reader's already rechecked unit."""

    def __init__(self, rules: ViewingRules) -> None:
        self.rules = rules

    def resolve(
        self,
        session: Session,
        item: CompactReference,
        *,
        observation: InventoryObservation,
    ) -> ListingEligibility:
        if item.state != "current" or item.listing is None:
            return ListingEligibility("unavailable", "This listing is not current.")
        if item.ref.snapshot_id != observation.snapshot_id:
            raise ApiFailure("SNAPSHOT_STALE")
        configured = _configuration(session, observation, self.rules)
        if configured is None:
            return ListingEligibility(
                "configuration_missing",
                "Viewing eligibility has not been configured.",
            )
        _, config = configured
        if item.ref not in config.eligibility.eligible_refs:
            return ListingEligibility(
                "unavailable", "This listing is not eligible for simulated viewing."
            )
        _resource(session, item)
        return ListingEligibility(
            "simulated_eligible", "Simulated viewing only; no real reservation."
        )


def _calendar(
    rules: ViewingRules, request: ViewingOptionsRequest, now: datetime
) -> list[ViewingSlot]:
    try:
        first = date.fromisoformat(request.from_date)
        # Validate the whole window even when an early day already has 24 candidates.
        if first > date.max - timedelta(days=request.days - 1):
            raise SchedulingError("DATE_OUT_OF_RANGE")
        return [
            ViewingSlot(
                starts_at_utc=utc_text(slot.starts_at_utc),
                ends_at_utc=utc_text(slot.ends_at_utc),
            )
            for offset in range(request.days)
            for slot in rules.candidate_slots(
                (first + timedelta(days=offset)).isoformat(), days=1, now=now
            )
        ]
    except SchedulingError:
        raise ApiFailure("VALIDATION_ERROR") from None


def _free_slots(db: Session, resource_id: str, candidates: list[ViewingSlot]) -> list[ViewingSlot]:
    if not candidates:
        return []
    # At most 7*24 candidates / 505 bound values / 24 returned scalar ordinals.
    # Capacity is the adopted literal 1. No owner, listing, snapshot, retention or
    # receipt filter: all durable bookings for this resource occupy [start, end).
    values = ",".join("(?,?,?)" for _ in candidates)
    parameters: list[object] = []
    for ordinal, slot in enumerate(candidates):
        parameters.extend((ordinal, slot.starts_at_utc, slot.ends_at_utc))
    parameters.append(resource_id)
    rows = (
        db.connection()
        .exec_driver_sql(
            "WITH candidates(ordinal,starts_at_utc,ends_at_utc) AS (VALUES " + values + ") "
            "SELECT c.ordinal FROM candidates c WHERE NOT EXISTS (SELECT 1 FROM bookings b "
            "WHERE b.resource_id=? AND b.starts_at_utc<c.ends_at_utc "
            "AND b.ends_at_utc>c.starts_at_utc) ORDER BY c.ordinal LIMIT 24",
            tuple(parameters),
        )
        .all()
    )
    return [candidates[row[0]] for row in rows]


class CompactViewingOptions:
    """Synchronous ViewingOptionsReader; construction performs no I/O or admission."""

    def __init__(
        self,
        reader: CompactInventoryReader,
        *,
        rules: ViewingRules | None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.reader, self.rules, self._clock = reader, rules, clock

    def options(self, request: ViewingOptionsRequest) -> ViewingOptions:
        assert_outside_write_transaction()
        try:
            selected = ViewingOptionsRequest.model_validate(request.model_dump(mode="python"))
            exact = ImmutableInventoryRef.model_validate(selected.ref.model_dump())
        except (AttributeError, TypeError, ValueError):
            raise ApiFailure("VALIDATION_ERROR") from None
        try:
            now = utc_instant(self._clock())
        except (AttributeError, TypeError, ValueError, OverflowError):
            raise ApiFailure("RULES_UNAVAILABLE") from None
        empty = ViewingOptions(
            ref=InventoryRef.model_validate(exact.model_dump()),
            state="unconfigured",
            rules_version=None,
            eligibility_version=None,
            calculated_at=utc_text(now),
            slots=[],
        )
        rules = self.rules
        if rules is None:
            return empty
        candidates = _calendar(rules, selected, now)
        try:
            batch = self.reader.read_refs((exact,))

            def observe(db: Session) -> ViewingOptions:
                # Original authenticated batch, not an unrelated second inventory read.
                self.reader.recheck(db, batch)
                configured = _configuration(db, batch.observation, rules)
                if configured is None:
                    return empty
                version, config = configured
                if exact.snapshot_id != batch.observation.snapshot_id:
                    raise ApiFailure("SNAPSHOT_STALE")
                if len(batch.items) != 1 or batch.items[0].ref != exact:
                    raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
                item = batch.items[0]
                if item.state == "missing":
                    raise ApiFailure("NOT_FOUND")
                if item.state != "current" or item.listing is None:
                    raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
                result = ViewingOptions(
                    ref=empty.ref,
                    state="ineligible",
                    rules_version=version,
                    eligibility_version=eligibility_version(config),
                    calculated_at=empty.calculated_at,
                    slots=[],
                )
                # Healthy deny-all/nonmember remains ineligible even without a mapping.
                if exact not in config.eligibility.eligible_refs:
                    return result
                resource_id = _resource(db, item)
                free = _free_slots(db, resource_id, candidates)
                assert len(free) <= MAX_CANDIDATES
                return ViewingOptions(
                    **result.model_dump(exclude={"state", "slots"}),
                    state="available" if free else "no_valid_slots",
                    slots=free,
                )

            return self.reader.store.read(observe)
        except ValueError:
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE") from None
