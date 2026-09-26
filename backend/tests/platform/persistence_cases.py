"""Synthetic foundation rows, not accepted domain actions or real buyer data."""

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.database.models import Base

NOW = "2026-09-24T04:00:00.000000Z"
LATER = "2026-10-24T04:00:00.000000Z"


def uid(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, "csa-be01-test/" + label))


def seed_rows(generation: str) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for who in ("a", "b"):
        owner = uid("owner-" + who)
        journey = uid("journey-" + who)
        rows.extend(
            [
                (
                    "owners",
                    dict(
                        id=owner,
                        display_name="Same synthetic name",
                        created_at=NOW,
                        shortlist_revision=0,
                        preference_revision=0,
                    ),
                ),
                ("journeys", dict(id=journey, owner_id=owner, created_at=NOW)),
                (
                    "conversation_sessions",
                    dict(
                        id=uid("session-" + who),
                        owner_id=owner,
                        journey_id=journey,
                        revision=0,
                        state_json={},
                        created_at=NOW,
                        last_activity_at=NOW,
                        expires_at=LATER,
                    ),
                ),
            ]
        )
    for label in ("1", "2"):
        rows.extend(
            [
                (
                    "inventory_snapshots",
                    dict(
                        snapshot_id=label * 64,
                        namespace="provided-cars-cleaned",
                        workbook_sha256="a" * 64,
                        sheet_name="cleaned dataset",
                        import_version="test-1",
                        normalization_version="test-1",
                        extraction_version="test-1",
                        evidence_review_version="test-1",
                        photo_policy_version="test-1",
                        schema_version="test-1",
                        index_version="test-1",
                        policy_version="DEMO-POLICY-1",
                        accepted_count=1,
                        rejected_count=0,
                        created_at=NOW,
                    ),
                ),
                (
                    "listing_versions",
                    dict(
                        namespace="provided-cars-cleaned",
                        snapshot_id=label * 64,
                        source_id="12",
                        source_row=13,
                        original_json={"model": 3.0, "title": "ميني كوبر"},
                        normalized_json={"model": "3"},
                    ),
                ),
            ]
        )
    owner = uid("owner-a")
    ref = dict(namespace="provided-cars-cleaned", snapshot_id="1" * 64, source_id="12")
    rows.extend(
        [
            (
                "active_inventory",
                dict(id=1, snapshot_id="1" * 64, index_version="test-1", revision=0),
            ),
            (
                "attribute_evidence",
                dict(
                    id=uid("evidence"),
                    **ref,
                    attribute="model",
                    raw_locator_json={"cell": "D13", "raw": 3.0},
                    normalized_json={"value": "3"},
                    status="known",
                    extraction_version="test-1",
                ),
            ),
            (
                "vehicle_resources",
                dict(id=uid("resource"), mapping_version="test-1", created_at=NOW),
            ),
            (
                "listing_resource_mappings",
                dict(
                    **ref,
                    resource_id=uid("resource"),
                    mapping_version="test-1",
                    provenance_json={"synthetic": True},
                ),
            ),
            (
                "owner_credentials",
                dict(
                    id=uid("credential"),
                    owner_id=owner,
                    token_digest="c" * 64,
                    context_id=uid("context"),
                    csrf_binding="synthetic-binding",
                    issued_at=NOW,
                    expires_at=LATER,
                ),
            ),
            (
                "messages",
                dict(
                    id=uid("message"),
                    owner_id=owner,
                    session_id=uid("session-a"),
                    client_message_id=uid("client-message"),
                    payload_hash="d" * 64,
                    expected_revision=0,
                    accepted_revision=1,
                    result_json={},
                    state="saved",
                    created_at=NOW,
                ),
            ),
            (
                "result_presentations",
                dict(
                    id=uid("presentation"),
                    owner_id=owner,
                    session_id=uid("session-a"),
                    snapshot_id="1" * 64,
                    criteria_hash="e" * 64,
                    created_revision=0,
                    created_at=NOW,
                ),
            ),
            ("presentation_items", dict(presentation_id=uid("presentation"), ordinal=0, **ref)),
            ("preference_settings", dict(owner_id=owner, collection_mode="explicit_save")),
            (
                "preferences",
                dict(
                    owner_id=owner,
                    key="budget",
                    value_json={"minimum_minor_units": 100},
                    strength="hard",
                    source_session_reference=uid("session-a"),
                    source_action_id=uid("action"),
                    confirmed_at=NOW,
                    expires_at=LATER,
                    applicability="confirmed",
                ),
            ),
            (
                "shortlist_memberships",
                dict(owner_id=owner, **ref, added_at=NOW, updated_at=NOW, expires_at=LATER),
            ),
            (
                "command_receipts",
                dict(
                    id=uid("command"),
                    owner_id=owner,
                    command_kind="shortlist",
                    client_action_id=uid("action"),
                    payload_hash="e" * 64,
                    applied_revision=1,
                    result_json={},
                    created_at=NOW,
                    expires_at=LATER,
                ),
            ),
            (
                "booking_drafts",
                dict(
                    id=uid("draft"),
                    owner_id=owner,
                    session_id=uid("session-a"),
                    revision=0,
                    **ref,
                    state="editing",
                    created_at=NOW,
                    updated_at=NOW,
                    expires_at=LATER,
                ),
            ),
            (
                "booking_reviews",
                dict(
                    id=uid("review"),
                    owner_id=owner,
                    draft_id=uid("draft"),
                    draft_revision=0,
                    operation_key=uid("operation-key"),
                    payload_hash="f" * 64,
                    immutable_payload_json={"synthetic": True},
                    store_generation=generation,
                    issued_at=NOW,
                    expires_at=LATER,
                    state="consumed",
                ),
            ),
            (
                "operation_outcomes",
                dict(
                    id=uid("operation"),
                    owner_id=owner,
                    operation_key=uid("operation-key"),
                    review_id=uid("review"),
                    payload_hash="f" * 64,
                    store_generation=generation,
                    terminal_state="SUCCEEDED",
                    terminal_result_json={},
                    terminal_at=NOW,
                    replay_valid_until=LATER,
                ),
            ),
            (
                "bookings",
                dict(
                    id=uid("booking"),
                    owner_id=owner,
                    review_id=uid("review"),
                    operation_id=uid("operation"),
                    resource_id=uid("resource"),
                    **ref,
                    starts_at_utc="2026-09-25T04:00:00.000000Z",
                    ends_at_utc="2026-09-25T04:30:00.000000Z",
                    timezone="Asia/Dubai",
                    immutable_receipt_json={},
                    confirmed_at=NOW,
                    expires_at=LATER,
                ),
            ),
            (
                "leads",
                dict(
                    id=uid("lead"),
                    owner_id=owner,
                    journey_id=uid("journey-a"),
                    source_session_reference=uid("session-a"),
                    revision=1,
                    stage="viewing_confirmed",
                    values_json={"synthetic": True},
                    created_at=NOW,
                    updated_at=NOW,
                    expires_at=LATER,
                ),
            ),
            ("lead_bookings", dict(lead_id=uid("lead"), booking_id=uid("booking"), owner_id=owner)),
            (
                "export_intents",
                dict(
                    id=uid("export"),
                    lead_id=uid("lead"),
                    lead_revision=1,
                    store_generation=generation,
                    projection_version=1,
                    state="pending",
                    attempts=0,
                    created_at=NOW,
                ),
            ),
            (
                "export_state",
                dict(
                    id=1,
                    store_generation=generation,
                    canonical_version=1,
                    state="pending",
                    updated_at=NOW,
                ),
            ),
            (
                "rule_versions",
                dict(
                    version="test-1",
                    policy_version="DEMO-POLICY-1",
                    rules_json={},
                    eligibility_version="test-1",
                    created_at=NOW,
                ),
            ),
            ("active_rules", dict(id=1, version="test-1", revision=0)),
            (
                "operational_events",
                dict(
                    id=uid("event"),
                    event_type="test_only",
                    generation_reference=generation,
                    safe_code="TEST",
                    created_at=NOW,
                ),
            ),
        ]
    )
    return rows


def seed(session: Session, generation: str) -> None:
    for table, values in seed_rows(generation):
        session.execute(Base.metadata.tables[table].insert().values(**values))
    session.execute(
        Base.metadata.tables["booking_drafts"].update().values(active_review_id=uid("review"))
    )
