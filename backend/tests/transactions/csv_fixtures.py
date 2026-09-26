"""Wholly synthetic buyer data; no workbook contacts, provider keys or transcripts."""

from typing import Any

from app.leads.csv_serialization import LeadExportRow

GENERATION = "30000000-0000-4000-8000-000000000001"
PROJECTION_VERSION = 17
LEAD_ID = "40000000-0000-4000-8000-000000000001"
BOOKING_ID = "50000000-0000-4000-8000-000000000001"
CREATED_AT = "2026-09-24T04:00:00Z"
UPDATED_AT = "2026-09-24T04:30:00Z"

# Independent copy of the frozen external contract: changing production order must fail.
EXPECTED_COLUMNS = (
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

FORMULA_PREFIXES = (
    "",
    " ",
    "\t",
    "\r",
    "\n",
    " \t\r\n",
    "\u00a0",
    "\u2003",
    "\ufeff",
    "\u200b",
    "\u2066",
    " \ufeff\t",
)
UNSUPPORTED_SCALAR_CONTROLS = ("\x00", "\x01", "\x0b", "\x0c", "\x1f", "\x7f", "\x85", "\x9f")
UNICODE_REQUIREMENTS = [
    'سيارة عائلية، "مريحة"\nمع مساحة للأمتعة',
    'Cafe\u0301 🚗 — العربية\r\nSecond line\twith comma, and quote"',
    "=SUM(1,2)",
    "null",
    "None",
    "not_applicable",
    "\x00=2+2\x7f\x85\x9f",
]


def lead_payload(number: int = 1) -> dict[str, Any]:
    """Fresh data per call so one mutated fixture cannot contaminate another."""
    return {
        "lead_id": f"40000000-0000-4000-8000-{number:012d}",
        "lead_revision": 3,
        "owner_reference": f"10000000-0000-4000-8000-{number:012d}",
        "journey_reference": f"60000000-0000-4000-8000-{number:012d}",
        "source_session_reference": f"70000000-0000-4000-8000-{number:012d}",
        "created_at_utc": CREATED_AT,
        "updated_at_utc": UPDATED_AT,
        "stage": "interested",
        "values": {
            "budget": {"state": "missing", "value": None},
            "requirements": [],
            "selected_refs": [],
            "email": {"state": "missing", "value": None},
            "phone": {"state": "declined", "value": None},
        },
        "booking_ids": [],
    }


def lead_row(number: int = 1) -> LeadExportRow:
    return LeadExportRow.model_validate(lead_payload(number))
