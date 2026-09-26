"""BE-18 parser/semantic proof only; these tests cannot prove Excel cell safety."""

import csv
import hashlib
import io
import json
import unicodedata
from copy import deepcopy
from dataclasses import asdict
from typing import Any

import pytest
from pydantic import ValidationError

from app.leads.csv_serialization import (
    CsvSerializationError,
    LeadExportRow,
    SerializedLeadCsv,
    serialize_leads_csv,
    validate_leads_csv,
)
from tests.transactions.csv_fixtures import (
    BOOKING_ID,
    CREATED_AT,
    EXPECTED_COLUMNS,
    FORMULA_PREFIXES,
    GENERATION,
    LEAD_ID,
    PROJECTION_VERSION,
    UNICODE_REQUIREMENTS,
    UNSUPPORTED_SCALAR_CONTROLS,
    UPDATED_AT,
    lead_payload,
    lead_row,
)


def render(rows: list[LeadExportRow]) -> SerializedLeadCsv:
    return serialize_leads_csv(
        rows, store_generation=GENERATION, projection_version=PROJECTION_VERSION
    )


def parsed_rows(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True))


def encode_rows(
    rows: list[list[str]], *, terminator: str = "\r\n", quote_all: bool = True
) -> bytes:
    buffer = io.StringIO(newline="")
    csv.writer(
        buffer, lineterminator=terminator, quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL
    ).writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def test_frozen_header_and_single_row_golden_bytes() -> None:
    result = render([lead_row()])
    header = '"' + '","'.join(EXPECTED_COLUMNS) + '"\r\n'
    row = (
        '"leads-csv-1","30000000-0000-4000-8000-000000000001","17",'
        '"40000000-0000-4000-8000-000000000001","3",'
        '"10000000-0000-4000-8000-000000000001","60000000-0000-4000-8000-000000000001",'
        '"70000000-0000-4000-8000-000000000001","2026-09-24T04:00:00Z",'
        '"2026-09-24T04:30:00Z","interested","local_only","missing",'
        '"","","","","[]","[]","missing","","declined","","[]"\r\n'
    )
    assert result.data == (header + row).encode("utf-8-sig")
    assert len(EXPECTED_COLUMNS) == 24
    assert result.validation.valid
    assert result.validation.row_count == 1
    assert result.validation.byte_length == len(result.data)
    assert result.validation.sha256 == hashlib.sha256(result.data).hexdigest()
    assert result.validation.neutralized_cell_count == 0


def test_unicode_json_exact_references_and_input_unchanged() -> None:
    payload = lead_payload()
    payload["stage"] = "viewing_confirmed"
    payload["booking_ids"] = [BOOKING_ID]
    payload["values"]["requirements"] = UNICODE_REQUIREMENTS.copy()
    refs = [{"namespace": "synthetic-fixtures", "snapshot_id": "f" * 64, "source_id": "00707"}]
    payload["values"]["selected_refs"] = refs
    payload["values"]["email"] = {"state": "provided", "value": 'null, "buyer"\r\nسطر'}
    payload["values"]["phone"] = {"state": "provided", "value": "+971000000000"}
    row = LeadExportRow.model_validate(payload)
    before = deepcopy(row.model_dump())
    result = render([row])
    actual = parsed_rows(result.data)[0]
    assert tuple(actual) == EXPECTED_COLUMNS
    assert json.loads(actual["requirements_json"]) == UNICODE_REQUIREMENTS
    assert json.loads(actual["selected_inventory_refs_json"]) == refs
    assert json.loads(actual["booking_ids_json"]) == [BOOKING_ID]
    assert actual["email_value"] == 'null, "buyer"\r\nسطر'
    assert actual["phone_value"] == "'+971000000000"
    assert actual["lead_id"] == LEAD_ID
    assert actual["lead_revision"] == "3"
    assert actual["created_at_utc"] == CREATED_AT
    assert actual["updated_at_utc"] == UPDATED_AT
    assert "سيارة" in actual["requirements_json"]
    assert not any(unicodedata.category(char) == "Cc" for char in actual["requirements_json"])
    assert result.validation.neutralized_cell_count == 1
    assert row.model_dump() == before
    assert payload["values"]["phone"]["value"] == "+971000000000"


