"""One genuine two-process recovery case; synthetic data, real Store and CSV files."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from tests.support.harness import PROJECT, configured_runtime_boundary

CHILD_TIMEOUT_SECONDS = 90
CRASH_EXIT_CODE = 73


def require(condition: bool, message: str) -> None:
    # Avoid pytest assertion rewriting of captured private child output or receipts.
    if not condition:
        raise AssertionError(message)


def test_fresh_process_recovers_committed_viewing_after_csv_before_manifest() -> None:
    configured = configured_runtime_boundary()
    # Same exclusive physical sub-boundary convention as projection_fixtures.
    root = configured.physical_root / "test-stores" / ("p-" + uuid4().hex[:16])
    environment = dict(os.environ)
    for name in tuple(environment):
        if name.startswith("CSA_") or name in {"GEMINI_API_KEY", "GOOGLE_API_KEY"}:
            environment.pop(name)
    environment.update(
        CSA_RUNTIME_ROOT=str(root),
        CSA_RUNTIME_PHYSICAL_ROOT=str(root),
        PYTHONPATH=str(PROJECT / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUTF8="1",
    )
    helper = Path(__file__).with_name("projection_restart_child.py")

    def child(mode: str, payload: str | None = None) -> subprocess.CompletedProcess[str]:
        # run() kills and waits for its exact child on timeout. No shell or grandchildren.
        # Never put captured output in assertion errors: its handoff includes a synthetic
        # owner credential carried only over these inherited private process pipes.
        return subprocess.run(
            [sys.executable, "-B", str(helper), mode],
            cwd=PROJECT,
            env=environment,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CHILD_TIMEOUT_SECONDS,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            check=False,
        )

    first = child("commit-and-crash")
    require(first.returncode == CRASH_EXIT_CODE, "First child did not reach the exact crash boundary")
    require(not first.stderr, "First child emitted unexpected diagnostics")
    receipt = json.loads(first.stdout)
    require(receipt["phase"] == "committed-csv-replaced-before-manifest", "Wrong crash phase")
    require(receipt["synthetic_only"] is True, "Unexpected nonsynthetic receipt")
    require(receipt["counts"] == [1, 1, 1, 1, 1], "Unexpected committed row counts")
    require(receipt["pid"] != os.getpid(), "Crash did not occur in a child process")

    # First run has returned/reaped before a fresh interpreter receives the original
    # locator/credential. Nothing creates another owner, draft, operation key or Store.
    second = child("recover", first.stdout)
    require(second.returncode == 0, "Fresh-process recovery failed")
    require(not second.stderr, "Recovery child emitted unexpected diagnostics")
    result = json.loads(second.stdout)
    require(result["phase"] == "recovered-original-operation", "Wrong recovery phase")
    require(result["pid"] not in {os.getpid(), receipt["pid"]}, "Recovery did not use a fresh process")
    require(result["generation"] == receipt["generation"], "Store generation changed")
    require(result["operation_key"] == receipt["terminal"]["operation_key"], "Operation key changed")
    require(result["booking_id"] == receipt["terminal"]["booking"]["booking_id"], "Booking changed")
    require(result["lead_id"] == receipt["terminal"]["lead"]["lead_id"], "Lead changed")
    require(result["counts"] == receipt["counts"], "Recovered row counts changed")
    require(result["canonical_unchanged"] is True, "Canonical rows changed")
    require(result["csv_rows"] == result["projection_version"] == 1, "Unexpected CSV publication")
    require(result["status_reads_unchanged"] is True, "Status reads changed the Store")
    # Retain the exclusive Store and fault/recovery files for existing runner evidence.
