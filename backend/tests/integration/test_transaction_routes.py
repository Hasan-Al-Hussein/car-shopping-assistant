"""P16 authored integration checks: real T7/Store/CSV; synthetic Inventory only.

NOT_RUN in the source grant. Requires coordinated application of the new modules
and an explicit disposable Windows runtime boundary before pytest is authorized.
"""

import csv
import io
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.api.schemas.routes import ROUTES
from app.api.schemas.viewings import BookingDraft, ViewingOptions, ViewingOptionsRequest
from app.database.models import OperationOutcome
from app.database.paths import RuntimeBoundary, initialize_runtime_root
from app.database.store import StoreError, assert_outside_write_transaction
from app.leads.projection import CsvProjector, ProjectionRun
from app.leads.projection_files import CSV_NAME, ProjectionFiles
from app.leads.router import lead_router
from app.leads.service import LeadService
from app.viewings.application import ViewingApplication
from app.viewings.router import viewing_router
from tests.platform.composed_contract_cases import operations
from tests.platform.memory_shortlist_cases import failed_commit
from tests.platform.test_identity import call, snapshot
from tests.support.harness import configured_runtime_boundary, runtime_environment
from tests.transactions.confirmation_fixtures import ConfirmationHarness, make_confirmation_harness
from tests.transactions.draft_fixtures import confirmation, update
from tests.transactions.lead_fixtures import buyer_values, correction, save_request


class SyntheticOptions:
    """Wire-route test only; no claim of actual capacity-observed service proof."""

    def options(self, request: ViewingOptionsRequest) -> ViewingOptions:
        return ViewingOptions(
            ref=request.ref,
            state="unconfigured",
            rules_version=None,
            eligibility_version=None,
            calculated_at="2026-09-24T04:00:00Z",
            slots=[],
        )


@dataclass
class RoutesHarness:
    flow: ConfirmationHarness
    application: ViewingApplication
    projector: CsvProjector

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        who: int = 0,
        overrides: dict[str, str | None] | None = None,
    ) -> httpx.Response:
        base = self.flow.drafts.base
        buyer = base.buyers[who]
        headers: dict[str, str | None] = {"X-Identity-Context": buyer.identity.context_id}
        if method != "GET":
            headers.update(
                {
                    "X-CSRF-Token": buyer.identity.csrf_token,
                    "Origin": base.settings.scheme + "://127.0.0.1:5173",
                }
            )
        headers.update(overrides or {})
        return call(
            base.app,
            base.settings,
            method,
            "/api/v1" + path,
            cookie=buyer.cookie,
            body=body,
            overrides=headers,
        )

    def create(self, *, who: int = 0) -> BookingDraft:
        result = self.request(
            "POST",
            "/booking-drafts",
            body=self.flow.drafts.command(who=who).model_dump(mode="json"),
            who=who,
        )
        assert result.status_code == 201
        draft = BookingDraft.model_validate(result.json()["data"])
        assert result.json()["meta"]["entity_revision"] == draft.revision
        return draft

    def confirm(self, draft: BookingDraft, *, who: int = 0) -> httpx.Response:
        return self.request(
            "POST",
            f"/booking-drafts/{draft.draft_id}/confirm",
            body=confirmation(draft).model_dump(mode="json"),
            who=who,
        )

    def terminal(self) -> dict[str, Any]:
        value = self.flow.drafts.base.store.read(
            lambda db: db.scalar(select(OperationOutcome.terminal_result_json)),
        )
        assert isinstance(value, dict)
        return value


@pytest.fixture
def h(monkeypatch: pytest.MonkeyPatch) -> RoutesHarness:
    configured = configured_runtime_boundary()
    root = configured.physical_root / "test-stores" / ("p16-" + str(uuid4())) / "runtime"
    boundary = RuntimeBoundary(root, root)
    initialize_runtime_root(boundary)
    for key, value in runtime_environment(boundary).items():
        monkeypatch.setenv(key, value)
    flow = make_confirmation_harness()
    base = flow.drafts.base
    projector = CsvProjector(base.store, clock=base.clock.now)
    application = ViewingApplication(flow.participant, projector=projector)
    base.app.include_router(viewing_router(application, options=SyntheticOptions()))
    base.app.include_router(
        lead_router(
            LeadService(base.auth, inventory=flow.lead_inventory),
            projector=projector,
        )
    )
    return RoutesHarness(flow, application, projector)


