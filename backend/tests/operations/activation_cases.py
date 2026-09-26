"""Future I9 disposable tests; no original project source is edited by fixtures.

Pending receipts here are explicit synthetic producer-format fixtures over real
accepted inventory. They do not prove the portable bootstrap CLI emitted them.
"""

import hashlib
import shutil
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from scripts.bootstrap_inventory import PINNED_INPUTS, BootstrapInputs, load_inputs
from sqlalchemy.orm import Session

from app.core.config import VIEWING_VENUE
from app.database.maintenance import shared_store_lease
from app.database.paths import (
    RuntimeBoundary,
    guarded_store_path,
    initialize_runtime_root,
)
from app.database.store import Store, initialize_store
from app.inventory.snapshots import InventoryRepository
from app.operations.viewing_configuration import ActivationRequest, ViewingConfigurationOperator
from app.sessions.state import canonical
from app.viewings.draft_configuration import (
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
)
from app.viewings.scheduling import ViewingRules
from tests.support.harness import PROJECT, configured_runtime_boundary, runtime_environment

RUN_ID = str(uuid4())
NOW = datetime(2026, 9, 24, 5, tzinfo=UTC)
ACCEPTED_PRODUCER = "1c89258d0b75455f2f64af7397a3b26c3d5c995bc7821a68f362cb38e1b265c8"


@dataclass
class ActivationCase:
    store: Store
    project: Path
    config: ViewingConfiguration
    request: ActivationRequest
    receipt: dict[str, Any]

    def operator(
        self,
        checkpoint: Callable[[str], None] = lambda phase: None,
        *,
        now: datetime = NOW,
    ) -> ViewingConfigurationOperator:
        return ViewingConfigurationOperator(
            str(self.store.path),
            boundary=self.store.boundary,
            project_root=self.project,
            clock=lambda: now,
            _checkpoint=checkpoint,
        )

    def repack(self, raw: bytes, **receipt_changes: Any) -> ActivationRequest:
        """Changed tests supply a consistent hash/receipt; adoption must still reject."""
        digest = hashlib.sha256(raw).hexdigest()
        self.receipt.update(
            configuration_bytes=len(raw),
            configuration_sha256=digest,
            configuration_id="viewing-config-1:" + digest,
        )
        self.receipt.update(receipt_changes)
        folder = self.project / self.request.bundle
        (folder / "pending-viewing-configuration.json").write_bytes(raw)
        receipt_raw = canonical(self.receipt)
        (folder / "receipt.json").write_bytes(receipt_raw)
        self.request = self.request.model_copy(
            update={
                "configuration_id": self.receipt["configuration_id"],
                "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
            }
        )
        return self.request


@pytest.fixture(scope="session")
def adopted_inputs() -> BootstrapInputs:
    return load_inputs()


@pytest.fixture(scope="session")
def operator_project() -> Path:
    project = PROJECT / "Records/build/OP-02/I9/test-runs" / RUN_ID / "p"
    project.mkdir(parents=True, exist_ok=False)
    for relative in PINNED_INPUTS:
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / relative, target)
    return project


@pytest.fixture
def activation_case(
    request: pytest.FixtureRequest,
    adopted_inputs: BootstrapInputs,
    operator_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ActivationCase:
    suffix = hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    configured = configured_runtime_boundary()
    case_id = hashlib.sha256((RUN_ID + ":" + request.node.nodeid).encode()).hexdigest()[:10]
    relative_root = Path("t") / case_id
    boundary = RuntimeBoundary(
        configured.logical_root / relative_root, configured.physical_root / relative_root
    )
    destination = boundary.logical_root / "test-stores" / "store.sqlite3"
    # Validate the adopted mapping before provisioning its short physical child.
    guarded_store_path(
        configured.logical_root / "test-stores" / "boundary-probe.sqlite3",
        boundary=configured,
        must_exist=False,
    )
    initialize_runtime_root(RuntimeBoundary(boundary.physical_root, boundary.physical_root))
    for key, value in runtime_environment(boundary).items():
        monkeypatch.setenv(key, value)
    store = initialize_store(destination, boundary=boundary)
    repository = InventoryRepository(store, clock=lambda: NOW)
    plan = repository.prepare(
        adopted_inputs.candidate,
        policy_version=adopted_inputs.policy.version,
        mappings=adopted_inputs.mappings,
    )
    stage = repository.stage(plan)
    observation = repository.activate(stage.snapshot_id, expected_revision=0)
    config = ViewingConfiguration(
        format="viewing-configuration-1",
        calendar_version=ViewingRules(adopted_inputs.policy).version,
        policy=adopted_inputs.policy,
        venue_label=VIEWING_VENUE,
        eligibility=adopted_inputs.eligibility,
        inventory=observation,
        mapping_digest=plan.mapping_digest,
    )
    encoded = canonical(config.model_dump(mode="json"))
    receipt = {
        "status": "INVENTORY_ACTIVATED_RULES_ACTIVATION_PENDING",
        "rules_activation": "NOT_RUN",
        "reader_admission": "NOT_RUN",
        "application_launch": "NOT_RUN",
        "simulation_only": True,
        "destination": str(store.path),
        "disposable_fixture": True,
        "started_at": NOW.isoformat(),
        "completed_at": NOW.isoformat(),
        "store_generation": store.generation,
        "schema_version": store.schema_version,
        "inventory": observation.model_dump(mode="json"),
        "listing_count": stage.listing_count,
        "evidence_count": stage.evidence_count,
        "stage_payload_sha256": stage.payload_sha256,
        "mapping_digest": plan.mapping_digest,
        "configuration_file": "pending-viewing-configuration.json",
        "configuration_sha256": hashlib.sha256(encoded).hexdigest(),
        "configuration_bytes": len(encoded),
        "configuration_id": configuration_id(config),
        "eligibility_version": eligibility_version(config),
        "input_hashes": adopted_inputs.source_hashes,
        "bootstrap_source_sha256": ACCEPTED_PRODUCER,
    }
    bundle = "Records/build/BE-05/I7/runs/" + suffix
    folder = operator_project / bundle
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "pending-viewing-configuration.json").write_bytes(encoded)
    receipt_bytes = canonical(receipt)
    (folder / "receipt.json").write_bytes(receipt_bytes)
    intent = ActivationRequest(
        operation_id=str(uuid4()),
        generation=store.generation,
        configuration_id=configuration_id(config),
        expected_active_version=None,
        expected_revision=0,
        bundle=bundle,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
    )
    return ActivationCase(store, operator_project, config, intent, receipt)


def sql(store: Store, statements: tuple[tuple[str, tuple[object, ...]], ...]) -> None:
    def write(db: Session) -> None:
        for statement, parameters in statements:
            db.connection().exec_driver_sql(statement, parameters)

    store.write(write)


def stored_state(store: Store) -> dict[str, tuple[tuple[object, ...], ...]]:
    """Bounded read-only evidence even when a negative test corrupts Store metadata."""
    with shared_store_lease(store.path, boundary=store.boundary):
        path = guarded_store_path(store.path, boundary=store.boundary, must_exist=True)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            return {
                table: tuple(
                    tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")
                )
                for table in (
                    "rule_versions",
                    "active_rules",
                    "operational_events",
                    "bookings",
                    "booking_drafts",
                    "booking_reviews",
                    "leads",
                    "lead_bookings",
                    "export_intents",
                    "export_state",
                )
            }


def business_state(store: Store) -> dict[str, tuple[tuple[object, ...], ...]]:
    return {
        name: rows
        for name, rows in stored_state(store).items()
        if name not in {"rule_versions", "active_rules", "operational_events"}
    }
