"""Explicit first-instance operator bootstrap; inert on import, never an API route.

Run with the approved backend interpreter and PROJECT/backend on PYTHONPATH.
The returned configuration is pending Transactions activation. This module does
not admit a reader, configure rules, enable a provider, or start an application.
"""

import argparse
import hashlib
import json
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import VIEWING_VENUE, DemoPolicy
from app.core.readiness import InventoryObservation
from app.database.paths import (
    COMPANIONS,
    RuntimeBoundary,
    boundary_from_environment,
    guarded_store_path,
    initialize_runtime_root,
    parse_runtime_path,
    validate_store_location,
)
from app.database.store import Store, initialize_store
from app.inventory.extraction import ExtractedCandidate, extract_reviewed
from app.inventory.import_reader import SourceSpec, read_workbook
from app.inventory.normalization import normalize_candidate
from app.inventory.resource_lineage import ReviewedResourceMapping, lineage_version
from app.inventory.review_catalogue import PUBLIC_FAMILIES
from app.inventory.snapshot_codec import prepare_candidate
from app.inventory.snapshots import InventoryRepository, StageReceipt
from app.inventory.source_catalogue import provided_source_catalogue
from app.sessions.state import canonical
from app.viewings.draft_configuration import (
    MAX_CONFIGURATION_BYTES,
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
    parse_configuration,
)
from app.viewings.eligibility import EligibilityPolicy
from app.viewings.scheduling import ViewingRules

PROJECT = Path(__file__).resolve().parents[1]
RECORDS = PROJECT / "Records/build/BE-05/I7"
ADOPTED = "Records/build/G-03/simulation-configuration-adopted/"
BE04 = "Records/build/BE-04/"
NAMESPACE = "provided-cars-cleaned"
SNAPSHOT = "5fe31b5951317db6d77b6786596861e32ccd2442f2f5f98927d57e6b4a2092f3"
WORKBOOK = "sources/Copy_of_sample_cars_dataset.xlsx"
WORKBOOK_SHA256 = "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9"
MAPPING_SHA256 = "610528e05a01eb55ccac626568f97d6454dfdbc5ac402fa6d6521512181fccf5"
PINNED_INPUTS = {
    BE04 + "final-hash-manifest.json": (
        "56a3d6ac1d896ee1285a6c0381d374b9d6e7d9dc2e32041912c659802f4315b4"
    ),
    BE04 + "evidence/accepted-inventory-integrity.json": (
        "36065f06e99e06e50816a5e0135a8ace6c8e00f7c6f5a647fa3bac0ecf6ebf0a"
    ),
    BE04 + "evidence/claim-ledger.json": (
        "ba33a9c2af1ccff6bcd035e66089ab969fdcae7089e2d6fbdf441590d9d3fada"
    ),
    BE04
    + "evidence/coverage.json": "f29085de572f3d8ca16f46e51baaecd85da6f3ebbeda163aeb7d2605ece7d75c",
    BE04 + "evidence/resolved-facts.json": (
        "923dca87c7573303967740f6870600471509946df57b3573c18369422c03d948"
    ),
    ADOPTED + "resource-mappings.json": MAPPING_SHA256,
    ADOPTED
    + "eligibility-policy.json": "aa8f51505ae834c0d361feb6702caee0112b7c3a57e41d9524db22a657e79f54",
    ADOPTED + "configuration-material.json": (
        "24e34aa787af8dffb2808b342da8a7517ffe67deec4d6bdd60c5b771168f013e"
    ),
    ADOPTED + "adoption.json": "2578dd1e06150e3c3526a31f5b888b161b9186a9270844b3b8b2952af724cdff",
}


class BootstrapError(ValueError):
    """Closed local-operator reason code; no raw rejected payload or exception."""


@dataclass(frozen=True)
class BootstrapInputs:
    candidate: ExtractedCandidate
    mappings: tuple[ReviewedResourceMapping, ...]
    policy: DemoPolicy
    eligibility: EligibilityPolicy
    mapping_digest: str
    source_hashes: dict[str, str]


@dataclass(frozen=True)
class BootstrapResult:
    store: Store
    inventory: InventoryObservation
    stage: StageReceipt
    mapping_digest: str
    pending_configuration: ViewingConfiguration
    evidence_directory: Path


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BootstrapError(code)


def _read_verified(relative: str, expected: str) -> bytes:
    raw = (PROJECT / relative).read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == expected, "INPUT_BYTES_CHANGED")
    return raw


