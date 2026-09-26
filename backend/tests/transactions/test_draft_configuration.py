"""P12A exact material/identity and predecode bounds; all Inventory fixtures synthetic."""

import json
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import VIEWING_VENUE, DemoPolicy
from app.core.errors import ApiFailure
from app.database.models import ActiveRules, RuleVersion
from app.inventory.references import ImmutableInventoryRef
from app.sessions.state import canonical
from app.viewings import draft_configuration as configuration
from app.viewings.draft_configuration import (
    ViewingConfiguration,
    configuration_id,
    eligibility_version,
    load_configuration,
    parse_configuration,
)
from app.viewings.eligibility import resolve_eligibility
from app.viewings.scheduling import ViewingRules
from tests.transactions.draft_fixtures import make_draft_harness, update
from tests.transactions.viewing_fixtures import active_fixture


def sample() -> ViewingConfiguration:
    active, _, policy = active_fixture()
    assert active.stage is not None
    return ViewingConfiguration(
        format="viewing-configuration-1",
        calendar_version=ViewingRules(DemoPolicy()).version,
        policy=DemoPolicy(),
        venue_label=VIEWING_VENUE,
        eligibility=policy,
        inventory=active.observation,
        mapping_digest=active.stage.mapping_digest,
    )


def parse(raw: str) -> ViewingConfiguration:
    value = sample()
    return parse_configuration(
        raw,
        rules=ViewingRules(DemoPolicy()),
        observation=value.inventory,
        namespace=value.eligibility.eligible_refs[0].namespace,
    )


def test_complete_json_roundtrip_and_exact_be13_eligibility_formula() -> None:
    value = sample()
    decoded = parse(value.model_dump_json())
    assert canonical(decoded.model_dump(mode="json")) == canonical(value.model_dump(mode="json"))
    assert decoded.policy.open_weekdays == (0, 1, 2, 3, 4, 5)
    active, ref, policy = active_fixture()
    assert (
        eligibility_version(decoded) == resolve_eligibility(active, ref, policy).eligibility_version
    )
    assert len(configuration_id(decoded)) == 81


def test_explicit_empty_policy_is_valid_deny_all() -> None:
    material = sample().model_dump(mode="json")
    material["eligibility"]["eligible_refs"] = []
    value = parse(json.dumps(material))
    assert value.eligibility.eligible_refs == ()


@pytest.mark.parametrize(
    "fault",
    [
        "missing_envelope_key",
        "extra",
        "missing_default",
        "float_alias",
        "bool_alias",
        "duplicate_ref",
        "unsorted",
        "foreign_snapshot",
        "foreign_namespace",
        "missing_observation",
        "calendar",
        "venue",
        "format",
        "digest",
        "observation_change",
        "too_many_refs",
    ],
)
def test_incomplete_normalized_or_wrong_binding_is_rejected(fault: str) -> None:
    material: dict[str, Any] = sample().model_dump(mode="json")
    refs = material["eligibility"]["eligible_refs"]
    if fault == "missing_envelope_key":
        material.pop("eligibility")
    elif fault == "extra":
        material["allow_all"] = True
    elif fault == "missing_default":
        material["policy"].pop("contact_required")
    elif fault == "float_alias":
        material["policy"]["capacity"] = 1.0
    elif fault == "bool_alias":
        material["policy"]["capacity"] = True
    elif fault == "duplicate_ref":
        refs.append(dict(refs[0]))
    elif fault == "unsorted":
        refs.insert(0, {**refs[0], "source_id": "zzz"})
    elif fault == "foreign_snapshot":
        refs[0]["snapshot_id"] = "0" * 64
    elif fault == "foreign_namespace":
        refs[0]["namespace"] = "another-namespace"
    elif fault == "missing_observation":
        material["inventory"].pop("mode")
    elif fault == "calendar":
        material["calendar_version"] = "other-calendar"
    elif fault == "venue":
        material["venue_label"] = "Real venue"
    elif fault == "format":
        material["format"] = "future-format"
    elif fault == "digest":
        material["mapping_digest"] = "F" * 64
    elif fault == "observation_change":
        material["inventory"]["active_revision"] += 1
    else:
        material["eligibility"]["eligible_refs"] = [
            {**refs[0], "source_id": f"{i:03d}"} for i in range(101)
        ]
    with pytest.raises(ApiFailure, match="RULES_UNAVAILABLE"):
        parse(json.dumps(material))


@pytest.mark.parametrize(
    "raw",
    [
        "[]", "null", "{}", '{"format":"x","format":"y"}',
        pytest.param(" " * 65_537, id="oversized-whitespace"), '{"x":NaN}',
    ],
)
def test_invalid_or_oversized_json_is_closed(raw: str) -> None:
    with pytest.raises(ApiFailure, match="RULES_UNAVAILABLE"):
        parse(raw)


def test_raw_oversized_row_is_rejected_before_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    drafts = make_draft_harness()
    prepared = drafts.inventory.prepare(
        ImmutableInventoryRef.model_validate(drafts.command().ref.model_dump())
    )

    def corrupt(db: Session) -> None:
        db.execute(
            text("UPDATE rule_versions SET rules_json = :raw WHERE version = :version"),
            {
                "raw": json.dumps({"oversized": "x" * 65_536}),
                "version": prepared.configuration_version,
            },
        )

    drafts.base.store.write(corrupt)

    def forbidden(*args: object, **kwargs: object) -> ViewingConfiguration:
        raise AssertionError("OVERSIZED_CONFIGURATION_WAS_MATERIALIZED_FOR_PARSING")

    monkeypatch.setattr(configuration, "parse_configuration", forbidden)
    with pytest.raises(ApiFailure, match="RULES_UNAVAILABLE"):
        drafts.base.store.read(
            lambda db: load_configuration(
                db,
                prepared.configuration_version,
                rules=ViewingRules(DemoPolicy()),
                observation=sample().inventory,
                namespace="provided-cars-cleaned",
            )
        )


@pytest.mark.parametrize(
    "fault", ["content", "policy_column", "eligibility_column", "revision_exhausted", "reactivated"]
)
def test_current_use_rechecks_configuration_content_and_activation(fault: str) -> None:
    drafts = make_draft_harness()
    first = drafts.service.create(drafts.base.context(), drafts.command())

    def change(db: Session) -> None:
        active = db.get(ActiveRules, 1)
        assert active is not None
        row = db.get(RuleVersion, active.version)
        assert row is not None
        if fault == "content":
            row.rules_json = {**row.rules_json, "mapping_digest": "0" * 64}
        elif fault == "policy_column":
            row.policy_version = "other-policy"
        elif fault == "eligibility_column":
            row.eligibility_version = "other-eligibility"
        elif fault == "revision_exhausted":
            active.revision = 2_147_483_648
        else:
            # Simulates A -> B -> A's retained final pointer/revision.
            active.revision += 2

    drafts.base.store.write(change)
    observed = drafts.service.get(drafts.base.context(), first.draft_id)
    assert observed.state == "needs_details" and observed.review is not None
    assert observed.review.state == "invalidated"
    assert drafts.counts() == (1, 1, 0, 0, 0, 0)
    if fault == "reactivated":
        assert (
            drafts.service.update(
                drafts.base.context(), first.draft_id, update(first, "refresh_review")
            ).state
            == "reviewable"
        )
    else:
        with pytest.raises(ApiFailure, match="RULES_UNAVAILABLE|ELIGIBILITY_UNAVAILABLE"):
            drafts.service.update(
                drafts.base.context(), first.draft_id, update(first, "refresh_review")
            )
        assert drafts.counts() == (1, 1, 0, 0, 0, 0)
