"""Frozen candidate references; no lookup of current inventory or publication."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from pydantic import ConfigDict, ValidationError

from app.api.schemas.common import InventoryRef
from app.inventory.import_reader import SourceManifest

NORMALIZATION_VERSION = "source-normalization-1"
NOT_APPLIED = "not-applied"
PHOTO_POLICY_VERSION = "supplied-photo-1"
SCHEMA_VERSION = "1.0.0"
VERSION_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z", re.ASCII)


class ImmutableInventoryRef(InventoryRef):
    """Internal immutable form of the unchanged shared wire contract."""

    model_config = ConfigDict(frozen=True)


@dataclass(frozen=True)
class SnapshotManifest:
    """The exact eight-key preimage from contracts/v1/inventory_protocol.md.

    Source/reader version labels remain in SourceManifest provenance. A reader
    change affecting derived meaning must bump the relevant transformation version.
    """

    namespace: str
    workbook_sha256: str
    sheet: str
    normalization_version: str = NORMALIZATION_VERSION
    extraction_version: str = NOT_APPLIED
    evidence_review_version: str = NOT_APPLIED
    photo_policy_version: str = PHOTO_POLICY_VERSION
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        try:
            InventoryRef(
                namespace=self.namespace, snapshot_id=self.workbook_sha256, source_id="validation"
            )
        except ValidationError:
            raise ValueError("MANIFEST_IDENTITY_INVALID") from None
        if not isinstance(self.sheet, str) or not self.sheet.strip() or len(self.sheet) > 200:
            raise ValueError("MANIFEST_SHEET_INVALID")
        for label in (
            self.normalization_version,
            self.extraction_version,
            self.evidence_review_version,
            self.photo_policy_version,
            self.schema_version,
        ):
            if not isinstance(label, str) or not VERSION_LABEL.fullmatch(label):
                raise ValueError("MANIFEST_VERSION_INVALID")

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")

    @property
    def snapshot_id(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def reference(self, source_id: str) -> ImmutableInventoryRef:
        try:
            return ImmutableInventoryRef(
                namespace=self.namespace, snapshot_id=self.snapshot_id, source_id=source_id
            )
        except ValidationError:
            raise ValueError("SOURCE_ID_INVALID") from None


def normalization_manifest(source: SourceManifest) -> SnapshotManifest:
    """Create identities for normalization-only output, with no fact review claim."""
    return SnapshotManifest(source.namespace, source.workbook_sha256, source.selected_sheet)
