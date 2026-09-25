"""Private, expiring viewing admission over the actual compact reader.

Construction never admits inventory or activates rules. Persisted review handles
are usable only while their original private entry survives in this process.
Rechecking does not consume or renew that entry, and confers no owner authority.
"""

import math
import os
import re
import secrets
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, fields
from threading import RLock
from time import monotonic

from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.database.store import assert_outside_write_transaction
from app.inventory.compact_reader import CompactInventoryReader
from app.inventory.references import ImmutableInventoryRef
from app.inventory.staging_plan import STAGING_POLICY_VERSION
from app.viewings.draft_admission import PreparedViewing
from app.viewings.draft_configuration import (
    ViewingConfiguration,
    eligibility_version,
    load_configuration,
)
from app.viewings.scheduling import ViewingRules
from sqlalchemy.orm import Session

ADMISSION_VERSION = "viewing-admission-1"
MAX_ADMISSIONS = 256
MAX_LIFETIME_SECONDS = 300
MAX_REVISION = 2_147_483_647


@dataclass(frozen=True, slots=True)
class _Authority:
    prepared: PreparedViewing
    observation: InventoryObservation
    resource_version: str
    expires_at: float
    compact_identity: tuple[str, ...] = field(repr=False)


def _same_material(expected: PreparedViewing, actual: PreparedViewing) -> bool:
    # Dataclass equality alone permits True == 1 in a forged revision field.
    return type(actual) is PreparedViewing and all(
        type(getattr(actual, item.name)) is type(getattr(expected, item.name))
        and getattr(actual, item.name) == getattr(expected, item.name)
        for item in fields(PreparedViewing)
    )


def _observation(db: Session, expected: InventoryObservation, ref: ImmutableInventoryRef) -> None:
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT m.store_generation,a.snapshot_id,a.index_version,a.revision,p.mode,"
            "s.namespace,s.index_version FROM store_metadata m "
            "LEFT JOIN active_inventory a ON a.id=1 "
            "LEFT JOIN inventory_storage_profile p ON p.id=1 "
            "LEFT JOIN inventory_snapshots s ON s.snapshot_id=a.snapshot_id WHERE m.id=1"
        )
        .first()
    )
    if row is None or row[0] != expected.generation:
        raise ApiFailure("STORE_GENERATION_CHANGED")
    if type(row[3]) is not int or tuple(row[1:]) != (
        expected.snapshot_id,
        expected.index_version,
        expected.active_revision,
        expected.mode,
        ref.namespace,
        expected.index_version,
    ):
        raise ApiFailure("SNAPSHOT_STALE")


def _configuration(
    db: Session,
    observation: InventoryObservation,
    ref: ImmutableInventoryRef,
    rules: ViewingRules,
) -> tuple[str, int, ViewingConfiguration]:
    rows = (
        db.connection()
        .exec_driver_sql(
            "SELECT id,CASE WHEN typeof(version)='text' "
            "AND length(CAST(version AS BLOB)) BETWEEN 1 AND 200 THEN version END,revision "
            "FROM active_rules ORDER BY id LIMIT 2"
        )
        .all()
    )
    if (
        len(rows) != 1
        or rows[0][0] != 1
        or type(rows[0][1]) is not str
        or type(rows[0][2]) is not int
        or not 0 <= rows[0][2] <= MAX_REVISION
    ):
        raise ApiFailure("RULES_UNAVAILABLE")
    version: str = rows[0][1]
    revision: int = rows[0][2]
    config = load_configuration(
        db, version, rules=rules, observation=observation, namespace=ref.namespace
    )
    return version, revision, config


