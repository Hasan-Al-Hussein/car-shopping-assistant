"""Explicit restored-inventory audit and immutable bundle publication; no DB writes."""

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.core.config import VIEWING_VENUE
from app.core.errors import ApiFailure
from app.database.paths import RuntimeBoundary, guarded_store_path, parse_runtime_path
from app.database.store import Store, StoreError, assert_outside_write_transaction, open_store
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.read_identity import MAX_REFERENCE_BATCH
from app.inventory.references import ImmutableInventoryRef
from app.inventory.resource_lineage import lineage_version
from app.inventory.snapshot_codec import digest_text
from app.inventory.snapshots import InventoryRepository
from app.inventory.staging_plan import STAGING_POLICY_VERSION, PreparedStage, stage_payload
from app.operations.restore_completion import RestoreCompletionError, completed_restore_scope
from app.operations.restored_bundle_contract import (
    MAX_RESTORED_RECEIPT_BYTES,
    RestoredBundleReceipt,
    RestoredBundleRequest,
    RestoredBundleResult,
    same_restore_association,
)
from app.operations.viewing_configuration import (
    AdoptedViewingMaterial,
    read_adopted_viewing_material,
)
from app.sessions.state import canonical
from app.viewings.draft_configuration import (
    MAX_CONFIGURATION_BYTES,
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
    parse_configuration,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

_CONFIGURATION = "pending-viewing-configuration.json"
_RECEIPT = "receipt.json"
_MAX_PRODUCER_BYTES = 256 * 1024


class RestoredBundleError(ValueError):
    """A closed producer code without paths, SQL, private facts or raw payloads."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise RestoredBundleError(code)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _guard(path: Path, *, directory: bool = False, missing: bool = False) -> None:
    """Guard the entire configured project chain; never follow a link to provision it."""
    _require(path.is_absolute(), "RESTORED_BUNDLE_PATH_INVALID")
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            _require(missing, "RESTORED_BUNDLE_FILE_MISSING")
            continue
        _require(
            not stat.S_ISLNK(info.st_mode)
            and not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
            "RESTORED_BUNDLE_PATH_REDIRECTED",
        )
        if component != path or directory:
            _require(stat.S_ISDIR(info.st_mode), "RESTORED_BUNDLE_DIRECTORY_REQUIRED")
        else:
            _require(
                stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                "RESTORED_BUNDLE_REGULAR_FILE_REQUIRED",
            )
    _require(path.resolve(strict=not missing) == path, "RESTORED_BUNDLE_PATH_REDIRECTED")


def _file_identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_nlink


def _read_bounded(path: Path, limit: int) -> bytes:
    _guard(path)
    before = path.lstat()
    _require(1 <= before.st_size <= limit, "RESTORED_BUNDLE_FILE_SIZE")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        _require(
            _file_identity(opened) == _file_identity(before),
            "RESTORED_BUNDLE_FILE_CHANGED",
        )
        raw = stream.read(limit + 1)
        _require(
            _file_identity(os.fstat(stream.fileno())) == _file_identity(opened),
            "RESTORED_BUNDLE_FILE_CHANGED",
        )
    _guard(path)
    _require(
        1 <= len(raw) <= limit
        and len(raw) == before.st_size
        and _file_identity(path.lstat()) == _file_identity(before),
        "RESTORED_BUNDLE_FILE_CHANGED",
    )
    return raw


def _write_exclusive(path: Path, raw: bytes, limit: int) -> None:
    _require(1 <= len(raw) <= limit, "RESTORED_BUNDLE_FILE_SIZE")
    _guard(path, missing=True)
    with path.open("xb") as stream:
        opened = os.fstat(stream.fileno())
        _require(
            stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1,
            "RESTORED_BUNDLE_REGULAR_FILE_REQUIRED",
        )
        written = stream.write(raw)
        _require(written == len(raw), "RESTORED_BUNDLE_PARTIAL_WRITE")
        stream.flush()
        os.fsync(stream.fileno())
        final = os.fstat(stream.fileno())
    _guard(path)
    _require(
        _file_identity(path.lstat()) == _file_identity(final)
        and _read_bounded(path, limit) == raw,
        "RESTORED_BUNDLE_FILE_CHANGED",
    )


def _bundle_folder(project: Path, request: RestoredBundleRequest) -> Path:
    _guard(project, directory=True)
    folder = project
    for component in request.bundle.split("/"):
        folder = folder / component
        _guard(folder, directory=True, missing=True)
        try:
            folder.mkdir()
        except FileExistsError:
            pass
        _guard(folder, directory=True)
    _check_contents(folder)
    return folder


def _check_contents(folder: Path) -> None:
    _guard(folder, directory=True)
    for entry in folder.iterdir():
        _require(entry.name in {_CONFIGURATION, _RECEIPT}, "RESTORED_BUNDLE_UNKNOWN_ARTIFACT")
        _guard(entry)


def _distinct(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        _require(key not in result, "RESTORED_BUNDLE_RECEIPT_INVALID")
        result[key] = value
    return result


def _parse_receipt(raw: bytes) -> RestoredBundleReceipt:
    try:
        material: object = json.loads(raw, object_pairs_hook=_distinct)
        parsed = RestoredBundleReceipt.model_validate_json(raw)
        _require(
            canonical(material) == raw == canonical(parsed.model_dump(mode="json")),
            "RESTORED_BUNDLE_RECEIPT_INVALID",
        )
        return parsed
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise RestoredBundleError("RESTORED_BUNDLE_RECEIPT_INVALID") from None


def _existing_receipt(raw: bytes, current: RestoredBundleReceipt) -> RestoredBundleReceipt:
    existing = _parse_receipt(raw)
    excluded = {"started_at", "completed_at", "restore"}
    _require(
        existing.model_dump(exclude=excluded) == current.model_dump(exclude=excluded)
        and same_restore_association(existing.restore, current.restore)
        and datetime.fromisoformat(existing.completed_at)
        <= datetime.fromisoformat(current.completed_at),
        "RESTORED_BUNDLE_RECEIPT_CONFLICT",
    )
    return existing


def _publish(
    project: Path,
    receipt: RestoredBundleReceipt,
    configuration: bytes,
) -> RestoredBundleResult:
    """Never replace partial/conflicting bytes; retry repeats the actual audit first."""
    _require(
        len(configuration) == receipt.configuration_bytes
        and hashlib.sha256(configuration).hexdigest() == receipt.configuration_sha256,
        "RESTORED_BUNDLE_CONFIGURATION_CONFLICT",
    )
    folder = _bundle_folder(project, receipt.request)
    config_path, receipt_path = folder / _CONFIGURATION, folder / _RECEIPT
    # Receipt-only or partial configuration artifacts are never silently repaired.
    if receipt_path.exists():
        _require(config_path.exists(), "RESTORED_BUNDLE_CONFIGURATION_MISSING")
    try:
        _write_exclusive(config_path, configuration, MAX_CONFIGURATION_BYTES)
    except FileExistsError:
        _require(
            _read_bounded(config_path, MAX_CONFIGURATION_BYTES) == configuration,
            "RESTORED_BUNDLE_CONFIGURATION_CONFLICT",
        )
    raw = canonical(receipt.model_dump(mode="json"))
    publication: Literal["created", "reused"] = "created"
    try:
        _write_exclusive(receipt_path, raw, MAX_RESTORED_RECEIPT_BYTES)
    except FileExistsError:
        raw = _read_bounded(receipt_path, MAX_RESTORED_RECEIPT_BYTES)
        _existing_receipt(raw, receipt)
        publication = "reused"
    _check_contents(folder)
    _require(
        _read_bounded(config_path, MAX_CONFIGURATION_BYTES) == configuration
        and _read_bounded(receipt_path, MAX_RESTORED_RECEIPT_BYTES) == raw,
        "RESTORED_BUNDLE_FILE_CHANGED",
    )
    return RestoredBundleResult(
        request=receipt.request,
        configuration_id=receipt.configuration_id,
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        publication=publication,
    )


@dataclass(frozen=True)
class _InventoryAudit:
    stage: PreparedStage
    batches: tuple[CompactBatch, ...]
    payload_sha256: str


def _audit(
    store: Store,
    reader: CompactInventoryReader,
    request: RestoredBundleRequest,
    adopted: AdoptedViewingMaterial,
) -> _InventoryAudit:
    active = InventoryRepository(store).active()
    plan = active.stage
    _require(
        plan is not None and active.observation == request.expected_inventory,
        "RESTORED_BUNDLE_INVENTORY_CHANGED",
    )
    assert plan is not None
    refs = tuple(
        ImmutableInventoryRef.model_validate(ref.model_dump())
        for ref in adopted.eligibility.eligible_refs
    )
    listings = {row.ref: row for row in plan.candidate.listings}
    mappings = {item.ref: item for item in adopted.mappings}
    actual_mappings = {item.ref: item for item in plan.mappings}
    _require(
        len(refs) == len(set(refs)) == len(listings) == len(plan.candidate.listings) == 100
        and len(mappings)
        == len(adopted.mappings)
        == len(actual_mappings)
        == len(plan.mappings)
        == 100
        and set(refs) == set(listings) == set(mappings) == set(actual_mappings)
        and actual_mappings == mappings
        and plan.mapping_digest == lineage_version(adopted.mappings)
        and plan.candidate.manifest.namespace == refs[0].namespace
        and plan.candidate.manifest.snapshot_id == request.expected_inventory.snapshot_id
        and plan.index.snapshot_id == request.expected_inventory.snapshot_id
        and plan.index.version == request.expected_inventory.index_version
        and plan.index.mode == request.expected_inventory.mode
        and plan.policy_version == adopted.rules.policy.version,
        "RESTORED_BUNDLE_ADOPTED_INVENTORY_REQUIRED",
    )
    reader.admit(plan.index.snapshot_id)
    batches = []
    for start in range(0, len(refs), MAX_REFERENCE_BATCH):
        selected = refs[start : start + MAX_REFERENCE_BATCH]
        batch = reader.read_refs(selected, expected_snapshot_id=plan.index.snapshot_id)
        _require(
            batch.observation == active.observation
            and tuple(item.ref for item in batch.items) == selected,
            "RESTORED_BUNDLE_INVENTORY_CHANGED",
        )
        for item in batch.items:
            _require(
                item.state == "current"
                and item.listing == listings[item.ref]
                and item.mapping == mappings[item.ref]
                and type(item.resource_version) is str
                and bool(item.resource_version),
                "RESTORED_BUNDLE_REVIEWED_RESOURCE_REQUIRED",
            )
        batches.append(batch)
    return _InventoryAudit(plan, tuple(batches), digest_text(stage_payload(plan)))


def _final_inventory_read(
    db: Session,
    store: Store,
    reader: CompactInventoryReader,
    request: RestoredBundleRequest,
    audit: _InventoryAudit,
) -> None:
    for batch in audit.batches:
        reader.recheck(db, batch)
    plan, expected = audit.stage, request.expected_inventory
    rows = db.connection().exec_driver_sql(
        "SELECT m.store_generation,m.schema_version,a.snapshot_id,a.index_version,a.revision,"
        "p.mode,s.namespace,s.index_version,s.policy_version,s.accepted_count,s.rejected_count,"
        "b.serialization_version,b.payload_sha256,"
        "(SELECT count(*) FROM listing_versions l WHERE l.snapshot_id=s.snapshot_id),"
        "(SELECT count(*) FROM attribute_evidence e WHERE e.snapshot_id=s.snapshot_id),"
        "CASE WHEN json_valid(b.payload_json) THEN CASE WHEN "
        "json_type(b.payload_json,'$.mapping_digest')='text' AND "
        "length(json_extract(b.payload_json,'$.mapping_digest'))=64 "
        "THEN json_extract(b.payload_json,'$.mapping_digest') END END "
        "FROM store_metadata m LEFT JOIN active_inventory a ON a.id=1 "
        "LEFT JOIN inventory_storage_profile p ON p.id=1 "
        "LEFT JOIN inventory_snapshots s ON s.snapshot_id=a.snapshot_id "
        "LEFT JOIN inventory_snapshot_payloads b ON b.snapshot_id=a.snapshot_id WHERE m.id=1"
    ).all()
    _require(
        len(rows) == 1
        and all(type(rows[0][index]) is int for index in (4, 9, 10, 13, 14))
        and tuple(rows[0])
        == (
            request.expected_generation,
            store.schema_version,
            expected.snapshot_id,
            expected.index_version,
            expected.active_revision,
            expected.mode,
            plan.candidate.manifest.namespace,
            plan.index.version,
            plan.policy_version,
            len(plan.candidate.listings),
            0,
            STAGING_POLICY_VERSION,
            audit.payload_sha256,
            len(plan.candidate.listings),
            len(plan.candidate.evidence),
            plan.mapping_digest,
        ),
        "RESTORED_BUNDLE_INVENTORY_CHANGED",
    )


def produce_restored_inventory_bundle(
    raw_store_path: str,
    *,
    boundary: RuntimeBoundary,
    project_root: Path,
    request: RestoredBundleRequest,
) -> RestoredBundleResult:
    """Audit existing restored state and publish two files; never activate inventory/Rules."""
    try:
        assert_outside_write_transaction()
        _require(
            type(raw_store_path) is str and type(request) is RestoredBundleRequest,
            "RESTORED_BUNDLE_INPUT_INVALID",
        )
        request = RestoredBundleRequest.model_validate_json(
            canonical(request.model_dump(mode="json"))
        )
        parsed_path = parse_runtime_path(raw_store_path)
        _guard(project_root, directory=True)
        started = _utc_now()
        adopted = read_adopted_viewing_material(project_root)
        producer_hash = hashlib.sha256(
            _read_bounded(Path(__file__), _MAX_PRODUCER_BYTES)
        ).hexdigest()
        with completed_restore_scope(
            parsed_path,
            boundary=boundary,
            restore_id=request.restore_id,
            expected_receipt_sha256=request.restore_receipt_sha256,
            expected_generation=request.expected_generation,
        ) as completed:
            entry = completed.observation
            physical = guarded_store_path(parsed_path, boundary=boundary, must_exist=True)
            store = open_store(parsed_path, boundary=boundary)
            _require(
                store.generation == request.expected_generation == entry.store_generation
                and store.schema_version == entry.schema_version == "0002"
                and store.inventory_mode == entry.inventory_mode == request.expected_inventory.mode,
                "RESTORED_BUNDLE_STORE_CHANGED",
            )
            reader = CompactInventoryReader(store)
            try:
                audit = _audit(store, reader, request, adopted)
                config = ViewingConfiguration(
                    format="viewing-configuration-1",
                    calendar_version=adopted.rules.version,
                    policy=adopted.rules.policy,
                    venue_label=VIEWING_VENUE,
                    eligibility=adopted.eligibility,
                    inventory=request.expected_inventory,
                    mapping_digest=audit.stage.mapping_digest,
                )
                configuration = canonical(config.model_dump(mode="json"))
                _require(
                    parse_configuration(
                        configuration.decode("utf-8"),
                        rules=adopted.rules,
                        observation=request.expected_inventory,
                        namespace=audit.stage.candidate.manifest.namespace,
                    ) == config,
                    "RESTORED_BUNDLE_CONFIGURATION_INVALID",
                )
                restored = completed.revalidate()
                _require(
                    same_restore_association(entry, restored),
                    "RESTORED_BUNDLE_RESTORE_CHANGED",
                )
                store.read(lambda db: _final_inventory_read(db, store, reader, request, audit))
                receipt = RestoredBundleReceipt(
                    format="restored-inventory-viewing-bundle-1",
                    status="RESTORED_INVENTORY_AUDITED",
                    inventory_activation="NOT_PERFORMED_BY_PRODUCER",
                    rules_activation="NOT_PERFORMED_BY_PRODUCER",
                    application_launch="NOT_PERFORMED_BY_PRODUCER",
                    reader_admission="COLD_AUDIT_PASSED",
                    evidence_role="CURRENT_STATE_AUDIT_NOT_ACTIVATION_RECEIPT",
                    simulation_only=True,
                    request=request,
                    restore=restored,
                    destination=str(physical),
                    disposable_fixture=physical.is_relative_to(
                        boundary.physical_root / "test-stores"
                    ),
                    started_at=started,
                    completed_at=_utc_now(),
                    store_generation=store.generation,
                    schema_version="0002",
                    inventory=request.expected_inventory,
                    listing_count=len(audit.stage.candidate.listings),
                    evidence_count=len(audit.stage.candidate.evidence),
                    stage_payload_sha256=audit.payload_sha256,
                    mapping_digest=audit.stage.mapping_digest,
                    configuration_file="pending-viewing-configuration.json",
                    configuration_sha256=hashlib.sha256(configuration).hexdigest(),
                    configuration_bytes=len(configuration),
                    configuration_id=configuration_id(config),
                    eligibility_version=eligibility_version(config),
                    input_hashes=adopted.source_hashes,
                    producer_source_sha256=producer_hash,
                )
                result = _publish(project_root, receipt, configuration)
            finally:
                reader.invalidate()
        # The observer's mandatory normal-exit revalidation must finish before success.
        return result
    except RestoredBundleError:
        raise
    except RestoreCompletionError:
        raise RestoredBundleError("RESTORED_BUNDLE_RESTORE_UNAVAILABLE") from None
    except (
        OSError, ValueError, TypeError, AttributeError, StoreError, SQLAlchemyError, ApiFailure
    ):
        raise RestoredBundleError("RESTORED_BUNDLE_UNAVAILABLE") from None
