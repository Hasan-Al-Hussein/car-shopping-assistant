"""Local enquiry facts and projection status; never imply dealer delivery."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.api.schemas.common import DTO, Id, InventoryRef, Revision, ShortText, UtcInstant
from app.api.schemas.inventory import BudgetRange


class ContactValue(DTO):
    state: Literal["provided", "missing", "declined"]
    value: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=320)] | None = (
        None
    )

    @model_validator(mode="after")
    def value_matches_state(self) -> "ContactValue":
        if (self.state == "provided") != (self.value is not None):
            raise ValueError("Only explicitly provided contact has a value.")
        return self


class BudgetValue(DTO):
    state: Literal["provided", "missing", "declined"]
    value: BudgetRange | None = None

    @model_validator(mode="after")
    def value_matches_state(self) -> "BudgetValue":
        if (self.state == "provided") != (self.value is not None):
            raise ValueError("Only an explicitly provided budget has a value.")
        return self


class LeadValues(DTO):
    budget: BudgetValue
    requirements: Annotated[list[ShortText], Field(max_length=24)]
    selected_refs: Annotated[list[InventoryRef], Field(max_length=10)]
    email: ContactValue
    phone: ContactValue


class LeadSaveRequest(DTO):
    client_action_id: Id
    session_id: Id
    intent: Literal["save_local_enquiry"]
    values: LeadValues


class LeadUpdateRequest(DTO):
    client_action_id: Id
    expected_revision: Revision
    session_id: Id
    intent: Literal["correct_local_enquiry"]
    values: LeadValues


class ExportCurrent(DTO):
    state: Literal["current"]
    version_scope: Literal["global_projection"] = "global_projection"
    store_generation: Id
    observed_at: UtcInstant
    canonical_version: Revision
    exported_version: Revision

    @model_validator(mode="after")
    def same_version(self) -> "ExportCurrent":
        if self.canonical_version != self.exported_version:
            raise ValueError("A current projection must match its canonical version.")
        return self


class ExportPending(DTO):
    state: Literal["pending", "failed"]
    version_scope: Literal["global_projection"] = "global_projection"
    store_generation: Id
    observed_at: UtcInstant
    canonical_version: Revision
    exported_version: Revision | None
    code: ShortText | None


class ExportNotRequested(DTO):
    state: Literal["not_requested"]


RequestedExportOutcome = Annotated[ExportCurrent | ExportPending, Field(discriminator="state")]


class LeadSaved(DTO):
    state: Literal["saved"]
    lead_id: Id
    revision: Revision


class LeadNotRequested(DTO):
    state: Literal["not_requested"]


class LeadRecord(DTO):
    lead_id: Id
    journey_id: Id
    revision: Revision
    stage: Literal["interested", "viewing_confirmed"]
    values: LeadValues
    booking_ids: Annotated[list[Id], Field(max_length=100)]
    updated_at: UtcInstant
    expires_at: UtcInstant
    delivery: Literal["local_only"] = "local_only"
    csv: RequestedExportOutcome


class LeadSaveResult(DTO):
    lead: LeadRecord
    replayed: Annotated[bool, Field(strict=True)]


class NoLead(DTO):
    state: Literal["not_created"]


class ReviewedLeadCreation(DTO):
    mode: Literal["create_from_review"]
    values: LeadValues
    source_session_revision: Revision


class ReviewedExistingLead(DTO):
    mode: Literal["preserve_existing"]
    lead_id: Id
    expected_revision: Revision


ReviewedLeadChange = Annotated[
    ReviewedLeadCreation | ReviewedExistingLead, Field(discriminator="mode")
]


def require_reviewed_lead(lead: LeadSaved, change: ReviewedLeadChange) -> None:
    if isinstance(change, ReviewedExistingLead) and (
        lead.lead_id != change.lead_id or lead.revision != change.expected_revision + 1
    ):
        raise ValueError(
            "Accepted lead must preserve the reviewed lead identity and next revision."
        )