def forbidden(*args: object, **kwargs: object) -> None:
    raise AssertionError("FORBIDDEN_SIDE_EFFECT")


def test_frozen_transaction_surface_and_public_options(h: RoutesHarness) -> None:
    expected = {item.operation_id: item for item in ROUTES if item.owner == "transactions"}
    actual = [
        (path, method, operation)
        for (path, method), operation in operations(h.flow.drafts.base.app.openapi()).items()
        if (
            operation.get("x-domain-owner") == "transactions"
            or operation.get("operationId") in expected
        )
    ]
    assert len(actual) == len(expected) == 11
    assert {operation["operationId"] for _, _, operation in actual} == expected.keys()
    for path, method, operation in actual:
        spec = expected[operation["operationId"]]
        assert (path, method) == ("/api/v1" + spec.path, spec.method.lower())
        assert {status for status in operation["responses"] if status.startswith("2")} == {
            str(spec.status)
        }
        assert operation["x-domain-owner"] == spec.owner
        assert operation["x-private"] == spec.private
        assert operation["x-mutates-state"] == spec.mutates
    base = h.flow.drafts.base
    result = call(
        base.app,
        base.settings,
        "POST",
        "/api/v1/viewing-options",
        body={
            "ref": h.flow.drafts.command().ref.model_dump(mode="json"),
            "from_date": "2026-09-25",
            "days": 1,
        },
    )
    assert result.status_code == 200 and result.json()["data"]["state"] == "unconfigured"


