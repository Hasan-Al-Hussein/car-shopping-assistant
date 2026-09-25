"""Pure BE-03 source normalization, provenance and candidate identity assembly."""

from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import ConfigDict, ValidationError

from app.api.schemas.inventory import ListingPhoto
from app.inventory.import_reader import (
    CLEANED_HEADERS,
    ImportReport,
    SourceCell,
    SourceManifest,
    SourceRecord,
    WorkbookReadResult,
    _source_id,
)
from app.inventory.references import ImmutableInventoryRef, SnapshotManifest, normalization_manifest
from app.inventory.text_normalization import TEXT_FIELDS, TextRepresentation, normalize_text


class ImmutableListingPhoto(ListingPhoto):
    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class CellProvenance:
    workbook_sha256: str
    sheet: str
    row: int
    source: SourceCell = field(repr=False)


@dataclass(frozen=True)
class NormalizedField:
    provenance: CellProvenance
    text: TextRepresentation


@dataclass(frozen=True)
class NormalizedListing:
    ref: ImmutableInventoryRef
    source: SourceRecord = field(repr=False)
    fields: tuple[NormalizedField, ...]
    photo: ImmutableListingPhoto = field(repr=False)
    photo_provenance: CellProvenance
    identity_provenance: CellProvenance

    def text(self, name: str) -> TextRepresentation:
        return next(item.text for item in self.fields if item.provenance.source.field == name)


@dataclass(frozen=True)
class NormalizedCandidate:
    manifest: SnapshotManifest
    source_manifest: SourceManifest
    records: tuple[NormalizedListing, ...] = field(repr=False)
    audit_records: tuple[SourceRecord, ...] = field(repr=False)
    reader_report: ImportReport = field(repr=False)

    def provenance_report(self) -> dict[str, Any]:
        """Deterministic row accounting without source prose, URLs or raw values."""
        return {
            "status": "normalized_candidate",
            "snapshot_id": self.manifest.snapshot_id,
            "manifest": asdict(self.manifest),
            "source_manifest": asdict(self.source_manifest),
            "selected_count": len(self.records),
            "normalized_count": len(self.records),
            "audit_only_count": len(self.audit_records),
            "published": False,
            "reader_report": self.reader_report.to_dict(),
            "records": [
                {
                    "ref": item.ref.model_dump(),
                    "sheet": item.source.sheet,
                    "row": item.source.row,
                    "identity_cell": item.identity_provenance.source.coordinate,
                    "photo_cell": item.photo_provenance.source.coordinate,
                    "photo_state": item.photo.state,
                    "fields": {
                        value.provenance.source.field: {
                            "cell": value.provenance.source.coordinate,
                            "source_python_type": value.provenance.source.python_type,
                            "source_data_type": value.provenance.source.data_type,
                            "state": value.text.state,
                            "reason": value.text.reason,
                            "transformations": value.text.transformations,
                        }
                        for value in item.fields
                    },
                }
                for item in self.records
            ],
        }


def normalize_photo(cell: SourceCell) -> ImmutableListingPhoto:
    """Validate the exact original string; never repair, fetch or infer from it."""
    if cell.field != "photo_url":
        raise ValueError("PHOTO_FIELD_UNSUPPORTED")
    value = cell.value
    if value is None or isinstance(value, str) and not value.strip():
        return ImmutableListingPhoto(state="missing", url=None, alt="Photo unavailable")
    if isinstance(value, str) and cell.data_type not in {"f", "e"}:
        try:
            return ImmutableListingPhoto(
                state="source_present", url=value, alt="Photo supplied with this car listing"
            )
        except ValidationError:
            pass
    return ImmutableListingPhoto(state="blocked", url=None, alt="Photo unavailable")


def _require_candidate(result: WorkbookReadResult) -> SourceManifest:
    source = result.manifest
    report = result.report
    selected = [sheet for sheet in report.sheets if sheet.role == "selected"]
    if (
        source is None
        or report.state != "accepted"
        or not report.source_unchanged
        or report.workbook_sha256_before != source.workbook_sha256
        or report.workbook_sha256_after != source.workbook_sha256
        or report.rejected_count
        or report.quarantined_count
        or report.accepted_count != len(result.selected_records)
        or len(selected) != 1
        or not selected[0].complete
        or selected[0].structural_error_count
        or selected[0].meaningful_rows != len(result.selected_records)
        or selected[0].sheet != source.selected_sheet
    ):
        raise ValueError("NORMALIZATION_REQUIRES_ACCEPTED_SOURCE")
    ids: set[str] = set()
    for record in result.selected_records:
        names = [cell.field for cell in record.cells]
        if (
            record.sheet != source.selected_sheet
            or record.structural_errors
            or record.source_id is None
            or record.source_id in ids
            or len(names) != len(CLEANED_HEADERS)
            or set(names) != set(CLEANED_HEADERS)
        ):
            raise ValueError("NORMALIZATION_SOURCE_INCONSISTENT")
        # Reuse the reader's one ID conversion rule; provenance and ref must agree.
        if _source_id(record.cell("Listing_ID")) != record.source_id:
            raise ValueError("NORMALIZATION_SOURCE_INCONSISTENT")
        ids.add(record.source_id)
    return source


def normalize_candidate(result: WorkbookReadResult) -> NormalizedCandidate:
    source = _require_candidate(result)
    manifest = normalization_manifest(source)
    listings: list[NormalizedListing] = []
    for record in result.selected_records:
        assert record.source_id is not None

        def provenance(cell: SourceCell, record: SourceRecord = record) -> CellProvenance:
            return CellProvenance(source.workbook_sha256, record.sheet, record.row, cell)

        listings.append(
            NormalizedListing(
                ref=manifest.reference(record.source_id),
                source=record,
                fields=tuple(
                    NormalizedField(
                        provenance(record.cell(name)), normalize_text(record.cell(name))
                    )
                    for name in TEXT_FIELDS
                ),
                photo=normalize_photo(record.cell("photo_url")),
                photo_provenance=provenance(record.cell("photo_url")),
                identity_provenance=provenance(record.cell("Listing_ID")),
            )
        )
    # Lexicographic source-ID order is deterministic, never a ranking or row lookup.
    listings.sort(key=lambda item: item.ref.source_id)
    return NormalizedCandidate(
        manifest, source, tuple(listings), result.audit_records, result.report
    )
