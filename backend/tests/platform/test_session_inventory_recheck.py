"""Actual Session consuming boundaries; this fixture's Inventory remains synthetic."""

from uuid import uuid4

import pytest
from sqlalchemy import update

from app.api.schemas.sessions import PresentationRegisterRequest, SessionSelectionRequest
from app.core.errors import ApiFailure
from app.database.models import ListingVersion
from tests.platform.session_cases import answer, make_harness, ref
from tests.platform.test_identity import snapshot
from tests.platform.test_sessions import message


@pytest.mark.parametrize(
    "boundary", ["register", "select", "begin", "complete_proof", "complete_ref"]
)
def test_every_consuming_boundary_rechecks_projection_in_owner_write(boundary: str) -> None:
    harness = make_harness()
    session = harness.create()
    admission = None
    if boundary.startswith("complete"):
        admission = harness.service.begin(harness.context(), session.session_id, message())
    before = harness.service.get(harness.context(), session.session_id)

    def mutate() -> None:
        harness.store.write(
            lambda db: db.execute(
                update(ListingVersion)
                .where(ListingVersion.source_id == "12")
                .values(normalized_json={"synthetic_changed_projection": True})
            ).close()
        )

    harness.inventory.after_prepare = mutate
    with pytest.raises(ApiFailure, match="SNAPSHOT_STALE"):
        if boundary == "register":
            harness.service.register(
                harness.context(),
                session.session_id,
                PresentationRegisterRequest(
                    expected_revision=0, client_action_id=str(uuid4()), presentation=harness.proof()
                ),
            )
        elif boundary == "select":
            harness.service.select(
                harness.context(),
                session.session_id,
                SessionSelectionRequest(
                    expected_revision=0,
                    client_action_id=str(uuid4()),
                    selected_ref=ref(),
                    presentation_id=None,
                ),
            )
        elif boundary == "begin":
            harness.service.begin(
                harness.context(),
                session.session_id,
                message().model_copy(update={"selected_ref": ref()}),
            )
        else:
            assert admission is not None and admission.ticket is not None
            harness.service.complete(
                harness.context(),
                admission.ticket,
                answer(admission),
                presentation=harness.proof() if boundary == "complete_proof" else None,
                selection=ref() if boundary == "complete_ref" else None,
            )
    assert harness.inventory.rechecks == 1
    assert harness.service.get(harness.context(), session.session_id) == before


def test_registered_replay_and_late_turn_skip_new_inventory_authority() -> None:
    harness = make_harness()
    session = harness.create()
    command = PresentationRegisterRequest(
        expected_revision=0, client_action_id=str(uuid4()), presentation=harness.proof(())
    )
    saved = harness.service.register(harness.context(), session.session_id, command)
    assert harness.inventory.rechecks == 1
    before = snapshot(harness.store)
    assert harness.service.register(harness.context(), session.session_id, command) == saved
    assert harness.inventory.rechecks == 1 and snapshot(harness.store) == before
    old = harness.service.begin(harness.context(), session.session_id, message(1))
    assert old.ticket is not None
    harness.service.begin(harness.context(), session.session_id, message(2))
    late = harness.service.complete(
        harness.context(), old.ticket, answer(old), presentation=harness.proof(), selection=ref()
    )
    assert late.state == "superseded" and harness.inventory.rechecks == 1


def test_turn_superseded_after_prepare_skips_recheck_in_final_write() -> None:
    harness = make_harness()
    session = harness.create()
    old = harness.service.begin(harness.context(), session.session_id, message())
    assert old.ticket is not None

    def supersede() -> None:
        harness.service.begin(harness.context(), session.session_id, message(1))

    harness.inventory.after_prepare = supersede
    late = harness.service.complete(
        harness.context(), old.ticket, answer(old), presentation=harness.proof()
    )
    assert late.state == "superseded"
    assert harness.inventory.prepares == 1 and harness.inventory.rechecks == 0
