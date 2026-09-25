"""Detached draft command/effect bindings; no session, ORM or live reply authority."""

from dataclasses import dataclass, field

from app.viewings.draft_admission import PreparedViewing


@dataclass(frozen=True)
class PreparedDraftChange:
    owner_id: str
    generation: str
    source_message_id: str | None
    session_id: str
    draft_id: str | None
    command_json: bytes = field(repr=False)
    payload_hash: str
    viewing: PreparedViewing | None


@dataclass(frozen=True)
class DraftCommandObservation:
    draft_id: str
    session_id: str
    applied_revision: int


@dataclass(frozen=True)
class DraftSessionTransition:
    owner_id: str
    generation: str
    session_id: str
    draft_id: str
    draft_revision: int
    source_message_id: str | None
    command_hash: str
    before_revision: int
    final_revision: int
    before_draft_id: str | None
    before_pending_json: bytes = field(repr=False)
    after_draft_id: str | None
    after_pending_json: bytes = field(repr=False)


@dataclass(frozen=True)
class DraftChangeEffect:
    draft_id: str
    session_id: str
    applied_revision: int
    replayed: bool
    transition: DraftSessionTransition | None
