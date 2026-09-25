"""Bounded private collection values and exact, process-local draft reply authority."""

import hashlib
import json
import re
from dataclasses import dataclass, field as private_field
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from app.api.schemas.common import Digest, Id, InventoryRef, Revision, ShortText, UtcInstant
from app.api.schemas.leads import BudgetValue, LeadSaveRequest, LeadUpdateRequest
from app.api.schemas.sessions import ClarificationIntent
from app.api.schemas.viewings import BookingDraftCreate, BookingDraftUpdate
from app.core.config import FrozenSettings
from app.core.errors import ApiFailure
from app.identity.authorization import OwnerUnit

FieldName = Literal["budget", "requirements", "ref", "local_date", "local_time"]
Purpose = Literal["local_enquiry", "viewing"]
MAX_COLLECTION_BYTES = 16_384
_REPLY_ISSUER = object()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


class FieldSource(FrozenSettings):
    field: FieldName
    start: Annotated[int, Field(ge=0, le=3999)]
    end: Annotated[int, Field(ge=1, le=4000)]

    @model_validator(mode="after")
    def ordered(self) -> "FieldSource":
        if self.end <= self.start:
            raise ValueError("COLLECTION_SOURCE_BOUNDS")
        return self


class StoredFieldSource(FieldSource):
    message_id: Id


