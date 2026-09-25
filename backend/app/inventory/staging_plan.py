"""Validated immutable inputs prepared before entering a Store write transaction."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from app.database.store import assert_outside_write_transaction
from app.inventory.extraction import ExtractedCandidate
from app.inventory.lexical_index import PreparedIndex, detect_fts5, prepare_index
from app.inventory.references import VERSION_LABEL
from app.inventory.resource_lineage import ReviewedResourceMapping, lineage_version
from app.inventory.snapshot_codec import (
    PreparedCandidate,
    canonical_json,
    decode_candidate,
    prepare_candidate,
)

STAGING_POLICY_VERSION = "inventory-stage-1"


@dataclass(frozen=True)
class PreparedStage:
    candidate: PreparedCandidate = field(repr=False)
    index: PreparedIndex = field(repr=False)
    policy_version: str
    mappings: tuple[ReviewedResourceMapping, ...] = field(repr=False)
    mapping_digest: str


def _mappings(
    candidate: PreparedCandidate, mappings: tuple[ReviewedResourceMapping, ...]
) -> tuple[ReviewedResourceMapping, ...]:
    refs = {listing.ref for listing in candidate.listings}
    evidence_refs = {row.evidence_id: row.ref for row in candidate.evidence}
    verified = tuple(
        ReviewedResourceMapping.model_validate(item.model_dump(mode="json")) for item in mappings
    )
    lineage_version(verified)
    for mapping in verified:
        if mapping.ref not in refs:
            raise ValueError("LINEAGE_LISTING_NOT_IN_CANDIDATE")
        if any(
            evidence_refs.get(evidence_id) != mapping.ref
            for evidence_id in mapping.source_evidence_ids
        ):
            raise ValueError("LINEAGE_EVIDENCE_WRONG_LISTING")
    return tuple(sorted(verified, key=lambda item: item.ref.source_id))


def prepare_stage(
    candidate: ExtractedCandidate,
    *,
    policy_version: str,
    mappings: tuple[ReviewedResourceMapping, ...] = (),
    capability_probe: Callable[[], bool] = detect_fts5,
) -> PreparedStage:
    """Trusted operator preparation; capability injection exists for explicit fault tests."""
    assert_outside_write_transaction()
    if not VERSION_LABEL.fullmatch(policy_version):
        raise ValueError("INVENTORY_POLICY_VERSION_INVALID")
    prepared = prepare_candidate(candidate)
    fts5 = capability_probe()
    if type(fts5) is not bool:
        raise ValueError("INVENTORY_FTS_CAPABILITY_INVALID")
    reviewed_mappings = _mappings(prepared, mappings)
    return PreparedStage(
        prepared,
        prepare_index(prepared, fts5=fts5),
        policy_version,
        reviewed_mappings,
        lineage_version(reviewed_mappings),
    )


def validate_stage(plan: PreparedStage) -> None:
    """Do not trust a hand-constructed dataclass as proof of preparation."""
    assert_outside_write_transaction()
    if not VERSION_LABEL.fullmatch(plan.policy_version):
        raise ValueError("INVENTORY_POLICY_VERSION_INVALID")
    expected = prepare_candidate(decode_candidate(plan.candidate.payload_json))
    mappings = _mappings(expected, plan.mappings)
    if (
        expected != plan.candidate
        or mappings != plan.mappings
        or lineage_version(mappings) != plan.mapping_digest
        or plan.index != prepare_index(expected, fts5=plan.index.mode == "fts5")
    ):
        raise ValueError("INVENTORY_STAGE_NOT_REPRODUCIBLE")


def stage_payload(plan: PreparedStage) -> str:
    """Seal policy, index and reviewed lineage together with the full candidate."""
    return canonical_json(
        {
            "version": STAGING_POLICY_VERSION,
            "candidate": json.loads(plan.candidate.payload_json),
            "policy_version": plan.policy_version,
            "index": {
                "version": plan.index.version,
                "mode": plan.index.mode,
                "policy_version": plan.index.policy_version,
            },
            "mappings": [item.model_dump(mode="json") for item in plan.mappings],
            "mapping_digest": plan.mapping_digest,
        }
    )


def decode_stage(payload: str) -> PreparedStage:
    """Current version decoder; unsupported historical policies fail explicitly."""
    data = json.loads(payload)
    if data["version"] != STAGING_POLICY_VERSION:
        raise ValueError("INVENTORY_STAGE_VERSION_UNSUPPORTED")
    prepared = prepare_candidate(decode_candidate(canonical_json(data["candidate"])))
    mappings = _mappings(
        prepared, tuple(ReviewedResourceMapping.model_validate(item) for item in data["mappings"])
    )
    if data["index"]["mode"] not in {"fts5", "bounded_lexical"}:
        raise ValueError("INVENTORY_INDEX_MODE_INVALID")
    if not VERSION_LABEL.fullmatch(data["policy_version"]):
        raise ValueError("INVENTORY_POLICY_VERSION_INVALID")
    plan = PreparedStage(
        prepared,
        prepare_index(prepared, fts5=data["index"]["mode"] == "fts5"),
        data["policy_version"],
        mappings,
        lineage_version(mappings),
    )
    if stage_payload(plan) != payload:
        raise ValueError("INVENTORY_STAGE_PAYLOAD_INCONSISTENT")
    return plan
