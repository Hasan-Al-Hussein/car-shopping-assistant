"""Versioned storage payloads within the existing session/message JSON columns."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import Digest, Id, InventoryRef
from app.api.schemas.inventory import PresentationProof, SearchCriteria
from app.api.schemas.sessions import MessageRequest, MessageResult, NoPendingIntent, PendingIntent
from app.core.config import FrozenSettings
from app.sessions.collection import CollectionEnvelope, RetainedCollectionCommand


class StoredPayload(FrozenSettings):
    model_config = ConfigDict(revalidate_instances="always")


class SessionContent(StoredPayload):
    version: Literal["session-state-1"] = "session-state-1"
    criteria: SearchCriteria = Field(default_factory=SearchCriteria)
    selected_ref: InventoryRef | None = None
    active_presentation_id: Id | None = None
    current_draft_id: Id | None = None
    pending_intent: PendingIntent = Field(default_factory=lambda: NoPendingIntent(kind="none"))
    collection: CollectionEnvelope | None = None


class StoredMessage(StoredPayload):
    version: Literal["session-message-1"] = "session-message-1"
    request: MessageRequest
    worker_epoch: Id
    assistant_result: MessageResult | None = None
    completion_hash: Digest | None = None
    applied_public_proof: PresentationProof | None = None
    applied_presentation_id: Id | None = None
    applied_selection: InventoryRef | None = None
    collection_command: RetainedCollectionCommand | None = None


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def copied[T: BaseModel](model: type[T], value: T) -> T:
    """Revalidate a detached copy, including unchecked model_copy/construct inputs."""
    return model.model_validate(value.model_dump(mode="json"))