def _stage_mapping_digest(db: Session, ref: ImmutableInventoryRef) -> str:
    # The preceding actual I5 token check authenticates this same transaction's
    # full persisted stage. Only this scalar crosses the SQL/application boundary.
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT serialization_version,"
            "CASE WHEN json_valid(payload_json) THEN "
            "CASE WHEN json_type(payload_json,'$.mapping_digest')='text' "
            "AND length(json_extract(payload_json,'$.mapping_digest'))=64 "
            "THEN json_extract(payload_json,'$.mapping_digest') END END "
            "FROM inventory_snapshot_payloads WHERE snapshot_id=?",
            (ref.snapshot_id,),
        )
        .first()
    )
    digest = None if row is None else row[1]
    if (
        row is None
        or row[0] != STAGING_POLICY_VERSION
        or type(digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
    return digest


def _mapping(db: Session, prepared: PreparedViewing, resource_version: str) -> None:
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT m.resource_id,m.mapping_version,r.mapping_version "
            "FROM listing_resource_mappings m "
            "LEFT JOIN vehicle_resources r ON r.id=m.resource_id "
            "WHERE m.namespace=? AND m.snapshot_id=? AND m.source_id=?",
            (prepared.ref.namespace, prepared.ref.snapshot_id, prepared.ref.source_id),
        )
        .first()
    )
    if row is None or tuple(row) != (
        prepared.resource_id,
        prepared.mapping_version,
        resource_version,
    ):
        raise ApiFailure("ELIGIBILITY_UNAVAILABLE")


