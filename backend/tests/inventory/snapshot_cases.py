"""Explicit synthetic variants and local proof artifacts; no execution on import."""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.models import Base
from app.database.store import Store
from app.inventory.extraction import ExtractedCandidate, extract_reviewed
from app.inventory.import_reader import WorkbookReadResult
from app.inventory.normalization import normalize_candidate
from app.inventory.ooxml_structure import CellStorage
from app.inventory.resource_lineage import ReviewedResourceMapping, lineage_version
from app.inventory.staging_plan import PreparedStage
from tests.platform.persistence_cases import seed_rows, uid
from tests.support.harness import PROJECT

NOW = datetime(2026, 9, 24, 4, tzinfo=UTC)


def variant_candidate(candidate: ExtractedCandidate) -> ExtractedCandidate:
    """In-memory synthetic workbook B: same numeric ID, different make and photo."""
    original = candidate.normalized_source
    fake_hash = "b" * 64
    old_photo = next(
        item.source.cell("photo_url").value
        for item in original.records
        if item.ref.source_id == "12"
    )
    photo = next(
        item.source.cell("photo_url").value
        for item in original.records
        if item.photo.state == "source_present" and item.source.cell("photo_url").value != old_photo
    )
    selected = []
    for item in original.records:
        source = item.source
        if source.source_id == "12":
            source = replace(
                source,
                cells=tuple(
                    replace(
                        cell,
                        value="synthetic different make" if cell.field == "make" else photo,
                        data_type="s",
                        python_type="str",
                        storage=CellStorage("inlineStr", None, None),
                    )
                    if cell.field in {"make", "photo_url"}
                    else cell
                    for cell in source.cells
                ),
            )
        selected.append(source)
    result = WorkbookReadResult(
        replace(original.source_manifest, workbook_sha256=fake_hash),
        replace(
            original.reader_report,
            workbook_sha256_before=fake_hash,
            workbook_sha256_after=fake_hash,
        ),
        tuple(selected),
        original.audit_records,
    )
    catalogue = candidate.catalogue.model_copy(update={"workbook_sha256": fake_hash})
    return extract_reviewed(normalize_candidate(result), catalogue)


def mapping_for(
    plan: PreparedStage,
    *,
    source_id: str = "12",
    predecessor: PreparedStage | None = None,
    resource_label: str = "resource",
) -> ReviewedResourceMapping:
    ref = plan.candidate.manifest.reference(source_id)
    evidence = next(row for row in plan.candidate.evidence if row.ref == ref)
    return ReviewedResourceMapping(
        ref=ref,
        resource_id=uid(resource_label),
        mapping_version="synthetic-reviewed-1",
        decision="reviewed_new_resource" if predecessor is None else "reviewed_same_vehicle",
        reviewed_by="synthetic fixture reviewer",
        reviewed_at=NOW,
        reason="Explicit synthetic identity review; not a claim about the real vehicle corpus.",
        source_evidence_ids=(evidence.evidence_id,),
        predecessor_ref=None
        if predecessor is None
        else predecessor.candidate.manifest.reference(source_id),
    )


def with_mappings(plan: PreparedStage, *mappings: ReviewedResourceMapping) -> PreparedStage:
    ordered = tuple(sorted(mappings, key=lambda item: item.ref.source_id))
    return replace(plan, mappings=ordered, mapping_digest=lineage_version(ordered))


def counts(store: Store, snapshot_id: str) -> dict[str, int]:
    tables = (
        "inventory_snapshots",
        "inventory_snapshot_payloads",
        "listing_versions",
        "attribute_evidence",
        "inventory_search_documents",
        "listing_resource_mappings",
    )
    return store.read(
        lambda session: {
            name: int(
                session.execute(
                    text(f"SELECT count(*) FROM {name} WHERE snapshot_id=:snapshot"),
                    {"snapshot": snapshot_id},
                ).scalar_one()
            )
            for name in tables
        }
    )


def execute(store: Store, statement: str, parameters: dict[str, Any] | None = None) -> None:
    def write(session: Session) -> None:
        session.execute(text(statement), parameters or {})

    store.write(write)


def record_evidence(name: str, value: object) -> None:
    allowed = (PROJECT / "Records/build/BE-05/evidence").resolve()
    root = Path(os.environ.get("INVENTORY_TEST_EVIDENCE_DIR", str(allowed))).resolve()
    if not root.is_relative_to(allowed):
        raise ValueError("INVENTORY_EVIDENCE_OUTSIDE_CANONICAL_ROOT")
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.json").write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def seed_historical_anchors(session: Session, generation: str, plan: PreparedStage) -> None:
    excluded = {
        "inventory_snapshots",
        "listing_versions",
        "active_inventory",
        "attribute_evidence",
        "vehicle_resources",
        "listing_resource_mappings",
    }
    for table, values in seed_rows(generation):
        if table in excluded:
            continue
        data = dict(values)
        if data.get("snapshot_id") == "1" * 64:
            data["snapshot_id"] = plan.index.snapshot_id
        if table == "bookings":
            data["immutable_receipt_json"] = {
                "original_ref": plan.candidate.manifest.reference("12").model_dump(),
                "original_listing": json.loads(
                    next(
                        row.normalized_json
                        for row in plan.candidate.listings
                        if row.ref.source_id == "12"
                    )
                ),
            }
        session.execute(Base.metadata.tables[table].insert().values(**data))


def anchors(store: Store) -> dict[str, list[dict[str, Any]]]:
    tables = ("bookings", "shortlist_memberships", "presentation_items", "booking_reviews")
    return store.read(
        lambda session: {
            table: [dict(row) for row in session.execute(text(f"SELECT * FROM {table}")).mappings()]
            for table in tables
        }
    )
