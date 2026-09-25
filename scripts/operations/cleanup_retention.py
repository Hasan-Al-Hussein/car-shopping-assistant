"""Trusted local policy cleanup. Default is inspection; --apply is explicit."""

import argparse
import json
import os
from dataclasses import asdict

from app.database.paths import StorePathError, boundary_from_environment, parse_runtime_path
from app.database.store import StoreError, open_store
from app.leads.projection_repository import ProjectionError
from app.operations.retention import RetentionService
from app.operations.retention_graph import RetentionError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or apply one bounded owner retention batch.")
    parser.add_argument("--store", required=True, help="Existing explicitly selected canonical SQLite file")
    parser.add_argument("--expected-generation", required=True, help="Reviewed current store generation")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--owner", help="One exact owner UUID; trusted local operator only")
    scope.add_argument("--after-owner", help="Exclusive owner cursor from a prior inspection")
    parser.add_argument("--apply", action="store_true", help="Apply the freshly inspected batch and reconcile CSV")
    args = parser.parse_args(argv)
    try:
        boundary = boundary_from_environment(os.environ)
        if boundary is None:
            raise RetentionError("RETENTION_RUNTIME_BOUNDARY_REQUIRED")
        store = open_store(parse_runtime_path(args.store), boundary=boundary)
        if args.expected_generation != store.generation:
            raise RetentionError("RETENTION_GENERATION_CHANGED")
        service = RetentionService(store)
        inspection = service.inspect(owner_id=args.owner, after_owner_id=args.after_owner)
        if not args.apply:
            print(json.dumps({"state": "inspection", "inspection": asdict(inspection)}, sort_keys=True))
            return 0
        result = service.apply(inspection)
        print(json.dumps({"state": "applied", "result": asdict(result),
                          "next_after_owner_id": inspection.next_after_owner_id}, sort_keys=True))
        return 0 if result.derived_state in {"current", "not_needed"} else 2
    except (OSError, StorePathError, StoreError, ProjectionError, RetentionError):
        # A transport/commit exception must not be advertised as a definite rollback.
        # Reinspect canonical state; never infer cleanup or publication success.
        print(json.dumps({"state": "unresolved", "code": "RETENTION_NOT_VERIFIED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
