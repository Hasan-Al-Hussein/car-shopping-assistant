"""Read-only, owner-partitioned fingerprints of actual disposable Store domain rows."""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from app.database.models import (
    Booking, BookingDraft, BookingReview, ExportIntent, Lead, LeadBooking,
    OperationOutcome, Owner, Preference, PreferenceSetting, ShortlistMembership,
)
from app.database.store import Store

MODELS = {
    "leads": Lead, "drafts": BookingDraft, "bookings": Booking, "exports": ExportIntent,
    "preferences": Preference, "shortlist": ShortlistMembership, "reviews": BookingReview,
    "outcomes": OperationOutcome, "lead_bookings": LeadBooking,
    "owner_revisions": Owner, "preference_settings": PreferenceSetting,
}
COUNTED = ("leads", "drafts", "bookings", "exports", "preferences", "shortlist")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    ).encode()).hexdigest()


@dataclass(frozen=True)
class DomainSnapshot:
    owned: dict[str, dict[str, str]]
    foreign: dict[str, dict[str, str]]
    shortlist_refs: list[dict[str, str]] = field(default_factory=list)
    lead_values: list[dict[str, Any]] = field(default_factory=list)


def snapshot(store: Store, owner_id: str) -> DomainSnapshot:
    def read(db: Any) -> DomainSnapshot:
        leads = {row.id: row.owner_id for row in db.scalars(select(Lead))}
        owned: dict[str, dict[str, str]] = {name: {} for name in MODELS}
        foreign: dict[str, dict[str, str]] = {name: {} for name in MODELS}
        shortlist_refs: list[dict[str, str]] = []
        lead_values: list[dict[str, Any]] = []
        for name, model in MODELS.items():
            for row in db.scalars(select(model)):
                owner = (row.id if isinstance(row, Owner) else leads.get(row.lead_id)
                         if isinstance(row, ExportIntent) else row.owner_id)
                material = ({"preference_revision": row.preference_revision,
                             "shortlist_revision": row.shortlist_revision}
                            if isinstance(row, Owner) else
                            {column.name: getattr(row, column.name) for column in model.__table__.columns})
                identity = digest([getattr(row, column.name) for column in model.__table__.primary_key])
                (owned if owner == owner_id else foreign)[name][identity] = digest(material)
                if owner == owner_id and isinstance(row, ShortlistMembership):
                    shortlist_refs.append({key: getattr(row, key) for key in (
                        "namespace", "snapshot_id", "source_id",
                    )})
                if owner == owner_id and isinstance(row, Lead):
                    values = row.values_json
                    lead_values.append({
                        "stage": row.stage, "revision": row.revision,
                        "budget": values["budget"], "requirements": values["requirements"],
                        "selected_refs": values["selected_refs"],
                        "email_state": values["email"]["state"], "phone_state": values["phone"]["state"],
                    })
        return DomainSnapshot(owned, foreign, sorted(shortlist_refs, key=lambda ref: ref["source_id"]),
                              sorted(lead_values, key=digest))
    return store.read(read)


def changes(before: dict[str, str], after: dict[str, str]) -> dict[str, int]:
    return {
        "inserted": len(after.keys() - before.keys()),
        "deleted": len(before.keys() - after.keys()),
        "updated": sum(before[key] != after[key] for key in before.keys() & after.keys()),
    }


def project_effects(before: DomainSnapshot, after: DomainSnapshot) -> dict[str, Any]:
    return {
        "effects": {name: len(after.owned[name]) - len(before.owned[name]) for name in COUNTED},
        "mutations": {name: changes(before.owned[name], after.owned[name]) for name in MODELS},
        "foreign_domains_unchanged": before.foreign == after.foreign,
        "shortlist_ids": [ref["source_id"] for ref in after.shortlist_refs],
        "shortlist_refs": after.shortlist_refs,
        "lead_values": after.lead_values,
        # Digests preserve evidence of identity/value equality without raw row payloads.
        "domain_before_sha256": digest(before.owned),
        "domain_after_sha256": digest(after.owned),
        "foreign_before_sha256": digest(before.foreign),
        "foreign_after_sha256": digest(after.foreign),
    }
