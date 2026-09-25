"""Relational storage contract. Domain services own authorization and transitions.

No ORM relationship cascades are used: retention must explicitly reconcile references.
UTC instants are canonical fixed-width ISO strings; bounded DTOs validate JSON before storage.
"""

from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.database.types import UtcStored, UTCText, utc_check


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {str: String, dict[str, Any]: JSON}


class Identified:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)


class Created:
    created_at: Mapped[UtcStored]


class Owned:
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"))


class ListingRef:
    namespace: Mapped[str]
    snapshot_id: Mapped[str]
    source_id: Mapped[str]


def listing_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["namespace", "snapshot_id", "source_id"],
        [
            "listing_versions.namespace",
            "listing_versions.snapshot_id",
            "listing_versions.source_id",
        ],
    )


def owned_fk(parent: str, column: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["owner_id", column], [f"{parent}.owner_id", f"{parent}.id"])


class StoreMetadata(Base, Created):
    __tablename__ = "store_metadata"
    id: Mapped[int] = mapped_column(primary_key=True)
    schema_version: Mapped[str]
    store_generation: Mapped[str] = mapped_column(String(36), unique=True)
    restored_at: Mapped[UtcStored | None]
    recovery_point: Mapped[UtcStored | None]
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)


class InventorySnapshot(Base, Created):
    __tablename__ = "inventory_snapshots"
    snapshot_id: Mapped[str] = mapped_column(primary_key=True)
    namespace: Mapped[str]
    workbook_sha256: Mapped[str] = mapped_column(String(64))
    sheet_name: Mapped[str]
    import_version: Mapped[str]
    normalization_version: Mapped[str]
    extraction_version: Mapped[str]
    evidence_review_version: Mapped[str]
    photo_policy_version: Mapped[str]
    schema_version: Mapped[str]
    index_version: Mapped[str]
    policy_version: Mapped[str]
    accepted_count: Mapped[int]
    rejected_count: Mapped[int]
    __table_args__ = (
        UniqueConstraint("namespace", "snapshot_id"),
        UniqueConstraint("snapshot_id", "index_version"),
        CheckConstraint("accepted_count >= 0 AND rejected_count >= 0", name="counts"),
    )


class ActiveInventory(Base):
    __tablename__ = "active_inventory"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str]
    index_version: Mapped[str]
    revision: Mapped[int]
    __table_args__ = (
        ForeignKeyConstraint(
            ["snapshot_id", "index_version"],
            ["inventory_snapshots.snapshot_id", "inventory_snapshots.index_version"],
        ),
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("revision >= 0", name="revision"),
    )


class ListingVersion(Base, ListingRef):
    __tablename__ = "listing_versions"
    namespace: Mapped[str] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(primary_key=True)
    source_row: Mapped[int]
    original_json: Mapped[dict[str, Any]]
    normalized_json: Mapped[dict[str, Any]]
    __table_args__ = (
        ForeignKeyConstraint(
            ["namespace", "snapshot_id"],
            ["inventory_snapshots.namespace", "inventory_snapshots.snapshot_id"],
        ),
        CheckConstraint("source_row >= 2", name="source_row"),
    )


class InventoryStorageProfile(Base):
    __tablename__ = "inventory_storage_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str]
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("mode IN ('fts5','bounded_lexical')", name="mode"),
    )


class InventorySnapshotPayload(Base):
    __tablename__ = "inventory_snapshot_payloads"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("inventory_snapshots.snapshot_id"), primary_key=True
    )
    serialization_version: Mapped[str] = mapped_column(String(128))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict[str, Any]]
    __table_args__ = (
        CheckConstraint(
            "typeof(serialization_version) = 'text' "
            "AND length(serialization_version) BETWEEN 1 AND 128 "
            "AND length(trim(serialization_version)) > 0",
            name="serialization_version",
        ),
        CheckConstraint(
            "typeof(payload_sha256) = 'text' AND length(payload_sha256) = 64 "
            "AND payload_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="payload_digest",
        ),
        CheckConstraint(
            "CASE WHEN json_valid(payload_json) THEN json_type(payload_json) = 'object' ELSE 0 END",
            name="payload_object",
        ),
    )


