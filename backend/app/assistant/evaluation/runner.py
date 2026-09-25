"""Serial evaluator with append-only checkpoints and explicit incomplete outcomes."""

import hashlib
import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import Any, Literal
from uuid import uuid4

from app.assistant.packet import minimize_text
from app.assistant.provider import ADAPTER_VERSION, SDK_VERSION
from app.core.config import CONFIGURATION_VERSION, CONTRACT_VERSION, POLICY_VERSION
from app.runtime_app import ApplicationComposition

from .diagnostics import safe_exception
from .driver import ServiceDriver
from .effects import MODELS
from .judging import combined, gate, judge
from .schema import (
    Assertion,
    AssertionResult,
    CaseResult,
    Corpus,
    EvaluationRun,
    Step,
    StepResult,
    Verdict,
)
from .transports import LimitedLiveTransport, ScriptedTransport


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unrun(case: Any, reason: str, *, verdict: Verdict = "NOT_RUN") -> CaseResult:
    return CaseResult(
        case_id=case.id,
        category=case.category,
        verdict=verdict,
        reason=reason,
        steps=[
            StepResult(
                index=index,
                kind=step.kind,
                synthetic_input=minimize_text(step.text),
                verdict=verdict,
                safe_error=reason,
                assertions=[
                    AssertionResult(
                        name=item.name,
                        path=item.path,
                        expected=item.expected,
                        observed=None,
                        verdict=verdict,
                        critical=item.critical,
                    )
                    for item in step.assertions
                ],
            )
            for index, step in enumerate(case.steps)
        ],
    )


def budget_exhausted(transport: ScriptedTransport | LimitedLiveTransport, step: Step) -> bool:
    return (
        isinstance(transport, LimitedLiveTransport)
        and transport.calls >= transport.limit
        and step.kind == "message"
        and not any(
            item.path == "provider_attempts" and item.operator == "equals" and item.expected == 0
            for item in step.assertions
        )
    )


def live_stop_reason(
    transport: ScriptedTransport | LimitedLiveTransport,
    step: Step | None = None,
) -> str | None:
    if not isinstance(transport, LimitedLiveTransport):
        return None
    reason = transport.stop_reason()
    if reason == "LIVE_CALL_BUDGET_EXHAUSTED" and step is not None:
        return reason if budget_exhausted(transport, step) else None
    return reason


def live_progress(
    run: EvaluationRun,
    transport: ScriptedTransport | LimitedLiveTransport,
) -> EvaluationRun:
    if not isinstance(transport, LimitedLiveTransport):
        return run
    return run.model_copy(
        update={
            "identities": {
                **run.identities,
                "provider_call_limit": transport.limit,
                "provider_delegate_calls": transport.calls,
                "provider_refused_admissions": transport.refused,
                "provider_stop_reason": transport.stop_reason(),
                "live_admission_seconds": transport.max_seconds,
                "live_min_call_interval_seconds": 6,
                "live_elapsed_seconds": transport.clock()
                - transport.deadline_at
                + transport.max_seconds,
            }
        }
    )


def interrupted_by_budget(
    measured: StepResult,
    reason: str = "LIVE_CALL_BUDGET_EXHAUSTED",
) -> StepResult:
    # Successful-save expectations are unrun when repair cannot proceed. Separately
    # assert that the refused interpretation caused no actual owned/foreign effects.
    assertions = [item.model_copy(update={"verdict": "NOT_RUN"}) for item in measured.assertions]
    for assertion in (
        Assertion.model_validate(
            {
                "name": "budget refusal performs no domain mutation",
                "path": "mutations",
                "expected": {name: {"inserted": 0, "updated": 0, "deleted": 0} for name in MODELS},
                "critical": "unauthorized_action",
            }
        ),
        Assertion(
            name="budget refusal preserves foreign rows",
            path="foreign_domains_unchanged",
            expected=True,
            critical="unauthorized_action",
        ),
    ):
        assertions.append(judge(assertion, measured.observed))
    return measured.model_copy(
        update={
            "verdict": combined([item.verdict for item in assertions]),
            "safe_error": reason,
            "assertions": assertions,
        }
    )


