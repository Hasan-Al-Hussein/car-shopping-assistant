"""Synthetic materialized BE05 observations, not proof of a validated stored stage."""

from datetime import UTC, datetime

from app.core.readiness import InventoryObservation
from app.inventory.lexical_index import PreparedIndex
from app.inventory.references import ImmutableInventoryRef, SnapshotManifest
from app.inventory.resource_lineage import ReviewedResourceMapping, lineage_version
from app.inventory.snapshot_codec import ListingRow, PreparedCandidate
from app.inventory.snapshots import ActiveSnapshot
from app.inventory.staging_plan import PreparedStage
from app.viewings.eligibility import EligibilityPolicy

GENERATION = "30000000-0000-4000-8000-000000000001"
RESOURCE = "50000000-0000-4000-8000-000000000001"
EVIDENCE = "80000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 9, 21, 3, 30, tzinfo=UTC)  # Monday, Dubai 07:30.


def active_fixture(
    *, seed: str = "a", mapped: bool = True, predecessor: ImmutableInventoryRef | None = None
) -> tuple[ActiveSnapshot, ImmutableInventoryRef, EligibilityPolicy]:
    manifest = SnapshotManifest("synthetic-cars", seed * 64, "synthetic-only")
    ref = manifest.reference("00707")
    mapping = ReviewedResourceMapping(
        ref=ref,
        resource_id=RESOURCE,
        mapping_version="synthetic-lineage-1",
        decision="reviewed_new_resource" if predecessor is None else "reviewed_same_vehicle",
        reviewed_by="synthetic-test-reviewer",
        reviewed_at=NOW,
        reason="Synthetic identity fixture only; no seller or store validation claim.",
        source_evidence_ids=(EVIDENCE,),
        predecessor_ref=predecessor,
    )
    mappings = (mapping,) if mapped else ()
    # Deliberately not a real stored envelope. A fake trusted source tests BE13 only.
    candidate = PreparedCandidate(
        manifest,
        "{}",
        "c" * 64,
        "synthetic-reader-1",
        0,
        (ListingRow(ref, 2, "{}", '{"seller_text":"test drives welcome"}'),),
        (),
    )
    index = PreparedIndex(
        manifest.snapshot_id, "d" * 64, "bounded_lexical", "synthetic-index-1", ()
    )
    stage = PreparedStage(
        candidate, index, "synthetic-stage-1", mappings, lineage_version(mappings)
    )
    observation = InventoryObservation(
        generation=GENERATION,
        active_revision=1,
        snapshot_id=manifest.snapshot_id,
        index_version=index.version,
        mode=index.mode,
    )
    return (
        ActiveSnapshot(observation, stage),
        ref,
        EligibilityPolicy(version="synthetic-permission-1", eligible_refs=(ref,)),
    )


class FakeInventory:
    """One-read counter; no repository/store or capacity behavior is emulated."""

    def __init__(self, active: ActiveSnapshot) -> None:
        self.snapshot = active
        self.calls = 0

    def active(self) -> ActiveSnapshot:
        self.calls += 1
        return self.snapshot
