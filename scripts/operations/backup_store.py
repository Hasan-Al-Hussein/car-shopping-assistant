"""Explicit local backup, verified inspection and bounded backup expiry."""

import argparse
import json
import os
import sqlite3
from dataclasses import asdict

from app.database.paths import StorePathError, boundary_from_environment, parse_runtime_path
from app.database.store import StoreError, open_store
from app.operations.backup_files import BackupError
from app.operations.backup_restore import BackupService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operate only verified backups of one existing Store.")
    parser.add_argument("--store", required=True)
    parser.add_argument("--expected-generation", required=True)
    command = parser.add_subparsers(dest="operation", required=True)
    command.add_parser("create", help="Explicitly create a SQLite API backup and accepted manifest")
    inspect = command.add_parser("inspect", help="Verify one immutable backup without restoring it")
    inspect.add_argument("--backup-id", required=True)
    expiry = command.add_parser("expiry", help="Inspect seven-day expiry; default does not delete")
    expiry_action = expiry.add_mutually_exclusive_group()
    expiry_action.add_argument("--apply", action="store_true", help="Delete the freshly verified expired pairs")
    expiry_action.add_argument("--resume", action="store_true", help="Reconcile recorded interrupted pair deletions")
    args = parser.parse_args(argv)
    try:
        boundary = boundary_from_environment(os.environ)
        if boundary is None:
            raise BackupError("BACKUP_RUNTIME_BOUNDARY_REQUIRED")
        store = open_store(parse_runtime_path(args.store), boundary=boundary)
        if store.generation != args.expected_generation:
            raise BackupError("BACKUP_GENERATION_CHANGED")
        service = BackupService(store)
        if args.operation == "create":
            value = service.create()
            print(json.dumps({"state": "created", "manifest": value.model_dump(mode="json")}, sort_keys=True))
        elif args.operation == "inspect":
            observed = service.inspect(args.backup_id)
            print(json.dumps({"state": observed.state, "pinned": observed.pinned,
                              "manifest": observed.manifest.model_dump(mode="json")}, sort_keys=True))
        else:
            if args.resume:
                removed = service.resume_expiry()
                print(json.dumps({"state": "expiry_reconciled", "backup_ids": removed}, sort_keys=True))
                return 0
            plan = service.inspect_expiry()
            if args.apply:
                removed = service.apply_expiry(plan)
                print(json.dumps({"state": "expired_pairs_removed", "backup_ids": removed}, sort_keys=True))
            else:
                print(json.dumps({"state": "expiry_inspection", "inspection": asdict(plan)}, sort_keys=True))
        return 0
    except (OSError, sqlite3.DatabaseError, StorePathError, StoreError, BackupError):
        # A partial failed file operation is not advertised as an all-or-none rollback.
        print(json.dumps({"state": "unresolved", "code": "BACKUP_NOT_VERIFIED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
