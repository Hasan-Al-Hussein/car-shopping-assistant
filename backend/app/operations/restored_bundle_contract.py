"""Strict restored-inventory evidence; parsing never grants restore authority."""

from datetime import datetime
from typing import Annotated, Literal, Self

from app.api.schemas.common import Digest, Id, ShortText, UtcInstant
from app.core.config import FrozenSettings
from app.core.readiness import InventoryObservation
from app.operations.restore_completion import CompletedRestoreObservation
from app.viewings.draft_configuration import MAX_CONFIGURATION_BYTES
from pydantic import Field, StringConstraints, model_validator

RESTORED_BUNDLE_ROOT = "Records/build/OP-02/T12-restored-readmission/runs/"
RESTORED_BUNDLE_FORMAT = "restored-inventory-viewing-bundle-1"
ADOPTED_SNAPSHOT = "5fe31b5951317db6d77b6786596861e32ccd2442f2f5f98927d57e6b4a2092f3"
MAX_RESTORED_RECEIPT_BYTES = 16_384
RestoredConfigurationId = Annotated[
    str, StringConstraints(strict=True, pattern=r"^viewing-config-1:[0-9a-f]{64}$")
]
RestoredBundle = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=(
            r"^Records/build/OP-02/T12-restored-readmission/runs/"
            r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$"
        ),
    ),
]


def same_restore_association(
    left: CompletedRestoreObservation, right: CompletedRestoreObservation
) -> bool:
    """Compare evidence only; the caller must obtain fresh actual scope authority."""
    return left.model_dump(exclude={"observed_at"}) == right.model_dump(
        exclude={"observed_at"}
    )


class RestoredBundleRequest(FrozenSettings):
    operation_id: Id
    restore_id: Id
    restore_receipt_sha256: Digest
    expected_generation: Id
    expected_inventory: InventoryObservation
    bundle: RestoredBundle

    @model_validator(mode="after")
    def associations(self) -> Self:
        if (
            self.bundle != RESTORED_BUNDLE_ROOT + self.operation_id
            or self.expected_inventory.generation != self.expected_generation
            or self.expected_inventory.active_revision != 1
            or self.expected_inventory.snapshot_id != ADOPTED_SNAPSHOT
        ):
            raise ValueError("RESTORED_BUNDLE_REQUEST_BINDING")
        return self


class RestoredBundleReceipt(FrozenSettings):
    format: Literal["restored-inventory-viewing-bundle-1"]
    status: Literal["RESTORED_INVENTORY_AUDITED"]
    inventory_activation: Literal["NOT_PERFORMED_BY_PRODUCER"]
    rules_activation: Literal["NOT_PERFORMED_BY_PRODUCER"]
    application_launch: Literal["NOT_PERFORMED_BY_PRODUCER"]
    reader_admission: Literal["COLD_AUDIT_PASSED"]
    evidence_role: Literal["CURRENT_STATE_AUDIT_NOT_ACTIVATION_RECEIPT"]
    simulation_only: Literal[True]
    request: RestoredBundleRequest
    restore: CompletedRestoreObservation
    destination: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4096)]
    disposable_fixture: bool
    started_at: UtcInstant
    completed_at: UtcInstant
    store_generation: Id
    schema_version: Literal["0002"]
    inventory: InventoryObservation
    listing_count: Annotated[int, Field(strict=True, ge=100, le=100)]
    evidence_count: Annotated[int, Field(strict=True, ge=0, le=20_000)]
    stage_payload_sha256: Digest
    mapping_digest: Digest
    configuration_file: Literal["pending-viewing-configuration.json"]
    configuration_sha256: Digest
    configuration_bytes: Annotated[int, Field(strict=True, ge=1, le=MAX_CONFIGURATION_BYTES)]
    configuration_id: RestoredConfigurationId
    eligibility_version: ShortText
    input_hashes: Annotated[dict[ShortText, Digest], Field(max_length=64)]
    producer_source_sha256: Digest

    @model_validator(mode="after")
    def associations(self) -> Self:
        request, restore = self.request, self.restore
        if (
            self.store_generation != request.expected_generation
            or self.inventory != request.expected_inventory
            or restore.store_generation != self.store_generation
            or restore.schema_version != self.schema_version
            or restore.inventory_mode != self.inventory.mode
            or restore.restore_id != request.restore_id
            or restore.receipt_sha256 != request.restore_receipt_sha256
            or not (
                datetime.fromisoformat(self.started_at)
                <= datetime.fromisoformat(self.completed_at)
            )
            or not (
                datetime.fromisoformat(restore.restore_completed_at)
                <= datetime.fromisoformat(restore.observed_at)
                <= datetime.fromisoformat(self.completed_at)
            )
        ):
            raise ValueError("RESTORED_BUNDLE_RECEIPT_BINDING")
        return self


class RestoredBundleResult(FrozenSettings):
    request: RestoredBundleRequest
    configuration_id: RestoredConfigurationId
    receipt_sha256: Digest
    publication: Literal["created", "reused"]
