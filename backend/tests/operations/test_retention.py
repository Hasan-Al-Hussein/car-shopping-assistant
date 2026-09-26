"""Authored source-only cases. Canonical-only cases do not claim CSV compliance."""

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.leads import LeadRecord
from app.core.errors import ApiFailure
from app.database import models as m
from app.identity.authorization import OwnerUnit
from app.identity.service import utc_text
from app.leads.changes import LeadCommandExpired
from app.leads.projection_files import MANIFEST_NAME, ProjectionFiles, manifest_bytes
from app.leads.projection_repository import ProjectionError
from app.operations import retention
from app.operations import retention_exports, retention_graph
from app.operations.retention import RetentionService
from app.operations.retention_graph import OwnerWork, RetentionError, TOMBSTONE
from app.sessions import repository as sessions
from app.sessions.collection import CollectionEnvelope, CollectionValues
from app.sessions.state import SessionContent
from tests.operations.retention_fixtures import RetentionHarness, make_retention_harness
from tests.platform.session_cases import answer, ref
from tests.transactions.confirmation_fixtures import make_confirmation_harness
from tests.transactions.conversational_fixtures import begin
from tests.transactions.draft_fixtures import confirmation
from tests.transactions.lead_fixtures import save_request
from tests.transactions.projection_fixtures import deny_replacement


@pytest.fixture
def flow(monkeypatch: pytest.MonkeyPatch) -> RetentionHarness:
    return make_retention_harness(monkeypatch)


