"""Versioned lexical materialization and an explicit local FTS5 capability probe."""

import json
from dataclasses import dataclass, field
from typing import Literal

from app.database.capabilities import detect_fts5 as shared_detect_fts5
from app.database.store import assert_outside_write_transaction
from app.inventory.references import ImmutableInventoryRef
from app.inventory.snapshot_codec import PreparedCandidate, canonical_json, digest_text

LEXICAL_POLICY_VERSION = "reviewed-values-lexical-1"
IndexMode = Literal["fts5", "bounded_lexical"]


@dataclass(frozen=True)
class LexicalDocument:
    ref: ImmutableInventoryRef
    text: str = field(repr=False)
    sha256: str


@dataclass(frozen=True)
class PreparedIndex:
    snapshot_id: str
    version: str
    mode: IndexMode
    policy_version: str
    documents: tuple[LexicalDocument, ...] = field(repr=False)


def detect_fts5() -> bool:
    """Use the accepted shared functional probe outside any write transaction."""
    assert_outside_write_transaction()
    return shared_detect_fts5()


def prepare_index(candidate: PreparedCandidate, *, fts5: bool) -> PreparedIndex:
    """Known reviewed values support ranking only; they never replace strict fact filters."""
    documents = []
    for listing in candidate.listings:
        data = json.loads(listing.normalized_json)
        claims = {claim["annotation"]["key"]: claim["annotation"] for claim in data["claims"]}
        values = set()
        for resolution in data["resolutions"]:
            if resolution["status"] != "known":
                continue
            for group in resolution["groups"]:
                # Roles and conditions remain in facts; monetary/distance constraints are typed.
                if resolution["family"] not in {"money", "distance", "cash_price", "mileage_km"}:
                    values.add(str(group["value"]["value"]).casefold())
                    values.update(
                        claims[key]["source"]["quote"].casefold() for key in group["claim_keys"]
                    )
        text = "\n".join(sorted(values))
        documents.append(LexicalDocument(listing.ref, text, digest_text(text)))
    mode: IndexMode = "fts5" if fts5 else "bounded_lexical"
    version = digest_text(
        canonical_json(
            {
                "snapshot_id": candidate.manifest.snapshot_id,
                "policy_version": LEXICAL_POLICY_VERSION,
                "mode": mode,
                "documents": [
                    {"ref": document.ref.model_dump(), "sha256": document.sha256}
                    for document in documents
                ],
            }
        )
    )
    return PreparedIndex(
        candidate.manifest.snapshot_id,
        version,
        mode,
        LEXICAL_POLICY_VERSION,
        tuple(documents),
    )
