"""Explicit reviewed resource mappings, never numeric-source-ID vehicle inference."""

from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.schemas.common import Id
from app.inventory.references import ImmutableInventoryRef
from app.inventory.snapshot_codec import canonical_json, digest_text


class ReviewedResourceMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: ImmutableInventoryRef
    resource_id: Id
    mapping_version: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
    decision: Literal["reviewed_new_resource", "reviewed_same_vehicle"]
    reviewed_by: Annotated[str, Field(min_length=1, max_length=200)]
    reviewed_at: datetime
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    source_evidence_ids: Annotated[tuple[Id, ...], Field(min_length=1, max_length=20)]
    predecessor_ref: ImmutableInventoryRef | None = None

    @model_validator(mode="after")
    def complete_review(self) -> Self:
        if self.reviewed_at.utcoffset() != timedelta(0):
            raise ValueError("LINEAGE_REVIEW_UTC_REQUIRED")
        if not self.reviewed_by.strip() or not self.reason.strip():
            raise ValueError("LINEAGE_REVIEW_REASON_REQUIRED")
        if len(set(self.source_evidence_ids)) != len(self.source_evidence_ids):
            raise ValueError("LINEAGE_DUPLICATE_EVIDENCE")
        if (self.decision == "reviewed_same_vehicle") != (self.predecessor_ref is not None):
            raise ValueError("LINEAGE_PREDECESSOR_REQUIRED_FOR_REUSE_ONLY")
        if self.predecessor_ref == self.ref:
            raise ValueError("LINEAGE_SELF_REFERENCE")
        if self.predecessor_ref and self.predecessor_ref.snapshot_id == self.ref.snapshot_id:
            raise ValueError("LINEAGE_REQUIRES_RETAINED_PREDECESSOR_SNAPSHOT")
        return self


def lineage_version(mappings: tuple[ReviewedResourceMapping, ...]) -> str:
    ordered = sorted(
        mappings,
        key=lambda item: (item.ref.namespace, item.ref.snapshot_id, item.ref.source_id),
    )
    refs = [(item.ref.namespace, item.ref.snapshot_id, item.ref.source_id) for item in ordered]
    if len(set(refs)) != len(refs):
        raise ValueError("LINEAGE_MULTIPLE_RESOURCES_FOR_LISTING")
    return digest_text(canonical_json([item.model_dump(mode="json") for item in ordered]))
