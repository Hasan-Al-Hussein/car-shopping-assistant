"""Real read-only search with coherent index/projection and signed page continuity."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import cast

from sqlalchemy.orm import Session

from app.api.schemas.inventory import SearchCriteria, SearchRequest, SearchResult
from app.core.errors import ApiFailure
from app.core.readiness import InventoryObservation
from app.inventory.compact_reader import CompactBatch, CompactInventoryReader
from app.inventory.public_errors import public_read_failure
from app.inventory.public_projection import map_listing_summary
from app.inventory.read_budget import check_deadline, read_deadline
from app.inventory.references import ImmutableInventoryRef
from app.inventory.search_contracts import (
    PublicInventorySigner,
    SearchCursorPosition,
    SearchSortKey,
)
from app.inventory.search_policy import RANKING_VERSION, normalize_criteria
from app.inventory.search_sql import SearchSelection, select_matches

SEARCH_WORK_SECONDS = 2.0


def _clock() -> datetime:
    return datetime.now(UTC)


def _no_checkpoint(phase: str) -> None:
    pass


class InventorySearchService:
    def __init__(
        self,
        reader: CompactInventoryReader,
        signer: PublicInventorySigner,
        *,
        clock: Callable[[], datetime] = _clock,
        _checkpoint: Callable[[str], None] = _no_checkpoint,
    ) -> None:
        self.reader = reader
        self.signer = signer
        self.clock = clock
        self._checkpoint = _checkpoint

    @staticmethod
    def _context(
        position: SearchCursorPosition, observation: InventoryObservation, criteria_hash: str
    ) -> None:
        if position.criteria_hash != criteria_hash:
            raise ApiFailure("VALIDATION_ERROR")
        if (
            position.snapshot_id != observation.snapshot_id
            or position.index_version != observation.index_version
            or position.generation != observation.generation
            or position.active_revision != observation.active_revision
            or position.ranking_version != RANKING_VERSION
        ):
            raise ApiFailure("SNAPSHOT_STALE")

    def search(self, supplied: SearchRequest, *, deadline_at: float | None = None) -> SearchResult:
        deadline = read_deadline(deadline_at, seconds=SEARCH_WORK_SECONDS)
        check_deadline(deadline)
        request = SearchRequest.model_validate(supplied.model_dump())
        criteria = SearchCriteria(
            query=request.query, filters=request.filters, soft_preferences=request.soft_preferences
        )
        policy = normalize_criteria(criteria)
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("INVENTORY_SERVER_CLOCK_REQUIRES_UTC")
        position = (
            self.signer.decode_search_cursor(request.cursor, now=now).position
            if request.cursor is not None
            else None
        )
        if position is not None:
            position = SearchCursorPosition.model_validate(position.model_dump(mode="json"))
            if request.snapshot_id is not None and request.snapshot_id != position.snapshot_id:
                raise ApiFailure("VALIDATION_ERROR")
        try:
            anchor = self.reader.read_search_anchor()
            observation = anchor.observation
            if observation.snapshot_id is None or observation.index_version is None:
                raise ApiFailure("UNSUPPORTED_STATE")
            if request.snapshot_id is not None and request.snapshot_id != observation.snapshot_id:
                raise ApiFailure("SNAPSHOT_STALE")
            if position is not None:
                self._context(position, observation, policy.criteria_hash)
            check_deadline(deadline)
            self._checkpoint("search.before_index")

            def select(session: Session) -> SearchSelection:
                self.reader._check_search_anchor(anchor)
                self.reader.recheck_identity(session, anchor.identity, expected_refs=())
                check_deadline(deadline)
                connection = cast(
                    sqlite3.Connection, session.connection().connection.driver_connection
                )
                connection.set_progress_handler(lambda: int(monotonic() >= deadline), 1000)
                try:
                    return select_matches(session, observation, policy)
                finally:
                    connection.set_progress_handler(None, 0)

            selection = self.reader.store.read(select)
            check_deadline(deadline)
            offset = 0
            if position is not None:
                if position.namespace != selection.namespace:
                    raise ApiFailure("VALIDATION_ERROR")
                offset = position.position
                if not 0 < offset < len(selection.ranked):
                    raise ApiFailure("VALIDATION_ERROR")
                previous = selection.ranked[offset - 1]
                if (previous.preference_score, previous.source_id) != (
                    position.sort_key.preference_score,
                    position.sort_key.source_id,
                ):
                    raise ApiFailure("VALIDATION_ERROR")
            selected = selection.ranked[offset : offset + request.page_size]
            refs = tuple(
                ImmutableInventoryRef(
                    namespace=selection.namespace,
                    snapshot_id=observation.snapshot_id,
                    source_id=item.source_id,
                )
                for item in selected
            )
            self._checkpoint("search.before_projection")
            batch: CompactBatch = self.reader.read_refs(
                refs, expected_snapshot_id=observation.snapshot_id
            )
            self.reader._check_search_anchor(anchor)
            if batch.observation != observation or tuple(item.ref for item in batch.items) != refs:
                raise ApiFailure("SNAPSHOT_STALE")
            if any(item.state != "current" or item.listing is None for item in batch.items):
                raise ValueError("INVENTORY_SEARCH_PROJECTION_MISMATCH")
            summaries = [
                map_listing_summary(item.listing)
                for item in batch.items
                if item.listing is not None
            ]
            check_deadline(deadline)
        except ValueError as error:
            raise public_read_failure(error) from error
        next_cursor = None
        next_offset = offset + len(selected)
        if next_offset < len(selection.ranked):
            last = selected[-1]
            next_cursor = self.signer.encode_search_cursor(
                SearchCursorPosition(
                    namespace=selection.namespace,
                    snapshot_id=observation.snapshot_id,
                    index_version=observation.index_version,
                    ranking_version=RANKING_VERSION,
                    criteria_hash=policy.criteria_hash,
                    sort_key=SearchSortKey(
                        preference_score=last.preference_score, source_id=last.source_id
                    ),
                    position=next_offset,
                    generation=observation.generation,
                    active_revision=observation.active_revision,
                ),
                now=now,
                continuation=request.cursor,
            )
        proof = self.signer.sign_presentation(
            snapshot_id=observation.snapshot_id,
            ordered_refs=refs,
            criteria_hash=policy.criteria_hash,
            now=now,
        )
        if (
            proof.snapshot_id != observation.snapshot_id
            or proof.criteria_hash != policy.criteria_hash
            or proof.ordered_refs != [item.ref for item in summaries]
        ):
            raise ApiFailure("INTERNAL_ERROR")
        return SearchResult(
            client_request_id=request.client_request_id,
            state="matches" if summaries else "no_supported_matches",
            items=summaries,
            supported_total=len(selection.ranked),
            next_cursor=next_cursor,
            presentation=proof,
            applied_criteria=policy.criteria,
            evidence_coverage=list(selection.coverage),
            unsupported_constraints=list(policy.unsupported),
        )