class CompactViewingInventory:
    """DraftInventory implementation shared by reads, drafts and confirmation.

    TTL starts before preparation and is never renewed. It may therefore expire
    before a review's displayed five-minute expiry. Eviction likewise requires
    explicit re-review, never automatic renewal of old or submitted intent.
    """

    def __init__(
        self,
        reader: CompactInventoryReader,
        *,
        rules: ViewingRules,
        lifetime_seconds: float = MAX_LIFETIME_SECONDS,
        capacity: int = MAX_ADMISSIONS,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        if (
            type(capacity) is not int
            or not 1 <= capacity <= MAX_ADMISSIONS
            or type(lifetime_seconds) not in (int, float)
            or not math.isfinite(lifetime_seconds)
            or not 1 <= lifetime_seconds <= MAX_LIFETIME_SECONDS
        ):
            raise ValueError("VIEWING_ADMISSION_BOUNDS_INVALID")
        self.reader, self.rules = reader, rules
        self._lifetime = float(lifetime_seconds)
        self._capacity = capacity
        self._clock = monotonic_clock
        self._pid = os.getpid()
        self._lock = RLock()
        self._entries: OrderedDict[tuple[str, ...], _Authority] = OrderedDict()
        self._epoch = 0
        self._closed = False
        self._last_clock = -math.inf

    def _process(self) -> None:
        # Never acquire an inherited lock after process replacement/fork.
        if os.getpid() != self._pid:
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE")

    def _now_locked(self) -> float:
        now = self._clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < self._last_clock:
            self._entries.clear()
            self._epoch += 1
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
        self._last_clock = float(now)
        for key in tuple(self._entries):
            if self._entries[key].expires_at <= now:
                del self._entries[key]
        if self._closed:
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
        return float(now)

    def invalidate(self) -> None:
        """Revoke all handles without changing the shared reader or its facts."""
        self._process()
        with self._lock:
            self._entries.clear()
            self._epoch += 1

    def close(self) -> None:
        """Terminal shutdown; this adapter cannot issue authority again."""
        self._process()
        with self._lock:
            self._entries.clear()
            self._epoch += 1
            self._closed = True

    def release(self, prepared: PreparedViewing) -> None:
        """Optional trusted cleanup; expiry/eviction also reclaim orphaned entries."""
        self._process()
        with self._lock:
            if (
                type(prepared) is PreparedViewing
                and type(prepared.identity) is tuple
                and all(type(part) is str for part in prepared.identity)
            ):
                entry = self._entries.get(prepared.identity)
                if entry is not None and _same_material(entry.prepared, prepared):
                    del self._entries[prepared.identity]

    def _authority(self, prepared: PreparedViewing) -> _Authority:
        self._process()
        if (
            type(prepared) is not PreparedViewing
            or type(prepared.identity) is not tuple
            or len(prepared.identity) != 2
            or any(type(part) is not str for part in prepared.identity)
            or prepared.identity[0] != ADMISSION_VERSION
            or re.fullmatch(r"[0-9a-f]{64}", prepared.identity[1]) is None
        ):
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
        with self._lock:
            self._now_locked()
            entry = self._entries.get(prepared.identity)
            if entry is None or not _same_material(entry.prepared, prepared):
                raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
            self._entries.move_to_end(prepared.identity)
            return entry

    def prepare(self, ref: ImmutableInventoryRef) -> PreparedViewing:
        assert_outside_write_transaction()
        self._process()
        with self._lock:
            expires_at = self._now_locked() + self._lifetime
            epoch = self._epoch
        try:
            if type(ref) is not ImmutableInventoryRef:
                raise ValueError("VIEWING_REFERENCE_INVALID")
            exact = ImmutableInventoryRef.model_validate(ref.model_dump())
            batch = self.reader.read_refs((exact,), expected_snapshot_id=exact.snapshot_id)
            if len(batch.items) != 1:
                raise ValueError("VIEWING_REFERENCE_INVALID")
            item = batch.items[0]
            if item.ref != exact or item.state != "current" or item.listing is None:
                raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
            handle = (ADMISSION_VERSION, secrets.token_hex(32))

            def capture(db: Session) -> _Authority:
                self.reader.recheck_identity(db, batch.identity, expected_refs=(exact,))
                _observation(db, batch.observation, exact)
                version, revision, config = _configuration(db, batch.observation, exact, self.rules)
                if _stage_mapping_digest(db, exact) != config.mapping_digest:
                    raise ApiFailure("RULES_UNAVAILABLE")
                # A healthy configured nonmember is denied before a missing mapping
                # is considered. The current wire vocabulary uses the same closed code.
                if exact not in config.eligibility.eligible_refs:
                    raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
                mapping = item.mapping
                if mapping is None or type(item.resource_version) is not str:
                    raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
                if batch.observation.index_version is None:
                    raise ApiFailure("SNAPSHOT_STALE")
                prepared = PreparedViewing(
                    batch.observation.generation,
                    exact,
                    batch.observation.active_revision,
                    batch.observation.index_version,
                    mapping.resource_id,
                    mapping.mapping_version,
                    eligibility_version(config),
                    version,
                    revision,
                    handle,
                )
                _mapping(db, prepared, item.resource_version)
                return _Authority(
                    prepared,
                    batch.observation,
                    item.resource_version,
                    expires_at,
                    batch.identity,
                )

            authority = self.reader.store.read(capture)
            self._process()
            with self._lock:
                now = self._now_locked()
                if epoch != self._epoch or now >= expires_at:
                    raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
                while len(self._entries) >= self._capacity:
                    self._entries.popitem(last=False)
                self._entries[handle] = authority
            return authority.prepared
        except ValueError:
            # prepare's consumer wrapper does not translate ValueError itself.
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE") from None

    def recheck(self, db: Session, prepared: PreparedViewing) -> None:
        entry = self._authority(prepared)
        try:
            self.reader.recheck_identity(
                db, entry.compact_identity, expected_refs=(entry.prepared.ref,)
            )
            _observation(db, entry.observation, prepared.ref)
            version, revision, config = _configuration(
                db, entry.observation, prepared.ref, self.rules
            )
            if (
                (version, revision)
                != (prepared.configuration_version, prepared.configuration_revision)
                or eligibility_version(config) != prepared.eligibility_version
                or prepared.ref not in config.eligibility.eligible_refs
            ):
                raise ApiFailure("RULES_UNAVAILABLE")
            _mapping(db, prepared, entry.resource_version)
            # Invalidation/eviction/expiry while SQL ran cannot republish authority.
            if self._authority(prepared) is not entry:
                raise ApiFailure("ELIGIBILITY_UNAVAILABLE")
        except ValueError:
            self.release(prepared)
            raise ApiFailure("ELIGIBILITY_UNAVAILABLE") from None
        except BaseException:
            self.release(prepared)
            raise