def load_inputs() -> BootstrapInputs:
    """Validate adopted material and reproduce the accepted candidate before writes."""
    raw = {name: _read_verified(name, digest) for name, digest in PINNED_INPUTS.items()}
    source_hashes = dict(PINNED_INPUTS)
    manifest = json.loads(raw[BE04 + "final-hash-manifest.json"])
    integrity = json.loads(raw[BE04 + "evidence/accepted-inventory-integrity.json"])
    pipeline = {
        entry["path"]: entry["sha256"]
        for entry in manifest["entries"]
        if entry["path"].startswith("backend/app/")
    }
    pipeline.update(
        {
            entry["file"]: entry["expected_sha256"]
            for entry in integrity
            if entry["file"].startswith("backend/app/")
        }
    )
    for name, digest in pipeline.items():
        _read_verified(name, digest)
    source_hashes.update(pipeline)
    _read_verified(WORKBOOK, WORKBOOK_SHA256)
    source_hashes[WORKBOOK] = WORKBOOK_SHA256

    source = read_workbook(PROJECT / WORKBOOK, SourceSpec(expected_sha256=WORKBOOK_SHA256))
    candidate = extract_reviewed(normalize_candidate(source), provided_source_catalogue())
    _require(
        candidate.manifest.snapshot_id == SNAPSHOT
        and candidate.manifest.namespace == NAMESPACE
        and len(candidate.records) == 100
        and len(candidate.normalized_source.audit_records) == 100
        and source.report.source_unchanged,
        "ACCEPTED_CANDIDATE_IDENTITY_MISMATCH",
    )
    for name, actual in (
        ("claim-ledger.json", candidate.evidence_ledger()),
        ("coverage.json", candidate.coverage_report()),
    ):
        _require(
            canonical(actual) == canonical(json.loads(raw[BE04 + "evidence/" + name])),
            "ACCEPTED_CANDIDATE_CONTENT_MISMATCH",
        )
    facts = json.loads(raw[BE04 + "evidence/resolved-facts.json"])["records"]
    _require(len(facts) == len(candidate.records), "ACCEPTED_FACT_COUNT_MISMATCH")
    for listing, expected in zip(candidate.records, facts, strict=True):
        _require(
            listing.normalized.ref.model_dump() == expected["ref"]
            and {family: listing.fact(family).public_fact() for family in PUBLIC_FAMILIES}
            == expected["public_facts"],
            "ACCEPTED_PUBLIC_FACTS_CHANGED",
        )

    mappings = tuple(
        ReviewedResourceMapping.model_validate_json(canonical(item))
        for item in json.loads(raw[ADOPTED + "resource-mappings.json"])
    )
    mapping_digest = lineage_version(mappings)
    # Equality is tested after real model serialization; file SHA is not assumed to be lineage.
    _require(mapping_digest == MAPPING_SHA256, "ADOPTED_LINEAGE_CANONICAL_MISMATCH")
    material = json.loads(raw[ADOPTED + "configuration-material.json"])
    policy = DemoPolicy.model_validate_json(canonical(material["policy"]))
    eligibility = EligibilityPolicy.model_validate_json(raw[ADOPTED + "eligibility-policy.json"])
    _require(
        canonical(eligibility.model_dump(mode="json")) == raw[ADOPTED + "eligibility-policy.json"],
        "ADOPTED_ELIGIBILITY_CANONICAL_MISMATCH",
    )
    prepared = prepare_candidate(candidate)
    refs = {listing.ref for listing in prepared.listings}
    evidence = {item.evidence_id: item.ref for item in prepared.evidence}
    _require(
        len(mappings) == 100
        and {item.ref for item in mappings} == refs
        and len({item.resource_id for item in mappings}) == 100
        and set(eligibility.eligible_refs) == refs
        and all(
            item.decision == "reviewed_new_resource"
            and item.predecessor_ref is None
            and all(evidence.get(key) == item.ref for key in item.source_evidence_ids)
            for item in mappings
        ),
        "ADOPTED_EXACT_REFERENCE_OR_EVIDENCE_MISMATCH",
    )
    rules = ViewingRules(policy)
    _require(
        material["simulation_only"] is True
        and material["first_stage_only"] is True
        and material["adopted_lineage_digest"] == mapping_digest
        and material["snapshot_identity"] == {"namespace": NAMESPACE, "snapshot_id": SNAPSHOT}
        and material["calendar_version"] == rules.version
        and material["venue_label"] == VIEWING_VENUE,
        "ADOPTED_CONFIGURATION_MISMATCH",
    )
    return BootstrapInputs(candidate, mappings, policy, eligibility, mapping_digest, source_hashes)


