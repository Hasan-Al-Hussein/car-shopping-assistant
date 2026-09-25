"""Explicit trusted local CSV repair. Inert on import; no buyer endpoint."""

import argparse
import json
import os
from dataclasses import asdict

from app.database.paths import (
    StorePathError,
    boundary_from_environment,
    parse_runtime_path,
)
from app.database.store import StoreError, open_store
from app.leads.projection import CsvProjector
from app.leads.projection_repository import ProjectionError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repair the selected local leads.csv projection.")
    parser.add_argument("--store", required=True, help="Existing explicit canonical SQLite path")
    parser.add_argument(
        "--reconcile-from-generation",
        help="Explicit original publication generation after a separately completed fenced restore",
    )
    arguments = parser.parse_args(argv)
    try:
        boundary = boundary_from_environment(os.environ)
        if boundary is None:
            raise ProjectionError("CSV_RUNTIME_BOUNDARY_REQUIRED")
        store = open_store(parse_runtime_path(arguments.store), boundary=boundary)
        result = CsvProjector(store).repair_once(
            reconcile_from_generation=arguments.reconcile_from_generation
        )
    except (OSError, StorePathError, StoreError, ProjectionError):
        print(json.dumps({"state": "failed", "code": "CSV_REPAIR_UNAVAILABLE"}))
        return 1
    # Closed status only: no canonical rows, contacts, transcript, cookies or credentials.
    print(json.dumps(asdict(result), sort_keys=True))
    return 0 if result.state in {"current", "empty"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