class InventorySearchDocument(Base, ListingRef):
    __tablename__ = "inventory_search_documents"
    namespace: Mapped[str] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(primary_key=True)
    index_version: Mapped[str] = mapped_column(String(64))
    document_text: Mapped[str]
    document_sha256: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        listing_fk(),
        ForeignKeyConstraint(
            ["snapshot_id", "index_version"],
            ["inventory_snapshots.snapshot_id", "inventory_snapshots.index_version"],
        ),
        CheckConstraint(
            "typeof(index_version) = 'text' AND length(index_version) = 64 "
            "AND index_version NOT GLOB '*[^0-9a-f]*'",
            name="index_digest",
        ),
        CheckConstraint(
            "typeof(document_sha256) = 'text' AND length(document_sha256) = 64 "
            "AND document_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="document_digest",
        ),
        CheckConstraint("typeof(document_text) = 'text'", name="document_text"),
    )


class AttributeEvidence(Base, Identified, ListingRef):
    __tablename__ = "attribute_evidence"
    attribute: Mapped[str]
    raw_locator_json: Mapped[dict[str, Any]]
    normalized_json: Mapped[dict[str, Any]]
    status: Mapped[str]
    extraction_version: Mapped[str]
    __table_args__ = (
        listing_fk(),
        CheckConstraint("status IN ('known','unknown','conflicting')", name="status"),
        Index(
            "ix_evidence_listing_attribute", "namespace", "snapshot_id", "source_id", "attribute"
        ),
    )


class VehicleResource(Base, Identified, Created):
    __tablename__ = "vehicle_resources"
    mapping_version: Mapped[str]


class ListingResourceMapping(Base, ListingRef):
    __tablename__ = "listing_resource_mappings"
    namespace: Mapped[str] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("vehicle_resources.id"))
    mapping_version: Mapped[str]
    provenance_json: Mapped[dict[str, Any]]
    __table_args__ = (listing_fk(),)


class Owner(Base, Identified, Created):
    __tablename__ = "owners"
    display_name: Mapped[str | None]
    shortlist_revision: Mapped[int]
    preference_revision: Mapped[int]
    __table_args__ = (
        CheckConstraint("shortlist_revision >= 0 AND preference_revision >= 0", name="revisions"),
    )


class OwnerCredential(Base, Identified, Owned):
    __tablename__ = "owner_credentials"
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    context_id: Mapped[str] = mapped_column(String(36), unique=True)
    csrf_binding: Mapped[str]
    issued_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    revoked_at: Mapped[UtcStored | None]
    __table_args__ = (CheckConstraint("issued_at < expires_at", name="lifetime"),)


class Journey(Base, Identified, Owned, Created):
    __tablename__ = "journeys"
    __table_args__ = (UniqueConstraint("owner_id"), UniqueConstraint("owner_id", "id"))


class ConversationSession(Base, Identified, Owned, Created):
    __tablename__ = "conversation_sessions"
    journey_id: Mapped[str]
    revision: Mapped[int]
    state_json: Mapped[dict[str, Any]]
    last_activity_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        owned_fk("journeys", "journey_id"),
        CheckConstraint("revision >= 0", name="revision"),
    )


class Message(Base, Identified, Owned, Created):
    __tablename__ = "messages"
    session_id: Mapped[str]
    client_message_id: Mapped[str]
    payload_hash: Mapped[str]
    expected_revision: Mapped[int]
    accepted_revision: Mapped[int]
    result_json: Mapped[dict[str, Any] | None]
    state: Mapped[str]
    __table_args__ = (
        UniqueConstraint("session_id", "client_message_id"),
        owned_fk("conversation_sessions", "session_id"),
        CheckConstraint("expected_revision >= 0 AND accepted_revision >= 0", name="revisions"),
    )


class ResultPresentation(Base, Identified, Owned, Created):
    __tablename__ = "result_presentations"
    session_id: Mapped[str]
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("inventory_snapshots.snapshot_id"))
    criteria_hash: Mapped[str]
    created_revision: Mapped[int]
    __table_args__ = (
        UniqueConstraint("id", "snapshot_id"),
        owned_fk("conversation_sessions", "session_id"),
        CheckConstraint("created_revision >= 0", name="revision"),
    )


class PresentationItem(Base, ListingRef):
    __tablename__ = "presentation_items"
    presentation_id: Mapped[str] = mapped_column(primary_key=True)
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    __table_args__ = (
        listing_fk(),
        ForeignKeyConstraint(
            ["presentation_id", "snapshot_id"],
            ["result_presentations.id", "result_presentations.snapshot_id"],
        ),
        CheckConstraint("ordinal >= 0", name="ordinal"),
    )