class CollectionValues(FrozenSettings):
    budget: BudgetValue = Field(default_factory=lambda: BudgetValue(state="missing"))
    requirements: Annotated[list[ShortText], Field(max_length=24)] = Field(default_factory=list)
    requirements_state: Literal["missing", "provided", "declined"] = "missing"
    ref: InventoryRef | None = None
    local_date: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")] | None = None
    local_time: Annotated[str, StringConstraints(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")] | None = None

    @model_validator(mode="after")
    def coherent(self) -> "CollectionValues":
        if (self.requirements_state == "provided") != bool(self.requirements):
            raise ValueError("COLLECTION_REQUIREMENTS_STATE")
        if self.local_date is not None:
            date.fromisoformat(self.local_date)
        # Defense in depth: Assistant must already route contact-bearing input locally.
        if any(re.search(r"[^\s@]+@[^\s@]+|(?:\+?\d[\s().-]*){7,}", text)
               for text in self.requirements):
            raise ValueError("COLLECTION_CONTACT_NOT_SUPPORTED")
        return self


class LeadBinding(FrozenSettings):
    lead_id: Id
    revision: Revision


class CollectionUpdate(FrozenSettings):
    expected_digest: Digest | None
    purpose: Purpose
    values: CollectionValues | None
    sources: Annotated[list[FieldSource], Field(max_length=5)] = Field(default_factory=list)
    question: ClarificationIntent | None = None
    display_local_enquiry: bool = False
    lead_binding: LeadBinding | None = None

    @model_validator(mode="after")
    def coherent(self) -> "CollectionUpdate":
        if len({source.field for source in self.sources}) != len(self.sources):
            raise ValueError("COLLECTION_DUPLICATE_SOURCE")
        if self.values is None and (
            self.sources or self.question is not None or self.display_local_enquiry
            or self.lead_binding is not None
        ):
            raise ValueError("COLLECTION_CLEAR_HAS_VALUES")
        return self


class CollectionEnvelope(FrozenSettings):
    version: Literal["session-collection-1"] = "session-collection-1"
    collection_id: Id
    revision: Revision
    owner_id: Id
    session_id: Id
    store_generation: Id
    created_at: UtcInstant
    expires_at: UtcInstant
    source_message_id: Id
    updated_message_id: Id
    purpose: Purpose
    values: CollectionValues
    provenance: Annotated[list[StoredFieldSource], Field(max_length=5)]
    question: ClarificationIntent | None = None
    displayed_values_digest: Digest | None = None
    lead_binding: LeadBinding | None = None

    @model_validator(mode="after")
    def coherent(self) -> "CollectionEnvelope":
        if (
            datetime.fromisoformat(self.expires_at) <= datetime.fromisoformat(self.created_at)
            or len({entry.field for entry in self.provenance}) != len(self.provenance)
            or len(_canonical(self.model_dump(mode="json"))) > MAX_COLLECTION_BYTES
        ):
            raise ValueError("COLLECTION_ENVELOPE_INVALID")
        if self.displayed_values_digest is not None and (
            self.question is None or self.question.purpose != "action_intent"
            or self.question.targets != ["confirmation"]
            or self.displayed_values_digest != collection_values_digest(self.values, self.lead_binding)
        ):
            raise ValueError("COLLECTION_DISPLAY_BINDING_INVALID")
        return self


class RetainedCollectionCommand(FrozenSettings):
    version: Literal["session-collection-command-1"] = "session-collection-command-1"
    kind: Literal["lead", "draft"]
    source_message_id: Id
    session_id: Id
    submitted_store_generation: Id
    request_hash: Digest
    command_hash: Digest
    command: LeadSaveRequest | LeadUpdateRequest | BookingDraftCreate | BookingDraftUpdate
    lead_id: Id | None = None
    draft_id: Id | None = None
    completion_hash: Digest
    completion_json: Annotated[str, StringConstraints(max_length=65_536)]

    @model_validator(mode="after")
    def coherent(self) -> "RetainedCollectionCommand":
        lead = isinstance(self.command, LeadSaveRequest | LeadUpdateRequest)
        if lead != (self.kind == "lead") or (lead and self.draft_id is not None) or (
            not lead and self.lead_id is not None
        ):
            raise ValueError("COLLECTION_COMMAND_KIND")
        if (
            isinstance(self.command, LeadSaveRequest) and self.lead_id is not None
            or isinstance(self.command, LeadUpdateRequest) and self.lead_id is None
            or isinstance(self.command, BookingDraftCreate) and self.draft_id is not None
            or isinstance(self.command, BookingDraftUpdate) and self.draft_id is None
        ):
            raise ValueError("COLLECTION_COMMAND_TARGET")
        if isinstance(self.command, LeadSaveRequest | LeadUpdateRequest | BookingDraftCreate) and self.command.session_id != self.session_id:
            raise ValueError("COLLECTION_COMMAND_SESSION")
        body = self.command.model_dump(mode="json")
        expected = dict(lead_id=self.lead_id, command=body) if lead else (
            dict(command="create", body=body) if isinstance(self.command, BookingDraftCreate)
            else dict(command="update", draft_id=self.draft_id, body=body)
        )
        if hashlib.sha256(_canonical(expected)).hexdigest() != self.command_hash:
            raise ValueError("COLLECTION_COMMAND_HASH")
        if len(self.completion_json.encode("utf-8")) > 65_536 or (
            hashlib.sha256(self.completion_json.encode("utf-8")).hexdigest() != self.completion_hash
        ):
            raise ValueError("COLLECTION_COMPLETION_BINDING")
        material = json.loads(self.completion_json)
        if not isinstance(material, dict) or _canonical(material).decode("utf-8") != self.completion_json or (
            material.get("kind") != "session-collection-completion-1"
            or _canonical(material.get("command")) != _canonical(body) or material.get("lead_id") != self.lead_id
            or material.get("draft_id") != self.draft_id
        ):
            raise ValueError("COLLECTION_COMPLETION_MATERIAL")
        return self


@dataclass(frozen=True)
class CollectionSnapshot:
    collection: CollectionEnvelope | None = private_field(repr=False)
    digest: str | None
    expired: bool
    now: str
    unresolved: RetainedCollectionCommand | None = private_field(repr=False)


def collection_digest(value: CollectionEnvelope | None) -> str | None:
    return None if value is None else hashlib.sha256(_canonical(value.model_dump(mode="json"))).hexdigest()


def collection_values_digest(values: CollectionValues, lead_binding: LeadBinding | None) -> str:
    return hashlib.sha256(_canonical({
        "version": "collection-displayed-values-1", "values": values.model_dump(mode="json"),
        "lead_binding": None if lead_binding is None else lead_binding.model_dump(mode="json"),
    })).hexdigest()


class DraftReplyAuthority:
    """No constructor or serialized representation. Only SessionService issues this."""

    __slots__ = ("_issuer", "_owner_id", "_session_id", "_generation", "_message_id",
                 "_epoch", "_request_hash", "_question_json", "_collection_digest", "_command_hash")
    _issuer: object
    _owner_id: str
    _session_id: str
    _generation: str
    _message_id: str
    _epoch: str
    _request_hash: str
    _question_json: bytes
    _collection_digest: str
    _command_hash: str

    def __new__(cls) -> "DraftReplyAuthority":
        raise TypeError("DRAFT_REPLY_AUTHORITY_IS_SERVICE_ISSUED")

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("DRAFT_REPLY_AUTHORITY_IS_IMMUTABLE")

    def __repr__(self) -> str:
        return "<DraftReplyAuthority>"


@dataclass(frozen=True)
class _DraftReplyMaterial:
    owner_id: str
    session_id: str
    generation: str
    message_id: str
    epoch: str
    request_hash: str
    question_json: bytes
    collection_digest: str
    command_hash: str


def _draft_reply_material(
    unit: OwnerUnit, *, session_id: str, generation: str, message_id: str,
    epoch: str, command_hash: str, command: BookingDraftCreate | BookingDraftUpdate,
    now: str,
) -> _DraftReplyMaterial | None:
    from app.sessions import repository as repo

    row = unit.session(session_id)
    content = repo.content(row)
    question = content.pending_intent
    if not isinstance(question, ClarificationIntent):
        return None
    collection = content.collection
    if (collection is None or collection.purpose != "viewing" or collection.question != question
        or collection.displayed_values_digest is not None):
        raise ApiFailure("UNSUPPORTED_STATE")
    intent = "create" if isinstance(command, BookingDraftCreate) else command.intent
    allowed = intent in {"suspend", "discard"}
    if question.purpose == "listing_reference":
        allowed |= intent == "create" or (
            intent == "edit" and command.ref is not None and command.appointment is None
        )
    elif question.purpose == "viewing_details":
        allowed |= intent in {"create", "refresh_review"} or (
            intent == "edit" and command.appointment is not None and command.ref is None
        )
    elif question.purpose == "action_intent" and question.targets == ["confirmation"]:
        allowed = intent in {"create", "refresh_review", "discard"}
    else:
        allowed = False
    if not allowed:
        raise ApiFailure("UNSUPPORTED_STATE")
    message = unit.message(session_id, message_id)
    digest = collection_digest(collection)
    assert digest is not None
    material = _DraftReplyMaterial(
        unit.owner_id, session_id, generation, message_id, epoch, message.payload_hash,
        _canonical(question.model_dump(mode="json")), digest, command_hash,
    )
    authority = _issue_draft_reply(material)
    assert authority is not None
    check_draft_reply_in_unit(unit, authority, session_id=session_id,
                             generation=generation, command_hash=command_hash, now=now)
    return material


def _issue_draft_reply(material: _DraftReplyMaterial | None) -> DraftReplyAuthority | None:
    """Mint outside the Store callback; only scalar material crosses that boundary."""
    if material is None:
        return None
    authority = object.__new__(DraftReplyAuthority)
    for key, value in {
        "_issuer": _REPLY_ISSUER, "_owner_id": material.owner_id, "_session_id": material.session_id,
        "_generation": material.generation, "_message_id": material.message_id, "_epoch": material.epoch,
        "_request_hash": material.request_hash,
        "_question_json": material.question_json,
        "_collection_digest": material.collection_digest, "_command_hash": material.command_hash,
    }.items():
        object.__setattr__(authority, key, value)
    return authority


def check_draft_reply_in_unit(
    unit: OwnerUnit, reply: DraftReplyAuthority, *, session_id: str,
    generation: str, command_hash: str, now: str,
) -> None:
    from app.sessions import repository as repo

    if type(reply) is not DraftReplyAuthority or getattr(reply, "_issuer", None) is not _REPLY_ISSUER:
        raise ApiFailure("UNSUPPORTED_STATE")
    if (unit.owner_id, session_id, generation, command_hash) != (
        reply._owner_id, reply._session_id, reply._generation, reply._command_hash,
    ):
        raise ApiFailure("UNSUPPORTED_STATE")
    row = repo.live_session(unit, session_id, now)
    content = repo.content(row)
    value = content.collection
    message = unit.message(session_id, reply._message_id)
    saved = repo.message_content(message)
    question = content.pending_intent
    echoed = saved.request.clarification_reply
    if (
        value is None or datetime.fromisoformat(value.expires_at) <= datetime.fromisoformat(now)
        or value.owner_id != unit.owner_id
        or value.session_id != session_id or value.store_generation != generation
        or value.purpose != "viewing" or collection_digest(value) != reply._collection_digest
        or message.state != "pending" or message.accepted_revision != row.revision
        or message.payload_hash != reply._request_hash or saved.worker_epoch != reply._epoch
        or saved.assistant_result is not None or not isinstance(question, ClarificationIntent)
        or value.question != question or echoed is None
        or (echoed.intent_id, echoed.created_revision) != (question.intent_id, question.created_revision)
        or _canonical(question.model_dump(mode="json")) != reply._question_json
    ):
        raise ApiFailure("REVISION_CONFLICT")
