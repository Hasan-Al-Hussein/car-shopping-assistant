"""Versioned corpus and report types; expected and observed outcomes stay separate."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from app.assistant.intent import TurnIntent
from app.core.config import FrozenSettings

Critical = Literal["wrong_car", "invented_fact", "unauthorized_action", "duplicate_commit"]
Verdict = Literal["PASS", "FAIL", "UNKNOWN", "NOT_RUN"]
Category = Literal[
    "supported_intent",
    "grounding",
    "ambiguity",
    "return",
    "review_confirmation",
    "provider_failure",
    "adversarial_mixed",
]


class Assertion(FrozenSettings):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    path: Annotated[str, Field(pattern=r"^[a-z_]+(?:\.[a-z_]+)*$")]
    operator: Literal["equals", "contains", "absent"] = "equals"
    expected: JsonValue = None
    critical: Critical | None = None


class Step(FrozenSettings):
    kind: Literal["message", "new_session", "replay", "confirm", "foreign_owner"] = "message"
    text: Annotated[str, Field(max_length=4000)] = ""
    intent: TurnIntent | None = None
    fault: Literal["quota", "timeout", "unavailable", "malformed"] | None = None
    select_source_id: str | None = None
    prose_mode: Literal["fixed", "grounded", "no_result"]
    expected_text: str | None = None
    scope_topics: list[str] = Field(default_factory=list)
    assertions: Annotated[list[Assertion], Field(min_length=1, max_length=30)]

    @model_validator(mode="after")
    def explicit_script(self) -> "Step":
        if self.kind == "message" and (
            not self.text or (self.intent is None) == (self.fault is None)
        ):
            raise ValueError("MESSAGE_REQUIRES_ONE_EXPLICIT_INTERPRETATION_OR_FAULT")
        if self.kind != "message" and (self.intent is not None or self.fault is not None):
            raise ValueError("NON_MESSAGE_CANNOT_SCRIPT_PROVIDER")
        if (self.prose_mode == "fixed") != (self.expected_text is not None):
            raise ValueError("FIXED_PROSE_REQUIRES_EXPLICIT_EXPECTED_TEXT")
        return self


class EvaluationCase(FrozenSettings):
    id: Annotated[str, Field(pattern=r"^A11-[0-9]{3}$")]
    title: Annotated[str, Field(min_length=1, max_length=180)]
    category: Category
    historical_ids: list[str] = Field(default_factory=list)
    scenarios: Annotated[list[str], Field(min_length=1)]
    live_eligible: bool = False
    steps: Annotated[list[Step], Field(min_length=1, max_length=16)]


class Corpus(FrozenSettings):
    version: Literal["BE24-CORPUS-1"] = "BE24-CORPUS-1"
    review_status: Literal["SOURCE_REVIEW_REQUIRED", "SOURCE_REVIEWED"]
    provenance: str
    namespace: str
    snapshot_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    workbook_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    evidence_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    cases: Annotated[list[EvaluationCase], Field(min_length=40, max_length=100)]

    @model_validator(mode="after")
    def complete_categories(self) -> "Corpus":
        required = {
            "supported_intent",
            "grounding",
            "ambiguity",
            "return",
            "review_confirmation",
            "provider_failure",
            "adversarial_mixed",
        }
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("DUPLICATE_CASE_ID")
        if {case.category for case in self.cases} != required:
            raise ValueError("INCOMPLETE_REQUIRED_CATEGORIES")
        return self


class AssertionResult(FrozenSettings):
    name: str
    path: str
    expected: JsonValue
    observed: JsonValue
    verdict: Verdict
    critical: Critical | None = None


class StepResult(FrozenSettings):
    index: int
    kind: str
    synthetic_input: str
    verdict: Verdict
    observed: dict[str, JsonValue] = Field(default_factory=dict)
    assertions: list[AssertionResult] = Field(default_factory=list)
    elapsed_ms: float | None = None
    provider_attempts: int | None = None
    tool_invocations: int | None = None
    usage: dict[str, int | None] = Field(default_factory=dict)
    safe_error: str | None = None
    safe_diagnostic: dict[str, JsonValue] | None = None


class CaseResult(FrozenSettings):
    case_id: str
    category: Category
    verdict: Verdict
    steps: list[StepResult]
    reason: str | None = None


class EvaluationRun(FrozenSettings):
    schema_version: Literal["BE24-RUN-1"] = "BE24-RUN-1"
    run_id: str
    mode: Literal["offline_scripted", "live_synthetic"]
    started_utc: str
    finished_utc: str | None = None
    identities: dict[str, JsonValue]
    cases: list[CaseResult]
    gate: Literal["PASS", "FAIL", "INCOMPLETE"] = "INCOMPLETE"
    denominator: int
    counts: dict[str, int] = Field(default_factory=dict)
    critical_failures: list[str] = Field(default_factory=list)
    unsupported_assertion_count: int = 0
    tool_action_failure_count: int = 0
    cleanup: Literal["NOT_RUN", "SETTLED", "PENDING"] = "NOT_RUN"
    live_quality: Literal["NOT_EVALUATED", "HUMAN_REVIEW_REQUIRED"] = "NOT_EVALUATED"
    timing_policy: Literal["observational_not_api_pilot"] = "observational_not_api_pilot"
