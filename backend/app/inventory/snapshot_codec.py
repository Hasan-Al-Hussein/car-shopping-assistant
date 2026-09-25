"""Canonical, lossless internal snapshot envelopes; no I/O or database access."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from pydantic import TypeAdapter

from app.inventory.extraction import ExtractedCandidate, extract_reviewed
from app.inventory.import_reader import SourceCell, SourceRecord, WorkbookReadResult
from app.inventory.normalization import CellProvenance, normalize_candidate
from app.inventory.references import ImmutableInventoryRef, SnapshotManifest
from app.inventory.review_catalogue import ReviewCatalogue

SERIALIZATION_VERSION = "inventory-payload-1"
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
SOURCE_ADAPTER = TypeAdapter(WorkbookReadResult)


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _value_data(value: object) -> dict[str, object]:
    # Preserve decoded Python types and float tokens, including unsupported facts.
    if value is None or type(value) in {str, int, bool}:
        return {"type": type(value).__name__, "value": value}
    if type(value) is float:
        return {"type": "float", "value": value.hex()}
    if type(value) in {datetime, date, time}:
        assert isinstance(value, (datetime, date, time))
        return {"type": type(value).__name__, "value": value.isoformat()}
    if type(value) is timedelta:
        return {
            "type": "timedelta",
            "value": [value.days, value.seconds, value.microseconds],
        }
    raise ValueError("SNAPSHOT_SOURCE_VALUE_UNSUPPORTED")


def _value_from_data(data: object) -> object:
    if not isinstance(data, dict) or set(data) != {"type", "value"}:
        raise ValueError("SNAPSHOT_SOURCE_VALUE_INVALID")
    kind, value = data["type"], data["value"]
    if kind == "NoneType" and value is None:
        return None
    if (kind, type(value)) in {("str", str), ("int", int), ("bool", bool)}:
        return value
    if kind == "float" and isinstance(value, str):
        return float.fromhex(value)
    if isinstance(value, str):
        if kind == "datetime":
            return datetime.fromisoformat(value)
        if kind == "date":
            return date.fromisoformat(value)
        if kind == "time":
            return time.fromisoformat(value)
    if (
        kind == "timedelta"
        and isinstance(value, list)
        and len(value) == 3
        and all(type(part) is int for part in value)
    ):
        return timedelta(days=value[0], seconds=value[1], microseconds=value[2])
    raise ValueError("SNAPSHOT_SOURCE_VALUE_INVALID")


def _cell_data(cell: SourceCell) -> dict[str, Any]:
    data = asdict(cell)
    data["value"] = _value_data(cell.value)
    return data


def _record_data(record: SourceRecord) -> dict[str, Any]:
    return {
        "sheet": record.sheet,
        "row": record.row,
        "source_id": record.source_id,
        "structural_errors": list(record.structural_errors),
        "cells": [_cell_data(cell) for cell in record.cells],
    }


def _source_data(candidate: ExtractedCandidate) -> dict[str, Any]:
    normalized = candidate.normalized_source
    return {
        "manifest": asdict(normalized.source_manifest),
        "report": asdict(normalized.reader_report),
        "selected_records": [_record_data(item.source) for item in normalized.records],
        "audit_records": [_record_data(item) for item in normalized.audit_records],
    }


def _provenance_data(value: CellProvenance) -> dict[str, Any]:
    return {
        "workbook_sha256": value.workbook_sha256,
        "sheet": value.sheet,
        "row": value.row,
        "source": _cell_data(value.source),
    }


def _source_from_data(data: object) -> WorkbookReadResult:
    # A private JSON copy allows decoding without mutating the caller's envelope.
    source = json.loads(canonical_json(data))
    for role in ("selected_records", "audit_records"):
        for record in source[role]:
            for cell in record["cells"]:
                cell["value"] = _value_from_data(cell["value"])
                if type(cell["value"]).__name__ != cell["python_type"]:
                    raise ValueError("SNAPSHOT_SOURCE_TYPE_MISMATCH")
    return SOURCE_ADAPTER.validate_python(source)


def _materialized(candidate: ExtractedCandidate) -> list[dict[str, Any]]:
    ledger = candidate.evidence_ledger()["records"]
    claims = {item["ref"]["source_id"]: item["claims"] for item in ledger}
    return [
        {
            "ref": item.normalized.ref.model_dump(),
            "source_row": item.normalized.source.row,
            "fields": {
                value.provenance.source.field: {
                    "provenance": _provenance_data(value.provenance),
                    "text": asdict(value.text),
                }
                for value in item.normalized.fields
            },
            "photo": item.normalized.photo.model_dump(mode="json"),
            "photo_provenance": _provenance_data(item.normalized.photo_provenance),
            "identity_provenance": _provenance_data(item.normalized.identity_provenance),
            "review": item.review.model_dump(mode="json"),
            "claims": claims[item.normalized.ref.source_id],
            "resolutions": [
                {
                    "family": fact.family,
                    "status": fact.status,
                    "disposition": fact.disposition,
                    "reason": fact.reason,
                    "strict_match_eligible": fact.strict_match_eligible,
                    "partial_coverage": fact.partial_coverage,
                    "claim_keys": [claim.annotation.key for claim in fact.claims],
                    "groups": [
                        {
                            "value": group.value.model_dump(mode="json"),
                            "qualifier": group.qualifier,
                            "claim_keys": [claim.annotation.key for claim in group.claims],
                        }
                        for group in fact.groups
                    ],
                }
                for fact in item.resolutions
            ],
        }
        for item in candidate.records
    ]


def _envelope(candidate: ExtractedCandidate) -> dict[str, Any]:
    return {
        "serialization_version": SERIALIZATION_VERSION,
        "manifest": asdict(candidate.manifest),
        "normalization_manifest": asdict(candidate.normalized_source.manifest),
        "source": _source_data(candidate),
        "catalogue": candidate.catalogue.model_dump(mode="json"),
        "listings": _materialized(candidate),
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("SNAPSHOT_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def decode_candidate(payload: str) -> ExtractedCandidate:
    """Rebuild with frozen extraction rules and compare every persisted meaning."""
    if len(payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("SNAPSHOT_PAYLOAD_LIMIT")
    try:
        data = json.loads(payload, object_pairs_hook=_unique_object)
        if data["serialization_version"] != SERIALIZATION_VERSION:
            raise ValueError("SNAPSHOT_SERIALIZATION_VERSION_UNSUPPORTED")
        source = _source_from_data(data["source"])
        catalogue = ReviewCatalogue.model_validate(data["catalogue"])
        candidate = extract_reviewed(normalize_candidate(source), catalogue)
        # Also rejects unknown fields, coerced values and forged materialized output.
        if canonical_json(_envelope(candidate)) != payload:
            raise ValueError("SNAPSHOT_PAYLOAD_NOT_CANONICAL_OR_INCONSISTENT")
        return candidate
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("SNAPSHOT_PAYLOAD_INVALID") from exc


@dataclass(frozen=True)
class ListingRow:
    ref: ImmutableInventoryRef
    source_row: int
    original_json: str = field(repr=False)
    normalized_json: str = field(repr=False)


@dataclass(frozen=True)
class EvidenceRow:
    evidence_id: str
    ref: ImmutableInventoryRef
    attribute: str
    raw_locator_json: str = field(repr=False)
    normalized_json: str = field(repr=False)
    status: str
    extraction_version: str


@dataclass(frozen=True)
class PreparedCandidate:
    manifest: SnapshotManifest
    payload_json: str = field(repr=False)
    payload_sha256: str
    import_version: str
    audit_count: int
    listings: tuple[ListingRow, ...] = field(repr=False)
    evidence: tuple[EvidenceRow, ...] = field(repr=False)


def prepare_candidate(candidate: ExtractedCandidate) -> PreparedCandidate:
    """Prepare outside the write lock; revalidate the full supplied object graph."""
    payload = canonical_json(_envelope(candidate))
    verified = decode_candidate(payload)
    if candidate != verified:
        raise ValueError("SNAPSHOT_CANDIDATE_NOT_REPRODUCIBLE")
    materialized = _materialized(verified)
    listings = tuple(
        ListingRow(
            item.normalized.ref,
            item.normalized.source.row,
            canonical_json(_record_data(item.normalized.source)),
            canonical_json(data),
        )
        for item, data in zip(verified.records, materialized, strict=True)
    )
    evidence = []
    for item in verified.records:
        for claim in item.claims:
            for ordinal, bound in enumerate((claim.evidence, *claim.condition_evidence)):
                evidence.append(
                    EvidenceRow(
                        bound.locator.evidence_id,
                        bound.ref,
                        claim.annotation.family,
                        canonical_json(bound.locator.model_dump(mode="json")),
                        canonical_json(
                            {
                                "annotation": claim.annotation.model_dump(mode="json"),
                                "ordinal": ordinal,
                                "review_version": claim.evidence_review_version,
                                "span_basis": bound.span_basis,
                                "source_row": bound.source_row,
                                "source_field": bound.source_field,
                                "source_python_type": bound.source.python_type,
                                "source_data_type": bound.source.data_type,
                            }
                        ),
                        item.fact(claim.annotation.family).status,
                        verified.manifest.extraction_version,
                    )
                )
    if len({row.evidence_id for row in evidence}) != len(evidence):
        raise ValueError("SNAPSHOT_DUPLICATE_EVIDENCE_ID")
    return PreparedCandidate(
        verified.manifest,
        payload,
        digest_text(payload),
        verified.normalized_source.source_manifest.reader_version,
        len(verified.normalized_source.audit_records),
        listings,
        tuple(evidence),
    )