def _destination(path: Path, *, boundary: RuntimeBoundary, disposable_fixture: bool) -> Path:
    resolved = guarded_store_path(path, boundary=boundary, must_exist=False)
    directory = "test-stores" if disposable_fixture else "stores"
    _require(
        resolved.is_relative_to(boundary.physical_root / directory),
        "EXPLICIT_DESTINATION_ROUTE_REQUIRED",
    )
    _require(
        not resolved.exists()
        and not any(Path(str(resolved) + suffix).exists() for suffix in COMPANIONS),
        "EXISTING_INSTANCE_REFUSED",
    )
    return resolved


def _evidence_destination(path: Path) -> Path:
    allowed = RECORDS / "runs"
    _require(allowed.resolve().is_relative_to(PROJECT.resolve()), "EVIDENCE_REDIRECTION")
    _require(
        path.is_absolute() and path.is_relative_to(allowed) and path != allowed,
        "EVIDENCE_OUTSIDE_I7_RUNS",
    )
    _require(not path.exists(), "EXISTING_EVIDENCE_REFUSED")
    # OneDrive may itself be a reparse-backed parent; enforce resolved containment
    # and reject redirection strictly below the already selected evidence boundary.
    _require(path.resolve().is_relative_to(allowed.resolve()), "EVIDENCE_REDIRECTION")
    for part in (path, *path.parents):
        if part == allowed:
            break
        if part.exists():
            info = part.lstat()
            _require(
                not part.is_symlink()
                and not (
                    getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                ),
                "EVIDENCE_REDIRECTION",
            )
    return path