@pytest.mark.parametrize("state", ["provided", "missing", "declined"])
def test_budget_zero_and_nonprovided_blanks_are_distinct(state: str) -> None:
    payload = lead_payload()
    payload["values"]["budget"] = {
        "state": state,
        "value": {"minimum": 0, "maximum": 0, "currency": "AED", "basis": "cash"}
        if state == "provided"
        else None,
    }
    actual = parsed_rows(render([LeadExportRow.model_validate(payload)]).data)[0]
    assert actual["budget_state"] == state
    assert actual["budget_minimum_minor_units"] == ("0" if state == "provided" else "")
    assert actual["budget_maximum_minor_units"] == ("0" if state == "provided" else "")
    assert actual["budget_currency"] == ("AED" if state == "provided" else "")
    assert actual["budget_basis"] == ("cash" if state == "provided" else "")


@pytest.mark.parametrize("bound", ["minimum", "maximum"])
def test_open_ended_budget_preserves_exact_minor_units(bound: str) -> None:
    payload = lead_payload()
    payload["values"]["budget"] = {
        "state": "provided",
        "value": {bound: 987654321123, "currency": "AED"},
    }
    actual = parsed_rows(render([LeadExportRow.model_validate(payload)]).data)[0]
    assert actual[f"budget_{bound}_minor_units"] == "987654321123"
    other_bound = "maximum" if bound == "minimum" else "minimum"
    assert actual[f"budget_{other_bound}_minor_units"] == ""


@pytest.mark.parametrize("literal", ["null", "None", "N/A", "not_applicable", "0"])
def test_provided_contact_literal_is_not_interpreted_as_status(literal: str) -> None:
    payload = lead_payload()
    payload["values"]["email"] = {"state": "provided", "value": literal}
    actual = parsed_rows(render([LeadExportRow.model_validate(payload)]).data)[0]
    assert actual["email_state"] == "provided"
    assert actual["email_value"] == literal


@pytest.mark.parametrize("field", ["budget", "email", "phone"])
def test_not_applicable_enum_rejects_instead_of_coercing(field: str) -> None:
    payload = lead_payload()
    payload["values"][field] = {"state": "not_applicable", "value": None}
    with pytest.raises(ValidationError):
        LeadExportRow.model_validate(payload)


@pytest.mark.parametrize("prefix", FORMULA_PREFIXES)
@pytest.mark.parametrize("operator", ["=", "+", "-", "@"])
def test_formula_prefix_is_neutralized_before_original_cell(prefix: str, operator: str) -> None:
    original = prefix + operator + "1+2"
    payload = lead_payload()
    payload["values"]["phone"] = {"state": "provided", "value": original}
    row = LeadExportRow.model_validate(payload)
    result = render([row])
    assert parsed_rows(result.data)[0]["phone_value"] == "'" + original
    assert result.validation.neutralized_cell_count == 1
    assert row.values.phone.value == original


@pytest.mark.parametrize("literal", ["'=1+2", "  '=1+2", "buyer=name", "buyer@example.test", " "])
def test_safe_text_does_not_gain_an_apostrophe(literal: str) -> None:
    payload = lead_payload()
    payload["values"]["email"] = {"state": "provided", "value": literal}
    result = render([LeadExportRow.model_validate(payload)])
    assert parsed_rows(result.data)[0]["email_value"] == literal
    assert result.validation.neutralized_cell_count == 0


