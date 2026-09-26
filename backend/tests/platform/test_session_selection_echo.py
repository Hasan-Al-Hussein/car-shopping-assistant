"""A retained car selection can coexist with a newer search presentation."""

from uuid import uuid4

import pytest

from app.api.schemas.sessions import MessageRequest, PresentationRegisterRequest
from app.core.errors import ApiFailure
from tests.platform.session_cases import SessionHarness, answer, make_harness, ref
from tests.platform.test_identity import snapshot


def changed_results(sources: tuple[str, ...] = ("13",)) -> tuple[SessionHarness, str, str]:
    harness = make_harness()
    session = harness.create()
    first = harness.service.begin(
        harness.context(), session.session_id,
        MessageRequest(client_message_id=str(uuid4()), expected_revision=0, text="First car"),
    )
    assert first.ticket is not None
    harness.service.complete(
        harness.context(), first.ticket, answer(first),
        presentation=harness.proof(("12",)), selection=ref("12"),
    )
    selected = harness.service.get(harness.context(), session.session_id)
    assert selected.active_presentation_id is not None
    second = harness.service.begin(
        harness.context(), session.session_id,
        MessageRequest(
            client_message_id=str(uuid4()), expected_revision=selected.revision,
            text="Show a different make",
        ),
    )
    assert second.ticket is not None
    harness.service.complete(
        harness.context(), second.ticket, answer(second),
        presentation=harness.proof(sources),
    )
    return harness, session.session_id, selected.active_presentation_id


def test_message_can_echo_retained_selection_after_search_changes() -> None:
    harness, session_id, _ = changed_results()
    current = harness.service.get(harness.context(), session_id)
    assert current.selected_ref is not None
    assert current.selected_ref.model_dump() == ref("12").model_dump()
    assert current.active_presentation_id is not None
    command = MessageRequest(
        client_message_id=str(uuid4()), expected_revision=current.revision,
        text="Remember my preference", selected_ref=current.selected_ref,
        presentation_id=current.active_presentation_id,
    )
    admitted = harness.service.begin(harness.context(), session_id, command)
    assert admitted.status == "accepted" and admitted.ticket is not None
    assert admitted.session.selected_ref == current.selected_ref
    assert admitted.session.active_presentation_id == current.active_presentation_id
    assert admitted.session.revision == current.revision + 1
    replay = harness.service.begin(harness.context(), session_id, command)
    assert replay.status == "pending" and replay.ticket is None
    assert replay.session.revision == admitted.session.revision


def test_new_selection_still_requires_membership_in_supplied_presentation() -> None:
    harness, session_id, old_presentation = changed_results()
    current = harness.service.get(harness.context(), session_id)
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="PRESENTATION_INVALID"):
        harness.service.begin(
            harness.context(), session_id,
            MessageRequest(
                client_message_id=str(uuid4()), expected_revision=current.revision,
                text="Choose another car", selected_ref=ref("13"),
                presentation_id=old_presentation,
            ),
        )
    assert snapshot(harness.store) == before


@pytest.mark.parametrize("changed_field", ["selection", "presentation"])
def test_changing_only_half_of_echo_still_checks_membership(changed_field: str) -> None:
    harness, session_id, _ = changed_results(())
    current = harness.service.get(harness.context(), session_id)
    presentation_id = current.active_presentation_id
    selected = ref("13") if changed_field == "selection" else current.selected_ref
    if changed_field == "presentation":
        current = harness.service.register(
            harness.context(), session_id,
            PresentationRegisterRequest(
                client_action_id=str(uuid4()), expected_revision=current.revision,
                presentation=harness.proof(()),
            ),
        )
        assert current.active_presentation_id != presentation_id
    before = snapshot(harness.store)
    with pytest.raises(ApiFailure, match="PRESENTATION_INVALID"):
        harness.service.begin(
            harness.context(), session_id,
            MessageRequest(
                client_message_id=str(uuid4()), expected_revision=current.revision,
                text="Do not accept a mismatched selection", selected_ref=selected,
                presentation_id=presentation_id,
            ),
        )
    assert snapshot(harness.store) == before
