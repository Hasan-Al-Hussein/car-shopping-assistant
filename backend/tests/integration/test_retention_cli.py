"""Actual retention CLI contracts, authored under the T10 source-only grant.

NOT_RUN. Uses the real disposable Store/retention/CSV fixtures. Only the trusted
clock and a labelled lock-timing seam are injected; no successful result is faked.
"""

import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.database import models as m
from app.database.store import Store
from app.leads.projection import CsvProjector, ProjectionRun
from app.leads.projection_files import (
    CSV_NAME,
    LOCK_NAME,
    MANIFEST_NAME,
    PENDING_NAME,
    ProjectionFiles,
)
from app.operations import retention
from app.operations.retention import RetentionService
from app.operations.retention_graph import MAX_ROWS
from tests.operations.retention_fixtures import RetentionHarness, make_retention_harness
from tests.platform.memory_shortlist_cases import failed_commit
from tests.platform.session_cases import answer
from tests.support.harness import PROJECT
from tests.transactions.conversational_fixtures import begin
from tests.transactions.projection_fixtures import deny_replacement

CLI_PATH = PROJECT / "scripts" / "operations" / "cleanup_retention.py"
PRIVATE_EMAIL = "cli-private-contact@example.invalid"
PRIVATE_TRANSCRIPT = "CLI_PRIVATE_BUYER_TRANSCRIPT_SENTINEL"
UNRESOLVED = {"state": "unresolved", "code": "RETENTION_NOT_VERIFIED"}
INSPECTION_KEYS = {
    "generation",
    "cutoff",
    "owner_id",
    "scope_after_owner_id",
    "next_after_owner_id",
    "digest",
    "changes",
    "protected_records",
    "unresolved_authorities",
    "expired_leads_present",
    "export_reconciliation",
    "protected_expired_leads",
    "protected_expired_reasons",
}
CANONICAL_KEYS = {
    "generation",
    "cutoff",
    "owner_id",
    "changes",
    "changed",
    "export_reconciliation",
    "canonical_version",
    "protected_expired_leads",
    "protected_expired_reasons",
}
PROTECTION_REASON_CODES = {
    "session_retention_active",
    "lead_retention_active",
    "draft_retained",
    "booking_retention_active",
    "outcome_replay_active",
    "review_retention_active",
    "unresolved_review",
    "unresolved_collection_command",
    "command_receipt_active",
    "protection_unclassified",
}
PUBLICATION_KEYS = {
    "state",
    "store_generation",
    "canonical_version",
    "published_version",
    "row_count",
    "filename",
    "code",
    "status_persisted",
}


def assert_protected_expiry(value: dict[str, Any]) -> None:
    count = value["protected_expired_leads"]
    reasons = value["protected_expired_reasons"]
    assert type(count) is int and 0 <= count <= MAX_ROWS
    assert isinstance(reasons, list) and len(reasons) <= len(PROTECTION_REASON_CODES)
    codes: list[str] = []
    total = 0
    for entry in reasons:
        assert isinstance(entry, list) and len(entry) == 2
        code, reason_count = entry
        assert isinstance(code, str) and code in PROTECTION_REASON_CODES
        assert type(reason_count) is int and 1 <= reason_count <= count
        codes.append(code)
        total += reason_count
    assert codes == sorted(set(codes))
    assert (count == 0) == (reasons == [])
    assert total >= count