class PreferenceSetting(Base):
    __tablename__ = "preference_settings"
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), primary_key=True)
    collection_mode: Mapped[str]
    __table_args__ = (
        CheckConstraint("collection_mode IN ('explicit_save','disabled')", name="mode"),
    )


class Preference(Base):
    __tablename__ = "preferences"
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    value_json: Mapped[dict[str, Any]]
    strength: Mapped[str]
    source_session_reference: Mapped[str]
    source_action_id: Mapped[str]
    source_message_reference: Mapped[str | None]
    confirmed_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    applicability: Mapped[str]
    __table_args__ = (CheckConstraint("strength IN ('hard','soft')", name="strength"),)


class ShortlistMembership(Base, ListingRef):
    __tablename__ = "shortlist_memberships"
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), primary_key=True)
    namespace: Mapped[str] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(primary_key=True)
    added_at: Mapped[UtcStored]
    updated_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    __table_args__ = (listing_fk(),)


class CommandReceipt(Base, Identified, Owned, Created):
    __tablename__ = "command_receipts"
    command_kind: Mapped[str]
    client_action_id: Mapped[str]
    payload_hash: Mapped[str]
    applied_revision: Mapped[int]
    result_json: Mapped[dict[str, Any]]
    expires_at: Mapped[UtcStored]
    __table_args__ = (
        UniqueConstraint("owner_id", "command_kind", "client_action_id"),
        CheckConstraint("applied_revision >= 0", name="revision"),
    )


class BookingDraft(Base, Identified, Owned, Created, ListingRef):
    __tablename__ = "booking_drafts"
    session_id: Mapped[str | None]
    revision: Mapped[int]
    appointment_json: Mapped[dict[str, Any] | None]
    state: Mapped[str]
    active_review_id: Mapped[str | None]
    updated_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    __table_args__ = (
        listing_fk(),
        UniqueConstraint("owner_id", "id"),
        owned_fk("conversation_sessions", "session_id"),
        ForeignKeyConstraint(
            ["owner_id", "id", "active_review_id"],
            ["booking_reviews.owner_id", "booking_reviews.draft_id", "booking_reviews.id"],
            name="fk_draft_active_review",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("revision >= 0", name="revision"),
    )


class BookingReview(Base, Identified, Owned):
    __tablename__ = "booking_reviews"
    draft_id: Mapped[str | None]
    draft_revision: Mapped[int]
    operation_key: Mapped[str]
    payload_hash: Mapped[str]
    immutable_payload_json: Mapped[dict[str, Any]]
    store_generation: Mapped[str]
    issued_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    state: Mapped[str]
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        UniqueConstraint("owner_id", "draft_id", "id"),
        UniqueConstraint("owner_id", "operation_key"),
        UniqueConstraint("owner_id", "id", "operation_key", "payload_hash", "store_generation"),
        owned_fk("booking_drafts", "draft_id"),
        CheckConstraint("draft_revision >= 0", name="revision"),
        CheckConstraint(
            "state IN ('valid','invalidated','expired','submitted','consumed')", name="state"
        ),
    )


class OperationOutcome(Base, Identified, Owned):
    __tablename__ = "operation_outcomes"
    operation_key: Mapped[str]
    review_id: Mapped[str] = mapped_column(unique=True)
    payload_hash: Mapped[str]
    store_generation: Mapped[str]
    terminal_state: Mapped[str]
    terminal_result_json: Mapped[dict[str, Any]]
    terminal_at: Mapped[UtcStored]
    replay_valid_until: Mapped[UtcStored]
    __table_args__ = (
        UniqueConstraint("owner_id", "operation_key"),
        UniqueConstraint("owner_id", "id", "review_id", "terminal_state"),
        ForeignKeyConstraint(
            ["owner_id", "review_id", "operation_key", "payload_hash", "store_generation"],
            [
                "booking_reviews.owner_id",
                "booking_reviews.id",
                "booking_reviews.operation_key",
                "booking_reviews.payload_hash",
                "booking_reviews.store_generation",
            ],
        ),
        CheckConstraint("terminal_state IN ('SUCCEEDED','REJECTED')", name="terminal_state"),
    )


