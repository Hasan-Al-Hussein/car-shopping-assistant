"""Pure leads-csv-1 bytes; ownership, capture and publication belong to callers.

The caller supplies one coherent authorized canonical snapshot. This module has
no database, filesystem, clock, network or logging boundary. It cannot establish
that supplied booking IDs were committed or that contacts belong to the buyer.
"""

import csv
import hashlib
import io
import json
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.common import DTO, Id, Revision, UtcInstant
from app.api.schemas.leads import LeadValues

CSV_SCHEMA_VERSION = "leads-csv-1"
CSV_COLUMNS = (
    "schema_version",
    "store_generation",
    "projection_version",
    "lead_id",
    "lead_revision",
    "owner_reference",
    "journey_reference",
    "source_session_reference",
    "created_at_utc",
    "updated_at_utc",
    "stage",
    "delivery_mode",
    "budget_state",
    "budget_minimum_minor_units",
    "budget_maximum_minor_units",
    "budget_currency",
    "budget_basis",
    "requirements_json",
    "selected_inventory_refs_json",
    "email_state",
    "email_value",
    "phone_state",
    "phone_value",
    "booking_ids_json",
)
_UTF8_BOM = b"\xef\xbb\xbf"


class LeadExportRow(DTO):
    """Internal export allowlist, deliberately separate from the buyer API DTO."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    lead_id: Id
    lead_revision: Revision
    owner_reference: Id
    journey_reference: Id
    source_session_reference: Id
    created_at_utc: UtcInstant
    updated_at_utc: UtcInstant
    stage: Literal["interested", "viewing_confirmed"]
    values: LeadValues
    booking_ids: Annotated[list[Id], Field(max_length=100)]

    @model_validator(mode="after")
    def coherent_record(self) -> "LeadExportRow":
        if datetime.fromisoformat(self.updated_at_utc) < datetime.fromisoformat(
            self.created_at_utc
        ):
            raise ValueError("Update time must not precede creation time.")
        if self.stage == "viewing_confirmed" and not self.booking_ids:
            raise ValueError("Viewing-confirmed lead requires a committed booking reference.")
        if len(set(self.booking_ids)) != len(self.booking_ids):
            raise ValueError("Booking references must be unique.")
        return self


class ProjectionIdentity(DTO):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    store_generation: Id
    projection_version: Revision


class CsvSerializationError(ValueError):
    """Safe diagnostic only: never include buyer values in exceptions/reports."""

    def __init__(self, code: str, row_number: int | None = None, column: str | None = None) -> None:
        self.code = code
        self.row_number = row_number
        self.column = column
        super().__init__(code if row_number is None else f"{code} at input row {row_number}")


@dataclass(frozen=True)
class CsvValidationIssue:
    code: str
    row_number: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class CsvValidationReport:
    valid: bool
    schema_version: str
    store_generation: str
    projection_version: int
    row_count: int
    byte_length: int
    sha256: str
    neutralized_cell_count: int
    issues: tuple[CsvValidationIssue, ...]


@dataclass(frozen=True)
class SerializedLeadCsv:
    data: bytes
    validation: CsvValidationReport


def _formula_leading(value: str) -> bool:
    for character in value:
        if character.isspace() or unicodedata.category(character) in {"Cc", "Cf"}:
            continue
        return character in "=+-@"
    return False


def _spreadsheet_text(value: str) -> str:
    # leads-csv-1 has no reversible scalar escape convention for these controls.
    if any(unicodedata.category(char) == "Cc" and char not in "\t\r\n" for char in value):
        raise CsvSerializationError("UNSUPPORTED_TEXT_CONTROL")
    return "'" + value if _formula_leading(value) else value


def _compact_json(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    # JSON escapes C0 by default, but ensure_ascii=False leaves DEL/C1 raw.
    return "".join(
        f"\\u{ord(char):04x}" if unicodedata.category(char) == "Cc" else char for char in rendered
    )


def _snapshot(rows: Sequence[LeadExportRow]) -> list[LeadExportRow]:
    snapshot: list[LeadExportRow] = []
    seen_leads: set[str] = set()
    seen_journeys: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, LeadExportRow):
            raise CsvSerializationError("INVALID_ROW_TYPE", index)
        try:
            # Revalidate nested mutable DTOs/copy(update=...) without changing the caller.
            copied = LeadExportRow.model_validate(row.model_dump(mode="python", warnings=False))
        except (TypeError, ValueError):
            raise CsvSerializationError("INVALID_CANONICAL_ROW", index) from None
        if copied.lead_id in seen_leads:
            raise CsvSerializationError("DUPLICATE_LEAD_ID", index)
        if copied.journey_reference in seen_journeys:
            raise CsvSerializationError("DUPLICATE_JOURNEY", index)
        seen_leads.add(copied.lead_id)
        seen_journeys.add(copied.journey_reference)
        snapshot.append(copied)
    return sorted(snapshot, key=lambda row: row.lead_id)


def _matrix(rows: list[LeadExportRow], identity: ProjectionIdentity) -> tuple[list[list[str]], int]:
    matrix = [list(CSV_COLUMNS)]
    neutralized = 0
    for index, row in enumerate(rows, start=1):
        values = row.values
        budget = values.budget.value
        cells = [
            CSV_SCHEMA_VERSION,
            identity.store_generation,
            str(identity.projection_version),
            row.lead_id,
            str(row.lead_revision),
            row.owner_reference,
            row.journey_reference,
            row.source_session_reference,
            row.created_at_utc,
            row.updated_at_utc,
            row.stage,
            "local_only",
            values.budget.state,
            str(budget.minimum) if budget is not None and budget.minimum is not None else "",
            str(budget.maximum) if budget is not None and budget.maximum is not None else "",
            budget.currency if budget is not None else "",
            budget.basis if budget is not None else "",
            _compact_json(values.requirements),
            _compact_json([ref.model_dump(mode="json") for ref in values.selected_refs]),
            values.email.state,
            values.email.value if values.email.value is not None else "",
            values.phone.state,
            values.phone.value if values.phone.value is not None else "",
            _compact_json(row.booking_ids),
        ]
        protected = []
        for column, cell in zip(CSV_COLUMNS, cells, strict=True):
            try:
                protected.append(_spreadsheet_text(cell))
            except CsvSerializationError as exc:
                raise CsvSerializationError(exc.code, index, column) from None
        neutralized += sum(
            original != safe for original, safe in zip(cells, protected, strict=True)
        )
        matrix.append(protected)
    return matrix, neutralized


def _encode(matrix: list[list[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerows(matrix)
    try:
        return buffer.getvalue().encode("utf-8-sig", errors="strict")
    except UnicodeEncodeError:
        raise CsvSerializationError("INVALID_UNICODE") from None


def _validate(
    data: bytes,
    expected: list[list[str]],
    identity: ProjectionIdentity,
    neutralized: int,
) -> CsvValidationReport:
    issue: CsvValidationIssue | None = None
    parsed: list[list[str]] = []
    if not data.startswith(_UTF8_BOM):
        issue = CsvValidationIssue("MISSING_UTF8_BOM")
    else:
        try:
            parsed = list(
                csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
            )
        except UnicodeDecodeError:
            issue = CsvValidationIssue("INVALID_UTF8")
        except csv.Error:
            issue = CsvValidationIssue("INVALID_CSV")
    if issue is None:
        if not parsed or parsed[0] != list(CSV_COLUMNS):
            issue = CsvValidationIssue("HEADER_MISMATCH")
        elif len(parsed) != len(expected):
            issue = CsvValidationIssue("ROW_COUNT_MISMATCH")
        else:
            for index, (actual, wanted) in enumerate(zip(parsed[1:], expected[1:], strict=True), 1):
                if len(actual) != len(CSV_COLUMNS):
                    issue = CsvValidationIssue("COLUMN_COUNT_MISMATCH", index)
                    break
                if actual != wanted:
                    column = next(
                        name
                        for name, cell, expected_cell in zip(
                            CSV_COLUMNS, actual, wanted, strict=True
                        )
                        if cell != expected_cell
                    )
                    issue = CsvValidationIssue("CELL_MISMATCH", index, column)
                    break
            if issue is None and _encode(parsed) != data:
                issue = CsvValidationIssue("NONCANONICAL_CSV")
    return CsvValidationReport(
        valid=issue is None,
        schema_version=CSV_SCHEMA_VERSION,
        store_generation=identity.store_generation,
        projection_version=identity.projection_version,
        row_count=max(0, len(parsed) - 1),
        byte_length=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        neutralized_cell_count=neutralized,
        issues=() if issue is None else (issue,),
    )


def serialize_leads_csv(
    rows: Sequence[LeadExportRow], *, store_generation: str, projection_version: int
) -> SerializedLeadCsv:
    """Return a complete deterministic in-memory projection; never publish or save it."""
    identity = ProjectionIdentity(
        store_generation=store_generation, projection_version=projection_version
    )
    expected, neutralized = _matrix(_snapshot(rows), identity)
    data = _encode(expected)
    report = _validate(data, expected, identity, neutralized)
    if not report.valid:
        raise CsvSerializationError("SERIALIZATION_VALIDATION_FAILED")
    return SerializedLeadCsv(data=data, validation=report)


def validate_leads_csv(
    data: bytes,
    rows: Sequence[LeadExportRow],
    *,
    store_generation: str,
    projection_version: int,
) -> CsvValidationReport:
    """Validate bytes against the exact supplied canonical snapshot, without I/O.

    An apostrophe in a CSV field is not reversible provenance. Validation therefore
    compares against canonical rows instead of guessing or stripping leading quotes.
    """
    identity = ProjectionIdentity(
        store_generation=store_generation, projection_version=projection_version
    )
    expected, neutralized = _matrix(_snapshot(rows), identity)
    return _validate(data, expected, identity, neutralized)
