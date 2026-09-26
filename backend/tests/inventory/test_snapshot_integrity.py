"""Deliberate corruption of disposable stores must never publish a partial candidate."""

import json
from dataclasses import replace

import pytest
from sqlalchemy.orm import Session

from app.database.models import InventorySnapshotPayload, InventoryStorageProfile
from app.database.store import Store
from app.inventory.snapshot_codec import canonical_json, digest_text
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import PreparedStage
from tests.inventory.snapshot_cases import counts, execute, record_evidence

MUTATIONS = {
    "listing-value": (
        "UPDATE listing_versions SET normalized_json='{}' WHERE snapshot_id=:s AND source_id='12'"
    ),
    "listing-original": (
        "UPDATE listing_versions SET original_json='{}' WHERE snapshot_id=:s AND source_id='12'"
    ),
    "evidence-ref": (
        "UPDATE attribute_evidence SET source_id='1' WHERE snapshot_id=:s AND source_id='12'"
    ),
    "evidence-span": (
        "UPDATE attribute_evidence SET raw_locator_json='{}' "
        "WHERE snapshot_id=:s AND source_id='12'"
    ),
    "evidence-value": (
        "UPDATE attribute_evidence SET normalized_json='{}' WHERE snapshot_id=:s AND source_id='12'"
    ),
    "canonical-index": (
        "UPDATE inventory_search_documents SET document_text='invented' "
        "WHERE snapshot_id=:s AND source_id='12'"
    ),
    "canonical-hash": (
        "UPDATE inventory_search_documents SET document_sha256=:wrong "
        "WHERE snapshot_id=:s AND source_id='12'"
    ),
    "fts-text": (
        "UPDATE inventory_search_fts SET document_text='invented' "
        "WHERE snapshot_id=:s AND source_id='12'"
    ),
    "fts-id-set": (
        "UPDATE inventory_search_fts SET source_id='999999' WHERE snapshot_id=:s AND source_id='12'"
    ),
    "fts-version": (
        "UPDATE inventory_search_fts SET index_version=:wrong "
        "WHERE snapshot_id=:s AND source_id='12'"
    ),
    "fts-namespace": (
        "UPDATE inventory_search_fts SET namespace='wrong' WHERE snapshot_id=:s AND source_id='12'"
    ),
    "fts-missing": "DELETE FROM inventory_search_fts WHERE snapshot_id=:s AND source_id='12'",
    "fts-duplicate": (
        "INSERT INTO inventory_search_fts SELECT * FROM inventory_search_fts "
        "WHERE snapshot_id=:s AND source_id='12'"
    ),
    "payload-digest": (
        "UPDATE inventory_snapshot_payloads SET payload_sha256=:wrong WHERE snapshot_id=:s"
    ),
    "policy": (
        "UPDATE inventory_snapshots SET policy_version='tampered-policy' WHERE snapshot_id=:s"
    ),
}


@pytest.mark.parametrize("mutation", tuple(MUTATIONS))
def test_corrupt_staged_candidate_rejects_read_reuse_activation_without_changing_active(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    second_plan: PreparedStage,
    mutation: str,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    active = repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    repo.stage(second_plan)
    before = counts(inventory_store, second_plan.index.snapshot_id)
    execute(
        inventory_store,
        MUTATIONS[mutation],
        {"s": second_plan.index.snapshot_id, "wrong": "f" * 64},
    )
    for action in (
        lambda: repo.snapshot(second_plan.index.snapshot_id),
        lambda: repo.stage(second_plan),
        lambda: repo.activate(second_plan.index.snapshot_id, expected_revision=1),
    ):
        with pytest.raises(ValueError):
            action()
    assert repo.active().observation == active
    # Most corruptions preserve every canonical row count, which is not an integrity proof.
    assert counts(inventory_store, second_plan.index.snapshot_id) == before
    record_evidence(
        "integrity-" + mutation,
        {
            "active_unchanged": active.model_dump(),
            "canonical_counts_unchanged": True,
            "read_reuse_activation_rejected": True,
        },
    )


@pytest.mark.parametrize("mutation", ["unknown-version", "unbound-photo", "inner-index"])
def test_hash_consistent_envelope_corruption_still_fails_admission(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
    mutation: str,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)

    def corrupt(session: Session) -> None:
        row = session.get(InventorySnapshotPayload, snapshot_plan.index.snapshot_id)
        assert row is not None
        data = json.loads(canonical_json(row.payload_json))
        if mutation == "unknown-version":
            data["version"] = "inventory-stage-unsupported"
        elif mutation == "unbound-photo":
            data["candidate"]["listings"][0]["photo"]["url"] = (
                "https://example.invalid/replaced.jpg"
            )
        else:
            data["index"]["version"] = "f" * 64
        row.payload_json = data
        row.payload_sha256 = digest_text(canonical_json(data))

    inventory_store.write(corrupt)
    with pytest.raises(ValueError):
        repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    assert repo.active().stage is None


def test_forged_prepared_index_is_rejected_before_persistence(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    document = replace(snapshot_plan.index.documents[0], text="invented")
    bad = replace(
        snapshot_plan,
        index=replace(
            snapshot_plan.index,
            documents=(document, *snapshot_plan.index.documents[1:]),
        ),
    )
    with pytest.raises(ValueError, match="NOT_REPRODUCIBLE"):
        InventoryRepository(inventory_store).stage(bad)
    assert set(counts(inventory_store, snapshot_plan.index.snapshot_id).values()) == {0}


def test_profile_is_checked_inside_the_unit_after_store_preflight(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)

    def corrupt_and_validate(session: Session) -> None:
        from app.inventory.snapshot_storage import validate_stored

        profile = session.get(InventoryStorageProfile, 1)
        assert profile is not None
        profile.mode = "bounded_lexical"
        session.flush()
        validate_stored(session, snapshot_plan, writable=True)

    with pytest.raises(ValueError, match="PROFILE_MISMATCH"):
        inventory_store.write(corrupt_and_validate)
    assert repo.snapshot(snapshot_plan.index.snapshot_id) == snapshot_plan


def test_incomplete_legacy_snapshot_cannot_be_observed_as_ready(
    inventory_store: Store,
    snapshot_plan: PreparedStage,
) -> None:
    repo = InventoryRepository(inventory_store)
    repo.stage(snapshot_plan)
    repo.activate(snapshot_plan.index.snapshot_id, expected_revision=0)
    execute(
        inventory_store,
        "DELETE FROM inventory_snapshot_payloads WHERE snapshot_id=:s",
        {
            "s": snapshot_plan.index.snapshot_id,
        },
    )
    with pytest.raises(ValueError, match="COMPLETE_STAGE_REQUIRED"):
        repo.active()