class Booking(Base, Identified, Owned, ListingRef):
    __tablename__ = "bookings"
    review_id: Mapped[str] = mapped_column(unique=True)
    operation_id: Mapped[str] = mapped_column(unique=True)
    operation_state: Mapped[str] = mapped_column(default="SUCCEEDED", server_default="SUCCEEDED")
    resource_id: Mapped[str] = mapped_column(ForeignKey("vehicle_resources.id"))
    starts_at_utc: Mapped[UtcStored]
    ends_at_utc: Mapped[UtcStored]
    timezone: Mapped[str]
    immutable_receipt_json: Mapped[dict[str, Any]]
    confirmed_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    __table_args__ = (
        listing_fk(),
        UniqueConstraint("owner_id", "id"),
        ForeignKeyConstraint(
            ["owner_id", "operation_id", "review_id", "operation_state"],
            [
                "operation_outcomes.owner_id",
                "operation_outcomes.id",
                "operation_outcomes.review_id",
                "operation_outcomes.terminal_state",
            ],
        ),
        CheckConstraint("operation_state = 'SUCCEEDED'", name="succeeded"),
        CheckConstraint("starts_at_utc < ends_at_utc", name="interval"),
        Index("ix_booking_resource_interval", "resource_id", "starts_at_utc", "ends_at_utc"),
    )


class Lead(Base, Identified, Owned, Created):
    __tablename__ = "leads"
    journey_id: Mapped[str]
    source_session_reference: Mapped[str]
    revision: Mapped[int]
    stage: Mapped[str]
    values_json: Mapped[dict[str, Any]]
    updated_at: Mapped[UtcStored]
    expires_at: Mapped[UtcStored]
    __table_args__ = (
        UniqueConstraint("owner_id", "id"),
        UniqueConstraint("owner_id", "journey_id"),
        owned_fk("journeys", "journey_id"),
        CheckConstraint("revision >= 0", name="revision"),
        CheckConstraint("stage IN ('interested','viewing_confirmed')", name="stage"),
    )


class LeadBooking(Base, Owned):
    __tablename__ = "lead_bookings"
    lead_id: Mapped[str] = mapped_column(primary_key=True)
    booking_id: Mapped[str] = mapped_column(primary_key=True, unique=True)
    __table_args__ = (owned_fk("leads", "lead_id"), owned_fk("bookings", "booking_id"))


class ExportIntent(Base, Identified, Created):
    __tablename__ = "export_intents"
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"))
    lead_revision: Mapped[int]
    store_generation: Mapped[str]
    projection_version: Mapped[int]
    state: Mapped[str]
    attempts: Mapped[int]
    last_error_code: Mapped[str | None]
    __table_args__ = (
        UniqueConstraint("store_generation", "projection_version", "lead_id"),
        CheckConstraint(
            "lead_revision >= 0 AND projection_version >= 0 AND attempts >= 0", name="versions"
        ),
    )


class ExportState(Base):
    __tablename__ = "export_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    store_generation: Mapped[str]
    canonical_version: Mapped[int]
    exported_version: Mapped[int | None]
    state: Mapped[str]
    updated_at: Mapped[UtcStored]
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint(
            "canonical_version >= 0 AND (exported_version IS NULL OR "
            "(exported_version >= 0 AND exported_version <= canonical_version))",
            name="versions",
        ),
    )


class RuleVersion(Base, Created):
    __tablename__ = "rule_versions"
    version: Mapped[str] = mapped_column(primary_key=True)
    policy_version: Mapped[str]
    rules_json: Mapped[dict[str, Any]]
    eligibility_version: Mapped[str]


class ActiveRules(Base):
    __tablename__ = "active_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(ForeignKey("rule_versions.version"))
    revision: Mapped[int]
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("revision >= 0", name="revision"),
    )


class OperationalEvent(Base, Identified, Created):
    __tablename__ = "operational_events"
    event_type: Mapped[str]
    source_reference: Mapped[str | None]
    config_reference: Mapped[str | None]
    generation_reference: Mapped[str | None]
    safe_code: Mapped[str | None]


# Every UTC storage field gets the same direct-SQL check, including nullable origins.
for _table in Base.metadata.tables.values():
    for _column in _table.columns:
        if isinstance(_column.type, UTCText):
            _table.append_constraint(
                CheckConstraint(utc_check(_column.name), name=f"utc_{_column.name}")
            )