@pytest.mark.parametrize("control", UNSUPPORTED_SCALAR_CONTROLS)
@pytest.mark.parametrize("position", ["start", "middle", "end"])
def test_unsupported_raw_control_rejects_without_bytes_or_input_change(
    control: str, position: str
) -> None:
    original = {"start": control + "=1", "middle": "buyer" + control + "=1", "end": "=1" + control}[
        position
    ]
    payload = lead_payload()
    payload["values"]["email"] = {"state": "provided", "value": original}
    row = LeadExportRow.model_validate(payload)
    with pytest.raises(CsvSerializationError) as error:
        render([row])
    assert error.value.code == "UNSUPPORTED_TEXT_CONTROL"
    assert error.value.column == "email_value"
    assert original not in str(error.value)
    assert row.values.email.value == original


@pytest.mark.parametrize("control", UNSUPPORTED_SCALAR_CONTROLS)
def test_json_leaf_controls_remain_exact_without_raw_csv_controls(control: str) -> None:
    payload = lead_payload()
    original = control + "=1" + control
    payload["values"]["requirements"] = [original]
    result = render([LeadExportRow.model_validate(payload)])
    cell = parsed_rows(result.data)[0]["requirements_json"]
    assert json.loads(cell) == [original]
    assert not any(unicodedata.category(char) == "Cc" for char in cell)
    assert result.validation.neutralized_cell_count == 0


def test_order_is_deterministic_and_generation_is_distinct_from_lead_revision() -> None:
    rows = [lead_row(2), lead_row(1)]
    first = render(rows)
    assert first.data == render(list(reversed(rows))).data
    assert first.data == render(rows).data
    assert [row["lead_id"] for row in parsed_rows(first.data)] == [LEAD_ID, rows[0].lead_id]
    assert all(row["projection_version"] == "17" for row in parsed_rows(first.data))
    assert all(row["lead_revision"] == "3" for row in parsed_rows(first.data))
    changed = serialize_leads_csv(
        rows, store_generation="30000000-0000-4000-8000-000000000002", projection_version=17
    )
    assert changed.data != first.data
    assert changed.validation.sha256 != first.validation.sha256


def test_empty_snapshot_is_a_valid_header_only_projection() -> None:
    result = render([])
    assert result.validation.valid
    assert result.validation.row_count == 0
    assert parsed_rows(result.data) == []
    assert result.data.decode("utf-8-sig") == '"' + '","'.join(EXPECTED_COLUMNS) + '"\r\n'


@pytest.mark.parametrize("duplicate", ["lead", "journey"])
def test_duplicate_logical_leads_fail_without_partial_output(duplicate: str) -> None:
    payload = lead_payload(2)
    field = "lead_id" if duplicate == "lead" else "journey_reference"
    payload[field] = lead_payload()[field]
    with pytest.raises(CsvSerializationError) as error:
        render([lead_row(), LeadExportRow.model_validate(payload)])
    assert error.value.code == ("DUPLICATE_LEAD_ID" if duplicate == "lead" else "DUPLICATE_JOURNEY")


@pytest.mark.parametrize(
    "field", ["provider_key", "raw_transcript", "seller_contact", "diagnostics"]
)
def test_unapproved_fields_cannot_enter_export_input(field: str) -> None:
    payload = lead_payload()
    payload[field] = "SYNTHETIC-DO-NOT-EXPORT"
    with pytest.raises(ValidationError) as error:
        LeadExportRow.model_validate(payload)
    assert "SYNTHETIC-DO-NOT-EXPORT" not in str(error.value)
    payload = lead_payload()
    payload["values"][field] = "SYNTHETIC-DO-NOT-EXPORT"
    with pytest.raises(ValidationError):
        LeadExportRow.model_validate(payload)


@pytest.mark.parametrize("bad_budget", [True, 1.5, "100"])
def test_budget_coercion_cannot_change_meaning(bad_budget: object) -> None:
    payload = lead_payload()
    payload["values"]["budget"] = {
        "state": "provided",
        "value": {"maximum": bad_budget, "currency": "AED"},
    }
    with pytest.raises(ValidationError):
        LeadExportRow.model_validate(payload)