def _write_new(path: Path, material: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(material)
        stream.flush()
        os.fsync(stream.fileno())


def _utc_now() -> datetime:
    return datetime.now(UTC)


def bootstrap_inventory(
    destination: Path,
    *,
    boundary: RuntimeBoundary,
    evidence_directory: Path,
    disposable_fixture: bool = False,
    initialize_runtime: bool = False,
    clock: Callable[[], datetime] = _utc_now,
) -> BootstrapResult:
    """Provision only a new explicit instance; failures retain all partial state."""
    validate_store_location(destination, boundary=boundary)
    directory = "test-stores" if disposable_fixture else "stores"
    _require(
        any(
            destination.is_relative_to(root / directory)
            for root in (boundary.logical_root, boundary.physical_root)
        ),
        "EXPLICIT_DESTINATION_ROUTE_REQUIRED",
    )
    output = _evidence_destination(evidence_directory)
    inputs = load_inputs()
    started = clock()
    _require(started.utcoffset() == timedelta(0), "UTC_CLOCK_REQUIRED")
    # Explicit root creation follows all pure route and adopted input checks.
    target = destination
    phase = "runtime_root"
    evidence_created = False
    store: Store | None = None
    observation: InventoryObservation | None = None
    try:
        if initialize_runtime:
            initialize_runtime_root(boundary)
        phase = "destination"
        target = _destination(destination, boundary=boundary, disposable_fixture=disposable_fixture)
        phase = "evidence_directory"
        output.mkdir(parents=True, exist_ok=False)
        evidence_created = True
        phase = "initialize"
        # initialize_store creates/upgrades the NEW store to the supported schema.
        # Existing stores never reach this call; reserve_new_store also uses O_EXCL.
        store = initialize_store(target, boundary=boundary)
        repository = InventoryRepository(store, clock=clock)
        phase = "prepare"
        plan = repository.prepare(
            inputs.candidate, policy_version=inputs.policy.version, mappings=inputs.mappings
        )
        _require(plan.mapping_digest == inputs.mapping_digest, "STAGE_MAPPING_CHANGED")
        phase = "stage"
        staged = repository.stage(plan)
        _require(staged.listing_count == 100 and not staged.reused, "STAGE_IDENTITY_MISMATCH")
        phase = "activate_inventory"
        observation = repository.activate(staged.snapshot_id, expected_revision=0)
        phase = "observe_inventory"
        active = repository.active()
        _require(
            active.observation == observation and active.stage == plan,
            "OBSERVED_INVENTORY_MISMATCH",
        )
        phase = "pending_configuration"
        configuration = ViewingConfiguration(
            format="viewing-configuration-1",
            calendar_version=ViewingRules(inputs.policy).version,
            policy=inputs.policy,
            venue_label=VIEWING_VENUE,
            eligibility=inputs.eligibility,
            inventory=observation,
            mapping_digest=plan.mapping_digest,
        )
        encoded = canonical(configuration.model_dump(mode="json"))
        _require(len(encoded) <= MAX_CONFIGURATION_BYTES, "CONFIGURATION_SIZE")
        parsed = parse_configuration(
            encoded.decode("utf-8"),
            rules=ViewingRules(inputs.policy),
            observation=observation,
            namespace=NAMESPACE,
        )
        _require(
            canonical(parsed.model_dump(mode="json")) == encoded, "CONFIGURATION_ROUNDTRIP_MISMATCH"
        )
        phase = "save_receipt"
        _write_new(output / "pending-viewing-configuration.json", encoded)
        receipt = {
            "status": "INVENTORY_ACTIVATED_RULES_ACTIVATION_PENDING",
            "rules_activation": "NOT_RUN",
            "reader_admission": "NOT_RUN",
            "application_launch": "NOT_RUN",
            "simulation_only": True,
            "destination": str(target),
            "disposable_fixture": disposable_fixture,
            "started_at": started.isoformat(),
            "completed_at": clock().isoformat(),
            "store_generation": store.generation,
            "schema_version": store.schema_version,
            "inventory": observation.model_dump(mode="json"),
            "listing_count": staged.listing_count,
            "evidence_count": staged.evidence_count,
            "stage_payload_sha256": staged.payload_sha256,
            "mapping_digest": plan.mapping_digest,
            "configuration_file": "pending-viewing-configuration.json",
            "configuration_sha256": hashlib.sha256(encoded).hexdigest(),
            "configuration_bytes": len(encoded),
            "configuration_id": configuration_id(parsed),
            "eligibility_version": eligibility_version(parsed),
            "input_hashes": inputs.source_hashes,
            "bootstrap_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        _write_new(output / "receipt.json", canonical(receipt))
        return BootstrapResult(store, observation, staged, plan.mapping_digest, parsed, output)
    except Exception:
        if not evidence_created:
            # No evidence directory is created just to report failed admission.
            # Any partial root remains untouched for explicit operator inspection.
            raise BootstrapError("BOOTSTRAP_ADMISSION_FAILED_STATE_PRESERVED") from None
        failure = {
            "status": "FAILED_INSTANCE_PRESERVED",
            "failed_phase": phase,
            "destination": str(target),
            "store_exists": target.exists(),
            "store_generation": None if store is None else store.generation,
            "inventory": None if observation is None else observation.model_dump(mode="json"),
            "rules_activation": "NOT_RUN",
            "retry_same_destination": False,
            "note": "Partial instance retained. No repair, overwrite or new target selected.",
        }
        try:
            _write_new(output / "failure.json", canonical(failure))
        except OSError:
            raise BootstrapError("FAILED_INSTANCE_PRESERVED_RECEIPT_UNAVAILABLE") from None
        raise BootstrapError("FAILED_INSTANCE_PRESERVED") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--evidence-directory", required=True, type=Path)
    parser.add_argument(
        "--initialize-runtime-root",
        dest="initialize_runtime",
        action="store_true",
        help="Explicitly initialize an ordinary configured runtime root after input validation.",
    )
    parser.add_argument(
        "--disposable-fixture",
        action="store_true",
        help="Explicitly select the existing approved test-stores boundary.",
    )
    args = parser.parse_args()
    try:
        boundary = boundary_from_environment(os.environ)
        if boundary is None:
            raise BootstrapError("EXPLICIT_RUNTIME_ROOT_REQUIRED")
        result = bootstrap_inventory(
            parse_runtime_path(args.destination),
            boundary=boundary,
            evidence_directory=args.evidence_directory,
            disposable_fixture=args.disposable_fixture,
            initialize_runtime=args.initialize_runtime,
        )
    except (OSError, ValueError, RuntimeError):
        print(
            json.dumps(
                {
                    "status": "BOOTSTRAP_FAILED",
                    "destination": str(args.destination),
                    "evidence_directory": str(args.evidence_directory),
                    "note": "Inspect retained artifacts. Do not overwrite this target.",
                }
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "INVENTORY_ACTIVATED_RULES_ACTIVATION_PENDING",
                "receipt": str(result.evidence_directory / "receipt.json"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
