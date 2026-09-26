"""Trusted async facades only; actual P9/BE06/07 composition requires its own grant."""

from typing import Protocol

from app.api.schemas.common import InventoryRef
from app.api.schemas.inventory import (
    ComparisonRequest,
    ComparisonResult,
    ListingResult,
    PresentationProof,
    SearchRequest,
    SearchResult,
)
from app.api.schemas.sessions import MessageRequest, MessageResult, SessionState, TranscriptTurn
from app.core.errors import ApiFailure
from app.identity.authorization import AuthorizedOwnerContext
from app.sessions.service import TurnAdmission, TurnTicket
from app.sessions.state import SessionContent


class SessionPort(Protocol):
    """P9C facade: matched begin retains clarification; only current completion resolves.

    No model callback inside a Store unit. Provider-unavailable completion preserves an
    existing question exactly. All methods require bounded caller/worker scheduling.
    """

    async def begin(
        self, context: AuthorizedOwnerContext, session_id: str, request: MessageRequest
    ) -> TurnAdmission: ...
    async def get(self, context: AuthorizedOwnerContext, session_id: str) -> SessionState: ...
    async def recent_context(
        self,
        context: AuthorizedOwnerContext,
        session_id: str,
        *,
        before_revision: int,
    ) -> tuple[TranscriptTurn, ...]: ...
    async def ordinal(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str, ordinal: int
    ) -> InventoryRef: ...
    async def original_refs(
        self, context: AuthorizedOwnerContext, session_id: str, presentation_id: str
    ) -> tuple[InventoryRef, ...]:
        """Adapt approved P9 owned presentation view to detached, ordered exact refs."""
        ...

    async def complete(
        self,
        context: AuthorizedOwnerContext,
        ticket: TurnTicket,
        result: MessageResult,
        *,
        update: SessionContent | None = None,
        presentation: PresentationProof | None = None,
        selection: InventoryRef | None = None,
    ) -> MessageResult: ...


class InventoryReadPort(Protocol):
    """One coherent exact read per call; caller deadline, no hidden retry or substitution."""

    async def search(self, request: SearchRequest, *, deadline_at: float) -> SearchResult: ...
    async def detail(self, ref: InventoryRef, *, deadline_at: float) -> ListingResult: ...
    async def compare(
        self, request: ComparisonRequest, *, deadline_at: float
    ) -> ComparisonResult: ...
    async def original_batch(
        self, refs: tuple[InventoryRef, ...], *, deadline_at: float
    ) -> tuple[ListingResult, ...]:
        """Up to 50 original refs in order, exact historical facts; no current-ID lookup."""
        ...


class CatalogVocabularyPort(Protocol):
    """Optional advisory labels, not proof of inventory matches or complete coverage."""

    async def catalog_vocabulary(
        self, *, deadline_at: float
    ) -> dict[str, tuple[str, ...]]: ...


class UnconfiguredInventory:
    """Honest unavailable boundary, not a permissive production fake."""

    async def search(self, request: SearchRequest, *, deadline_at: float) -> SearchResult:
        raise ApiFailure("STORE_UNAVAILABLE")

    async def catalog_vocabulary(self, *, deadline_at: float) -> dict[str, tuple[str, ...]]:
        return {}

    async def detail(self, ref: InventoryRef, *, deadline_at: float) -> ListingResult:
        raise ApiFailure("STORE_UNAVAILABLE")

    async def compare(self, request: ComparisonRequest, *, deadline_at: float) -> ComparisonResult:
        raise ApiFailure("STORE_UNAVAILABLE")

    async def original_batch(
        self, refs: tuple[InventoryRef, ...], *, deadline_at: float
    ) -> tuple[ListingResult, ...]:
        raise ApiFailure("STORE_UNAVAILABLE")
