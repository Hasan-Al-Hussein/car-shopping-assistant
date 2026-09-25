"""Internal detached command bindings and receipt observations, never write authority."""

from dataclasses import dataclass, field
from typing import Literal

from app.api.schemas.leads import LeadRecord
from app.shortlist.inventory import ReferenceBatch


@dataclass(frozen=True)
class LeadChangeEnvelope:
    owner_id: str
    submitted_store_generation: str
    source_message_id: str | None
    lead_id: str | None
    command_type: Literal["save", "update"]
    command_json: bytes = field(repr=False)
    payload_hash: str


@dataclass(frozen=True)
class PreparedLeadChange:
    envelope: LeadChangeEnvelope
    references: ReferenceBatch | None


@dataclass(frozen=True)
class _CommandIdentity:
    client_action_id: str
    payload_hash: str
    submitted_store_generation: str
    observed_store_generation: str


@dataclass(frozen=True)
class LeadCommandKnown(_CommandIdentity):
    accepted: LeadRecord = field(repr=False)
    accepted_at: str
    replay_valid_until: str
    generation_relation: Literal["same_generation", "historical_generation"]
    state: Literal["known"] = field(default="known", init=False)
    csv_basis: Literal["receipt_snapshot"] = field(default="receipt_snapshot", init=False)


@dataclass(frozen=True)
class LeadCommandAbsent(_CommandIdentity):
    state: Literal["absent"] = field(default="absent", init=False)
    definitive_noncommit: Literal[False] = field(default=False, init=False)


@dataclass(frozen=True)
class LeadCommandExpired(_CommandIdentity):
    replay_valid_until: str
    state: Literal["expired"] = field(default="expired", init=False)


@dataclass(frozen=True)
class LeadCommandUnreconciled(_CommandIdentity):
    reason: Literal["generation_changed", "canonical_authority_missing"]
    state: Literal["unreconciled"] = field(default="unreconciled", init=False)
    definitive_noncommit: Literal[False] = field(default=False, init=False)


type LeadCommandObservation = (
    LeadCommandKnown | LeadCommandAbsent | LeadCommandExpired | LeadCommandUnreconciled
)
type LeadPreparation = (
    PreparedLeadChange | LeadCommandKnown | LeadCommandExpired | LeadCommandUnreconciled
)