def test_stage_and_provenance_are_required() -> None:
    payload = lead_payload()
    payload["stage"] = "viewing_confirmed"
    with pytest.raises(ValidationError):
        LeadExportRow.model_validate(payload)
    payload = lead_payload()
    del payload["source_session_reference"]
    with pytest.raises(ValidationError):
        LeadExportRow.model_validate(payload)
    payload = lead_payload()
    payload["updated_at_utc"] = "2026-09-23T00:00:00Z"
    with pytest.raises(ValidationError):
        LeadExportRow.model_validate(payload)


def test_nested_mutation_is_revalidated_and_not_repaired() -> None:
    row = lead_row()
    row.values.phone.value = "SYNTHETIC-DECLINED-CONTACT"
    with pytest.raises(CsvSerializationError) as error:
        render([row])
    assert error.value.code == "INVALID_CANONICAL_ROW"
    assert "SYNTHETIC-DECLINED-CONTACT" not in str(error.value)
    assert row.values.phone.state == "declined"
    assert row.values.phone.value == "SYNTHETIC-DECLINED-CONTACT"


def test_invalid_unicode_fails_without_replacement_characters() -> None:
    payload = lead_payload()
    payload["values"]["requirements"] = ["Unpaired surrogate \ud800"]
    with pytest.raises((ValidationError, CsvSerializationError)) as error:
        render([LeadExportRow.model_validate(payload)])
    if isinstance(error.value, CsvSerializationError):
        assert error.value.code == "INVALID_UNICODE"
    assert payload["values"]["requirements"] == ["Unpaired surrogate \ud800"]


@pytest.mark.parametrize(
    "tamper", ["cell", "header", "drop_row", "column", "lf", "quotes", "bom", "utf8"]
)
def test_validator_rejects_tampering_and_reports_no_buyer_values(tamper: str) -> None:
    original = render([lead_row()]).data
    matrix = list(csv.reader(io.StringIO(original.decode("utf-8-sig"), newline="")))
    if tamper == "cell":
        matrix[1][20] = "SYNTHETIC-DO-NOT-LOG"
        data = encode_rows(matrix)
    elif tamper == "header":
        matrix[0][0] = "SYNTHETIC-DO-NOT-LOG"
        data = encode_rows(matrix)
    elif tamper == "drop_row":
        data = encode_rows(matrix[:1])
    elif tamper == "column":
        data = encode_rows([matrix[0], matrix[1][:-1]])
    elif tamper == "lf":
        data = encode_rows(matrix, terminator="\n")
    elif tamper == "quotes":
        data = encode_rows(matrix, quote_all=False)
    elif tamper == "bom":
        data = original[3:]
    else:
        data = original[:3] + b"\xff" + original[3:]
    report = validate_leads_csv(
        data, [lead_row()], store_generation=GENERATION, projection_version=PROJECTION_VERSION
    )
    assert not report.valid
    assert len(report.issues) == 1
    assert "SYNTHETIC-DO-NOT-LOG" not in json.dumps(asdict(report))


def test_validator_rejects_original_formula_and_wrong_projection_identity() -> None:
    payload = lead_payload()
    payload["values"]["phone"] = {"state": "provided", "value": "=1+1"}
    row = LeadExportRow.model_validate(payload)
    safe = render([row]).data
    unsafe = safe.replace(b"'=1+1", b"=1+1")
    report = validate_leads_csv(
        unsafe, [row], store_generation=GENERATION, projection_version=PROJECTION_VERSION
    )
    assert report.issues[0].column == "phone_value"
    for generation, version in [(GENERATION, 18), ("30000000-0000-4000-8000-000000000002", 17)]:
        report = validate_leads_csv(
            safe, [row], store_generation=generation, projection_version=version
        )
        assert not report.valid


def test_serializer_returns_bytes_without_opening_files(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_file_io(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("SERIALIZER_MUST_NOT_OPEN_FILES")

    monkeypatch.setattr("builtins.open", no_file_io)
    result = render([lead_row()])
    assert result.validation.valid
    # The shared autouse fixture separately denies default HTTPX live transports.
