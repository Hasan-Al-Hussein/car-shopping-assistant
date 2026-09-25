"""Explicit local viewing-rules operation; inert on import and never a buyer route.

Use the selected backend interpreter with PROJECT/backend on PYTHONPATH, after
the coordinated RuntimeBoundary and Inventory consumer application. Both commands
require the original operation identity and expectations; reconcile never writes.
"""

import argparse
import json
import os
from pathlib import Path

from app.database.paths import boundary_from_environment
from app.operations.viewing_configuration import (
    ActivationError,
    ActivationRequest,
    ViewingConfigurationOperator,
)

PROJECT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("activate", "reconcile"))
    # Preserve raw strings: the shared path parser must see dot/traversal evidence.
    parser.add_argument("--store", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--expected-generation", required=True)
    parser.add_argument("--configuration-id", required=True)
    parser.add_argument(
        "--expected-active-configuration",
        required=True,
        help="Exact current ID, or the literal 'absent' for no ActiveRules row.",
    )
    parser.add_argument("--expected-revision", required=True, type=int)
    parser.add_argument(
        "--bundle",
        required=True,
        help="Project-relative direct child of Records/build/BE-05/I7/runs.",
    )
    parser.add_argument("--receipt-sha256", required=True)
    args = parser.parse_args(argv)
    request: ActivationRequest | None = None
    try:
        request = ActivationRequest(
            operation_id=args.operation_id,
            generation=args.expected_generation,
            configuration_id=args.configuration_id,
            expected_active_version=(
                None
                if args.expected_active_configuration == "absent"
                else args.expected_active_configuration
            ),
            expected_revision=args.expected_revision,
            bundle=args.bundle,
            receipt_sha256=args.receipt_sha256,
        )
        boundary = boundary_from_environment(os.environ)
        if boundary is None:
            raise ActivationError("ACTIVATION_RUNTIME_BOUNDARY_REQUIRED")
        operator = ViewingConfigurationOperator(args.store, boundary=boundary, project_root=PROJECT)
        if args.command == "reconcile":
            observed = operator.reconcile(request)
            print(
                json.dumps(
                    {
                        "status": "RECORDED" if observed.result is not None else "NOT_RECORDED",
                        "observation": observed.model_dump(mode="json"),
                        "automatic_retry": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        result = operator.activate(request)
    except ActivationError as exc:
        print(
            json.dumps(
                {
                    "status": "ACTIVATION_NOT_CONFIRMED",
                    "safe_code": str(exc),
                    "operation_id": None if request is None else request.operation_id,
                    "automatic_retry": False,
                }
            )
        )
        return 1
    except (OSError, ValueError, RuntimeError):
        print(
            json.dumps(
                {
                    "status": "ACTIVATION_NOT_CONFIRMED",
                    "safe_code": "ACTIVATION_INPUT_OR_STATE_UNAVAILABLE",
                    "operation_id": None if request is None else request.operation_id,
                    "automatic_retry": False,
                }
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "status": "ACTIVATION_OUTCOME_UNRESOLVED",
                    "operation_id": None if request is None else request.operation_id,
                    "automatic_retry": False,
                }
            )
        )
        return 1

    try:
        receipt = operator.publish_receipt(result)
    except Exception:
        # Store.write already returned. Receipt failure cannot roll the commit back.
        print(
            json.dumps(
                {
                    "status": "ACTIVATION_COMMITTED_RECEIPT_UNAVAILABLE",
                    "result": result.model_dump(mode="json"),
                    "automatic_retry": False,
                },
                ensure_ascii=False,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": "ACTIVATION_RECORDED",
                "result": result.model_dump(mode="json"),
                "receipt": receipt.relative_to(operator.project).as_posix(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
