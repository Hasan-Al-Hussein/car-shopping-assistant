"""Explicit adopted configuration activation; no startup hook or buyer authority.

Targets the selected RuntimeBoundary API, which requires coordinated application.
File preparation/admission and receipt publication stay outside the atomic writer.
"""

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from app.api.schemas.common import Digest, Id, Revision, ShortText, UtcInstant
from app.core.config import VIEWING_VENUE, DemoPolicy, FrozenSettings
from app.core.readiness import InventoryObservation
from app.database.paths import RuntimeBoundary, guarded_store_path, parse_runtime_path
from app.database.store import Store, assert_outside_write_transaction, open_store
from app.identity.service import utc_text
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.read_identity import MAX_REFERENCE_BATCH
from app.inventory.references import ImmutableInventoryRef
from app.inventory.resource_lineage import ReviewedResourceMapping, lineage_version
from app.inventory.staging_plan import STAGING_POLICY_VERSION
from app.operations.restore_completion import (
    CompletedRestoreObservation,
    CompletedRestoreScope,
    RestoreCompletionError,
    completed_restore_scope,
    recheck_completed_restore_metadata,
)
from app.operations.restored_bundle_contract import (
    RESTORED_BUNDLE_ROOT,
    RestoredBundleReceipt,
    same_restore_association,
)
from app.sessions.state import canonical
from app.viewings.draft_configuration import (
    MAX_CONFIGURATION_BYTES,
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
    load_configuration,
    parse_configuration,
)
from app.viewings.eligibility import EligibilityPolicy
from app.viewings.scheduling import ViewingRules
from pydantic import Field, StringConstraints, model_validator
from sqlalchemy.orm import Session

MAX_REVISION = 2_147_483_647
MAX_RECEIPT_BYTES = 16_384
MAX_EVENT_BYTES = 4_096
EVENT_TYPE = "viewing_configuration_activation_v1"
NAMESPACE = "provided-cars-cleaned"
SNAPSHOT = "5fe31b5951317db6d77b6786596861e32ccd2442f2f5f98927d57e6b4a2092f3"
ADOPTED = "Records/build/G-03/simulation-configuration-adopted/"
BE04 = "Records/build/BE-04/"
# Explicitly reviewed producer versions; never derive adoption from current bytes.
SUPPORTED_PRODUCERS = frozenset(
    {
        "1c89258d0b75455f2f64af7397a3b26c3d5c995bc7821a68f362cb38e1b265c8",
        "e707efa672e0e3153af89c7a092eb2b3153c7e6fa73ba900c490a2c8a39cf318",
        "e143d072d79690f5113cf10e7e4a83c1e0fe347241569a290775a60a38508abd",
    }
)
# Explicitly reviewed restored producer; never learn adoption from current bytes.
SUPPORTED_RESTORED_PRODUCERS = frozenset(
    {"d931067b0f1bff49ad27f18b5421360a46f07c74c5bf0d1a68b798ef9f86975b"}
)
MAPPING_DIGEST = "610528e05a01eb55ccac626568f97d6454dfdbc5ac402fa6d6521512181fccf5"
WORKBOOK = "sources/Copy_of_sample_cars_dataset.xlsx"
WORKBOOK_DIGEST = "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9"
# These reviewed pins are authority; a bundle cannot choose replacement pins.
PINNED = {
    ADOPTED + "resource-mappings.json": MAPPING_DIGEST,
    ADOPTED
    + "eligibility-policy.json": "aa8f51505ae834c0d361feb6702caee0112b7c3a57e41d9524db22a657e79f54",
    ADOPTED + "configuration-material.json": (
        "24e34aa787af8dffb2808b342da8a7517ffe67deec4d6bdd60c5b771168f013e"
    ),
    ADOPTED + "adoption.json": "2578dd1e06150e3c3526a31f5b888b161b9186a9270844b3b8b2952af724cdff",
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
}
PIN_LENGTHS = {
    ADOPTED + "resource-mappings.json": 81_385,
    ADOPTED + "eligibility-policy.json": 13_648,
    ADOPTED + "configuration-material.json": 2_133,
    ADOPTED + "adoption.json": 879,
    BE04 + "final-hash-manifest.json": 23_660,
    BE04 + "evidence/accepted-inventory-integrity.json": 1_920,
    BE04 + "evidence/claim-ledger.json": 2_031_889,
    BE04 + "evidence/coverage.json": 667_320,
    BE04 + "evidence/resolved-facts.json": 1_181_087,
}
ConfigurationId = Annotated[
    str, StringConstraints(strict=True, pattern=r"^viewing-config-1:[0-9a-f]{64}$")
]
Bundle = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=(
            r"^(?:Records/build/BE-05/I7/runs/[A-Za-z0-9][A-Za-z0-9_-]{0,79}"
            r"|Records/build/OP-02/T12-restored-readmission/runs/"
            r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$"
        ),
    ),
]


