"""Keyless public search-signing injection agreed with Platform; no concrete signer."""

from datetime import datetime
from typing import Annotated, Literal, Protocol, Self

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from app.api.schemas.common import DTO, Digest, Id, UtcInstant
from app.api.schemas.inventory import PresentationProof
from app.inventory.references import ImmutableInventoryRef

SourceId = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9._-]{1,128}$")]


class SearchSortKey(DTO):
    model_config = ConfigDict(frozen=True)
    preference_score: Annotated[int, Field(strict=True, ge=0, le=24)]
    source_id: SourceId


class SearchCursorPosition(DTO):
    model_config = ConfigDict(frozen=True)
    namespace: Annotated[str, StringConstraints(strict=True, pattern=r"^[a-z0-9_-]{1,64}$")]
    snapshot_id: Digest
    index_version: Digest
    ranking_version: Annotated[
        str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9._-]{1,64}$")
    ]
    criteria_hash: Digest
    sort_key: SearchSortKey
    position: Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]
    generation: Id
    active_revision: Annotated[int, Field(strict=True, ge=1, le=2_147_483_647)]


class SearchCursorClaims(DTO):
    model_config = ConfigDict(frozen=True)
    version: Literal["inventory-search-cursor-1"] = "inventory-search-cursor-1"
    position: SearchCursorPosition
    issued_at: UtcInstant
    expires_at: UtcInstant

    @model_validator(mode="after")
    def ordered_time(self) -> Self:
        if datetime.fromisoformat(self.issued_at) >= datetime.fromisoformat(self.expires_at):
            raise ValueError("INVENTORY_CURSOR_INTERVAL_INVALID")
        return self


class PublicInventorySigner(Protocol):
    """Platform owns keys, canonical encoding, purpose, expiry and rotation.

    Domain input is detached and revalidated by the signer. Continuation authenticates
    the original token and preserves its original expiry; no signing fallback exists.
    """

    def sign_presentation(
        self,
        *,
        snapshot_id: str,
        ordered_refs: tuple[ImmutableInventoryRef, ...],
        criteria_hash: str,
        now: datetime,
    ) -> PresentationProof: ...

    def verify_presentation(self, proof: PresentationProof, *, now: datetime) -> None: ...

    def encode_search_cursor(
        self,
        position: SearchCursorPosition,
        *,
        now: datetime,
        continuation: str | None = None,
    ) -> str: ...

    def decode_search_cursor(self, token: str, *, now: datetime) -> SearchCursorClaims: ...
