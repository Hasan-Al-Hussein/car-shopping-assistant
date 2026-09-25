"""Bounded immutable P12A configuration; no authoring, activation or default permission."""

import hashlib
import json
from typing import Literal, Self

from pydantic import model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas.common import Digest, ShortText
from app.core.config import VIEWING_VENUE, DemoPolicy, FrozenSettings
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.sessions.state import canonical
from app.viewings.eligibility import ELIGIBILITY_RULES_VERSION, EligibilityPolicy
from app.viewings.scheduling import ViewingRules

MAX_CONFIGURATION_BYTES = 65_536


class ViewingConfiguration(FrozenSettings):
    format: Literal["viewing-configuration-1"]
    calendar_version: ShortText
    policy: DemoPolicy
    venue_label: Literal["Simulated local viewing — no real venue or reservation."]
    eligibility: EligibilityPolicy
    inventory: InventoryObservation
    mapping_digest: Digest

    @model_validator(mode="after")
    def coherent_permission(self) -> Self:
        if self.inventory.snapshot_id is None:
            raise ValueError("ACTIVE_CONFIGURATION_REQUIRED")
        refs = self.eligibility.eligible_refs
        keys = [(ref.namespace, ref.snapshot_id, ref.source_id) for ref in refs]
        if keys != sorted(keys) or any(
            ref.snapshot_id != self.inventory.snapshot_id for ref in refs
        ):
            raise ValueError("CONFIGURATION_REFERENCE_BINDING")
        return self


def configuration_id(value: ViewingConfiguration) -> str:
    return (
        "viewing-config-1:" + hashlib.sha256(canonical(value.model_dump(mode="json"))).hexdigest()
    )


def eligibility_version(value: ViewingConfiguration) -> str:
    material = dict(
        algorithm=ELIGIBILITY_RULES_VERSION,
        policy_version=value.eligibility.version,
        eligible_refs=[ref.model_dump(mode="json") for ref in value.eligibility.eligible_refs],
        inventory=value.inventory.model_dump(mode="json"),
        mapping_digest=value.mapping_digest,
    )
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{ELIGIBILITY_RULES_VERSION}:{value.eligibility.version}:{digest}"


def _distinct(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_CONFIGURATION_KEY")
        result[key] = value
    return result


def parse_configuration(
    raw: str,
    *,
    rules: ViewingRules,
    observation: InventoryObservation,
    namespace: str,
) -> ViewingConfiguration:
    try:
        if not 1 <= len(raw.encode("utf-8")) <= MAX_CONFIGURATION_BYTES:
            raise ValueError("CONFIGURATION_SIZE")
        material = canonical(json.loads(raw, object_pairs_hook=_distinct))
        value = ViewingConfiguration.model_validate_json(material)
        if (
            material != canonical(value.model_dump(mode="json"))
            or len(material) > MAX_CONFIGURATION_BYTES
            or canonical(value.policy.model_dump(mode="json"))
            != canonical(rules.policy.model_dump(mode="json"))
            or value.calendar_version != rules.version
            or value.venue_label != VIEWING_VENUE
            or value.inventory != observation
            or any(ref.namespace != namespace for ref in value.eligibility.eligible_refs)
        ):
            raise ValueError("CONFIGURATION_BINDING")
        return value
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise ApiFailure("RULES_UNAVAILABLE") from None


def load_configuration(
    db: Session,
    version: str,
    *,
    rules: ViewingRules,
    observation: InventoryObservation,
    namespace: str,
) -> ViewingConfiguration:
    # This fixed raw projection avoids SQLAlchemy JSON decoding before the size gate.
    row = (
        db.execute(
            text("""
        SELECT policy_version, eligibility_version,
               typeof(rules_json) AS kind,
               length(CAST(rules_json AS BLOB)) AS byte_count,
               CASE WHEN typeof(rules_json) = 'text'
                    AND length(CAST(rules_json AS BLOB)) BETWEEN 1 AND 65536
                    THEN CAST(rules_json AS TEXT) ELSE NULL END AS material
        FROM rule_versions WHERE version = :version
    """),
            {"version": version},
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["kind"] != "text" or type(row["material"]) is not str:
        raise ApiFailure("RULES_UNAVAILABLE")
    value = parse_configuration(
        row["material"], rules=rules, observation=observation, namespace=namespace
    )
    if (
        version != configuration_id(value)
        or row["policy_version"] != value.policy.version
        or row["eligibility_version"] != eligibility_version(value)
    ):
        raise ApiFailure("RULES_UNAVAILABLE")
    return value
