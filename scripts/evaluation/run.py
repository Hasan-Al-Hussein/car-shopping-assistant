"""Run only by explicit operator invocation on a prepared, empty disposable instance."""

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import func, select

from app.assistant.evaluation.runner import ReportWriter, evaluate, load_oracle, sha256
from app.assistant.evaluation.schema import Corpus, EvaluationRun
from app.assistant.evaluation.transports import LimitedLiveTransport, LivePermission, ScriptedTransport
from app.assistant.transport import GoogleGenAITransport
from app.core.config import Settings, load_settings
from app.database.models import Owner
from app.database.store import open_store
from app.runtime_app import ApplicationComposition, build_composition

PROJECT = Path(__file__).resolve().parents[2]
CORPUS = PROJECT / "fixtures/assistant/evaluation/corpus-v1.json"


async def retain_until_settled(
    composition: ApplicationComposition, exercise: Awaitable[EvaluationRun],
) -> EvaluationRun:
    """The CLI owns one loop until its original adapter/worker really settle."""
    try:
        return await exercise
    finally:
        if not composition.close():
            print(json.dumps({"gate": "INCOMPLETE", "reason": "RETAINING_ORIGINAL_PENDING_WORK"}))
            while not await composition.shutdown():
                await asyncio.sleep(0.05)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, help="Existing empty-owner store under the approved test-stores boundary.")
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--enable-live", action="store_true", help="Requires a separate granted live run; defaults off.")
    parser.add_argument("--approved-free-only", action="store_true")
    parser.add_argument("--max-calls", type=int, default=1)
    parser.add_argument("--max-live-seconds", type=int, default=1500)
    parser.add_argument("--access-evidence", type=Path)
    parser.add_argument("--access-evidence-sha256")
    args = parser.parse_args(argv)
    composition = None
    try:
        corpus = Corpus.model_validate_json(CORPUS.read_bytes())
        selected = None if args.cases is None else set(args.cases)
        if selected is not None and not selected <= {case.id for case in corpus.cases}:
            raise ValueError("UNKNOWN_EVALUATION_CASE")
        oracle = load_oracle(PROJECT, corpus)
        environment = {key: os.environ[key] for key in ("CSA_RUNTIME_ROOT", "CSA_RUNTIME_PHYSICAL_ROOT") if key in os.environ}
        environment["CSA_STORE_PATH"] = args.store
        access_hash = None
        if args.enable_live:
            if not args.approved_free_only or args.access_evidence is None:
                raise ValueError("LIVE_EVALUATION_NOT_AUTHORIZED")
            path = args.access_evidence.resolve()
            if not path.is_relative_to((PROJECT / "Records/build/F-05").resolve()):
                raise ValueError("LIVE_ACCESS_EVIDENCE_OUTSIDE_ACCEPTED_DIRECTORY")
            access_hash = sha256(path)
            if access_hash != args.access_evidence_sha256:
                raise ValueError("LIVE_ACCESS_EVIDENCE_CHANGED")
            environment["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "")
        configured = load_settings(environment)
        settings = Settings(store_path=configured.store_path, runtime_boundary=configured.runtime_boundary,
                            gemini_api_key=configured.gemini_api_key if args.enable_live else SecretStr("synthetic-evaluation-never-live"))
        if args.enable_live:
            permission = LivePermission(enabled=True, approved_free_only=args.approved_free_only,
                                        max_calls=args.max_calls, max_seconds=args.max_live_seconds,
                                        access_evidence_sha256=access_hash or "")
            permission.require(settings)
            transport = LimitedLiveTransport(
                GoogleGenAITransport(settings), permission.max_calls,
                max_seconds=permission.max_seconds,
            )
        else:
            transport = ScriptedTransport()
        if settings.store_path is None or settings.runtime_boundary is None:
            raise ValueError("EVALUATION_RUNTIME_BOUNDARY_REQUIRED")
        store = open_store(settings.store_path, boundary=settings.runtime_boundary)
        if not store.path.is_relative_to(settings.runtime_boundary.physical_root / "test-stores"):
            raise ValueError("EVALUATION_REQUIRES_DISPOSABLE_TEST_STORE")
        if store.read(lambda db: int(db.scalar(select(func.count()).select_from(Owner)) or 0)):
            raise ValueError("EVALUATION_REFUSES_EXISTING_BUYER_STATE")
        # A fixed clock keeps the explicit appointment scripts reproducible. This is labelled
        # in every report and is not actual appointment availability or a wall-clock demo.
        clock = lambda: datetime(2026, 9, 24, 4, tzinfo=UTC)
        composition = build_composition(settings, store, clock=clock, provider_transport=transport, event_sink=lambda event: None)
        observed = composition.admit_inventory()
        if observed.snapshot_id != corpus.snapshot_id:
            raise ValueError("EVALUATION_ACTIVE_SNAPSHOT_CHANGED")
        output = PROJECT / "Records/build/BE-24/runs" / str(uuid4())
        writer = ReportWriter(output)
        with (output / "report-schema.json").open("x", encoding="utf-8") as stream:
            json.dump(EvaluationRun.model_json_schema(), stream, ensure_ascii=False, indent=2)
        report = asyncio.run(retain_until_settled(composition, evaluate(composition, corpus, project=PROJECT, corpus_path=CORPUS,
            oracle=oracle, writer=writer, mode="live_synthetic" if args.enable_live else "offline_scripted",
            transport=transport, selected=selected, access_evidence_sha256=access_hash)))
        print(json.dumps({"gate": report.gate, "report": str(output / "report.json"), "mode": report.mode}))
        return 0 if report.gate == "PASS" else 1 if report.gate == "FAIL" else 2
    except Exception:
        print(json.dumps({"gate": "INCOMPLETE", "reason": "EVALUATION_ADMISSION_OR_EXECUTION_UNAVAILABLE"}))
        return 2
    finally:
        if composition is not None and not composition.close():
            # Do not replace or destroy a retained worker/provider on unsuccessful settlement.
            print(json.dumps({"gate": "INCOMPLETE", "reason": "EVALUATION_SHUTDOWN_PENDING"}))


if __name__ == "__main__":
    raise SystemExit(main())