class ActivationError(ValueError):
    """Closed operator code; never include raw paths, material or private exceptions."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ActivationError(code)


class ActivationRequest(FrozenSettings):
    operation_id: Id
    generation: Id
    configuration_id: ConfigurationId
    expected_active_version: ConfigurationId | None
    expected_revision: Revision
    bundle: Bundle
    receipt_sha256: Digest

    @model_validator(mode="after")
    def absent_pointer(self) -> Self:
        if self.expected_active_version is None and self.expected_revision != 0:
            raise ValueError("ABSENT_POINTER_REQUIRES_ZERO_REVISION")
        return self


class ActivationResult(FrozenSettings):
    request: ActivationRequest
    revision: Revision
    changed: bool
    committed_at: UtcInstant

    @model_validator(mode="after")
    def transition(self) -> Self:
        changed = self.request.configuration_id != self.request.expected_active_version
        if self.changed != changed or self.revision != self.request.expected_revision + int(
            changed
        ):
            raise ValueError("ACTIVATION_RESULT_TRANSITION_INVALID")
        return self


class Reconciliation(FrozenSettings):
    result: ActivationResult | None
    active_version: ConfigurationId | None
    active_revision: Revision


class _Event(FrozenSettings):
    format: Literal["viewing-activation-event-1"]
    result: ActivationResult


class _Receipt(FrozenSettings):
    status: Literal["INVENTORY_ACTIVATED_RULES_ACTIVATION_PENDING"]
    rules_activation: Literal["NOT_RUN"]
    reader_admission: Literal["NOT_RUN"]
    application_launch: Literal["NOT_RUN"]
    simulation_only: Literal[True]
    destination: Annotated[str, Field(min_length=1, max_length=4096)]
    disposable_fixture: bool
    started_at: Annotated[str, Field(min_length=1, max_length=40)]
    completed_at: Annotated[str, Field(min_length=1, max_length=40)]
    store_generation: Id
    schema_version: Literal["0002"]
    inventory: InventoryObservation
    listing_count: Annotated[int, Field(strict=True, ge=0, le=100)]
    evidence_count: Annotated[int, Field(strict=True, ge=0, le=20_000)]
    stage_payload_sha256: Digest
    mapping_digest: Digest
    configuration_file: Literal["pending-viewing-configuration.json"]
    configuration_sha256: Digest
    configuration_bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_CONFIGURATION_BYTES)]
    configuration_id: ConfigurationId
    eligibility_version: ShortText
    input_hashes: Annotated[dict[ShortText, Digest], Field(max_length=64)]
    bootstrap_source_sha256: Digest


@dataclass(frozen=True, slots=True)
class AdoptedViewingMaterial:
    rules: ViewingRules
    eligibility: EligibilityPolicy
    mappings: tuple[ReviewedResourceMapping, ...]
    source_hashes: dict[str, str]


@dataclass(frozen=True, slots=True)
class _Pending:
    request: ActivationRequest
    config: ViewingConfiguration
    receipt: _Receipt | RestoredBundleReceipt
    adoption: AdoptedViewingMaterial


@dataclass(frozen=True, slots=True)
class _Member:
    ref: ImmutableInventoryRef
    resource_id: str
    mapping_version: str
    resource_version: str


@dataclass(frozen=True, slots=True)
class _Proof:
    refs: tuple[ImmutableInventoryRef, ...]
    token: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Prepared:
    pending: _Pending
    proofs: tuple[_Proof, ...]
    members: tuple[_Member, ...]


def _distinct(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "DUPLICATE_OPERATOR_JSON_KEY")
        result[key] = value
    return result


def _json(raw: bytes) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_distinct)
    except (UnicodeError, ValueError, RecursionError):
        raise ActivationError("OPERATOR_JSON_INVALID") from None


def _relative_parts(relative: str) -> tuple[str, ...]:
    _require(type(relative) is str and len(relative) <= 512, "OPERATOR_PATH_INVALID")
    parts = tuple(relative.split("/"))
    _require(
        bool(parts)
        and all(
            part not in ("", ".", "..")
            and not part.endswith((".", " "))
            and not any(char in part for char in "\\:\x00")
            and not os.path.isreserved(part)
            for part in parts
        ),
        "OPERATOR_PATH_INVALID",
    )
    return parts


def _project_path(project: Path, relative: str, *, missing: bool = False) -> Path:
    parts = _relative_parts(relative)
    base = project.resolve(strict=True)
    _require(base.is_dir(), "PROJECT_BOUNDARY_INVALID")
    path = base
    for part in parts:
        path = path / part
        if not path.exists():
            _require(missing and not path.is_symlink(), "OPERATOR_FILE_MISSING")
            continue
        info = path.lstat()
        _require(
            not path.is_symlink() and path.resolve(strict=True) == path,
            "OPERATOR_PATH_REDIRECTION",
        )
        _require(
            not stat.S_ISREG(info.st_mode) or info.st_nlink == 1,
            "OPERATOR_FILE_HARDLINK",
        )
    return path


def _read_file(project: Path, relative: str, limit: int) -> bytes:
    path = _project_path(project, relative)
    _require(path.is_file(), "OPERATOR_FILE_NOT_REGULAR")
    with path.open("rb") as stream:
        info = os.fstat(stream.fileno())
        _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "OPERATOR_FILE_NOT_REGULAR")
        raw = stream.read(limit + 1)
    _require(1 <= len(raw) <= limit, "OPERATOR_FILE_SIZE")
    _require(_project_path(project, relative) == path, "OPERATOR_PATH_REDIRECTION")
    return raw


def _adoption(project: Path) -> AdoptedViewingMaterial:
    raw: dict[str, bytes] = {}
    for relative, digest in PINNED.items():
        material = _read_file(project, relative, PIN_LENGTHS[relative])
        _require(hashlib.sha256(material).hexdigest() == digest, "ADOPTED_SOURCE_CHANGED")
        raw[relative] = material
    material = _json(raw[ADOPTED + "configuration-material.json"])
    policy = DemoPolicy.model_validate_json(canonical(material["policy"]))
    rules = ViewingRules(policy)
    eligibility = EligibilityPolicy.model_validate_json(raw[ADOPTED + "eligibility-policy.json"])
    mappings = tuple(
        ReviewedResourceMapping.model_validate_json(canonical(item))
        for item in _json(raw[ADOPTED + "resource-mappings.json"])
    )
    _require(
        lineage_version(mappings) == MAPPING_DIGEST
        and material["adopted_lineage_digest"] == MAPPING_DIGEST
        and material["simulation_only"] is True
        and material["first_stage_only"] is True
        and material["calendar_version"] == rules.version
        and material["venue_label"] == VIEWING_VENUE
        and material["snapshot_identity"] == {"namespace": NAMESPACE, "snapshot_id": SNAPSHOT}
        and len(mappings) == len(eligibility.eligible_refs) == 100
        and {item.ref for item in mappings} == set(eligibility.eligible_refs)
        and len({item.resource_id for item in mappings}) == 100,
        "ADOPTED_MATERIAL_INVALID",
    )
    hashes = dict(PINNED)
    manifest = _json(raw[BE04 + "final-hash-manifest.json"])
    integrity = _json(raw[BE04 + "evidence/accepted-inventory-integrity.json"])
    hashes.update(
        {
            item["path"]: item["sha256"]
            for item in manifest["entries"]
            if item["path"].startswith("backend/app/")
        }
    )
    hashes.update(
        {
            item["file"]: item["expected_sha256"]
            for item in integrity
            if item["file"].startswith("backend/app/")
        }
    )
    hashes[WORKBOOK] = WORKBOOK_DIGEST
    return AdoptedViewingMaterial(rules, eligibility, mappings, hashes)


def read_adopted_viewing_material(project_root: Path) -> AdoptedViewingMaterial:
    """Read the existing exact adoption pins; no bundle or Store authority is inferred."""
    assert_outside_write_transaction()
    return _adoption(project_root)


def _pending(project: Path, store: Store, request: ActivationRequest) -> _Pending:
    adopted = _adoption(project)
    encoded = _read_file(
        project, request.bundle + "/pending-viewing-configuration.json", MAX_CONFIGURATION_BYTES
    )
    raw_receipt = _read_file(project, request.bundle + "/receipt.json", MAX_RECEIPT_BYTES)
    _require(
        hashlib.sha256(raw_receipt).hexdigest() == request.receipt_sha256,
        "EXPECTED_RECEIPT_MISMATCH",
    )
    receipt_material = canonical(_json(raw_receipt))
    receipt: _Receipt | RestoredBundleReceipt
    if request.bundle.startswith(RESTORED_BUNDLE_ROOT):
        receipt = RestoredBundleReceipt.model_validate_json(receipt_material)
        _require(receipt_material == raw_receipt, "RECEIPT_CANONICAL_MISMATCH")
        _require(
            receipt.request.operation_id == request.operation_id
            and receipt.request.bundle == request.bundle
            and receipt.request.expected_generation == request.generation
            and request.expected_active_version is None
            and request.expected_revision == 0,
            "RESTORED_ACTIVATION_REQUEST_MISMATCH",
        )
        supported_producer = receipt.producer_source_sha256 in SUPPORTED_RESTORED_PRODUCERS
    else:
        receipt = _Receipt.model_validate_json(receipt_material)
        supported_producer = receipt.bootstrap_source_sha256 in SUPPORTED_PRODUCERS
    _require(
        canonical(receipt.model_dump(mode="json")) == receipt_material, "RECEIPT_CANONICAL_MISMATCH"
    )
    config = parse_configuration(
        encoded.decode("utf-8"),
        rules=adopted.rules,
        observation=receipt.inventory,
        namespace=NAMESPACE,
    )
    target = guarded_store_path(
        parse_runtime_path(receipt.destination), boundary=store.boundary, must_exist=True
    )
    selected = guarded_store_path(store.path, boundary=store.boundary, must_exist=True)
    directory = "test-stores" if receipt.disposable_fixture else "stores"
    started = datetime.fromisoformat(receipt.started_at)
    completed = datetime.fromisoformat(receipt.completed_at)
    _require(
        target == selected
        and target.is_relative_to(store.boundary.physical_root / directory)
        and receipt.store_generation == store.generation == request.generation
        and receipt.inventory.generation == request.generation
        and receipt.inventory.active_revision == 1
        and receipt.schema_version == store.schema_version
        and supported_producer
        and receipt.input_hashes == adopted.source_hashes
        and receipt.listing_count == 100
        and receipt.mapping_digest == config.mapping_digest == MAPPING_DIGEST
        and receipt.configuration_bytes == len(encoded)
        and receipt.configuration_sha256 == hashlib.sha256(encoded).hexdigest()
        and receipt.configuration_id == configuration_id(config) == request.configuration_id
        and receipt.eligibility_version == eligibility_version(config)
        and config.eligibility == adopted.eligibility
        and config.inventory.snapshot_id == SNAPSHOT
        and canonical(config.model_dump(mode="json")) == encoded
        and started.utcoffset() == completed.utcoffset() == timedelta(0)
        and started <= completed,
        "PENDING_ADOPTION_OR_TARGET_MISMATCH",
    )
    return _Pending(request, config, receipt, adopted)


def _generation(db: Session, expected: str) -> None:
    row = (
        db.connection()
        .exec_driver_sql("SELECT store_generation FROM store_metadata WHERE id=1")
        .first()
    )
    _require(row is not None and row[0] == expected, "ACTIVATION_GENERATION_CHANGED")


def _pointer(db: Session) -> tuple[str | None, int]:
    rows = (
        db.connection()
        .exec_driver_sql(
            "SELECT id,CASE WHEN typeof(version)='text' AND "
            "length(CAST(version AS BLOB)) BETWEEN 1 AND 200 THEN version END,revision "
            "FROM active_rules ORDER BY id LIMIT 2"
        )
        .all()
    )
    if not rows:
        return None, 0
    _require(
        len(rows) == 1
        and rows[0][0] == 1
        and type(rows[0][1]) is str
        and re.fullmatch(r"viewing-config-1:[0-9a-f]{64}", rows[0][1]) is not None
        and type(rows[0][2]) is int
        and 0 <= rows[0][2] <= MAX_REVISION,
        "ACTIVE_CONFIGURATION_POINTER_INVALID",
    )
    return cast(str, rows[0][1]), cast(int, rows[0][2])


def _event(db: Session, request: ActivationRequest) -> ActivationResult | None:
    _generation(db, request.generation)
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT "
            "CASE WHEN typeof(event_type)='text' AND length(CAST(event_type AS BLOB)) "
            "BETWEEN 1 AND 100 THEN event_type END,"
            "CASE WHEN typeof(source_reference)='text' AND length(CAST(source_reference AS BLOB)) "
            "BETWEEN 1 AND 4096 THEN source_reference END,"
            "CASE WHEN typeof(config_reference)='text' AND length(CAST(config_reference AS BLOB)) "
            "BETWEEN 1 AND 200 THEN config_reference END,"
            "CASE WHEN typeof(generation_reference)='text' AND length(generation_reference)=36 "
            "THEN generation_reference END,"
            "CASE WHEN typeof(safe_code)='text' AND length(CAST(safe_code AS BLOB)) "
            "BETWEEN 1 AND 100 THEN safe_code END,"
            "CASE WHEN typeof(created_at)='text' AND length(created_at) BETWEEN 20 AND 27 "
            "THEN created_at END FROM operational_events WHERE id=?",
            (request.operation_id,),
        )
        .first()
    )
    if row is None:
        return None
    _require(row[0] == EVENT_TYPE, "ACTIVATION_OPERATION_ID_CONFLICT")
    _require(all(type(value) is str for value in row), "ACTIVATION_EVENT_INVALID")
    try:
        raw = row[1].encode("utf-8")
        value = _Event.model_validate_json(canonical(_json(raw)))
        _require(canonical(value.model_dump(mode="json")) == raw, "ACTIVATION_EVENT_INVALID")
    except (TypeError, ValueError, RecursionError):
        raise ActivationError("ACTIVATION_EVENT_INVALID") from None
    result = value.result
    _require(result.request == request, "ACTIVATION_OPERATION_ID_CONFLICT")
    code = (
        "VIEWING_CONFIGURATION_ACTIVATED" if result.changed else "VIEWING_CONFIGURATION_UNCHANGED"
    )
    _require(
        row[2] == request.configuration_id
        and row[3] == request.generation
        and row[4] == code
        and row[5] == result.committed_at,
        "ACTIVATION_EVENT_INVALID",
    )
    return result


def _inventory_scalars(db: Session, pending: _Pending) -> None:
    expected = pending.config.inventory
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT m.store_generation,m.schema_version,a.snapshot_id,a.index_version,a.revision,"
            "p.mode,s.namespace,s.index_version,b.serialization_version,b.payload_sha256,"
            "s.accepted_count,(SELECT count(*) FROM attribute_evidence e "
            "WHERE e.namespace=s.namespace AND e.snapshot_id=s.snapshot_id) "
            "FROM store_metadata m LEFT JOIN active_inventory a ON a.id=1 "
            "LEFT JOIN inventory_storage_profile p ON p.id=1 "
            "LEFT JOIN inventory_snapshots s ON s.snapshot_id=a.snapshot_id "
            "LEFT JOIN inventory_snapshot_payloads b ON b.snapshot_id=a.snapshot_id WHERE m.id=1"
        )
        .first()
    )
    _require(
        row is not None
        and type(row[4]) is int
        and tuple(row)
        == (
            pending.request.generation,
            pending.receipt.schema_version,
            expected.snapshot_id,
            expected.index_version,
            expected.active_revision,
            expected.mode,
            NAMESPACE,
            expected.index_version,
            STAGING_POLICY_VERSION,
            pending.receipt.stage_payload_sha256,
            pending.receipt.listing_count,
            pending.receipt.evidence_count,
        ),
        "ACTIVATION_INVENTORY_CHANGED",
    )


def _stage_digest(db: Session, pending: _Pending) -> None:
    row = (
        db.connection()
        .exec_driver_sql(
            "SELECT CASE WHEN json_valid(payload_json) THEN "
            "CASE WHEN json_type(payload_json,'$.mapping_digest')='text' "
            "AND length(json_extract(payload_json,'$.mapping_digest'))=64 "
            "THEN json_extract(payload_json,'$.mapping_digest') END END "
            "FROM inventory_snapshot_payloads WHERE snapshot_id=?",
            (pending.config.inventory.snapshot_id,),
        )
        .first()
    )
    _require(
        row is not None and row[0] == pending.config.mapping_digest,
        "ACTIVATION_STAGE_MAPPING_CHANGED",
    )


def _recheck(db: Session, reader: CompactInventoryReader, prepared: _Prepared) -> None:
    for proof in prepared.proofs:
        reader.recheck_identity(db, proof.token, expected_refs=proof.refs)
    _inventory_scalars(db, prepared.pending)
    for member in prepared.members:
        row = (
            db.connection()
            .exec_driver_sql(
                "SELECT m.resource_id,m.mapping_version,r.mapping_version "
                "FROM listing_resource_mappings m JOIN vehicle_resources r ON r.id=m.resource_id "
                "WHERE m.namespace=? AND m.snapshot_id=? AND m.source_id=?",
                (member.ref.namespace, member.ref.snapshot_id, member.ref.source_id),
            )
            .first()
        )
        _require(
            row is not None
            and tuple(row) == (member.resource_id, member.mapping_version, member.resource_version),
            "ACTIVATION_REVIEWED_RESOURCE_CHANGED",
        )


def _prepare(store: Store, reader: CompactInventoryReader, pending: _Pending) -> _Prepared:
    assert_outside_write_transaction()
    snapshot = pending.config.inventory.snapshot_id
    _require(snapshot is not None, "ACTIVATION_CURRENT_SNAPSHOT_REQUIRED")
    reader.admit(cast(str, snapshot))
    refs = pending.config.eligibility.eligible_refs
    batches = tuple(
        refs[start : start + MAX_REFERENCE_BATCH]
        for start in range(0, len(refs), MAX_REFERENCE_BATCH)
    ) or ((),)
    expected_mappings = {item.ref: item for item in pending.adoption.mappings}
    proofs: list[_Proof] = []
    members: list[_Member] = []
    for batch_refs in batches:
        batch: CompactBatch = reader.read_refs(batch_refs, expected_snapshot_id=snapshot)
        _require(
            batch.observation == pending.config.inventory and len(batch.items) == len(batch_refs),
            "ACTIVATION_INVENTORY_CHANGED",
        )
        for ref, item in zip(batch_refs, batch.items, strict=True):
            _require(
                item.ref == ref
                and item.state == "current"
                and item.listing is not None
                and item.mapping is not None
                and item.mapping == expected_mappings.get(ref)
                and type(item.resource_version) is str,
                "ACTIVATION_REVIEWED_RESOURCE_REQUIRED",
            )
            assert item.mapping is not None and item.resource_version is not None
            members.append(
                _Member(
                    ref,
                    item.mapping.resource_id,
                    item.mapping.mapping_version,
                    item.resource_version,
                )
            )
        proofs.append(_Proof(batch_refs, batch.identity))
    prepared = _Prepared(pending, tuple(proofs), tuple(members))

    def capture(db: Session) -> None:
        _recheck(db, reader, prepared)
        _stage_digest(db, pending)

    store.read(capture)
    return prepared


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _no_checkpoint(phase: str) -> None:
    """Controlled test interleaving only; the production default does nothing."""


class ViewingConfigurationOperator:
    """Trusted explicit local operation, with no public route or automatic activation."""

    def __init__(
        self,
        raw_store_path: str,
        *,
        boundary: RuntimeBoundary,
        project_root: Path,
        clock: Callable[[], datetime] = _utc_now,
        _checkpoint: Callable[[str], None] = _no_checkpoint,
    ) -> None:
        assert_outside_write_transaction()
        self.store = open_store(parse_runtime_path(raw_store_path), boundary=boundary)
        self.project = project_root.resolve(strict=True)
        self._clock = clock
        self._checkpoint = _checkpoint

    def _request(self, request: ActivationRequest) -> ActivationRequest:
        _require(type(request) is ActivationRequest, "ACTIVATION_REQUEST_INVALID")
        validated = ActivationRequest.model_validate_json(
            canonical(request.model_dump(mode="json"))
        )
        _require(validated.generation == self.store.generation, "ACTIVATION_GENERATION_CHANGED")
        # Validate raw relative text even on a terminal lookup; do not normalize it.
        _relative_parts(validated.bundle)
        return validated

    def reconcile(self, request: ActivationRequest) -> Reconciliation:
        """Read only; absence is not a rollback claim and never initiates activation."""
        request = self._request(request)

        def read(db: Session) -> Reconciliation:
            result = _event(db, request)
            version, revision = _pointer(db)
            return Reconciliation(result=result, active_version=version, active_revision=revision)

        return self.store.read(read)

    def activate(self, request: ActivationRequest) -> ActivationResult:
        assert_outside_write_transaction()
        request = self._request(request)
        recorded = self.store.read(lambda db: _event(db, request))
        if recorded is not None:
            return recorded
        pending = _pending(self.project, self.store, request)
        if isinstance(pending.receipt, RestoredBundleReceipt):
            restore = pending.receipt.restore
            try:
                with completed_restore_scope(
                    self.store.path,
                    boundary=self.store.boundary,
                    restore_id=restore.restore_id,
                    expected_receipt_sha256=restore.receipt_sha256,
                    expected_generation=request.generation,
                ) as completed:
                    observed = completed.observation
                    _require(
                        same_restore_association(observed, restore),
                        "RESTORED_COMPLETION_ASSOCIATION_CHANGED",
                    )
                    _require(
                        datetime.fromisoformat(pending.receipt.completed_at)
                        <= datetime.fromisoformat(observed.observed_at),
                        "RESTORED_BUNDLE_FUTURE_OBSERVATION",
                    )
                    return self._activate_pending(pending, completed=completed)
            except RestoreCompletionError as error:
                raise ActivationError("RESTORED_COMPLETION_UNAVAILABLE") from error
        return self._activate_pending(pending)

    def _activate_pending(
        self, pending: _Pending, *, completed: CompletedRestoreScope | None = None
    ) -> ActivationResult:
        reader = CompactInventoryReader(self.store)
        try:
            prepared = _prepare(self.store, reader, pending)
            created_at = utc_text(self._clock())
            self._checkpoint("activation.prepared")
            restoration = None
            if isinstance(pending.receipt, RestoredBundleReceipt):
                _require(completed is not None, "RESTORED_COMPLETION_SCOPE_REQUIRED")
                assert completed is not None
                restoration = completed.revalidate()
                _require(
                    same_restore_association(restoration, pending.receipt.restore),
                    "RESTORED_COMPLETION_ASSOCIATION_CHANGED",
                )
            if restoration is None:
                return self.store.write(lambda db: self._commit(db, reader, prepared, created_at))
            return self.store.write(
                lambda db: self._commit(db, reader, prepared, created_at, restoration)
            )
        finally:
            reader.invalidate()

    def _commit(
        self,
        db: Session,
        reader: CompactInventoryReader,
        prepared: _Prepared,
        created_at: str,
        restoration: CompletedRestoreObservation | None = None,
    ) -> ActivationResult:
        pending, request = prepared.pending, prepared.pending.request
        # A racing exact original operation remains terminal even if inventory moved.
        recorded = _event(db, request)
        if recorded is not None:
            return recorded
        if isinstance(pending.receipt, RestoredBundleReceipt):
            _require(restoration is not None, "RESTORED_COMPLETION_SCOPE_REQUIRED")
            assert restoration is not None
            recheck_completed_restore_metadata(db, restoration)
        _recheck(db, reader, prepared)
        current, revision = _pointer(db)
        _require(
            (current, revision) == (request.expected_active_version, request.expected_revision),
            "ACTIVATION_EXPECTATION_CONFLICT",
        )
        changed = current != request.configuration_id
        _require(not changed or revision < MAX_REVISION, "ACTIVATION_REVISION_EXHAUSTED")
        exists = (
            db.connection()
            .exec_driver_sql(
                "SELECT 1 FROM rule_versions WHERE version=?", (request.configuration_id,)
            )
            .first()
            is not None
        )
        if exists:
            existing = load_configuration(
                db,
                request.configuration_id,
                rules=pending.adoption.rules,
                observation=pending.config.inventory,
                namespace=NAMESPACE,
            )
            _require(existing == pending.config, "IMMUTABLE_CONFIGURATION_CHANGED")
        else:
            db.connection().exec_driver_sql(
                "INSERT INTO rule_versions "
                "(version,policy_version,rules_json,eligibility_version,created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    request.configuration_id,
                    pending.config.policy.version,
                    canonical(pending.config.model_dump(mode="json")).decode("utf-8"),
                    eligibility_version(pending.config),
                    created_at,
                ),
            )
        self._checkpoint("activation.row_staged")
        next_revision = revision + int(changed)
        if changed:
            if current is None:
                db.connection().exec_driver_sql(
                    "INSERT INTO active_rules (id,version,revision) VALUES (1,?,?)",
                    (request.configuration_id, next_revision),
                )
            else:
                updated = db.connection().exec_driver_sql(
                    "UPDATE active_rules SET version=?,revision=? WHERE id=1 AND version=? "
                    "AND revision=?",
                    (request.configuration_id, next_revision, current, revision),
                )
                _require(updated.rowcount == 1, "ACTIVATION_EXPECTATION_CONFLICT")
        self._checkpoint("activation.pointer_staged")
        result = ActivationResult(
            request=request, revision=next_revision, changed=changed, committed_at=created_at
        )
        event = canonical(
            _Event(format="viewing-activation-event-1", result=result).model_dump(mode="json")
        )
        _require(len(event) <= MAX_EVENT_BYTES, "ACTIVATION_EVENT_SIZE")
        code = "VIEWING_CONFIGURATION_ACTIVATED" if changed else "VIEWING_CONFIGURATION_UNCHANGED"
        db.connection().exec_driver_sql(
            "INSERT INTO operational_events "
            "(id,created_at,event_type,source_reference,config_reference,"
            "generation_reference,safe_code) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                request.operation_id,
                created_at,
                EVENT_TYPE,
                event.decode("utf-8"),
                request.configuration_id,
                request.generation,
                code,
            ),
        )
        self._checkpoint("activation.event_staged")
        return result

    def publish_receipt(self, result: ActivationResult) -> Path:
        """After commit only; failures leave the original event reconcilable."""
        assert_outside_write_transaction()
        request = self._request(result.request)
        recorded = self.store.read(lambda db: _event(db, request))
        _require(recorded == result, "ACTIVATION_RECORDED_RESULT_REQUIRED")
        relative = f"Records/operations/viewing-configurations/{request.operation_id}.json"
        raw = canonical(
            {"format": "viewing-activation-receipt-1", "result": result.model_dump(mode="json")}
        )
        _require(len(raw) <= MAX_EVENT_BYTES, "ACTIVATION_RECEIPT_SIZE")
        target = _project_path(self.project, relative, missing=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _project_path(self.project, relative, missing=True)
        if target.exists():
            _require(
                _read_file(self.project, relative, MAX_EVENT_BYTES) == raw,
                "ACTIVATION_RECEIPT_CONFLICT",
            )
            return target
        self._checkpoint("receipt.before_write")
        with target.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _project_path(self.project, relative)
        return target
