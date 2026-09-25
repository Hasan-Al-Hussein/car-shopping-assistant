"""Persist and validate a version-bound index inside the caller's Store unit."""

import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.models import InventorySearchDocument
from app.inventory.lexical_index import PreparedIndex

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def insert_index(session: Session, index: PreparedIndex) -> None:
    for document in index.documents:
        session.add(
            InventorySearchDocument(
                **document.ref.model_dump(),
                index_version=index.version,
                document_text=document.text,
                document_sha256=document.sha256,
            )
        )
    session.flush()
    if index.mode == "fts5":
        session.execute(
            text(
                "INSERT INTO inventory_search_fts "
                "(namespace,snapshot_id,source_id,index_version,document_text) "
                "VALUES (:namespace,:snapshot_id,:source_id,:index_version,:document_text)"
            ),
            [
                {
                    **document.ref.model_dump(),
                    "index_version": index.version,
                    "document_text": document.text,
                }
                for document in index.documents
            ],
        )


def matching_ids(session: Session, index: PreparedIndex, term: str) -> tuple[str, ...]:
    """Bounded one-token index diagnostic, not the BE06 buyer search contract."""
    if len(term) > 100 or TOKEN.fullmatch(term) is None:
        raise ValueError("INVENTORY_INDEX_DIAGNOSTIC_TERM_INVALID")
    normalized = term.casefold()
    if index.mode == "bounded_lexical":
        return tuple(
            document.ref.source_id
            for document in index.documents
            if normalized in {token.casefold() for token in TOKEN.findall(document.text)}
        )
    return tuple(
        session.execute(
            text(
                "SELECT source_id FROM inventory_search_fts "
                "WHERE inventory_search_fts MATCH :term "
                "AND snapshot_id=:snapshot AND index_version=:version "
                "ORDER BY source_id"
            ),
            {
                "term": '"' + normalized + '"',
                "snapshot": index.snapshot_id,
                "version": index.version,
            },
        ).scalars()
    )


def validate_index(session: Session, index: PreparedIndex, *, writable: bool) -> None:
    expected = [
        (
            item.ref.namespace,
            item.ref.snapshot_id,
            item.ref.source_id,
            index.version,
            item.text,
            item.sha256,
        )
        for item in index.documents
    ]
    actual = [
        (
            item.namespace,
            item.snapshot_id,
            item.source_id,
            item.index_version,
            item.document_text,
            item.document_sha256,
        )
        for item in session.scalars(
            select(InventorySearchDocument)
            .where(InventorySearchDocument.snapshot_id == index.snapshot_id)
            .order_by(InventorySearchDocument.source_id)
        )
    ]
    if actual != expected:
        raise ValueError("INVENTORY_CANONICAL_INDEX_MISMATCH")
    if index.mode != "fts5":
        return
    rows = [
        tuple(row)
        for row in session.execute(
            text(
                "SELECT namespace,snapshot_id,source_id,index_version,document_text "
                "FROM inventory_search_fts WHERE snapshot_id=:snapshot "
                "ORDER BY source_id,namespace,index_version,document_text"
            ),
            {"snapshot": index.snapshot_id},
        )
    ]
    if rows != [row[:5] for row in expected]:
        raise ValueError("INVENTORY_FTS_CONTENT_MISMATCH")
    if writable:
        session.execute(
            text(
                "INSERT INTO inventory_search_fts(inventory_search_fts) VALUES ('integrity-check')"
            )
        )
    # Read-only MATCH observes postings without issuing the write-only integrity command.
    for document in index.documents:
        token = TOKEN.search(document.text)
        if token and document.ref.source_id not in matching_ids(session, index, token.group()):
            raise ValueError("INVENTORY_FTS_POSTING_MISMATCH")
