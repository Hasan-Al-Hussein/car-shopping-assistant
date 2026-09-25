"""Durable terminal results versus observations without proof of noncommit."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.api.schemas.common import DTO, Id, OpaqueKey, UtcInstant
from app.api.schemas.leads import (
    ExportNotRequested,
    LeadNotRequested,
    LeadSaved,
    RequestedExportOutcome,
    require_reviewed_lead,
)
from app.api.schemas.viewings import BookingCoreReceipt


class BookingNotCreated(DTO):
    state: Literal["not_created"]


BusinessRejectionCode = Literal[
    "REVIEW_STALE",
    "CAPACITY_UNAVAILABLE",
    "ELIGIBILITY_UNAVAILABLE",
    "RULES_UNAVAILABLE",
    "UNSUPPORTED_STATE",
    "SNAPSHOT_STALE",
    "LEAD_REVISION_CONFLICT",
]


class OperationSucceeded(DTO):
    state: Literal["succeeded"]
    operation_key: OpaqueKey
    review_id: Id
    original_store_generation: Id
    terminal_at: UtcInstant
    replay_valid_until: UtcInstant
    booking: BookingCoreReceipt
    lead: LeadSaved
    csv: RequestedExportOutcome

    @model_validator(mode="after")
    def consistent_receipt_identity(self) -> "OperationSucceeded":
        review = self.booking.review
        if (self.review_id, self.operation_key, self.original_store_generation) != (
            review.review_id,
            review.operation_key,
            review.store_generation,
        ):
            raise ValueError("Terminal outcome must identify its exact committed review.")
        require_reviewed_lead(self.lead, review.lead_change)
        if datetime.fromisoformat(self.replay_valid_until) <= datetime.fromisoformat(
            self.terminal_at
        ):
            raise ValueError("Replay authority must follow terminal time.")
        return self


class OperationRejected(DTO):
    state: Literal["rejected"]
    operation_key: OpaqueKey
    review_id: Id
    original_store_generation: Id
    terminal_at: UtcInstant
    replay_valid_until: UtcInstant
    rejection_code: BusinessRejectionCode
    booking: BookingNotCreated
    lead: LeadNotRequested
    csv: ExportNotRequested

    @model_validator(mode="after")
    def ordered_replay_lifetime(self) -> "OperationRejected":
        if datetime.fromisoformat(self.replay_valid_until) <= datetime.fromisoformat(
            self.terminal_at
        ):
            raise ValueError("Replay authority must follow terminal time.")
        return self


class OperationNotObserved(DTO):
    state: Literal["not_observed"]
    operation_key: OpaqueKey
    observed_store_generation: Id
    definitive_noncommit: Literal[False] = False
    recovery: Literal["read_original_operation", "retry_original_operation"]


class OperationGenerationUnresolved(DTO):
    state: Literal["unresolved_generation"]
    operation_key: OpaqueKey
    observed_store_generation: Id
    submitted_store_generation: Id
    definitive_noncommit: Literal[False] = False
    recovery: Literal["operator_reconciliation"] = "operator_reconciliation"


OperationStatus = Annotated[
    OperationSucceeded | OperationRejected | OperationNotObserved | OperationGenerationUnresolved,
    Field(discriminator="state"),
]
