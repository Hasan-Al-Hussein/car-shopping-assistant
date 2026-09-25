"""Process-authenticated inventory content identity; never owner/action authority."""

import hashlib
import hmac
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.common import Digest
from app.core.readiness import InventoryObservation
from app.inventory.persisted_fingerprint import FINGERPRINT_VERSION
from app.inventory.references import ImmutableInventoryRef

READ_IDENTITY_VERSION: Final = "inventory-read-1"
MAX_REFERENCE_BATCH = 50
MAX_IDENTITY_PARTS = 128
IDENTITY_PART_SIZE = 512
CertificateId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$", strict=True)]


class ReferenceIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    ref: ImmutableInventoryRef
    state: Literal["current", "historical", "missing"]


class AdmittedIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: Literal["inventory-read-1"] = READ_IDENTITY_VERSION
    fingerprint_version: Literal["inventory-persisted-1"] = FINGERPRINT_VERSION
    schema_version: Literal["0002"] = "0002"
    mode: Literal["fts5", "bounded_lexical"]
    epoch: Annotated[int, Field(strict=True, ge=0)]
    observation: InventoryObservation
    references: Annotated[tuple[ReferenceIdentity, ...], Field(max_length=MAX_REFERENCE_BATCH)]
    certificates: Annotated[tuple[tuple[Digest, CertificateId], ...], Field(max_length=51)]


def issue_identity(key: bytes, value: AdmittedIdentity) -> tuple[str, ...]:
    payload = value.model_dump_json()
    parts = tuple(
        payload[offset : offset + IDENTITY_PART_SIZE]
        for offset in range(0, len(payload), IDENTITY_PART_SIZE)
    )
    if len(parts) + 2 > MAX_IDENTITY_PARTS:
        raise ValueError("INVENTORY_READ_IDENTITY_LIMIT")
    signature = hmac.new(
        key, (READ_IDENTITY_VERSION + "\0" + payload).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return (READ_IDENTITY_VERSION, *parts, signature)


def verify_identity(key: bytes, value: tuple[str, ...]) -> AdmittedIdentity:
    if (
        type(value) is not tuple
        or not 3 <= len(value) <= MAX_IDENTITY_PARTS
        or any(type(part) is not str or not 1 <= len(part) <= IDENTITY_PART_SIZE for part in value)
        or value[0] != READ_IDENTITY_VERSION
        or len(value[-1]) != 64
        or not value[-1].isascii()
    ):
        raise ValueError("INVENTORY_READ_IDENTITY_INVALID")
    payload = "".join(value[1:-1])
    signature = hmac.new(
        key, (READ_IDENTITY_VERSION + "\0" + payload).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, value[-1]):
        raise ValueError("INVENTORY_READ_IDENTITY_INVALID")
    return AdmittedIdentity.model_validate_json(payload)
