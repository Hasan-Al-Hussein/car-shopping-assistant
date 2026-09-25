"""Exact current references, explicit demo permission and reviewed resource identity.

The repository is the trusted read boundary. Its materialized active() result is
coherent; do not replace it with separate listing/current/mapping reads or call it
inside a later booking write transaction. These observations cannot authorize a commit.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.schemas.common import InventoryRef
from app.core.readiness import InventoryObservation
from app.inventory.references import ImmutableInventoryRef
from app.inventory.resource_lineage import lineage_version
from app.inventory.snapshots import ActiveSnapshot

ELIGIBILITY_RULES_VERSION = "viewing-eligibility-1"


class EligibilityPolicy(BaseModel):
    """Trusted operator configuration, never inferred or accepted from a buyer body."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    version: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
    eligible_refs: Annotated[tuple[ImmutableInventoryRef, ...], Field(max_length=100)]

    @model_validator(mode="after")
    def unique_references(self) -> Self:
        if len(set(self.eligible_refs)) != len(self.eligible_refs):
            raise ValueError("DUPLICATE_ELIGIBILITY_REFERENCE")
        return self


class ActiveInventoryReader(Protocol):
    """InventoryRepository conforms directly; fake sources prove pure rules only."""

    def active(self) -> ActiveSnapshot: ...


class EligibilityIntegrityError(ValueError):
    """Unavailable dependency integrity, never a missing/ineligible business result."""


@dataclass(frozen=True)
class EligibilityResult:
    ref: ImmutableInventoryRef
    state: Literal["eligible", "unconfigured", "stale", "missing", "ineligible", "unavailable"]
    reason: Literal[
        "ELIGIBLE_SIMULATED",
        "ELIGIBILITY_NOT_CONFIGURED",
        "INVENTORY_NOT_CONFIGURED",
        "REFERENCE_NOT_CURRENT",
        "REFERENCE_MISSING",
        "NOT_IN_DEMO_ALLOWLIST",
        "REVIEWED_RESOURCE_MISSING",
    ]
    eligibility_version: str | None
    observation: InventoryObservation
    resource_id: str | None = None
    mapping_version: str | None = None
    mapping_digest: str | None = None


def observe_eligibility(
    reader: ActiveInventoryReader,
    ref: InventoryRef,
    policy: EligibilityPolicy | None,
) -> EligibilityResult:
    """One authoritative read; store/busy/generation/integrity failures propagate."""
    exact_ref = ImmutableInventoryRef.model_validate(ref.model_dump(mode="python"))
    return resolve_eligibility(reader.active(), exact_ref, policy)


def resolve_eligibility(
    active: ActiveSnapshot,
    ref: InventoryRef,
    policy: EligibilityPolicy | None,
) -> EligibilityResult:
    """Pure rules over an already validated repository observation, not a stage validator."""
    exact_ref = ImmutableInventoryRef.model_validate(ref.model_dump(mode="python"))
    observation = InventoryObservation.model_validate(active.observation.model_dump(mode="python"))
    stage = active.stage
    if (stage is None) != (observation.snapshot_id is None):
        raise EligibilityIntegrityError("INVENTORY_OBSERVATION_INCOHERENT")
    if stage is None:
        return EligibilityResult(
            exact_ref, "unconfigured", "INVENTORY_NOT_CONFIGURED", None, observation
        )
    if (
        stage.candidate.manifest.snapshot_id != observation.snapshot_id
        or stage.index.snapshot_id != observation.snapshot_id
        or stage.index.version != observation.index_version
        or stage.index.mode != observation.mode
        or lineage_version(stage.mappings) != stage.mapping_digest
    ):
        raise EligibilityIntegrityError("INVENTORY_OBSERVATION_INCOHERENT")
    if policy is None:
        return EligibilityResult(
            exact_ref, "unconfigured", "ELIGIBILITY_NOT_CONFIGURED", None, observation
        )
    # Revalidate model_copy/model_construct bypasses; retain a private immutable copy.
    configured = EligibilityPolicy.model_validate(policy.model_dump(mode="python"))
    material = {
        "algorithm": ELIGIBILITY_RULES_VERSION,
        "policy_version": configured.version,
        "eligible_refs": [
            item.model_dump(mode="json")
            for item in sorted(
                configured.eligible_refs,
                key=lambda item: (item.namespace, item.snapshot_id, item.source_id),
            )
        ],
        "inventory": observation.model_dump(mode="json"),
        "mapping_digest": stage.mapping_digest,
    }
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    version = f"{ELIGIBILITY_RULES_VERSION}:{configured.version}:{digest}"
    if exact_ref.snapshot_id != observation.snapshot_id:
        return EligibilityResult(exact_ref, "stale", "REFERENCE_NOT_CURRENT", version, observation)
    listings = [listing for listing in stage.candidate.listings if listing.ref == exact_ref]
    if not listings:
        return EligibilityResult(exact_ref, "missing", "REFERENCE_MISSING", version, observation)
    if len(listings) != 1:
        raise EligibilityIntegrityError("DUPLICATE_CURRENT_REFERENCE")
    if exact_ref not in configured.eligible_refs:
        return EligibilityResult(
            exact_ref, "ineligible", "NOT_IN_DEMO_ALLOWLIST", version, observation
        )
    mappings = [mapping for mapping in stage.mappings if mapping.ref == exact_ref]
    if not mappings:
        return EligibilityResult(
            exact_ref, "unavailable", "REVIEWED_RESOURCE_MISSING", version, observation
        )
    if len(mappings) != 1:
        raise EligibilityIntegrityError("MULTIPLE_CURRENT_RESOURCE_MAPPINGS")
    mapping = mappings[0]
    return EligibilityResult(
        exact_ref,
        "eligible",
        "ELIGIBLE_SIMULATED",
        version,
        observation,
        mapping.resource_id,
        mapping.mapping_version,
        stage.mapping_digest,
    )
