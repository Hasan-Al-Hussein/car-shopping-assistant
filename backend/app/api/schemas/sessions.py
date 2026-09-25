"""Ordered, owner-scoped conversation state and explicit presentation registration."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.api.schemas.common import DTO, Id, InventoryRef, OpaqueKey, Revision, ShortText, UtcInstant
from app.api.schemas.inventory import (
    ComparisonResult,
    HandoffSummary,
    PresentationProof,
    SearchCriteria,
    SearchResult,
)
from app.api.schemas.leads import LeadSaveResult
from app.api.schemas.memory import MembershipResult, PreferenceRecord
from app.api.schemas.operations import OperationStatus
from app.api.schemas.viewings import ConfirmRequest


class SessionCreateRequest(DTO):
    client_action_id: Id


class NoPendingIntent(DTO):
    kind: Literal["none"]


class ClarificationIntent(DTO):
    kind: Literal["clarification"]
    intent_id: Id
    created_revision: Revision
    purpose: Literal["search_criteria", "listing_reference", "viewing_details", "action_intent"]
    targets: Annotated[
        list[
            Literal[
                "query",
                "makes",
                "models",
                "trims",
                "years",
                "budget",
                "mileage_km",
                "body_types",
                "fuel_types",
                "transmissions",
                "soft_preferences",
                "selected_ref",
                "appointment",
                "confirmation",
                "preference_scope",
            ]
        ],
        Field(min_length=1, max_length=12),
    ]
    question: ShortText

    @model_validator(mode="after")
    def purpose_matches_targets(self) -> "ClarificationIntent":
        permitted = {
            "search_criteria": {
                "query",
                "makes",
                "models",
                "trims",
                "years",
                "budget",
                "mileage_km",
                "body_types",
                "fuel_types",
                "transmissions",
                "soft_preferences",
            },
            "listing_reference": {"selected_ref"},
            "viewing_details": {"appointment"},
            "action_intent": {"confirmation", "preference_scope"},
        }
        if (
            len(set(self.targets)) != len(self.targets)
            or not set(self.targets) <= permitted[self.purpose]
        ):
            raise ValueError("Clarification targets must be distinct and match their purpose.")
        return self


class ViewingReviewIntent(DTO):
    kind: Literal["viewing_review"]
    draft_id: Id
    review_id: Id
    operation_key: OpaqueKey


class UnresolvedOperationIntent(DTO):
    kind: Literal["operation_unresolved"]
    draft_id: Id
    operation_key: OpaqueKey
    submitted_store_generation: Id


PendingIntent = Annotated[
    NoPendingIntent | ClarificationIntent | ViewingReviewIntent | UnresolvedOperationIntent,
    Field(discriminator="kind"),
]


class SessionState(DTO):
    session_id: Id
    journey_id: Id
    revision: Revision
    criteria: SearchCriteria
    selected_ref: InventoryRef | None
    active_presentation_id: Id | None
    current_draft_id: Id | None
    pending_intent: PendingIntent
    recalled_preferences: PreferenceRecord

    @model_validator(mode="after")
    def coherent_pending_context(self) -> "SessionState":
        if isinstance(self.pending_intent, ClarificationIntent) and (
            self.pending_intent.created_revision > self.revision
        ):
            raise ValueError("Pending clarification cannot originate in a future revision.")
        if isinstance(self.pending_intent, ViewingReviewIntent | UnresolvedOperationIntent) and (
            self.pending_intent.draft_id != self.current_draft_id
        ):
            raise ValueError("Pending viewing intent must reference the retained current draft.")
        return self


class PresentationRegisterRequest(DTO):
    expected_revision: Revision
    client_action_id: Id
    presentation: PresentationProof


class SessionSelectionRequest(DTO):
    expected_revision: Revision
    client_action_id: Id
    selected_ref: InventoryRef
    presentation_id: Id | None = None


class ExplicitConfirmation(ConfirmRequest):
    draft_id: Id


class ClarificationReply(DTO):
    intent_id: Id
    created_revision: Revision


class MessageRequest(DTO):
    client_message_id: Id
    expected_revision: Revision
    text: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4000)]
    selected_ref: InventoryRef | None = None
    presentation_id: Id | None = None
    explicit_confirmation: ExplicitConfirmation | None = None
    clarification_reply: ClarificationReply | None = None


class AnswerEvidence(DTO):
    ref: InventoryRef
    attributes: Annotated[list[ShortText], Field(max_length=24)]


class ActionNotRequested(DTO):
    state: Literal["not_requested"] = "not_requested"


class ActionRejected(DTO):
    state: Literal["rejected"]
    client_action_id: Id
    code: Literal["VALIDATION_ERROR", "REVISION_CONFLICT", "UNSUPPORTED_STATE", "LEAD_EXISTS"]


class ActionUnresolved(DTO):
    state: Literal["unresolved"]
    client_action_id: Id
    submitted_store_generation: Id
    recovery: Literal["read_current_state", "retry_same_action", "operator_reconciliation"]


class PreferenceActionSucceeded(DTO):
    state: Literal["succeeded"]
    client_action_id: Id
    result: PreferenceRecord


class ShortlistActionSucceeded(DTO):
    state: Literal["succeeded"]
    client_action_id: Id
    result: MembershipResult

    @model_validator(mode="after")
    def same_action(self) -> "ShortlistActionSucceeded":
        if self.client_action_id != self.result.client_action_id:
            raise ValueError("Shortlist action must identify its exact membership command.")
        return self


class LeadActionSucceeded(DTO):
    state: Literal["succeeded"]
    client_action_id: Id
    result: LeadSaveResult


class MessageActionResults(DTO):
    preferences: Annotated[
        ActionNotRequested | PreferenceActionSucceeded | ActionRejected | ActionUnresolved,
        Field(discriminator="state"),
    ] = Field(default_factory=ActionNotRequested)
    shortlist: Annotated[
        ActionNotRequested | ShortlistActionSucceeded | ActionRejected | ActionUnresolved,
        Field(discriminator="state"),
    ] = Field(default_factory=ActionNotRequested)
    lead: Annotated[
        ActionNotRequested | LeadActionSucceeded | ActionRejected | ActionUnresolved,
        Field(discriminator="state"),
    ] = Field(default_factory=ActionNotRequested)


class MessageResult(DTO):
    client_message_id: Id
    session_id: Id
    turn_revision: Revision
    current_revision: Revision
    state: Literal["answered", "clarification", "provider_unavailable", "superseded"]
    text: Annotated[str, StringConstraints(strict=True, max_length=12000)]
    evidence: Annotated[list[AnswerEvidence], Field(max_length=10)] = []
    search: SearchResult | None = None
    comparison: ComparisonResult | None = None
    handoff_summary: HandoffSummary | None = None
    pending_intent: PendingIntent
    operation: OperationStatus | None = None
    actions: MessageActionResults = Field(default_factory=MessageActionResults)
    persistence: Literal["saved", "not_saved"]
    provider_state: Literal["not_used", "available", "unavailable"]

    @model_validator(mode="after")
    def revision_order(self) -> "MessageResult":
        if self.current_revision < self.turn_revision:
            raise ValueError("Current revision cannot precede this turn.")
        return self


class TranscriptTurn(DTO):
    message_id: Id
    client_message_id: Id
    session_id: Id
    accepted_revision: Revision
    accepted_at: UtcInstant
    user_text: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4000)]
    state: Literal["completed", "pending", "interrupted"]
    historical: Literal[True] = True
    assistant_result: MessageResult | None

    @model_validator(mode="after")
    def coherent_turn(self) -> "TranscriptTurn":
        if (self.state == "completed") != (self.assistant_result is not None):
            raise ValueError("Only a completed turn contains its original assistant result.")
        if self.assistant_result is not None and (
            self.session_id,
            self.client_message_id,
            self.accepted_revision,
        ) != (
            self.assistant_result.session_id,
            self.assistant_result.client_message_id,
            self.assistant_result.turn_revision,
        ):
            raise ValueError("Transcript must retain the exact original turn result.")
        return self


class TranscriptPage(DTO):
    session_id: Id
    observed_revision: Revision
    items: Annotated[list[TranscriptTurn], Field(max_length=50)]
    next_cursor: Annotated[str, StringConstraints(strict=True, max_length=2048)] | None

    @model_validator(mode="after")
    def ordered_owned_page(self) -> "TranscriptPage":
        revisions = [turn.accepted_revision for turn in self.items]
        if revisions != sorted(set(revisions)):
            raise ValueError("Transcript turns must be in increasing accepted revision order.")
        if any(
            turn.session_id != self.session_id or turn.accepted_revision > self.observed_revision
            for turn in self.items
        ):
            raise ValueError(
                "Transcript page must retain its session and observed revision boundary."
            )
        if not self.items and self.next_cursor is not None:
            raise ValueError("An empty transcript page cannot have a continuation.")
        return self
