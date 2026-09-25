"""Exact relational projections of sealed stages inside caller-owned Store units."""

from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    AttributeEvidence,
    InventorySnapshot,
    InventorySnapshotPayload,
    InventoryStorageProfile,
    ListingResourceMapping,
    ListingVersion,
    VehicleResource,
)
from app.inventory.index_storage import validate_index
from app.inventory.lexical_index import IndexMode
from app.inventory.resource_lineage import ReviewedResourceMapping
from app.inventory.snapshot_codec import canonical_json, digest_text
from app.inventory.staging_plan import (
    STAGING_POLICY_VERSION,
    PreparedStage,
    decode_stage,
    stage_payload,
)

MAX_LINEAGE_SNAPSHOTS = 64


def check_profile(session: Session, mode: IndexMode) -> None:
    profile = session.get(InventoryStorageProfile, 1)
    if profile is None or profile.mode != mode:
        raise ValueError("INVENTORY_STORAGE_PROFILE_MISMATCH")


def snapshot_values(plan: PreparedStage) -> dict[str, Any]:
    manifest = asdict(plan.candidate.manifest)
    manifest["sheet_name"] = manifest.pop("sheet")
    return {
        **manifest,
        "snapshot_id": plan.candidate.manifest.snapshot_id,
        "import_version": plan.candidate.import_version,
        "index_version": plan.index.version,
        "policy_version": plan.policy_version,
        "accepted_count": len(plan.candidate.listings),
        "rejected_count": 0,
    }


def sealed_payload(session: Session, snapshot_id: str) -> str:
    row = session.get(InventorySnapshotPayload, snapshot_id)
    if row is None or row.serialization_version != STAGING_POLICY_VERSION:
        raise ValueError("INVENTORY_COMPLETE_STAGE_REQUIRED")
    payload = canonical_json(row.payload_json)
    if row.payload_sha256 != digest_text(payload):
        raise ValueError("INVENTORY_STAGE_DIGEST_MISMATCH")
    return payload


def _mapping_key(mapping: ReviewedResourceMapping) -> tuple[str, str, str]:
    return mapping.ref.namespace, mapping.ref.snapshot_id, mapping.ref.source_id


def _verify_predecessor(
    session: Session,
    mapping: ReviewedResourceMapping,
    predecessors: dict[str, PreparedStage],
) -> None:
    predecessor = mapping.predecessor_ref
    if predecessor is None:
        raise ValueError("LINEAGE_PREDECESSOR_REQUIRED")
    row = session.get(
        ListingResourceMapping,
        (predecessor.namespace, predecessor.snapshot_id, predecessor.source_id),
    )
    if row is None or row.resource_id != mapping.resource_id:
        raise ValueError("LINEAGE_PREDECESSOR_RESOURCE_MISMATCH")
    parent = predecessors.get(predecessor.snapshot_id)
    if parent is None:
        raise ValueError("LINEAGE_VALIDATED_PREDECESSOR_REQUIRED")
    reviewed = [item for item in parent.mappings if item.ref == predecessor]
    if (
        len(reviewed) != 1
        or reviewed[0].resource_id != mapping.resource_id
        or row.mapping_version != reviewed[0].mapping_version
        or canonical_json(row.provenance_json)
        != canonical_json(reviewed[0].model_dump(mode="json"))
    ):
        raise ValueError("LINEAGE_PREDECESSOR_NOT_SEALED")


def validate_lineage(
    session: Session,
    plan: PreparedStage,
    predecessors: dict[str, PreparedStage],
) -> None:
    expected = [
        (
            *_mapping_key(item),
            item.resource_id,
            item.mapping_version,
            canonical_json(item.model_dump(mode="json")),
        )
        for item in plan.mappings
    ]
    actual = [
        (
            item.namespace,
            item.snapshot_id,
            item.source_id,
            item.resource_id,
            item.mapping_version,
            canonical_json(item.provenance_json),
        )
        for item in session.scalars(
            select(ListingResourceMapping)
            .where(ListingResourceMapping.snapshot_id == plan.index.snapshot_id)
            .order_by(ListingResourceMapping.source_id)
        )
    ]
    if actual != expected:
        raise ValueError("INVENTORY_LINEAGE_CONTENT_MISMATCH")
    for mapping in plan.mappings:
        resource = session.get(VehicleResource, mapping.resource_id)
        if resource is None:
            raise ValueError("LINEAGE_RESOURCE_MISSING")
        if mapping.decision == "reviewed_new_resource":
            if resource.mapping_version != mapping.mapping_version:
                raise ValueError("LINEAGE_RESOURCE_VERSION_MISMATCH")
        else:
            _verify_predecessor(session, mapping, predecessors)


def insert_lineage(
    session: Session,
    plan: PreparedStage,
    created_at: str,
    dependencies: tuple[PreparedStage, ...],
) -> None:
    predecessors = {item.index.snapshot_id: item for item in dependencies}
    for mapping in plan.mappings:
        resource = session.get(VehicleResource, mapping.resource_id)
        if mapping.decision == "reviewed_new_resource":
            if resource is not None:
                raise ValueError("LINEAGE_NEW_RESOURCE_ALREADY_EXISTS")
            session.add(
                VehicleResource(
                    id=mapping.resource_id,
                    mapping_version=mapping.mapping_version,
                    created_at=created_at,
                )
            )
            session.flush()
        else:
            if resource is None:
                raise ValueError("LINEAGE_RESOURCE_MISSING")
            _verify_predecessor(session, mapping, predecessors)
        session.add(
            ListingResourceMapping(
                **mapping.ref.model_dump(),
                resource_id=mapping.resource_id,
                mapping_version=mapping.mapping_version,
                provenance_json=mapping.model_dump(mode="json"),
            )
        )
    session.flush()