@pytest.fixture
def cli() -> ModuleType:
    # Load the delivered script itself without invoking its __main__ branch.
    spec = importlib.util.spec_from_file_location("retention_cli_contract", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class CliHarness:
    flow: RetentionHarness
    main: Callable[[list[str] | None], int]

    def arguments(
        self,
        *extra: str,
        store: Path | str | None = None,
        generation: str | None = None,
    ) -> list[str]:
        current = self.flow.projection.store
        return [
            "--store",
            str(current.path if store is None else store),
            "--expected-generation",
            current.generation if generation is None else generation,
            *extra,
        ]

    def exports(self) -> tuple[bool, tuple[tuple[str, bytes | None], ...]]:
        root = self.flow.projection.store.boundary.physical_root / "exports"
        names = (CSV_NAME, MANIFEST_NAME, PENDING_NAME, LOCK_NAME)
        return root.exists(), tuple(
            (name, (root / name).read_bytes() if (root / name).exists() else None) for name in names
        )

    def private_message(self) -> None:
        base = self.flow.projection.leads.sessions
        admitted = begin(base, self.flow.projection.leads.session_ids[0])
        assert admitted.ticket is not None
        base.service.complete(base.context(), admitted.ticket, answer(admitted, PRIVATE_TRANSCRIPT))

    def expired_publication(self) -> None:
        self.private_message()
        self.flow.projection.save(email=PRIVATE_EMAIL)
        assert self.flow.projection.projector.repair_once().state == "current"
        assert PRIVATE_EMAIL.encode() in self.flow.projection.files.path(CSV_NAME).read_bytes()
        self.flow.projection.leads.sessions.clock.value += timedelta(days=90)

    def output(
        self,
        capsys: pytest.CaptureFixture[str],
        argv: list[str],
    ) -> tuple[int, dict[str, Any]]:
        code = self.main(argv)
        captured = capsys.readouterr()
        assert captured.err == "" and len(captured.out.splitlines()) == 1
        value = json.loads(captured.out)
        assert isinstance(value, dict)
        self.assert_private_output(captured.out)
        if value["state"] == "inspection":
            assert set(value) == {"state", "inspection"}
            assert set(value["inspection"]) == INSPECTION_KEYS
            assert_protected_expiry(value["inspection"])
        elif value["state"] == "applied":
            assert set(value) == {"state", "result", "next_after_owner_id"}
            result = value["result"]
            assert set(result) == {"canonical", "publication", "derived_state", "code"}
            assert set(result["canonical"]) == CANONICAL_KEYS
            assert_protected_expiry(result["canonical"])
            if result["publication"] is not None:
                assert set(result["publication"]) == PUBLICATION_KEYS
        else:
            assert value == UNRESOLVED
        return code, value

    def assert_private_output(self, output: str) -> None:
        base = self.flow.projection.leads.sessions
        for secret in (
            PRIVATE_EMAIL,
            PRIVATE_TRANSCRIPT,
            str(base.store.path),
            json.dumps(str(base.store.path))[1:-1],
            *(buyer.cookie for buyer in base.buyers),
            *(buyer.identity.csrf_token for buyer in base.buyers),
        ):
            assert secret not in output
        for private_field in ("values_json", "email_value", "phone_value", "result_json"):
            assert private_field not in output


@pytest.fixture
def h(cli: ModuleType, monkeypatch: pytest.MonkeyPatch) -> CliHarness:
    flow = make_retention_harness(monkeypatch)

    def actual_service(store: Store) -> RetentionService:
        # CLI has no clock argument: inject only time, retaining real methods/Store.
        return RetentionService(store, clock=flow.projection.leads.sessions.clock.now)

    monkeypatch.setattr(cli, "RetentionService", actual_service)
    return CliHarness(flow, cast(Callable[[list[str] | None], int], cli.main))


def test_default_inspection_preserves_expired_canonical_facts_and_csv_bytes(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    h.expired_publication()
    before, exports = h.flow.facts(), h.exports()
    database = h.flow.projection.store.path.read_bytes()
    code, result = h.output(capsys, h.arguments("--owner", h.flow.owners[0]))
    assert code == 0 and result["state"] == "inspection"
    inspected = result["inspection"]
    assert inspected["owner_id"] == h.flow.owners[0]
    assert inspected["generation"] == h.flow.projection.store.generation
    assert ["delete.leads", 1] in inspected["changes"]
    assert inspected["expired_leads_present"] and inspected["export_reconciliation"]
    assert inspected["protected_expired_leads"] == 0
    assert inspected["protected_expired_reasons"] == []
    assert h.flow.facts() == before and h.exports() == exports
    assert h.flow.projection.store.path.read_bytes() == database


def test_default_inspection_never_creates_missing_exports_directory(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before, exports = h.flow.facts(), h.exports()
    assert not exports[0]
    code, result = h.output(capsys, h.arguments())
    assert code == 0 and result["state"] == "inspection"
    assert result["inspection"]["protected_expired_leads"] == 0
    assert result["inspection"]["protected_expired_reasons"] == []
    assert h.flow.facts() == before and h.exports() == exports


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--store"],
        ["--expected-generation"],
        ["--store", "unused.sqlite3", "--expected-generation", "unused", "--unknown-option"],
        [
            "--store",
            "unused.sqlite3",
            "--expected-generation",
            "unused",
            "--owner",
            "first",
            "--after-owner",
            "second",
        ],
    ],
)
def test_malformed_arguments_exit_two_before_any_store_access(
    cli: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("ARGUMENT_ERROR_OPENED_STORE")

    monkeypatch.setattr(cli, "open_store", forbidden)
    with pytest.raises(SystemExit) as stopped:
        cli.main(arguments)
    assert stopped.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "usage:" in captured.err and "error:" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("boundary", ["missing", "physical_only", "relative", "volume_root"])
def test_invalid_runtime_boundary_returns_closed_error_without_mutation(
    h: CliHarness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    boundary: str,
) -> None:
    before, exports = h.flow.facts(), h.exports()
    if boundary in {"missing", "physical_only"}:
        monkeypatch.delenv("CSA_RUNTIME_ROOT", raising=False)
        if boundary == "missing":
            monkeypatch.delenv("CSA_RUNTIME_PHYSICAL_ROOT", raising=False)
    else:
        root = (
            "relative-private-boundary"
            if boundary == "relative"
            else h.flow.projection.store.path.anchor
        )
        monkeypatch.setenv("CSA_RUNTIME_ROOT", root)
        monkeypatch.delenv("CSA_RUNTIME_PHYSICAL_ROOT", raising=False)
    code, result = h.output(capsys, h.arguments("--apply"))
    assert code == 1 and result == UNRESOLVED
    assert h.flow.facts() == before and h.exports() == exports


@pytest.mark.parametrize("path_kind", ["relative", "outside", "absent"])
def test_invalid_or_absent_store_is_not_created(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
    path_kind: str,
) -> None:
    root = h.flow.projection.store.boundary.physical_root
    paths = {
        "relative": "relative-private-store.sqlite3",
        "outside": root / "outside-private-store.sqlite3",
        "absent": root / "stores" / "absent-private-store.sqlite3",
    }
    before, exports = h.flow.facts(), h.exports()
    target = Path(paths[path_kind])
    assert not target.exists()
    code, result = h.output(capsys, h.arguments("--apply", store=target))
    assert code == 1 and result == UNRESOLVED and not target.exists()
    assert h.flow.facts() == before and h.exports() == exports


@pytest.mark.parametrize(
    "generation",
    [
        "00000000-0000-0000-0000-000000000000",
        "PRIVATE_GENERATION_TEXT",
    ],
)
def test_wrong_or_malformed_generation_is_closed_and_does_not_apply(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
    generation: str,
) -> None:
    h.expired_publication()
    before, exports = h.flow.facts(), h.exports()
    code, result = h.output(capsys, h.arguments("--apply", generation=generation))
    assert code == 1 and result == UNRESOLVED
    assert generation not in json.dumps(result)
    assert h.flow.facts() == before and h.exports() == exports


@pytest.mark.parametrize("scope", ["--owner", "--after-owner"])
def test_malformed_scope_is_private_and_does_not_apply(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
    scope: str,
) -> None:
    before, exports = h.flow.facts(), h.exports()
    code, result = h.output(capsys, h.arguments(scope, PRIVATE_EMAIL, "--apply"))
    assert code == 1 and result == UNRESOLVED
    assert h.flow.facts() == before and h.exports() == exports


def test_read_only_owner_cursor_visits_each_owner_and_preserves_exhaustion(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before, exports = h.flow.facts(), h.exports()
    first, second = sorted(h.flow.owners)
    code, page = h.output(capsys, h.arguments())
    assert code == 0 and page["inspection"]["owner_id"] == first
    assert page["inspection"]["next_after_owner_id"] == first
    assert page["inspection"]["protected_expired_leads"] == 0
    assert page["inspection"]["protected_expired_reasons"] == []
    code, page = h.output(capsys, h.arguments("--after-owner", first))
    assert code == 0 and page["inspection"]["owner_id"] == second
    assert page["inspection"]["next_after_owner_id"] is None
    assert page["inspection"]["protected_expired_leads"] == 0
    assert page["inspection"]["protected_expired_reasons"] == []
    code, empty = h.output(capsys, h.arguments("--after-owner", second))
    assert code == 0 and empty["inspection"]["owner_id"] is None
    assert empty["inspection"]["scope_after_owner_id"] == second
    assert empty["inspection"]["changes"] == []
    assert empty["inspection"]["protected_expired_leads"] == 0
    assert empty["inspection"]["protected_expired_reasons"] == []
    assert h.flow.facts() == before and h.exports() == exports


def test_explicit_absent_owner_cannot_become_another_owner_cleanup(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    h.private_message()
    h.flow.projection.leads.sessions.clock.value += timedelta(days=7)
    absent = str(uuid4())
    before, exports = h.flow.facts(), h.exports()
    code, applied = h.output(capsys, h.arguments("--owner", absent, "--apply"))
    result = applied["result"]
    assert code == 0 and result["derived_state"] == "not_needed"
    assert result["canonical"]["owner_id"] == absent
    assert not result["canonical"]["changed"] and result["canonical"]["changes"] == []
    assert h.flow.facts() == before and h.exports() == exports


def test_explicit_apply_not_needed_cleans_actual_expired_transcript_without_csv(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    h.private_message()
    h.flow.projection.leads.sessions.clock.value += timedelta(days=7)
    before_exports = h.exports()
    code, applied = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    result = applied["result"]
    assert code == 0 and result["derived_state"] == "not_needed"
    assert result["publication"] is None and result["canonical"]["changed"]
    assert ["delete.messages", 1] in result["canonical"]["changes"]
    assert (
        h.flow.projection.store.read(
            lambda db: db.scalar(select(func.count()).select_from(m.Message)),
        )
        == 0
    )
    assert h.exports() == before_exports


def test_explicit_apply_current_removes_last_lead_and_publishes_header_only(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    h.expired_publication()
    version = h.flow.projection.metadata()[1]
    code, applied = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    result = applied["result"]
    assert code == 0 and result["derived_state"] == "current"
    assert result["canonical"]["changed"]
    assert result["canonical"]["canonical_version"] == version + 1
    assert result["publication"]["state"] == "current"
    assert result["publication"]["status_persisted"] is True
    assert h.flow.projection.rows() == []
    assert PRIVATE_EMAIL.encode() not in h.flow.projection.files.path(CSV_NAME).read_bytes()
    before = h.flow.facts()
    code, repeated = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    assert code == 0 and repeated["result"]["derived_state"] == "not_needed"
    assert not repeated["result"]["canonical"]["changed"] and h.flow.facts() == before


def test_actual_windows_withdrawal_failure_exits_two_then_repairs_same_version(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    h.expired_publication()
    csv_path = h.flow.projection.files.path(CSV_NAME)
    original = csv_path.read_bytes()
    with deny_replacement(csv_path):
        code, applied = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    result = applied["result"]
    assert code == 2 and result["derived_state"] == "failed"
    assert result["canonical"]["changed"] and result["publication"] is None
    assert result["code"] == "RETENTION_CSV_WITHDRAWAL_FAILED"
    assert csv_path.read_bytes() == original
    assert h.flow.projection.metadata()[0] == "failed"
    assert (
        h.flow.projection.store.read(
            lambda db: db.scalar(select(func.count()).select_from(m.Lead)),
        )
        == 0
    )
    code, repaired = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    assert code == 0 and repaired["result"]["derived_state"] == "current"
    assert (
        repaired["result"]["canonical"]["canonical_version"]
        == result["canonical"]["canonical_version"]
    )
    assert h.flow.projection.rows() == []


def test_actual_postcommit_publication_lock_contention_exits_two_pending(
    h: CliHarness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    h.expired_publication()

    class ContendedProjector(CsvProjector):
        def repair_once(self, *, reconcile_from_generation: str | None = None) -> ProjectionRun:
            # Deterministic timing seam only. Real lock exclusion and real T8 run.
            assert (
                self.store.read(
                    lambda db: db.scalar(select(func.count()).select_from(m.Lead)),
                )
                == 0
            )
            with ProjectionFiles(self.store).lock():
                return super().repair_once(reconcile_from_generation=reconcile_from_generation)

    with monkeypatch.context() as patch:
        patch.setattr(retention, "CsvProjector", ContendedProjector)
        code, applied = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    result = applied["result"]
    assert code == 2 and result["derived_state"] == "pending"
    assert result["canonical"]["changed"] and result["publication"]["state"] == "busy"
    assert result["code"] == "CSV_PUBLISHER_BUSY"
    assert not h.flow.projection.files.path(CSV_NAME).exists()
    assert h.flow.projection.metadata()[0] == "pending"
    code, repaired = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    assert code == 0 and repaired["result"]["derived_state"] == "current"
    assert (
        repaired["result"]["canonical"]["canonical_version"]
        == result["canonical"]["canonical_version"]
    )


def test_commit_failure_exits_one_unresolved_and_keeps_canonical_and_csv(
    h: CliHarness,
    capsys: pytest.CaptureFixture[str],
) -> None:
    h.expired_publication()
    before, exports = h.flow.facts(), h.exports()
    with failed_commit():
        code, result = h.output(capsys, h.arguments("--owner", h.flow.owners[0], "--apply"))
    assert code == 1 and result == UNRESOLVED
    assert h.flow.facts() == before and h.exports() == exports


@pytest.mark.parametrize(("arguments", "expected"), [(["--help"], 0), ([], 2)])
def test_delivered_script_entrypoint_exit_codes_without_store(
    arguments: list[str],
    expected: int,
) -> None:
    # Actual __main__ process mapping, with no Store action. Sequential and bounded.
    result = subprocess.run(
        [sys.executable, str(CLI_PATH), *arguments],
        cwd=PROJECT,
        env={**os.environ, "PYTHONPATH": str(PROJECT / "backend"), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == expected
    if expected == 0:
        assert "--apply" in result.stdout and "--expected-generation" in result.stdout
        assert result.stderr == ""
    else:
        assert result.stdout == "" and "required" in result.stderr
    assert "Traceback" not in result.stdout + result.stderr
