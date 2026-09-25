"""Explicit local restore and interrupted-restore reconciliation. Never an app hook."""

import argparse
import json
import os

from app.database.maintenance import MaintenanceError
from app.database.paths import boundary_from_environment, parse_runtime_path
from app.database.store import StoreError
from app.operations.restore_operator import RestoreService
from app.operations.restore_observation import RestoreObservation
from app.operations.restore_retention import ProtectedRetentionError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True)
    actions = parser.add_subparsers(dest="action", required=True)
    apply = actions.add_parser("apply")
    apply.add_argument("--backup-id", required=True)
    apply.add_argument("--expected-generation", required=True)
    actions.add_parser("inspect")
    resume = actions.add_parser("resume")
    resume.add_argument("--restore-id")
    arguments = parser.parse_args(argv)
    try:
        boundary = boundary_from_environment(os.environ)
        if boundary is None:
            raise ValueError("RESTORE_BOUNDARY_REQUIRED")
        service = RestoreService(parse_runtime_path(arguments.store), boundary=boundary)
        if arguments.action == "apply":
            result = service.restore_observed(arguments.backup_id, expected_generation=arguments.expected_generation)
        elif arguments.action == "resume":
            result = service.resume_observed(restore_id=arguments.restore_id)
        else:
            result = service.inspect()
        print(json.dumps({"state": "no_pending_restore"} if result is None
                         else result.model_dump(mode="json"), sort_keys=True))
        return 1 if isinstance(result, RestoreObservation) and result.projection != "current" else 0
    except ProtectedRetentionError as exc:
        print(json.dumps({
            "state": "unresolved", "code": "RESTORE_RETENTION_PROTECTED_EXPIRED_LEADS",
            "expired_leads": exc.expired_leads, "protection_reasons": exc.reasons,
            "restore_id": exc.restore_id,
            "next_action": "inspect_then_reconcile_original_authority",
        }, sort_keys=True))
        return 1
    except (MaintenanceError, StoreError, OSError, ValueError):
        # An interrupted step may have committed its swap. Never say rolled back,
        # retry a fresh restore, remove its marker or reveal private/path values.
        print(json.dumps({"state": "unresolved", "code": "RESTORE_NOT_VERIFIED",
                          "next_action": "inspect_then_resume_original_restore"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