def identities(
    project: Path, corpus: Corpus, corpus_path: Path, composition: ApplicationComposition
) -> dict[str, Any]:
    paths = sorted(
        set(
            [
                *project.glob("backend/app/**/*.py"),
                *project.glob("scripts/evaluation/*.py"),
                *project.glob("fixtures/assistant/evaluation/*.json"),
            ]
        )
    )
    files = {path.relative_to(project).as_posix(): sha256(path) for path in paths}
    settings = composition.settings
    return {
        "corpus_version": corpus.version,
        "corpus_sha256": sha256(corpus_path),
        "corpus_review_status": corpus.review_status,
        "case_ids": [case.id for case in corpus.cases],
        "corpus_source_review_sha256": sha256(project / "Records/build/BE-24/source-review.md"),
        "source_workbook_sha256": corpus.workbook_sha256,
        "snapshot_ids": [corpus.snapshot_id],
        "evidence_review_sha256": corpus.evidence_sha256,
        "source_files": files,
        "extraction_source": "backend/app/inventory/extraction.py",
        "retrieval_source": "backend/app/inventory/search_policy.py",
        "prompt_sources": [
            "backend/app/assistant/packet.py",
            "backend/app/assistant/intent.py",
            "backend/app/assistant/interpretation.py",
        ],
        "provider_model": settings.provider_model,
        "provider_sdk_version": version("google-genai"),
        "provider_sdk_expected": SDK_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "configuration_version": CONFIGURATION_VERSION,
        "contract_version": CONTRACT_VERSION,
        "policy_version": POLICY_VERSION,
        "config_sha256": hashlib.sha256(settings.model_dump_json().encode()).hexdigest(),
        "contract_sha256": sha256(project / "contracts/v1/openapi.json"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "clock_utc": composition.clock().isoformat(),
        "store_generation": composition.store.generation,
        "source_mode": "accepted_workbook_real_services_disposable_store",
        "privacy": (
            "fixed_synthetic_prompts_no_contact_seeds_minimized_output_no_raw_provider_payload"
        ),
        "accuracy_threshold": None,
        "api_latency_pilot": "separate_3_client_200_request_gate",
    }


class ReportWriter:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=False)
        self.directory, self.sequence = directory, 0

    def write(self, run: EvaluationRun, *, final: bool = False) -> None:
        name = "report.json" if final else f"checkpoint-{self.sequence:03d}.json"
        with (self.directory / name).open("x", encoding="utf-8") as stream:
            stream.write(run.model_dump_json(indent=2))
            stream.write("\n")
        self.sequence += 1


