"""Explicit audit admission and separate, coherent, bounded inventory reads.

No certificate stores facts. Every fact read and caller-owned write recheck hashes
fresh persisted content. Search anchors carry only admission metadata. This module
neither authorizes owners nor publishes buyer routes.
"""

import hashlib
import hmac
import json
import re
import secrets
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from threading import RLock
from typing import Literal

from sqlalchemy.orm import Session

from app.core.readiness import InventoryObservation, ReadinessRegistry
from app.database.store import Store, assert_outside_write_transaction, open_store
from app.inventory.persisted_fingerprint import (
    FingerprintLayout,
    global_fingerprint,
    snapshot_fingerprint,
)
from app.inventory.read_identity import (
    MAX_REFERENCE_BATCH,
    AdmittedIdentity,
    ReferenceIdentity,
    issue_identity,
    verify_identity,
)
from app.inventory.references import ImmutableInventoryRef
from app.inventory.resource_lineage import ReviewedResourceMapping
from app.inventory.snapshot_codec import ListingRow, canonical_json, digest_text
from app.inventory.snapshot_storage import MAX_LINEAGE_SNAPSHOTS, load_stage_set
from app.inventory.snapshots import REVISION

MAX_CERTIFICATES = 64
MAX_PROJECTION_BYTES = 1024 * 1024


class _RequestUnavailable(ValueError):
    """A stale request or absent admission does not prove stored-content damage."""


@dataclass(frozen=True, slots=True)
class CompactReference:
    ref: ImmutableInventoryRef
    state: Literal["current", "historical", "missing"]
    listing: ListingRow | None = field(repr=False)
    mapping: ReviewedResourceMapping | None = field(default=None, repr=False)
    resource_version: str | None = None


@dataclass(frozen=True, slots=True)
class CompactBatch:
    observation: InventoryObservation
    items: tuple[CompactReference, ...]
    identity: tuple[str, ...]
    stamp: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SearchAnchor:
    """Fresh admission metadata only; not evidence that stored facts are valid."""

    observation: InventoryObservation
    identity: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class AuditReceipt:
    snapshot_id: str | None
    certificate_id: str | None


@dataclass(frozen=True, slots=True)
class _Certificate:
    snapshot_id: str
    namespace: str
    index_version: str
    issued_id: str
    global_digest: str
    dependencies: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class _Admission:
    observation: InventoryObservation
    certificate: _Certificate | None


def _no_checkpoint(phase: str) -> None:
    """Controlled test interleavings only; the production default is inert."""


def _ref_key(ref: ImmutableInventoryRef) -> tuple[str, str, str]:
    return ref.namespace, ref.snapshot_id, ref.source_id