def _validate_one(
    session: Session,
    plan: PreparedStage,
    predecessors: dict[str, PreparedStage],
    *,
    writable: bool,
) -> None:
    """Exact sets and values, not counts alone. Never creates or repairs content."""
    check_profile(session, plan.index.mode)
    snapshot = session.get(InventorySnapshot, plan.index.snapshot_id)
    if snapshot is None or any(
        getattr(snapshot, key) != value for key, value in snapshot_values(plan).items()
    ):
        raise ValueError("INVENTORY_SNAPSHOT_METADATA_MISMATCH")
    if sealed_payload(session, plan.index.snapshot_id) != stage_payload(plan):
        raise ValueError("INVENTORY_IMMUTABLE_STAGE_MISMATCH")
    listings = [
        (
            item.namespace,
            item.snapshot_id,
            item.source_id,
            item.source_row,
            canonical_json(item.original_json),
            canonical_json(item.normalized_json),
        )
        for item in session.scalars(
            select(ListingVersion)
            .where(ListingVersion.snapshot_id == plan.index.snapshot_id)
            .order_by(ListingVersion.source_id)
        )
    ]
    expected_listings = [
        (
            item.ref.namespace,
            item.ref.snapshot_id,
            item.ref.source_id,
            item.source_row,
            item.original_json,
            item.normalized_json,
        )
        for item in plan.candidate.listings
    ]
    if listings != expected_listings:
        raise ValueError("INVENTORY_LISTING_CONTENT_MISMATCH")
    evidence = [
        (
            item.id,
            item.namespace,
            item.snapshot_id,
            item.source_id,
            item.attribute,
            canonical_json(item.raw_locator_json),
            canonical_json(item.normalized_json),
            item.status,
            item.extraction_version,
        )
        for item in session.scalars(
            select(AttributeEvidence)
            .where(AttributeEvidence.snapshot_id == plan.index.snapshot_id)
            .order_by(AttributeEvidence.id)
        )
    ]
    expected_evidence = sorted(
        (
            item.evidence_id,
            item.ref.namespace,
            item.ref.snapshot_id,
            item.ref.source_id,
            item.attribute,
            item.raw_locator_json,
            item.normalized_json,
            item.status,
            item.extraction_version,
        )
        for item in plan.candidate.evidence
    )
    if evidence != expected_evidence:
        raise ValueError("INVENTORY_EVIDENCE_CONTENT_MISMATCH")
    validate_lineage(session, plan, predecessors)
    validate_index(session, plan.index, writable=writable)


def validate_stored(
    session: Session,
    plan: PreparedStage,
    *,
    writable: bool,
    dependencies: tuple[PreparedStage, ...] = (),
) -> None:
    """Recheck every prepared ancestor in the same transaction as the target."""
    predecessors: dict[str, PreparedStage] = {}
    for parent in dependencies:
        _validate_one(session, parent, predecessors, writable=False)
        predecessors[parent.index.snapshot_id] = parent
    _validate_one(session, plan, predecessors, writable=writable)


def load_dependencies(
    session: Session,
    plan: PreparedStage,
    mode: IndexMode,
) -> tuple[PreparedStage, ...]:
    """Read-unit preparation, bounded and cycle checked; no decoding under a write lock."""
    visiting = {plan.index.snapshot_id}
    completed: dict[str, PreparedStage] = {}

    def visit(child: PreparedStage) -> None:
        for mapping in child.mappings:
            ref = mapping.predecessor_ref
            if ref is None:
                continue
            if ref.snapshot_id in visiting:
                raise ValueError("LINEAGE_CYCLE_REJECTED")
            if ref.snapshot_id in completed:
                continue
            if len(visiting) + len(completed) >= MAX_LINEAGE_SNAPSHOTS:
                raise ValueError("LINEAGE_SNAPSHOT_LIMIT")
            parent = decode_stage(sealed_payload(session, ref.snapshot_id))
            if parent.index.mode != mode or parent.index.snapshot_id != ref.snapshot_id:
                raise ValueError("INVENTORY_STAGE_IDENTITY_MISMATCH")
            visiting.add(ref.snapshot_id)
            visit(parent)
            visiting.remove(ref.snapshot_id)
            _validate_one(session, parent, completed, writable=False)
            completed[ref.snapshot_id] = parent

    visit(plan)
    return tuple(completed.values())


def load_stage_set(
    session: Session,
    snapshot_id: str,
    mode: IndexMode,
) -> tuple[PreparedStage, tuple[PreparedStage, ...]] | None:
    """Use only in a read unit: decoding/preparation must stay outside write locks."""
    check_profile(session, mode)
    if session.get(InventorySnapshot, snapshot_id) is None:
        return None
    plan = decode_stage(sealed_payload(session, snapshot_id))
    if plan.index.mode != mode or plan.index.snapshot_id != snapshot_id:
        raise ValueError("INVENTORY_STAGE_IDENTITY_MISMATCH")
    dependencies = load_dependencies(session, plan, mode)
    _validate_one(
        session,
        plan,
        {item.index.snapshot_id: item for item in dependencies},
        writable=False,
    )
    return plan, dependencies


def load_stage(session: Session, snapshot_id: str, mode: IndexMode) -> PreparedStage | None:
    loaded = load_stage_set(session, snapshot_id, mode)
    return None if loaded is None else loaded[0]
