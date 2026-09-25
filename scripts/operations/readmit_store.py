"""Explicit restored-inventory/viewing readmission with one retained original UUID."""

import argparse
import json
import os
from pathlib import Path

from app.core.config import load_settings
from app.database.paths import boundary_from_environment
from app.operations.restored_readmission import (
    ReadmissionRequest, readmitted_runtime, run_readmission,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--restore-id", required=True)
    parser.add_argument("--restore-receipt-sha256", required=True)
    parser.add_argument("--expected-generation", required=True)
    parser.add_argument("--runtime-audit", action="store_true")
    args = parser.parse_args(argv)
    original_operation: str | None = None
    try:
        boundary = boundary_from_environment(os.environ)
        if boundary is None:
            raise ValueError("READMISSION_BOUNDARY_REQUIRED")
        request = ReadmissionRequest(
            operation_id=args.operation_id, restore_id=args.restore_id,
            restore_receipt_sha256=args.restore_receipt_sha256,
            expected_generation=args.expected_generation,
        )
        original_operation = request.operation_id
        project = Path(args.project)
        if args.runtime_audit:
            settings = load_settings({**os.environ, "CSA_STORE_PATH": args.store})
            with readmitted_runtime(settings, project_root=project, request=request) as (_, result):
                output = {"format": "readmission-operator-result-1",
                          "runtime": "audited_and_closed", "result": result.model_dump(mode="json")}
            # Emit only after the actual fresh composition settled successfully.
            print(json.dumps(output, sort_keys=True))
            return 0
        result = run_readmission(
            args.store, boundary=boundary, project_root=project, request=request,
        )
        print(json.dumps({"format": "readmission-operator-result-1", "runtime": "not_started",
                          "result": result.model_dump(mode="json")}, sort_keys=True))
        known = result.viewing.result
        current = (known is not None
                   and result.current_viewing.state == "ready"
                   and result.viewing.active_version == known.request.configuration_id
                   and result.viewing.active_revision == known.revision
                   and result.current_csv is not None and result.current_csv.projection == "current")
        return 0 if current else 1
    except (RuntimeError, OSError, ValueError):
        print(json.dumps({"state": "unresolved", "code": "READMISSION_NOT_VERIFIED",
                          "operation_id": original_operation,
                          "next_action": "reconcile_same_original_request"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
