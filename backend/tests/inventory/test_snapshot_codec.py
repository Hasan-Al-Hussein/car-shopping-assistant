"""BE05 preparation proof; these tests perform no store initialization."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pytest
from pydantic import ValidationError

from app.inventory.extraction import ExtractedCandidate
from app.inventory.lexical_index import prepare_index
from app.inventory.resource_lineage import ReviewedResourceMapping, lineage_version
from app.inventory.snapshot_codec import (
    PreparedCandidate,
    canonical_json,
    decode_candidate,
    digest_text,
    prepare_candidate,
)
from app.inventory.staging_plan import prepare_stage, validate_stage

ACCEPTED_SNAPSHOT = "5fe31b5951317db6d77b6786596861e32ccd2442f2f5f98927d57e6b4a2092f3"


def test_full_accepted_candidate_round_trip(
    snapshot_candidate: ExtractedCandidate, prepared_snapshot: PreparedCandidate
) -> None:
    restored = decode_candidate(prepared_snapshot.payload_json)
    assert restored == snapshot_candidate
    assert prepared_snapshot.manifest.snapshot_id == ACCEPTED_SNAPSHOT
    assert prepared_snapshot.payload_sha256 == digest_text(prepared_snapshot.payload_json)
    assert len(prepared_snapshot.listings) == prepared_snapshot.audit_count == 100
    assert len(prepared_snapshot.evidence) == 1079
    assert len({row.evidence_id for row in prepared_snapshot.evidence}) == 1079
    assert restored.evidence_ledger() == snapshot_candidate.evidence_ledger()
    assert restored.coverage_report() == snapshot_candidate.coverage_report()
    for left, right in zip(snapshot_candidate.records, restored.records, strict=True):
        assert left.normalized.photo == right.normalized.photo
        assert left.normalized.source == right.normalized.source
        for fact in left.resolutions[:12]:
            assert fact.public_fact() == right.fact(fact.family).public_fact()


@pytest.mark.parametrize(
    "mutation",
    ("manifest", "annotation", "span", "photo", "resolution", "missing_row", "audit", "extra"),
)
def test_round_trip_rejects_changed_materialized_meaning(
    prepared_snapshot: PreparedCandidate, mutation: str
) -> None:
    data = json.loads(prepared_snapshot.payload_json)
    listing = data["listings"][0]
    if mutation == "manifest":
        data["manifest"]["extraction_version"] = "forged"
    elif mutation == "annotation":
        listing["claims"][0]["annotation"]["value"]["value"] = "invented"
    elif mutation == "span":
        listing["claims"][0]["evidence"][0]["span_start"] += 1
    elif mutation == "photo":
        listing["photo"]["url"] = data["listings"][1]["photo"]["url"]
    elif mutation == "resolution":
        listing["resolutions"][0]["groups"][0]["value"]["value"] = "invented"
    elif mutation == "missing_row":
        data["listings"].pop()
    elif mutation == "audit":
        data["source"]["audit_records"].pop()
    else:
        data["unused_but_not_allowed"] = True
    with pytest.raises(ValueError):
        decode_candidate(canonical_json(data))


def test_exact_float_type_and_ooxml_tokens_survive(prepared_snapshot: PreparedCandidate) -> None:
    data = json.loads(prepared_snapshot.payload_json)
    selected = {row["source_id"]: row for row in data["source"]["selected_records"]}
    model = next(cell for cell in selected["12"]["cells"] if cell["field"] == "model")
    assert model["value"] == {"type": "float", "value": float(3).hex()}
    assert model["storage"]["value"] == "3.0"
    restored = decode_candidate(prepared_snapshot.payload_json)
    row = next(item for item in restored.records if item.review.source_id == "12")
    assert type(row.normalized.source.cell("model").value) is float
    assert row.fact("model").groups[0].value.value == "3"


def test_duplicate_json_keys_and_noncanonical_bytes_are_rejected(
    prepared_snapshot: PreparedCandidate,
) -> None:
    with pytest.raises(ValueError, match="DUPLICATE_JSON_KEY"):
        decode_candidate('{"serialization_version":"x","serialization_version":"y"}')
    with pytest.raises(ValueError, match="NOT_CANONICAL"):
        decode_candidate(prepared_snapshot.payload_json + "\n")


def test_forged_live_candidate_is_rejected(snapshot_candidate: ExtractedCandidate) -> None:
    first = snapshot_candidate.records[0]
    bad_source = replace(first.normalized.identity_provenance, row=900)
    bad_listing = replace(
        first, normalized=replace(first.normalized, identity_provenance=bad_source)
    )
    changed = replace(snapshot_candidate, records=(bad_listing, *snapshot_candidate.records[1:]))
    with pytest.raises(ValueError):
        prepare_candidate(changed)


def test_lexical_identity_is_bound_to_mode_policy_snapshot_and_content(
    prepared_snapshot: PreparedCandidate,
) -> None:
    fts = prepare_index(prepared_snapshot, fts5=True)
    fallback = prepare_index(prepared_snapshot, fts5=False)
    assert fts.version != fallback.version
    assert fts.documents == fallback.documents
    assert fts == prepare_index(prepared_snapshot, fts5=True)
    assert len(fts.documents) == 100
    assert {item.ref for item in fts.documents} == {item.ref for item in prepared_snapshot.listings}
    assert all(item.sha256 == digest_text(item.text) for item in fts.documents)
    assert any(
        any("\u0600" <= character <= "\u06ff" for character in item.text) for item in fts.documents
    )
    assert any("\n3\n" in "\n" + item.text + "\n" for item in fts.documents)


def _mapping(prepared: PreparedCandidate) -> ReviewedResourceMapping:
    listing = prepared.listings[0]
    evidence = next(row for row in prepared.evidence if row.ref == listing.ref)
    return ReviewedResourceMapping(
        ref=listing.ref,
        resource_id=str(uuid5(NAMESPACE_URL, "synthetic-be05-resource")),
        mapping_version="synthetic-reviewed-1",
        decision="reviewed_new_resource",
        reviewed_by="synthetic-reviewer",
        reviewed_at=datetime(2026, 9, 24, tzinfo=UTC),
        reason="Explicit synthetic reviewed mapping; not inferred from the numeric source ID.",
        source_evidence_ids=(evidence.evidence_id,),
    )


def test_no_lineage_is_created_implicitly(snapshot_candidate: ExtractedCandidate) -> None:
    plan = prepare_stage(
        snapshot_candidate, policy_version="DEMO-POLICY-1", capability_probe=lambda: True
    )
    assert plan.mappings == ()
    assert plan.index.mode == "fts5"
    validate_stage(plan)
    with pytest.raises(ValueError, match="NOT_REPRODUCIBLE"):
        validate_stage(replace(plan, index=replace(plan.index, version="0" * 64)))


def test_lineage_requires_full_ref_and_evidence_binding(
    snapshot_candidate: ExtractedCandidate, prepared_snapshot: PreparedCandidate
) -> None:
    mapping = _mapping(prepared_snapshot)
    plan = prepare_stage(
        snapshot_candidate,
        policy_version="DEMO-POLICY-1",
        mappings=(mapping,),
        capability_probe=lambda: False,
    )
    assert plan.mappings == (mapping,) and plan.index.mode == "bounded_lexical"
    assert plan.mapping_digest == lineage_version((mapping,))
    different = next(row for row in prepared_snapshot.evidence if row.ref != mapping.ref)
    bad = mapping.model_copy(update={"source_evidence_ids": (different.evidence_id,)})
    with pytest.raises(ValueError, match="EVIDENCE_WRONG_LISTING"):
        prepare_stage(
            snapshot_candidate,
            policy_version="DEMO-POLICY-1",
            mappings=(bad,),
            capability_probe=lambda: True,
        )
    with pytest.raises(ValueError, match="MULTIPLE_RESOURCES"):
        lineage_version((mapping, mapping))


@pytest.mark.parametrize(
    "change",
    [
        {"predecessor_ref": None, "decision": "reviewed_same_vehicle"},
        {"reason": " "},
        {"reviewed_by": " "},
    ],
)
def test_unreviewed_or_incomplete_lineage_is_rejected(
    prepared_snapshot: PreparedCandidate, change: dict[str, Any]
) -> None:
    data = _mapping(prepared_snapshot).model_dump(mode="json")
    data.update(change)
    with pytest.raises(ValidationError):
        ReviewedResourceMapping.model_validate(data)