def test_confirm_commits_at_reviewed_r_and_publishes_actual_csv(
    h: RoutesHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = h.create()
    base = h.flow.drafts.base
    reviewed = base.service.get(base.context(), draft.session_id).revision
    original = h.projector.repair_once
    calls: list[bool] = []

    def repair() -> ProjectionRun:
        assert_outside_write_transaction()
        assert h.flow.counts() == (1, 1, 1, 1, 1)
        assert base.service.get(base.context(), draft.session_id).revision == reviewed + 1
        calls.append(True)
        return original()

    monkeypatch.setattr(h.projector, "repair_once", repair)
    result = h.confirm(draft)
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["state"] == "succeeded" and data["csv"]["state"] == "current"
    assert data["operation_key"] == confirmation(draft).operation_key
    assert calls == [True]
    current = base.service.get(base.context(), draft.session_id)
    assert current.current_draft_id is None and current.pending_intent.kind == "none"
    assert base.service.transcript(base.context(), draft.session_id).items == []
    stored = h.terminal()
    assert stored["csv"]["state"] == "pending"
    assert stored["booking"] == data["booking"] and stored["lead"] == data["lead"]
    raw = ProjectionFiles(base.store).path(CSV_NAME).read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
    assert len(rows) == 1 and data["lead"]["lead_id"] in rows[0].values()


def test_exact_confirm_replay_skips_prepare_and_session_writer(
    h: RoutesHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = h.create()
    first = h.confirm(draft).json()["data"]
    base = h.flow.drafts.base
    before, terminal = snapshot(base.store), h.terminal()
    monkeypatch.setattr(h.flow.participant, "prepare", forbidden)
    monkeypatch.setattr(h.flow.participant, "apply_in_unit", forbidden)
    monkeypatch.setattr(base.auth, "write", forbidden)
    replay = h.confirm(draft)
    assert replay.status_code == 200 and replay.json()["data"] == first
    assert h.terminal() == terminal and snapshot(base.store) == before
    assert h.flow.counts() == (1, 1, 1, 1, 1)


def test_replacement_operation_key_cannot_create_another_booking(h: RoutesHarness) -> None:
    draft = h.create()
    assert h.confirm(draft).status_code == 200
    body = confirmation(draft).model_dump(mode="json")
    body["operation_key"] = "X" * 43
    before = snapshot(h.flow.drafts.base.store)
    result = h.request("POST", f"/booking-drafts/{draft.draft_id}/confirm", body=body)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert h.flow.counts() == (1, 1, 1, 1, 1)
    assert snapshot(h.flow.drafts.base.store) == before


def test_gets_preserve_state_and_never_repair(
    h: RoutesHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = h.create()
    data = h.confirm(draft).json()["data"]
    base = h.flow.drafts.base
    before = snapshot(base.store)
    monkeypatch.setattr(h.projector, "repair_once", forbidden)
    monkeypatch.setattr(base.auth, "write", forbidden)
    paths = (
        f"/booking-drafts/{draft.draft_id}",
        f"/bookings/{data['booking']['booking_id']}",
        f"/operations/{data['operation_key']}?submitted_store_generation={data['original_store_generation']}",
        "/leads/current",
        f"/leads/{data['lead']['lead_id']}",
    )
    for path in paths:
        assert h.request("GET", path).status_code == 200
    assert snapshot(base.store) == before


def test_owner_and_csrf_guards_precede_effects(h: RoutesHarness) -> None:
    draft = h.create()
    denied = h.request(
        "POST",
        f"/booking-drafts/{draft.draft_id}/confirm",
        body=confirmation(draft).model_dump(mode="json"),
        overrides={"X-CSRF-Token": "X" * 43},
    )
    assert denied.status_code == 403 and h.flow.counts() == (0, 0, 0, 0, 0)
    assert h.confirm(draft, who=1).status_code == 404
    saved = h.confirm(draft).json()["data"]
    for path in (
        f"/booking-drafts/{draft.draft_id}",
        f"/bookings/{saved['booking']['booking_id']}",
        f"/leads/{saved['lead']['lead_id']}",
    ):
        assert h.request("GET", path, who=1).status_code == 404
    status = h.request("GET", f"/operations/{saved['operation_key']}", who=1).json()["data"]
    assert status["state"] == "not_observed" and status["definitive_noncommit"] is False


def test_intervening_edit_does_not_accept_stale_review(h: RoutesHarness) -> None:
    draft = h.create()
    changed = h.request(
        "PATCH",
        f"/booking-drafts/{draft.draft_id}",
        body=update(draft, "suspend").model_dump(mode="json"),
    )
    assert changed.status_code == 200
    before = snapshot(h.flow.drafts.base.store)
    result = h.confirm(draft)
    assert result.status_code == 409 and result.json()["error"]["code"] == "REVIEW_STALE"
    assert snapshot(h.flow.drafts.base.store) == before


def test_capacity_rejection_is_durable_409_and_advances_once(h: RoutesHarness) -> None:
    first, other = h.create(), h.create(who=1)
    base = h.flow.drafts.base
    before = base.service.get(base.context(1), other.session_id).revision
    assert h.confirm(first).status_code == 200
    denied = h.confirm(other, who=1)
    assert denied.status_code == 409
    assert denied.json()["data"]["rejection_code"] == "CAPACITY_UNAVAILABLE"
    assert base.service.get(base.context(1), other.session_id).revision == before + 1
    assert h.confirm(other, who=1).json()["data"] == denied.json()["data"]
    assert base.service.get(base.context(1), other.session_id).revision == before + 1
    assert h.flow.counts() == (1, 2, 1, 1, 1)


@pytest.mark.parametrize("fault", ["resolve", "commit"])
def test_precommit_failure_rolls_back_and_does_not_publish(
    h: RoutesHarness,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    draft = h.create()
    base = h.flow.drafts.base
    before = snapshot(base.store)
    monkeypatch.setattr(h.projector, "repair_once", forbidden)
    if fault == "resolve":
        original = h.flow.participant.resolve_session_in_unit

        def broken(*args: Any, **kwargs: Any) -> None:
            original(*args, **kwargs)
            raise StoreError("SYNTHETIC_AFTER_RESOLVE")

        monkeypatch.setattr(h.flow.participant, "resolve_session_in_unit", broken)
        result = h.confirm(draft)
    else:
        with failed_commit():
            result = h.confirm(draft)
    assert result.status_code == 503 and result.json()["error"]["outcome_state"] == "unresolved"
    assert h.flow.counts() == (0, 0, 0, 0, 0) and snapshot(base.store) == before


@pytest.mark.parametrize("fault", ["repair", "observe"])
def test_postcommit_failure_retains_success_and_original_key(
    h: RoutesHarness,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    draft = h.create()

    def broken(*args: object, **kwargs: object) -> None:
        assert_outside_write_transaction()
        raise StoreError("SYNTHETIC_POSTCOMMIT_FAILURE")

    with monkeypatch.context() as patch:
        target, name = (
            (h.projector, "repair_once")
            if fault == "repair"
            else (h.flow.participant, "observe_csv_in_unit")
        )
        patch.setattr(target, name, broken)
        result = h.confirm(draft)
    error = result.json()["error"]
    assert result.status_code == 503
    assert error["operation_key"] == confirmation(draft).operation_key
    assert error["outcome_state"] == "succeeded" and error["retry_action"] == "read"
    assert h.flow.counts() == (1, 1, 1, 1, 1)
    terminal = h.terminal()
    recovered = h.request("GET", f"/operations/{error['operation_key']}")
    assert recovered.status_code == 200 and recovered.json()["data"]["state"] == "succeeded"
    assert h.terminal() == terminal


def test_busy_postcommit_audit_never_claims_current(
    h: RoutesHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = h.create()
    assert h.confirm(draft).json()["data"]["csv"]["state"] == "current"
    terminal = h.terminal()
    monkeypatch.setattr(
        h.projector,
        "repair_once",
        lambda: ProjectionRun(
            "busy",
            h.flow.drafts.base.store.generation,
            None,
            None,
            None,
            code="CSV_PUBLISHER_BUSY",
        ),
    )
    replay = h.confirm(draft)
    assert replay.status_code == 200
    assert replay.json()["data"]["csv"]["state"] == "pending"
    assert replay.json()["data"]["csv"]["code"] == "CSV_AUDIT_PENDING"
    assert h.terminal() == terminal


def test_absent_original_generation_is_uncertain_not_permission_for_new_key(
    h: RoutesHarness,
) -> None:
    key = "U" * 43
    generation = str(uuid4())
    result = h.request("GET", f"/operations/{key}?submitted_store_generation={generation}")
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["state"] == "unresolved_generation" and data["definitive_noncommit"] is False
    assert data["submitted_store_generation"] == generation and data["operation_key"] == key


def test_enquiry_save_replay_correction_and_read_are_owned(h: RoutesHarness) -> None:
    flow, base = h.flow, h.flow.drafts.base
    before = h.request("GET", "/leads/current")
    assert before.status_code == 200 and before.json()["data"] == {"state": "not_created"}
    command = save_request(flow.drafts.sessions[0])
    first = h.request("POST", "/leads", body=command.model_dump(mode="json"))
    assert first.status_code == 201
    lead = first.json()["data"]["lead"]
    assert lead["csv"]["state"] == "current" and lead["delivery"] == "local_only"
    replay = h.request("POST", "/leads", body=command.model_dump(mode="json"))
    assert replay.status_code == 201 and replay.json()["data"]["replayed"] is True
    values = buyer_values()
    values.requirements = ["Updated buyer requirement"]
    change = correction(flow.drafts.sessions[0], lead["revision"], values)
    corrected = h.request(
        "PATCH",
        f"/leads/{lead['lead_id']}",
        body=change.model_dump(mode="json"),
    )
    assert corrected.status_code == 200 and corrected.json()["data"]["lead"]["revision"] == 2
    assert corrected.json()["data"]["lead"]["csv"]["state"] == "current"
    assert h.request("GET", f"/leads/{lead['lead_id']}", who=1).status_code == 404
    state = snapshot(base.store)
    current = h.request("GET", f"/leads/{lead['lead_id']}").json()["data"]
    assert current["values"]["requirements"] == values.requirements
    assert snapshot(base.store) == state


def test_enquiry_postcommit_failure_keeps_one_saved_command(
    h: RoutesHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = save_request(h.flow.drafts.sessions[0])

    def broken() -> ProjectionRun:
        assert_outside_write_transaction()
        raise StoreError("SYNTHETIC_PUBLICATION_FAILURE")

    with monkeypatch.context() as patch:
        patch.setattr(h.projector, "repair_once", broken)
        failed = h.request("POST", "/leads", body=command.model_dump(mode="json"))
    assert failed.status_code == 503
    assert failed.json()["error"]["retry_action"] == "same_operation_only"
    assert h.flow.counts() == (0, 0, 1, 0, 1)
    current = h.request("GET", "/leads/current")
    assert current.status_code == 200 and current.json()["data"]["csv"]["state"] == "pending"
    replay = h.request("POST", "/leads", body=command.model_dump(mode="json"))
    assert replay.status_code == 201 and replay.json()["data"]["replayed"] is True
    assert replay.json()["data"]["lead"]["csv"]["state"] == "current"
    assert h.flow.counts() == (0, 0, 1, 0, 1)