async def evaluate(
    composition: ApplicationComposition,
    corpus: Corpus,
    *,
    project: Path,
    corpus_path: Path,
    oracle: dict[str, Any],
    writer: ReportWriter,
    mode: Literal["offline_scripted", "live_synthetic"],
    transport: ScriptedTransport | LimitedLiveTransport,
    selected: set[str] | None = None,
    access_evidence_sha256: str | None = None,
) -> EvaluationRun:
    run = EvaluationRun(
        run_id=str(uuid4()),
        mode=mode,
        started_utc=datetime.now(UTC).isoformat(),
        identities=identities(project, corpus, corpus_path, composition),
        denominator=len(corpus.cases),
        cases=[unrun(case, "NOT_STARTED") for case in corpus.cases],
        live_quality="HUMAN_REVIEW_REQUIRED" if mode == "live_synthetic" else "NOT_EVALUATED",
    )
    if mode == "live_synthetic":
        run = run.model_copy(
            update={
                "identities": {
                    **run.identities,
                    "provider_access_evidence_sha256": access_evidence_sha256,
                    "provider_call_limit": transport.limit
                    if isinstance(transport, LimitedLiveTransport)
                    else 0,
                }
            }
        )
    driver = ServiceDriver(
        composition, corpus, oracle, transport if isinstance(transport, ScriptedTransport) else None
    )
    writer.write(live_progress(run, transport))
    try:
        for position, case in enumerate(corpus.cases):
            reason = (
                "NOT_SELECTED"
                if selected is not None and case.id not in selected
                else "OFFLINE_FAULT_OR_AUTHORITY_CASE"
                if mode == "live_synthetic" and not case.live_eligible
                else live_stop_reason(transport)
            )
            if reason is not None:
                run.cases[position] = unrun(case, reason)
                writer.write(live_progress(gate(run), transport))
                continue
            completed: list[StepResult] = []
            step_started: float | None = None
            stop_reason = "EARLIER_STEP_DID_NOT_PASS"
            try:
                actor = await driver.actor()
                for index, step in enumerate(case.steps):
                    live_stop = live_stop_reason(transport, step)
                    if live_stop is not None:
                        stop_reason = live_stop
                        break
                    refused_before = (
                        transport.refused if isinstance(transport, LimitedLiveTransport) else 0
                    )
                    step_started = monotonic()
                    measured = await driver.perform(actor, step, index)
                    if (
                        isinstance(transport, LimitedLiveTransport)
                        and transport.refused > refused_before
                    ):
                        stop_reason = transport.stop_reason() or "LIVE_CALL_BUDGET_EXHAUSTED"
                        measured = interrupted_by_budget(measured, stop_reason)
                    completed.append(measured)
                    run.cases[position] = CaseResult(
                        case_id=case.id,
                        category=case.category,
                        verdict="NOT_RUN",
                        steps=completed + unrun(case, "NOT_STARTED").steps[index + 1 :],
                    )
                    writer.write(live_progress(gate(run), transport))
                    if completed[-1].verdict != "PASS":
                        stop_reason = live_stop_reason(transport) or stop_reason
                        break
                remaining = unrun(case, stop_reason).steps[len(completed) :]
                all_steps = completed + remaining
                run.cases[position] = CaseResult(
                    case_id=case.id,
                    category=case.category,
                    verdict=combined([step.verdict for step in all_steps]),
                    steps=all_steps,
                    reason=stop_reason if remaining or completed[-1].verdict == "NOT_RUN" else None,
                )
            except Exception as error:
                # Error details can contain keys, raw source, paths or private payloads.
                remaining = unrun(case, "UNEXPECTED_EXECUTION_ERROR", verdict="UNKNOWN").steps[
                    len(completed) :
                ]
                if remaining and step_started is not None:
                    remaining[0] = remaining[0].model_copy(
                        update={
                            "elapsed_ms": (monotonic() - step_started) * 1000,
                            "safe_error": "UNEXPECTED_EXECUTION_ERROR",
                            "safe_diagnostic": safe_exception(error, project),
                        }
                    )
                run.cases[position] = CaseResult(
                    case_id=case.id,
                    category=case.category,
                    verdict="FAIL"
                    if any(step.verdict == "FAIL" for step in completed)
                    else "UNKNOWN",
                    steps=completed + remaining,
                    reason="UNEXPECTED_EXECUTION_ERROR",
                )
                # Unobserved outcome does not authorize a new case after possibly retained work.
                break
            writer.write(live_progress(gate(run), transport))
    finally:
        settled = await composition.shutdown()
        run = run.model_copy(
            update={
                "cleanup": "SETTLED" if settled else "PENDING",
                "finished_utc": datetime.now(UTC).isoformat(),
            }
        )
        run = gate(live_progress(run, transport))
        writer.write(run, final=True)
    return run


def load_oracle(project: Path, corpus: Corpus) -> dict[str, Any]:
    path = project / "Records/build/BE-04/evidence/resolved-facts.json"
    if (
        sha256(path) != corpus.evidence_sha256
        or sha256(project / "sources/Copy_of_sample_cars_dataset.xlsx") != corpus.workbook_sha256
    ):
        raise ValueError("EVALUATION_SOURCE_IDENTITY_CHANGED")
    return {
        item["ref"]["source_id"]: item
        for item in json.loads(path.read_text(encoding="utf-8"))["records"]
    }
