"""Detector canaries deliberately corrupt observations, never expected results."""

from uuid import uuid4

import pytest
from pydantic import JsonValue

from app.assistant.evaluation.judging import combined, gate, judge
from app.assistant.evaluation.schema import Assertion, CaseResult, Critical, EvaluationRun, StepResult


def report(assertion: Assertion, actual: JsonValue) -> EvaluationRun:
    # Pure synthetic detector fixture, explicitly not a real corpus/model run.
    observation = {"value": actual}
    result = judge(assertion, observation)
    step = StepResult(index=0, kind="canary", synthetic_input="SYNTHETIC DETECTOR CONTROL",
                      verdict=result.verdict, assertions=[result])
    control = judge(assertion, {"value": assertion.expected})
    cases = [CaseResult(case_id=f"CONTROL-{index}", category="grounding", verdict="PASS",
                        steps=[step.model_copy(update={"verdict": "PASS", "assertions": [control]})])
             for index in range(39)]
    cases.append(CaseResult(case_id="CANARY", category="grounding", verdict=result.verdict, steps=[step]))
    return EvaluationRun(run_id=str(uuid4()), mode="offline_scripted", started_utc="2026-09-24T00:00:00Z",
        identities={"corpus_review_status": "SOURCE_REVIEWED", "case_ids": [case.case_id for case in cases],
                    "fixture": "gate-unit-control-not-corpus-evidence"},
        cases=cases, denominator=40, cleanup="SETTLED")


@pytest.mark.parametrize("critical,expected,corrupt", [
    ("wrong_car", {"snapshot_id": "a" * 64, "source_id": "3"}, {"snapshot_id": "a" * 64, "source_id": "4"}),
    ("invented_fact", "unknown", "known"),
    ("unauthorized_action", {"leads": 0, "bookings": 0}, {"leads": 1, "bookings": 0}),
    ("duplicate_commit", {"bookings": 0}, {"bookings": 1}),
])
def test_critical_canary_rejects_corrupted_observation(
    critical: Critical, expected: JsonValue, corrupt: JsonValue,
) -> None:
    assertion = Assertion.model_validate({"name": "critical control", "path": "value",
                                         "expected": expected, "critical": critical})
    assert gate(report(assertion, expected)).gate == "PASS"
    failed = gate(report(assertion, corrupt))
    assert failed.gate == "FAIL" and len(failed.critical_failures) == 1
    preserved = failed.cases[-1].steps[0].assertions[0]
    assert preserved.expected == expected and preserved.observed == corrupt
    assert preserved.verdict == "FAIL" and critical in failed.critical_failures[0]


def test_unknown_unrun_and_live_cannot_be_averaged_into_pass() -> None:
    assertion = Assertion(name="unknown fact", path="missing", expected="known", critical="invented_fact")
    unknown = judge(assertion, {})
    assert unknown.verdict == "UNKNOWN"
    assert combined(["PASS", "NOT_RUN"]) == "NOT_RUN"
    passed = report(Assertion(name="exact", path="value", expected=1), 1)
    assert gate(passed.model_copy(update={"mode": "live_synthetic", "live_quality": "HUMAN_REVIEW_REQUIRED"})).gate == "INCOMPLETE"
    assert gate(passed.model_copy(update={"cleanup": "PENDING"})).gate == "INCOMPLETE"
    assert gate(passed.model_copy(update={"denominator": 41})).gate == "INCOMPLETE"


def test_observed_provider_failure_is_preserved_even_when_expected() -> None:
    assertion = Assertion(name="expected unavailable", path="value", expected="provider_unavailable")
    checked = judge(assertion, {"value": "provider_unavailable"})
    assert checked.verdict == "PASS" and checked.observed == "provider_unavailable"
