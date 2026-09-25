"""Explicit durability and exact shortlist references, separate from conversation edits."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from app.api.schemas.common import DTO, Id, InventoryRef, Revision, ShortText, UtcInstant
from app.api.schemas.inventory import BudgetRange, ListingSummary


class BudgetPreference(DTO):
    key: Literal["budget"]
    value: BudgetRange | None
    strength: Literal["hard", "soft"]


class CategoryPreference(DTO):
    key: Literal["makes", "use_cases", "requirements"]
    value: Annotated[list[ShortText], Field(max_length=24)]
    strength: Literal["hard", "soft"]

    @model_validator(mode="after")
    def bounded_categories(self) -> "CategoryPreference":
        if self.key != "requirements" and len(self.value) > 12:
            raise ValueError("At most 12 values are allowed for this preference.")
        return self


PreferenceValue = Annotated[BudgetPreference | CategoryPreference, Field(discriminator="key")]


class PreferencesUpdate(DTO):
    expected_revision: Revision
    session_id: Id
    client_action_id: Id
    scope: Literal["durable"]
    intent: Literal["remember", "correct"]
    changes: Annotated[list[PreferenceValue], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def distinct_changes(self) -> "PreferencesUpdate":
        if len({change.key for change in self.changes}) != len(self.changes):
            raise ValueError("Each preference can be changed once per command.")
        return self


class PreferenceCollectionUpdate(DTO):
    expected_revision: Revision
    session_id: Id
    client_action_id: Id
    intent: Literal["stop_saving", "resume_saving"]


PreferenceCommand = Annotated[
    PreferencesUpdate | PreferenceCollectionUpdate, Field(discriminator="intent")
]


class PreferenceEntry(DTO):
    preference: PreferenceValue
    source_session_id: Id
    source_action_id: Id
    source_message_id: Id | None = None
    confirmed_at: UtcInstant
    expires_at: UtcInstant
    applicability: Literal["confirmed", "requires_reconfirmation"]

    @model_validator(mode="after")
    def meaningful_retained_value(self) -> "PreferenceEntry":
        if self.preference.value is None or self.preference.value == []:
            raise ValueError("Clearing a preference removes its entry.")
        if datetime.fromisoformat(self.expires_at) <= datetime.fromisoformat(self.confirmed_at):
            raise ValueError("Preference expiry must follow its own confirmation.")
        return self


class PreferenceRecord(DTO):
    entries: Annotated[list[PreferenceEntry], Field(max_length=4)]
    revision: Revision
    collection_mode: Literal["explicit_save", "disabled"]

    @model_validator(mode="after")
    def distinct_entries(self) -> "PreferenceRecord":
        if len({entry.preference.key for entry in self.entries}) != len(self.entries):
            raise ValueError("Each retained preference has independent, unique provenance.")
        return self


class ShortlistItem(DTO):
    ref: InventoryRef
    state: Literal["current", "historical", "missing"]
    listing: ListingSummary | None
    added_at: UtcInstant
    expires_at: UtcInstant

    @model_validator(mode="after")
    def exact_saved_listing(self) -> "ShortlistItem":
        if (self.state == "missing") != (self.listing is None):
            raise ValueError("Only a missing saved listing has no summary.")
        if self.listing is not None and self.listing.ref != self.ref:
            raise ValueError("Saved item and listing must use the same exact reference.")
        return self


class ShortlistResult(DTO):
    revision: Revision
    items: Annotated[list[ShortlistItem], Field(max_length=50)]
    total: Annotated[int, Field(strict=True, ge=0)]
    next_cursor: Annotated[str, Field(max_length=2048, strict=True)] | None

    @model_validator(mode="after")
    def coherent_page(self) -> "ShortlistResult":
        if self.total < len(self.items) or (not self.items and self.next_cursor is not None):
            raise ValueError("Shortlist page must agree with its total and continuation.")
        return self


class MembershipResult(DTO):
    ref: InventoryRef
    client_action_id: Id
    saved: StrictBool
    changed_at_apply: StrictBool
    replayed: StrictBool
    applied_revision: Revision
    current_revision: Revision
    reference_state: Literal["current", "historical", "missing"]


class MembershipRequest(DTO):
    client_action_id: Id
    expected_revision: Revision
