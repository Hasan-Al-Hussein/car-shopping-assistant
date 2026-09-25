"""Reviewed simulated viewing intent; caller cannot replace facts at confirmation."""

from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from app.api.schemas.common import DTO, Id, InventoryRef, OpaqueKey, Revision, ShortText, UtcInstant
from app.api.schemas.leads import (
    LeadSaved,
    RequestedExportOutcome,
    ReviewedLeadChange,
    require_reviewed_lead,
)


class AppointmentSelection(DTO):
    starts_at_utc: UtcInstant
    timezone: Literal["Asia/Dubai"] = "Asia/Dubai"
    appointment_type: Literal["viewing"] = "viewing"


class BookingDraftCreate(DTO):
    client_action_id: Id
    session_id: Id
    expected_session_revision: Revision
    ref: InventoryRef
    appointment: AppointmentSelection | None = None


class BookingDraftUpdate(DTO):
    client_action_id: Id
    expected_revision: Revision
    intent: Literal["edit", "suspend", "discard", "refresh_review"]
    ref: InventoryRef | None = None
    appointment: AppointmentSelection | None = None

    @model_validator(mode="after")
    def edit_is_explicit(self) -> "BookingDraftUpdate":
        if self.intent != "edit" and (self.ref is not None or self.appointment is not None):
            raise ValueError("Only an explicit edit can change selected details.")
        if self.intent == "edit" and self.ref is None and self.appointment is None:
            raise ValueError("An edit requires changed details.")
        return self


class BookingReview(DTO):
    review_id: Id
    draft_id: Id
    session_id: Id
    draft_revision: Revision
    ref: InventoryRef
    resource_id: Id
    starts_at_utc: UtcInstant
    ends_at_utc: UtcInstant
    local_start: Annotated[str, StringConstraints(strict=True, max_length=40)]
    timezone: Literal["Asia/Dubai"] = "Asia/Dubai"
    appointment_type: Literal["viewing"] = "viewing"
    venue_label: Literal["Simulated local viewing — no real venue or reservation."]
    simulation: Literal[True] = True
    rules_version: ShortText
    eligibility_version: ShortText
    store_generation: Id
    operation_key: OpaqueKey
    issued_at: UtcInstant
    expires_at: UtcInstant
    lead_effect: Literal["save_local_enquiry"] = "save_local_enquiry"
    lead_change: ReviewedLeadChange
    state: Literal["valid", "invalidated", "expired", "submitted", "consumed"]

    @model_validator(mode="after")
    def positive_interval(self) -> "BookingReview":
        start = datetime.fromisoformat(self.starts_at_utc.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.ends_at_utc.replace("Z", "+00:00"))
        if end <= start:
            raise ValueError("Appointment end must follow its start.")
        local = datetime.fromisoformat(self.local_start)
        expected = start.astimezone(ZoneInfo(self.timezone))
        if local.tzinfo is None or local != expected or local.utcoffset() != expected.utcoffset():
            raise ValueError(
                "Local start must show the authoritative instant in the declared zone."
            )
        if datetime.fromisoformat(self.expires_at) <= datetime.fromisoformat(self.issued_at):
            raise ValueError("Review expiry must follow issue.")
        return self


class BookingDraft(DTO):
    draft_id: Id
    session_id: Id
    revision: Revision
    ref: InventoryRef
    appointment: AppointmentSelection | None
    state: Literal[
        "needs_details", "reviewable", "suspended", "discarded", "resolved", "unresolved"
    ]
    expires_at: UtcInstant
    required_fields: Annotated[list[ShortText], Field(max_length=12)]
    review: BookingReview | None

    @model_validator(mode="after")
    def coherent_draft(self) -> "BookingDraft":
        if self.state == "reviewable" and (
            self.review is None
            or self.review.state != "valid"
            or self.required_fields
            or self.appointment is None
        ):
            raise ValueError("A reviewable draft needs complete details and a valid review.")
        if self.review is not None:
            if (self.draft_id, self.session_id, self.revision, self.ref) != (
                self.review.draft_id,
                self.review.session_id,
                self.review.draft_revision,
                self.review.ref,
            ):
                raise ValueError("Nested review must identify this exact draft version.")
            if self.review.state == "valid" and self.state != "reviewable":
                raise ValueError("Only a reviewable draft can expose an actionable review.")
            if self.appointment is not None and (
                self.appointment.starts_at_utc != self.review.starts_at_utc
            ):
                raise ValueError("Appointment and nested review must agree.")
        return self


class ConfirmRequest(DTO):
    review_id: Id
    expected_draft_revision: Revision
    operation_key: OpaqueKey
    rules_version: ShortText
    store_generation: Id
    confirmation: Literal["confirm_simulated_viewing"]


class BookingCoreReceipt(DTO):
    state: Literal["confirmed_simulated"]
    booking_id: Id
    review: BookingReview
    confirmed_at: UtcInstant

    @model_validator(mode="after")
    def consumed_review(self) -> "BookingCoreReceipt":
        if self.review.state != "consumed":
            raise ValueError("A confirmed receipt must identify a consumed review.")
        return self


class BookingReceipt(BookingCoreReceipt):
    lead: LeadSaved
    csv: RequestedExportOutcome

    @model_validator(mode="after")
    def accepted_lead_identity(self) -> "BookingReceipt":
        require_reviewed_lead(self.lead, self.review.lead_change)
        return self


def require_date(value: str) -> str:
    date.fromisoformat(value)
    return value


class ViewingOptionsRequest(DTO):
    ref: InventoryRef
    from_date: Annotated[
        str,
        StringConstraints(strict=True, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        AfterValidator(require_date),
    ]
    days: Annotated[int, Field(strict=True, ge=1, le=7)] = 7


class ViewingSlot(DTO):
    starts_at_utc: UtcInstant
    ends_at_utc: UtcInstant
    timezone: Literal["Asia/Dubai"] = "Asia/Dubai"

    @model_validator(mode="after")
    def positive_interval(self) -> "ViewingSlot":
        if datetime.fromisoformat(self.ends_at_utc) <= datetime.fromisoformat(self.starts_at_utc):
            raise ValueError("Slot end must follow its start.")
        return self


class ViewingOptions(DTO):
    ref: InventoryRef
    state: Literal["available", "no_valid_slots", "ineligible", "unconfigured"]
    rules_version: ShortText | None
    eligibility_version: ShortText | None
    calculated_at: UtcInstant
    no_hold: Literal[True] = True
    slots: Annotated[list[ViewingSlot], Field(max_length=24)]

    @model_validator(mode="after")
    def coherent_options(self) -> "ViewingOptions":
        if (self.state == "available") != bool(self.slots):
            raise ValueError("Only available options contain selectable slots.")
        if self.state != "unconfigured" and (
            self.rules_version is None or self.eligibility_version is None
        ):
            raise ValueError(
                "Configured options must identify their rule and eligibility versions."
            )
        return self