def test_inspection_and_exact_session_boundary_preserve_other_owner(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    session_id = flow.projection.leads.session_ids[0]
    admission = begin(base, session_id)
    assert admission.ticket is not None
    base.service.complete(base.context(), admission.ticket, answer(admission, "Private synthetic transcript"))
    start = base.clock.value
    base.clock.value = start + timedelta(days=7, microseconds=-1)
    before = flow.facts()
    observed = flow.service.inspect(owner_id=flow.owners[0])
    assert observed.changes == () and flow.facts() == before
    base.clock.value += timedelta(microseconds=1)
    second_before = base.store.read(lambda db: dict(db.execute(
        select(m.ConversationSession.__table__).where(m.ConversationSession.owner_id == flow.owners[1])
    ).mappings().one()))
    observed = flow.service.inspect(owner_id=flow.owners[0])
    assert ("delete.messages", 1) in observed.changes
    commit = flow.service._commit(observed)
    assert commit.changed and not commit.export_reconciliation
    assert base.store.read(lambda db: db.scalar(select(func.count()).select_from(m.Message))) == 0
    assert base.store.read(lambda db: dict(db.execute(
        select(m.ConversationSession.__table__).where(m.ConversationSession.owner_id == flow.owners[1])
    ).mappings().one())) == second_before
    # A live receipt may need the origin skeleton, but the transcript is gone.
    assert base.store.read(lambda db: db.get(m.ConversationSession, session_id) is not None)
    after = flow.facts()
    assert not flow.service._commit(flow.service.inspect(owner_id=flow.owners[0])).changed
    assert flow.facts() == after


def test_preference_shortlist_and_credential_expiry_advance_only_owned_revisions(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    def seed(db: Session) -> None:
        for who, owner in enumerate(flow.owners):
            anchor = base.clock.now() + timedelta(minutes=who)
            stamp, expiry = utc_text(anchor), utc_text(anchor + timedelta(days=30))
            db.add(m.Preference(
                owner_id=owner, key="requirements", value_json={"value": ["Synthetic needs"]},
                strength="soft", source_session_reference=flow.projection.leads.session_ids[who],
                source_action_id=str(uuid4()), source_message_reference=None,
                confirmed_at=stamp, expires_at=expiry, applicability="confirmed",
            ))
            db.add(m.ShortlistMembership(owner_id=owner, **ref().model_dump(), added_at=stamp,
                                          updated_at=stamp, expires_at=expiry))

    base.store.write(seed)
    base.clock.value += timedelta(days=30)
    before_revisions = base.store.read(lambda db: tuple((row.id, row.preference_revision, row.shortlist_revision)
                                                       for row in db.scalars(select(m.Owner).order_by(m.Owner.id))))
    result = flow.service._commit(flow.service.inspect(owner_id=flow.owners[0]))
    assert ("delete.preferences", 1) in result.changes
    assert ("delete.shortlist_memberships", 1) in result.changes
    assert ("delete.owner_credentials", 1) in result.changes
    after_revisions = base.store.read(lambda db: tuple((row.id, row.preference_revision, row.shortlist_revision)
                                                      for row in db.scalars(select(m.Owner).order_by(m.Owner.id))))
    for before, after in zip(before_revisions, after_revisions, strict=True):
        if before[0] == flow.owners[0]:
            assert after == (before[0], before[1] + 1, before[2] + 1)
        else:
            assert after == before
    assert base.store.read(lambda db: db.get(m.Preference, (flow.owners[1], "requirements")) is not None)


def test_late_domain_change_invalidates_inspection_without_partial_cleanup(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    base.clock.value += timedelta(days=7)
    observed = flow.service.inspect(owner_id=flow.owners[0])
    # Real independent owner lead capture changes the global projection identity.
    flow.projection.leads.session_ids = (flow.projection.leads.session_ids[0], base.create(1).session_id)
    flow.projection.save(1)
    before = flow.facts()
    with pytest.raises(RetentionError, match="RETENTION_INSPECTION_CHANGED"):
        flow.service._commit(observed)
    assert flow.facts() == before


def test_injected_failure_after_real_mutations_rolls_back_every_table(
    flow: RetentionHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = flow.projection.leads.sessions
    flow.projection.save()
    base.clock.value += timedelta(days=90)
    observed = flow.service.inspect(owner_id=flow.owners[0])
    before = flow.facts()
    original = retention.apply_owner

    def fail(db: Session, work: OwnerWork) -> None:
        original(db, work)
        raise RuntimeError("synthetic after actual retention mutations")

    monkeypatch.setattr(retention, "apply_owner", fail)
    with pytest.raises(RuntimeError, match="after actual retention mutations"):
        flow.service._commit(observed)
    assert flow.facts() == before


@pytest.mark.parametrize("tamper", ["generation", "digest", "cutoff"])
def test_stale_or_changed_inspection_does_not_delete(flow: RetentionHarness, tamper: str) -> None:
    observed = flow.service.inspect(owner_id=flow.owners[0])
    changed = {"generation": str(uuid4()), "digest": "f" * 64,
               "cutoff": utc_text(flow.projection.leads.sessions.clock.now() + timedelta(seconds=1))}
    before = flow.facts()
    with pytest.raises(RetentionError):
        flow.service._commit(replace(observed, **{tamper: changed[tamper]}))
    assert flow.facts() == before


def test_unknown_original_command_survives_expired_session_and_lead(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    other = begin(base, flow.projection.leads.session_ids[0])
    assert other.ticket is not None
    base.service.complete(base.context(), other.ticket, answer(other, "Unrelated old private text"))
    message_id, _ = flow.unresolved_lead_command()
    original = base.store.read(lambda db: dict(db.execute(select(m.Message.__table__).where(m.Message.id == message_id)).mappings().one()))
    base.clock.value += timedelta(days=91)
    observed = flow.service.inspect(owner_id=flow.owners[0])
    assert observed.unresolved_authorities == 1 and observed.expired_leads_present
    flow.service._commit(observed)
    assert base.store.read(lambda db: dict(db.execute(select(m.Message.__table__).where(m.Message.id == message_id)).mappings().one())) == original
    assert base.store.read(lambda db: db.get(m.Message, other.message_id) is None)
    assert base.store.read(lambda db: db.get(m.ConversationSession, original["session_id"]) is not None)
    assert base.store.read(lambda db: db.scalar(select(func.count()).select_from(m.Lead))) == 1
    assert base.store.read(lambda db: db.get(m.Owner, flow.owners[0]) is not None)


def test_expired_receipt_redaction_retains_original_key_barrier(flow: RetentionHarness) -> None:
    leads, base = flow.projection.leads, flow.projection.leads.sessions
    command = save_request(leads.session_ids[0])
    leads.service.save(base.context(), command)
    # A different unresolved original command holds the owner/lead, not this old receipt.
    saved = leads.service.get(base.context())
    assert isinstance(saved, LeadRecord)
    flow.unresolved_lead_command(saved_lead=saved)
    base.clock.value += timedelta(days=91)
    flow.service._commit(flow.service.inspect(owner_id=flow.owners[0]))

    def inspect(db: Session) -> LeadCommandExpired:
        receipt = db.scalar(select(m.CommandReceipt).where(m.CommandReceipt.client_action_id == command.client_action_id))
        assert receipt is not None and receipt.result_json == {"version": TOMBSTONE}
        owner = db.get(m.Owner, flow.owners[0])
        assert owner is not None
        observed = leads.service.lookup_change_in_unit(
            OwnerUnit(db, owner), command, submitted_generation=base.store.generation,
            observed_generation=base.store.generation, now=utc_text(base.clock.now()),
        )
        assert isinstance(observed, LeadCommandExpired)
        return observed

    assert base.store.read(inspect).state == "expired"
    before = flow.facts()

    def retry(db: Session) -> None:
        owner = db.get(m.Owner, flow.owners[0])
        assert owner is not None
        leads.service.change_in_unit(
            OwnerUnit(db, owner), command, submitted_generation=base.store.generation,
            generation=base.store.generation, now=utc_text(base.clock.now()), prepared=None,
        )

    # Trusted test unit isolates the receipt barrier. Real expired credentials also reject.
    with pytest.raises(ApiFailure, match="REPLAY_EXPIRED"):
        base.store.write(retry)
    with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
        base.context()
    assert flow.facts() == before


@pytest.mark.parametrize("terminal", [False, True], ids=["submitted_unknown", "terminal_success"])
def test_review_and_terminal_authority_survive_origin_transcript_expiry(terminal: bool) -> None:
    flow = make_confirmation_harness()
    base = flow.drafts.base
    owner = base.auth.read(base.context(), lambda unit: unit.owner_id)
    draft = flow.create()
    assert draft.review is not None
    if terminal:
        flow.commit(draft, flow.prepare(draft))
    else:
        base.auth.write(base.context(), lambda unit: flow.drafts.service.mark_submitted(
            unit, draft.draft_id, confirmation(draft), generation=base.store.generation,
            now=utc_text(base.clock.now()),
        ))
    before_counts = flow.counts()
    base.clock.value += timedelta(days=8)
    service = RetentionService(base.store, clock=base.clock.now)
    observed = service.inspect(owner_id=owner)
    service._commit(observed)
    assert flow.counts() == before_counts
    assert base.store.read(lambda db: db.get(m.BookingReview, draft.review.review_id) is not None)
    if not terminal:
        assert observed.unresolved_authorities == 1


def test_empty_owner_cursor_is_a_noop(flow: RetentionHarness) -> None:
    observed = flow.service.inspect(after_owner_id="ffffffff-ffff-4fff-bfff-ffffffffffff")
    assert observed.owner_id is None
    before = flow.facts()
    assert not flow.service._commit(observed).changed
    assert flow.facts() == before


def test_terminal_survives_parent_detachment_then_expires_as_one_group() -> None:
    flow = make_confirmation_harness()
    base = flow.drafts.base
    owner_id = base.auth.read(base.context(), lambda unit: unit.owner_id)
    start = base.clock.value
    draft = flow.create()
    assert draft.review is not None
    review_id = draft.review.review_id
    base.clock.value += timedelta(minutes=1)
    effect = flow.commit(draft, flow.prepare(draft))
    before_counts = flow.counts()
    base.clock.value = start + timedelta(days=90, seconds=30)
    service = RetentionService(base.store, clock=base.clock.now)
    service._commit(service.inspect(owner_id=owner_id))

    def replay(db: Session) -> None:
        owner = db.get(m.Owner, owner_id)
        review = db.get(m.BookingReview, review_id)
        assert owner is not None and review is not None and review.draft_id is None
        assert db.get(m.BookingDraft, draft.draft_id) is None
        assert db.get(m.ConversationSession, draft.session_id) is None
        known = flow.participant.lookup_in_unit(
            OwnerUnit(db, owner), draft_id=draft.draft_id, command=confirmation(draft),
            generation=base.store.generation, now=utc_text(base.clock.now()),
        )
        assert known == effect.terminal

    # Trusted retained-proof lookup; this does not bypass actual credential expiry.
    base.store.read(replay)
    assert flow.counts() == before_counts
    base.clock.value = start + timedelta(days=90, minutes=1)
    commit = service._commit(service.inspect(owner_id=owner_id))
    assert commit.export_reconciliation and flow.counts() == (0, 0, 0, 0, 0)
    assert base.store.read(lambda db: db.get(m.Owner, owner_id) is None)
    assert base.store.read(lambda db: db.get(m.BookingReview, review_id) is None)
    with pytest.raises(ApiFailure, match="IDENTITY_REQUIRED"):
        base.context()


def test_expired_private_collection_is_cleared_without_erasing_original_command(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    message_id, _ = flow.unresolved_lead_command()
    session_id = flow.projection.leads.session_ids[0]
    start = base.clock.value
    collection = CollectionEnvelope(
        collection_id=str(uuid4()), revision=1, owner_id=flow.owners[0], session_id=session_id,
        store_generation=base.store.generation, created_at=utc_text(start),
        expires_at=utc_text(start + timedelta(minutes=30)), source_message_id=message_id,
        updated_message_id=message_id, purpose="local_enquiry",
        values=CollectionValues(requirements=["Synthetic private needs"], requirements_state="provided"),
        provenance=[],
    )

    def seed(db: Session) -> None:
        row = db.get(m.ConversationSession, session_id)
        assert row is not None
        current = sessions.content(row)
        row.state_json = SessionContent.model_validate({
            **current.model_dump(mode="json"), "collection": collection.model_dump(mode="json"),
        }).model_dump(mode="json")

    base.store.write(seed)
    before = base.store.read(lambda db: dict(db.execute(select(m.ConversationSession.__table__).where(
        m.ConversationSession.id == session_id)).mappings().one()))
    command_before = base.store.read(lambda db: dict(db.execute(select(m.Message.__table__).where(
        m.Message.id == message_id)).mappings().one()))
    base.clock.value += timedelta(minutes=30)
    flow.service._commit(flow.service.inspect(owner_id=flow.owners[0]))
    after = base.store.read(lambda db: dict(db.execute(select(m.ConversationSession.__table__).where(
        m.ConversationSession.id == session_id)).mappings().one()))
    assert after["state_json"] == {**before["state_json"], "collection": None}
    assert after["revision"] == before["revision"] + 1
    assert after["expires_at"] == before["expires_at"]
    assert base.store.read(lambda db: dict(db.execute(select(m.Message.__table__).where(
        m.Message.id == message_id)).mappings().one())) == command_before


def test_forged_export_flag_cannot_bypass_withdrawal(flow: RetentionHarness) -> None:
    flow.projection.save()
    assert flow.projection.projector.repair_once().state == "current"
    flow.projection.leads.sessions.clock.value += timedelta(days=90)
    observed = flow.service.inspect(owner_id=flow.owners[0])
    assert observed.export_reconciliation
    before = flow.facts()
    csv_before = flow.projection.files.path("leads.csv").read_bytes()
    with pytest.raises(RetentionError, match="RETENTION_INSPECTION_CHANGED"):
        flow.service.apply(replace(observed, export_reconciliation=False))
    assert flow.facts() == before
    assert flow.projection.files.path("leads.csv").read_bytes() == csv_before


@pytest.mark.parametrize("scope", [{"owner_id": "invalid"}, {"after_owner_id": "invalid"}])
def test_invalid_operator_scope_is_a_closed_error(flow: RetentionHarness, scope: dict[str, str]) -> None:
    before = flow.facts()
    with pytest.raises(RetentionError, match="RETENTION_SCOPE_INVALID"):
        flow.service.inspect(**scope)
    assert flow.facts() == before


def test_actual_csv_removes_expired_owner_only_and_preserves_current_owner(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    flow.projection.save(email="expired-synthetic@example.invalid")
    base.clock.value += timedelta(days=1)
    current = flow.projection.save(1, email="retained-synthetic@example.invalid")
    assert flow.projection.projector.repair_once().state == "current"
    version = flow.projection.metadata()[1]
    base.clock.value += timedelta(days=89)
    result = flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert result.canonical.changed and result.derived_state == "current"
    assert result.canonical.canonical_version == version + 1
    assert [row["lead_id"] for row in flow.projection.rows()] == [current.lead_id]
    data = flow.projection.files.path("leads.csv").read_bytes()
    assert b"expired-synthetic" not in data and b"retained-synthetic" in data


def test_actual_csv_last_lead_cleanup_publishes_header_only_once(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    flow.projection.save(email="last-synthetic@example.invalid")
    assert flow.projection.projector.repair_once().state == "current"
    version = flow.projection.metadata()[1]
    base.clock.value += timedelta(days=90)
    result = flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert result.derived_state == "current" and result.canonical.canonical_version == version + 1
    assert flow.projection.rows() == []
    assert flow.projection.metadata()[3] == ()
    before = flow.facts()
    repeat = flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert not repeat.canonical.changed
    assert flow.facts() == before


def test_real_windows_lock_keeps_failure_truth_and_repair_uses_new_version(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    flow.projection.save(email="locked-expired@example.invalid")
    assert flow.projection.projector.repair_once().state == "current"
    base.clock.value += timedelta(days=90)
    with deny_replacement(flow.projection.files.path("leads.csv")):
        result = flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert result.canonical.changed and result.derived_state == "failed"
    assert flow.projection.metadata()[0] == "failed"
    assert flow.projection.store.read(lambda db: db.scalar(select(func.count()).select_from(m.Lead))) == 0
    repaired = flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert repaired.derived_state == "current" and flow.projection.rows() == []
    assert repaired.canonical.canonical_version == result.canonical.canonical_version


def test_protected_expired_lead_withdraws_csv_without_fabricating_current(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions
    flow.unresolved_lead_command()
    assert flow.projection.projector.repair_once().state == "current"
    base.clock.value += timedelta(days=91)
    result = flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert result.derived_state == "failed"
    assert not flow.projection.files.path("leads.csv").exists()
    assert flow.projection.files.path("leads.manifest.json").exists()
    assert flow.projection.store.read(lambda db: db.scalar(select(func.count()).select_from(m.Lead))) == 1
    assert flow.projection.metadata()[0] != "current"


def test_real_owned_graph_is_rejected_before_truncation(
    flow: RetentionHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = flow.facts()
    monkeypatch.setattr(retention_graph, "MAX_ROWS", 1)
    with pytest.raises(RetentionError, match="RETENTION_OWNER_GRAPH_LIMIT"):
        flow.service.inspect(owner_id=flow.owners[0])
    assert flow.facts() == before


def test_oversized_json_is_rejected_before_decoding_protection(flow: RetentionHarness) -> None:
    base = flow.projection.leads.sessions

    def corrupt(db: Session) -> None:
        row = db.get(m.ConversationSession, flow.projection.leads.session_ids[0])
        assert row is not None
        row.state_json = {"oversized_synthetic": "x" * retention_graph.MAX_ROW_JSON}

    base.store.write(corrupt)
    before = flow.facts()
    with pytest.raises(RetentionError, match="RETENTION_JSON_LIMIT"):
        flow.service.inspect(owner_id=flow.owners[0])
    assert flow.facts() == before


def test_export_version_exhaustion_does_not_delete(flow: RetentionHarness) -> None:
    flow.projection.save()
    base = flow.projection.leads.sessions

    def exhaust(db: Session) -> None:
        row = db.get(m.ExportState, 1)
        assert row is not None
        row.canonical_version = retention_graph.MAX_REVISION

    base.store.write(exhaust)
    base.clock.value += timedelta(days=90)
    before = flow.facts()
    with pytest.raises(RetentionError, match="RETENTION_EXPORT_VERSION_EXHAUSTED"):
        flow.service.inspect(owner_id=flow.owners[0])
    assert flow.facts() == before


def test_foreign_descriptor_stops_before_canonical_or_file_deletion(flow: RetentionHarness) -> None:
    flow.projection.save()
    assert flow.projection.projector.repair_once().state == "current"
    files = flow.projection.files
    manifest = files.manifest(MANIFEST_NAME)
    assert manifest is not None
    files.path(MANIFEST_NAME).write_bytes(manifest_bytes(manifest.model_copy(update={"store_binding": "0" * 64})))
    flow.projection.leads.sessions.clock.value += timedelta(days=90)
    before = flow.facts()
    csv_before = files.path("leads.csv").read_bytes()
    with pytest.raises(ProjectionError, match="CSV_DIFFERENT_STORE"):
        flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert flow.facts() == before and files.path("leads.csv").read_bytes() == csv_before


def test_simulated_crash_after_commit_recovers_without_a_second_version(
    flow: RetentionHarness, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BaseException seam; not evidence of a real abrupt process termination."""
    flow.projection.save()
    assert flow.projection.projector.repair_once().state == "current"
    flow.projection.leads.sessions.clock.value += timedelta(days=90)

    class SyntheticCrash(BaseException):
        pass

    def crash(files: ProjectionFiles, *, generation: str, version: int | None) -> None:
        raise SyntheticCrash()

    original = retention_exports.withdraw_expired
    monkeypatch.setattr(retention_exports, "withdraw_expired", crash)
    with pytest.raises(SyntheticCrash):
        flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    state = flow.projection.metadata()
    assert state[0] == "pending"
    assert flow.projection.store.read(lambda db: db.scalar(select(func.count()).select_from(m.Lead))) == 0
    monkeypatch.setattr(retention_exports, "withdraw_expired", original)
    repaired = flow.service.apply(flow.service.inspect(owner_id=flow.owners[0]))
    assert repaired.derived_state == "current" and flow.projection.rows() == []
    assert repaired.canonical.canonical_version == state[1]
