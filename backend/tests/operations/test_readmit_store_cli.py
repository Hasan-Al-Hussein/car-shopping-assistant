"""Actual child CLI calls after separately authorized coordinated application."""

import json

import pytest
from sqlalchemy.orm import Session

from app.database.models import ActiveInventory
from tests.operations.test_backup_restore_cli import run_cli
from tests.operations.test_restored_readmission import Case
from tests.operations.test_restored_readmission import case as case


def arguments(value: Case) -> tuple[str, ...]:
    return (
        "--store", str(value.store.path), "--project", str(value.project),
        "--operation-id", value.request.operation_id, "--restore-id", value.request.restore_id,
        "--restore-receipt-sha256", value.request.restore_receipt_sha256,
        "--expected-generation", value.request.expected_generation,
    )


def test_readmit_cli_configures_then_audits_and_closes_actual_fresh_runtime(
    case: Case, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CSA_ASSISTANT_ENABLED", "false")
    flags = arguments(case)
    configured = run_cli("readmit_store.py", *flags)
    assert configured.returncode == 0 and configured.stderr == ""
    payload = json.loads(configured.stdout)
    assert payload["runtime"] == "not_started"
    assert payload["result"]["current_viewing"]["state"] == "ready"
    assert payload["result"]["current_csv"]["projection"] == "current"
    command = (case.records / "activation-request.json").read_bytes()
    audited = run_cli("readmit_store.py", *flags, "--runtime-audit")
    assert audited.returncode == 0 and audited.stderr == ""
    result = json.loads(audited.stdout)
    assert result["runtime"] == "audited_and_closed"
    assert result["result"]["request"] == case.request.model_dump(mode="json")
    assert (case.records / "activation-request.json").read_bytes() == command


def test_readmit_cli_preserves_known_event_but_exits_unsuccessfully_on_changed_inventory(
    case: Case,
) -> None:
    first = case.run()

    def change(db: Session) -> None:
        current = db.get(ActiveInventory, 1)
        assert current is not None
        current.revision += 1  # Labelled adverse later-pointer fixture.

    case.store.write(change)
    repeated = run_cli("readmit_store.py", *arguments(case))
    assert repeated.returncode == 1 and repeated.stderr == ""
    payload = json.loads(repeated.stdout)
    assert payload["runtime"] == "not_started"
    assert payload["result"]["viewing"] == first.viewing.model_dump(mode="json")
    assert payload["result"]["current_viewing"]["state"] == "unavailable"
    assert payload["result"]["current_csv"]["projection"] == "current"


def test_readmit_cli_does_not_echo_unvalidated_original_operation(case: Case) -> None:
    flags = list(arguments(case))
    flags[flags.index("--operation-id") + 1] = "sensitive-unvalidated-value-xxxxxxxxxx"
    rejected = run_cli("readmit_store.py", *flags)
    assert rejected.returncode == 1 and rejected.stderr == ""
    assert json.loads(rejected.stdout) == {
        "state": "unresolved", "code": "READMISSION_NOT_VERIFIED", "operation_id": None,
        "next_action": "reconcile_same_original_request",
    }
    assert not case.records.exists()