class CompactInventoryReader:
    def __init__(
        self,
        store: Store,
        *,
        capacity: int = MAX_CERTIFICATES,
        _checkpoint: Callable[[str], None] = _no_checkpoint,
    ) -> None:
        if type(capacity) is not int or not 1 <= capacity <= MAX_CERTIFICATES:
            raise ValueError("INVENTORY_CERTIFICATE_CAPACITY_INVALID")
        self.store = store
        self._layout = FingerprintLayout.for_store(store)
        self._capacity = capacity
        self._certificates: OrderedDict[str, _Certificate] = OrderedDict()
        self._lock = RLock()
        self._epoch = 0
        self._signing_key = secrets.token_bytes(32)
        self._checkpoint = _checkpoint

    def invalidate(self) -> None:
        """Failed refresh, disposal or lost admission never leaves cached readiness."""
        with self._lock:
            self._certificates.clear()
            self._epoch += 1

    def _observation(self, session: Session) -> InventoryObservation:
        rows = (
            session.connection()
            .exec_driver_sql(
                "SELECT id,snapshot_id,index_version,revision FROM active_inventory ORDER BY id"
            )
            .all()
        )
        if not rows:
            return InventoryObservation(generation=self.store.generation, active_revision=0)
        if len(rows) != 1 or rows[0][0] != 1:
            raise ValueError("INVENTORY_ACTIVE_TUPLE_INVALID")
        _, snapshot_id, index_version, revision = rows[0]
        REVISION.validate_python(revision, strict=True)
        if revision < 1:
            raise ValueError("INVENTORY_ACTIVE_TUPLE_INVALID")
        return InventoryObservation(
            generation=self.store.generation,
            active_revision=revision,
            snapshot_id=snapshot_id,
            index_version=index_version,
            mode=self._layout.mode,
        )

    def _audit(self, session: Session, snapshot_id: str | None) -> _Admission:
        observation = self._observation(session)
        selected = observation.snapshot_id if snapshot_id is None else snapshot_id
        if selected is None:
            global_fingerprint(session, self.store, self._layout, audit_postings=True)
            return _Admission(observation, None)
        loaded = load_stage_set(session, selected, self._layout.mode)
        if loaded is None:
            raise ValueError("INVENTORY_SNAPSHOT_NOT_STAGED")
        plan, parents = loaded
        if selected == observation.snapshot_id and plan.index.version != observation.index_version:
            raise ValueError("INVENTORY_ACTIVE_TUPLE_INVALID")
        snapshot_ids = sorted({selected, *(parent.index.snapshot_id for parent in parents)})
        global_digest = global_fingerprint(session, self.store, self._layout, audit_postings=True)
        dependencies = tuple((item, snapshot_fingerprint(session, item)) for item in snapshot_ids)
        self._checkpoint("admission.audited")
        return _Admission(
            observation,
            _Certificate(
                selected,
                plan.candidate.manifest.namespace,
                plan.index.version,
                secrets.token_hex(16),
                global_digest,
                dependencies,
            ),
        )

    def _admit(self, snapshot_id: str | None, store: Store) -> _Admission:
        assert_outside_write_transaction()
        if snapshot_id is not None and (
            type(snapshot_id) is not str or re.fullmatch(r"[0-9a-f]{64}", snapshot_id) is None
        ):
            raise ValueError("INVENTORY_SNAPSHOT_ID_INVALID")
        with self._lock:
            epoch = self._epoch
        try:
            result = store.read(lambda session: self._audit(session, snapshot_id))
            self._checkpoint("admission.before_publish")
            with self._lock:
                if epoch != self._epoch:
                    raise ValueError("INVENTORY_ADMISSION_INVALIDATED")
                certificate = result.certificate
                if certificate is not None:
                    self._certificates[certificate.snapshot_id] = certificate
                    self._certificates.move_to_end(certificate.snapshot_id)
                    while len(self._certificates) > self._capacity:
                        self._certificates.popitem(last=False)
            return result
        except BaseException:
            self.invalidate()
            raise

    def admit(self, snapshot_id: str) -> AuditReceipt:
        """Explicit operator audit; a stored checksum or supplied object cannot admit."""
        result = self._admit(snapshot_id, self.store)
        certificate = result.certificate
        assert certificate is not None
        return AuditReceipt(certificate.snapshot_id, certificate.issued_id)

    def refresh(self, registry: ReadinessRegistry) -> None:
        """Fresh open/audit occurs inside the existing serialized refresh callback."""

        def observe() -> InventoryObservation:
            fresh = open_store(self.store.path, boundary=self.store.boundary)
            if (fresh.generation, fresh.schema_version, fresh.inventory_mode) != (
                self.store.generation,
                self.store.schema_version,
                self.store.inventory_mode,
            ):
                raise ValueError("INVENTORY_STORE_IDENTITY_MISMATCH")
            return self._admit(None, fresh).observation

        try:
            registry.refresh_inventory(observe)
        except BaseException:
            self.invalidate()
            raise

    def _verified(
        self, session: Session, refs: tuple[ImmutableInventoryRef, ...]
    ) -> tuple[InventoryObservation, tuple[_Certificate, ...], int]:
        observation = self._observation(session)
        self._checkpoint("compact.active_selected")
        global_digest = global_fingerprint(session, self.store, self._layout)
        roots = set()
        if observation.snapshot_id is not None:
            roots.add(observation.snapshot_id)
        for ref in refs:
            if (
                session.connection()
                .exec_driver_sql(
                    "SELECT 1 FROM inventory_snapshots WHERE snapshot_id=?", (ref.snapshot_id,)
                )
                .first()
                is not None
            ):
                roots.add(ref.snapshot_id)
        with self._lock:
            epoch = self._epoch
            certificates = []
            for root in sorted(roots):
                certificate = self._certificates.get(root)
                if certificate is None:
                    raise _RequestUnavailable("INVENTORY_AUDIT_ADMISSION_REQUIRED")
                certificates.append(certificate)
        dependencies = {sid for cert in certificates for sid, _ in cert.dependencies}
        if len(dependencies) > MAX_LINEAGE_SNAPSHOTS:
            raise _RequestUnavailable("INVENTORY_BATCH_DEPENDENCY_LIMIT")
        digests = {sid: snapshot_fingerprint(session, sid) for sid in sorted(dependencies)}
        for certificate in certificates:
            if certificate.global_digest != global_digest or any(
                digests[sid] != expected for sid, expected in certificate.dependencies
            ):
                raise ValueError("INVENTORY_CERTIFIED_CONTENT_CHANGED")
            if certificate.snapshot_id == observation.snapshot_id and (
                certificate.index_version != observation.index_version
            ):
                raise ValueError("INVENTORY_ACTIVE_TUPLE_INVALID")
        return observation, tuple(certificates), epoch

    def _still_admitted(self, identity: AdmittedIdentity) -> None:
        with self._lock:
            if identity.epoch != self._epoch or identity.mode != self._layout.mode:
                raise _RequestUnavailable("INVENTORY_ADMISSION_INVALIDATED")
            for snapshot_id, issued_id in identity.certificates:
                certificate = self._certificates.get(snapshot_id)
                if certificate is None or certificate.issued_id != issued_id:
                    raise _RequestUnavailable("INVENTORY_ADMISSION_INVALIDATED")

    def _projection(
        self, session: Session, ref: ImmutableInventoryRef, observation: InventoryObservation
    ) -> CompactReference:
        row = (
            session.connection()
            .exec_driver_sql(
                "SELECT source_row,original_json,normalized_json FROM listing_versions "
                "WHERE namespace=? AND snapshot_id=? AND source_id=?",
                _ref_key(ref),
            )
            .first()
        )
        if row is None:
            return CompactReference(ref, "missing", None)
        source_row, original_text, normalized_text = row
        if (
            type(source_row) is not int
            or source_row < 2
            or any(
                type(value) is not str or len(value.encode("utf-8")) > MAX_PROJECTION_BYTES
                for value in (original_text, normalized_text)
            )
        ):
            raise ValueError("INVENTORY_COMPACT_PROJECTION_INVALID")
        original, normalized = json.loads(original_text), json.loads(normalized_text)
        if (
            type(original) is not dict
            or type(normalized) is not dict
            or original.get("source_id") != ref.source_id
            or original.get("row") != source_row
            or normalized.get("ref") != ref.model_dump()
            or normalized.get("source_row") != source_row
        ):
            raise ValueError("INVENTORY_COMPACT_PROJECTION_INVALID")
        mapping_row = (
            session.connection()
            .exec_driver_sql(
                "SELECT m.provenance_json,r.mapping_version FROM listing_resource_mappings m "
                "JOIN vehicle_resources r ON r.id=m.resource_id "
                "WHERE m.namespace=? AND m.snapshot_id=? AND m.source_id=?",
                _ref_key(ref),
            )
            .first()
        )
        mapping = None
        resource_version = None
        if mapping_row is not None:
            mapping = ReviewedResourceMapping.model_validate_json(mapping_row[0])
            resource_version = mapping_row[1]
            if mapping.ref != ref:
                raise ValueError("INVENTORY_COMPACT_RESOURCE_INVALID")
        state: Literal["current", "historical"] = (
            "current" if ref.snapshot_id == observation.snapshot_id else "historical"
        )
        return CompactReference(
            ref,
            state,
            ListingRow(ref, source_row, canonical_json(original), canonical_json(normalized)),
            mapping,
            resource_version,
        )

    def _stamp(self, batch: CompactBatch) -> str:
        payload = canonical_json(
            {
                "identity": batch.identity,
                "observation": batch.observation.model_dump(mode="json"),
                "items": [
                    (
                        _ref_key(item.ref),
                        item.state,
                        None
                        if item.listing is None
                        else (
                            _ref_key(item.listing.ref),
                            item.listing.source_row,
                            digest_text(item.listing.original_json),
                            digest_text(item.listing.normalized_json),
                        ),
                        None if item.mapping is None else item.mapping.model_dump(mode="json"),
                        item.resource_version,
                    )
                    for item in batch.items
                ],
            }
        )
        return hmac.new(self._signing_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def read_refs(
        self, refs: tuple[ImmutableInventoryRef, ...], *, expected_snapshot_id: str | None = None
    ) -> CompactBatch:
        assert_outside_write_transaction()
        if type(refs) is not tuple or len(refs) > MAX_REFERENCE_BATCH:
            raise ValueError("INVENTORY_REFERENCE_BATCH_LIMIT")
        refs = tuple(ImmutableInventoryRef.model_validate(ref.model_dump()) for ref in refs)

        def read(session: Session) -> CompactBatch:
            observation, certificates, epoch = self._verified(session, refs)
            if expected_snapshot_id is not None and observation.snapshot_id != expected_snapshot_id:
                raise _RequestUnavailable("INVENTORY_EXPECTED_SNAPSHOT_CHANGED")
            items = tuple(self._projection(session, ref, observation) for ref in refs)
            identity = AdmittedIdentity(
                mode=self._layout.mode,
                epoch=epoch,
                observation=observation,
                references=tuple(
                    ReferenceIdentity(ref=item.ref, state=item.state) for item in items
                ),
                certificates=tuple((cert.snapshot_id, cert.issued_id) for cert in certificates),
            )
            batch = CompactBatch(
                observation,
                items,
                issue_identity(self._signing_key, identity),
                "",
            )
            return replace(batch, stamp=self._stamp(batch))

        try:
            batch = self.store.read(read)
            self._still_admitted(verify_identity(self._signing_key, batch.identity))
            return batch
        except _RequestUnavailable:
            raise
        except BaseException:
            self.invalidate()
            raise

    def read_search_anchor(self) -> SearchAnchor:
        """Bind a search to fresh metadata; recheck_identity must precede selection.

        The empty reference identity carries no listing facts. Public search keeps
        this separate guarded unit so activation before selection is still stale.
        Other readers continue using the fully verified read_refs/read_header.
        """
        assert_outside_write_transaction()

        def read(session: Session) -> SearchAnchor:
            observation = self._observation(session)
            self._checkpoint("compact.active_selected")
            with self._lock:
                epoch = self._epoch
                certificate = (
                    None
                    if observation.snapshot_id is None
                    else self._certificates.get(observation.snapshot_id)
                )
                if observation.snapshot_id is not None and certificate is None:
                    raise _RequestUnavailable("INVENTORY_AUDIT_ADMISSION_REQUIRED")
                certificates = (
                    ()
                    if certificate is None
                    else ((certificate.snapshot_id, certificate.issued_id),)
                )
            identity = AdmittedIdentity(
                mode=self._layout.mode,
                epoch=epoch,
                observation=observation,
                references=(),
                certificates=certificates,
            )
            return SearchAnchor(observation, issue_identity(self._signing_key, identity))

        try:
            anchor = self.store.read(read)
            self._still_admitted(verify_identity(self._signing_key, anchor.identity))
            return anchor
        except _RequestUnavailable:
            raise
        except BaseException:
            self.invalidate()
            raise

    def _check_search_anchor(self, anchor: SearchAnchor) -> None:
        """Check metadata continuity without another Store read or fact claim."""
        if type(anchor) is not SearchAnchor:
            raise ValueError("INVENTORY_READ_IDENTITY_INVALID")
        identity = verify_identity(self._signing_key, anchor.identity)
        if identity.references or identity.observation != anchor.observation:
            raise ValueError("INVENTORY_READ_IDENTITY_INVALID")
        self._still_admitted(identity)

    def read_header(self) -> InventoryObservation:
        return self.read_refs(()).observation

    def recheck(self, session: Session, batch: CompactBatch) -> None:
        """Trusted adapter inside an existing authorized unit; no Store/full decode."""
        if (
            type(batch) is not CompactBatch
            or type(batch.items) is not tuple
            or len(batch.items) > MAX_REFERENCE_BATCH
            or type(batch.stamp) is not str
            or not hmac.compare_digest(batch.stamp, self._stamp(batch))
        ):
            raise ValueError("INVENTORY_READ_IDENTITY_INVALID")
        identity = verify_identity(self._signing_key, batch.identity)
        if identity.observation != batch.observation or identity.references != tuple(
            ReferenceIdentity(ref=item.ref, state=item.state) for item in batch.items
        ):
            raise ValueError("INVENTORY_READ_IDENTITY_INVALID")
        self.recheck_identity(
            session, batch.identity, expected_refs=tuple(item.ref for item in batch.items)
        )

    def recheck_identity(
        self,
        session: Session,
        token: tuple[str, ...],
        *,
        expected_refs: tuple[ImmutableInventoryRef, ...],
    ) -> None:
        """Opaque tuple adapter for P9/P10/T3; no facts or owner authority in token."""
        identity = verify_identity(self._signing_key, token)
        if tuple(item.ref for item in identity.references) != expected_refs:
            raise ValueError("INVENTORY_READ_IDENTITY_INVALID")
        connection = session.connection()
        options = connection.get_execution_options()
        if (
            not connection.in_transaction()
            or "store_write" not in options
            or type(options["store_write"]) is not bool
        ):
            raise ValueError("INVENTORY_EXISTING_STORE_UNIT_REQUIRED")
        try:
            self._still_admitted(identity)
            refs = tuple(item.ref for item in identity.references)
            observation, certificates, epoch = self._verified(session, refs)
            if (
                observation != identity.observation
                or epoch != identity.epoch
                or tuple((cert.snapshot_id, cert.issued_id) for cert in certificates)
                != identity.certificates
            ):
                raise _RequestUnavailable("INVENTORY_READ_IDENTITY_STALE")
            for item in identity.references:
                present = (
                    connection.exec_driver_sql(
                        "SELECT 1 FROM listing_versions WHERE namespace=? "
                        "AND snapshot_id=? AND source_id=?",
                        _ref_key(item.ref),
                    ).first()
                    is not None
                )
                if present != (item.state != "missing"):
                    raise ValueError("INVENTORY_REFERENCE_CHANGED")
            self._still_admitted(identity)
        except _RequestUnavailable:
            raise
        except BaseException:
            self.invalidate()
            raise
