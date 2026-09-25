"""Real HTTP PDF demonstrations. Authored only; no mock, database or provider client.

Use the sibling README. A captured run still needs independent grounding review.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "Records/build/platform/post-guidance-full-pdf/demo-runs"
FIRST_TURN_OUTPUT_ROOT = (
    ROOT / "Records/build/assistant/pdf-first-live-diagnosis/post-503-first-turn/runs"
)
MAX_REQUESTS = 24
RUN_SECONDS = 240
REQUEST_SECONDS = 35
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUIREMENTS = ["quiet cabin", "space for a folding bicycle"]
SEARCH_TEXT = "Show me cars from the supplied inventory."
SAVE_TEXT = (
    'Please explicitly remember these two soft requirements for future conversations: '
    '"quiet cabin" and "space for a folding bicycle". Save these preferences now.'
)
RECALL_TEXT = (
    "What requirements did I ask you to remember in my earlier conversation? "
    "Tell me the saved values."
)
SAFE_KEYS = set("""
data meta state service inventory store assistant viewing export active_snapshot_id
request_id contract_version policy_version inventory_snapshot_id store_generation entity_revision
mode identity_mode notice_version notice_acknowledged session_id journey_id revision criteria
query filters soft_preferences selected_ref active_presentation_id pending_intent kind
recalled_preferences entries preference key value strength source_session_id source_action_id
source_message_id message_id confirmed_at expires_at applicability collection_mode client_message_id
client_action_id expected_revision current_revision turn_revision text evidence ref attributes
namespace snapshot_id source_id search items supported_total presentation presentation_id
ordered_refs applied_criteria evidence_coverage unsupported_constraints constraints_relaxed
make model trim year cash_price mileage_km warranty qualifier claims status reason currency
minimum maximum minor_units basis handoff_summary listing expressed_criteria fit_reasons
unresolved_questions attribute criterion question actions preferences shortlist lead result operation
persistence provider_state accepted_revision accepted_at user_text assistant_result historical
observed_revision next_cursor error code retryable retry_action outcome_state source_total
supported excluded_unknown excluded_conflicting excluded_unsupported_qualifier
evidence_id workbook_sha256 sheet cell span_start span_end extraction_version category
review_status verification original_unit semantic_role
""".split())
NUMERIC_CONTEXT_KEYS = set("""
session_id journey_id request_id store_generation source_session_id source_action_id
source_message_id message_id client_message_id client_action_id active_presentation_id presentation_id
snapshot_id inventory_snapshot_id active_snapshot_id accepted_at confirmed_at expires_at
source_id evidence_id workbook_sha256
""".split())
EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
PHONE = re.compile(r"(?<!\w)\+?\d[\d ()./-]{6,}\d(?!\w)")
URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
SECRET = re.compile(r"\b(?:AIza[A-Za-z0-9_-]{20,}|[A-Za-z0-9_-]{43})\b")


class Unmet(Exception):
    """Named condition only: exception text must never contain response bodies."""


def require(condition: Any, code: str) -> None:
    if not condition:
        raise Unmet(code)


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def object_value(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "RESPONSE_OBJECT_REQUIRED")
    return value


def identifier(value: Any) -> str:
    require(isinstance(value, str) and re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value
    ), "INVALID_RESPONSE_IDENTIFIER")
    return value


def local_origin(value: str) -> str:
    parsed = urlsplit(value)
    require(
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and parsed.username is None and parsed.password is None
        and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment,
        "EXACT_LOOPBACK_ORIGIN_REQUIRED",
    )
    _ = parsed.port  # Reject malformed ports before any HTTP or output creation.
    return f"{parsed.scheme}://{parsed.netloc}"


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


class Demo:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.first_turn_only = args.first_turn_only
        self.max_requests = 6 if self.first_turn_only else MAX_REQUESTS
        self.run_seconds = 60 if self.first_turn_only else RUN_SECONDS
        self.message_posts = 0
        self.started = time.monotonic()
        self.count = 0
        self.context: str | None = None
        self.csrf: str | None = None
        self.generation: str | None = None
        self.last_meta: dict[str, Any] = {}
        self.secrets: set[str] = set()
        self.turns: dict[str, list[str]] = {}
        self.results: dict[str, dict[str, Any]] = {}
        self.prompts: dict[str, str] = {}
        output_root = FIRST_TURN_OUTPUT_ROOT if self.first_turn_only else OUTPUT_ROOT
        self.marker = output_root / (
            "attempt-used.json" if self.first_turn_only else "incomplete.json"
        )
        require(not self.marker.exists(), (
            "PREVIOUS_FIRST_TURN_REQUIRES_OPERATOR_RECONCILIATION"
            if self.first_turn_only else "PREVIOUS_DEMO_REQUIRES_OPERATOR_RECONCILIATION"
        ))
        self.run_id = str(uuid4())
        self.directory = output_root / self.run_id
        self.directory.mkdir(parents=True, exist_ok=False)
        self.journal = self.directory / "evidence.jsonl"
        self.last_request: dict[str, Any] | None = None
        self.owner_started = False
        self.client = httpx.AsyncClient(
            base_url=args.base_url, trust_env=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    def clean(self, value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {name: self.clean(item, name) for name, item in value.items() if name in SAFE_KEYS}
        if isinstance(value, list):
            return [self.clean(item, key) for item in value]
        if isinstance(value, str):
            for secret in sorted(self.secrets, key=len, reverse=True):
                value = value.replace(secret, "[credential removed]")
            for pattern in (EMAIL, URL, SECRET):
                value = pattern.sub("[private content removed]", value)
            if key not in NUMERIC_CONTEXT_KEYS:
                value = PHONE.sub("[private content removed]", value)
            return value
        return value

    def record(self, event: dict[str, Any]) -> None:
        # Write-ahead records are durable before a mutation can reach the backend.
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"utc": now(), **event}, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    async def request(
        self, method: str, path: str, body: dict[str, Any] | None = None,
        *, private: bool = False, expected_status: int = 200,
    ) -> dict[str, Any]:
        remaining = self.run_seconds - (time.monotonic() - self.started)
        require(remaining > 1 and self.count < self.max_requests, "FINITE_REQUEST_BUDGET_EXHAUSTED")
        if self.first_turn_only and method == "POST" and path.endswith("/messages"):
            require(self.message_posts == 0, "FIRST_TURN_MESSAGE_LIMIT_REACHED")
            self.message_posts += 1
        self.count += 1
        mutation = method != "GET"
        headers = {"Accept": "application/json"}
        if mutation:
            headers["Origin"] = self.args.origin
        if private:
            require(self.context and self.csrf, "LOCAL_ACCESS_REQUIRED")
            headers["X-Identity-Context"] = self.context
            if mutation:
                headers["X-CSRF-Token"] = self.csrf
        self.last_request = {
            "sequence": self.count, "method": method, "path": path,
            "body": self.clean(body), "mutation": mutation,
        }
        if mutation and not self.owner_started:
            # Exclusive marker also prevents a second process starting fresh access.
            with self.marker.open("x", encoding="utf-8") as stream:
                json.dump({"run_id": self.run_id, "journal": str(self.journal)}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            self.owner_started = True
        self.record({"event": "request_before_dispatch", **self.last_request})
        try:
            async with asyncio.timeout(min(REQUEST_SECONDS, remaining)):
                async with self.client.stream(
                    method, path, json=body, headers=headers,
                    timeout=httpx.Timeout(min(REQUEST_SECONDS, remaining), connect=5),
                ) as response:
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        require(len(chunks) + len(chunk) <= MAX_RESPONSE_BYTES, "RESPONSE_TOO_LARGE")
                        chunks.extend(chunk)
                    require("application/json" in response.headers.get("content-type", ""),
                            "JSON_RESPONSE_REQUIRED")
                    payload = object_value(json.loads(chunks))
                    # Capture credentials only in memory, before sanitizing any logged prose.
                    for cookie in self.client.cookies.jar:
                        self.secrets.add(cookie.value)
                    identity = payload.get("data", {})
                    if isinstance(identity, dict):
                        for name in ("csrf_token", "context_id"):
                            if isinstance(identity.get(name), str):
                                self.secrets.add(identity[name])
                    self.record({"event": "response", "sequence": self.count,
                                 "http_status": response.status_code,
                                 "response": self.clean(payload)})
                    require(response.status_code not in {404, 405},
                            "PRECONDITION_REQUIRED_ROUTE_OR_RESOURCE_UNAVAILABLE")
                    require(response.status_code != 503, "PRECONDITION_REQUIRED_SERVICE_UNAVAILABLE")
                    require(response.status_code == expected_status, "UNEXPECTED_HTTP_STATUS")
        except (TimeoutError, httpx.HTTPError):
            self.record({"event": "transport_unresolved", **self.last_request,
                         "automatic_retry": False})
            raise Unmet("ORIGINAL_REQUEST_OUTCOME_UNRESOLVED_NO_RETRY") from None
        except (ValueError, UnicodeError):
            raise Unmet("UNREADABLE_RESPONSE_ORIGINAL_REQUEST_RETAINED") from None
        data, meta = object_value(payload.get("data")), object_value(payload.get("meta"))
        require(meta.get("contract_version") == "1.0.0"
                and meta.get("policy_version") == "DEMO-POLICY-1", "CONTRACT_OR_POLICY_CHANGED")
        self.last_meta = meta
        if private:
            require(meta.get("identity_context_id") == self.context
                    and meta.get("store_generation") == self.generation,
                    "OWNER_OR_STORE_ASSOCIATION_CHANGED")
            revision = next((data[name] for name in ("current_revision", "revision", "observed_revision")
                             if name in data), None)
            require(type(revision) is int and meta.get("entity_revision") == revision,
                    "ENVELOPE_REVISION_MISMATCH")
            self.record({"event": "private_envelope_verified", "sequence": self.count,
                         "same_bootstrapped_owner": True, "same_store_generation": True,
                         "entity_revision": revision})
        return data

    async def session(self) -> dict[str, Any]:
        state = await self.request("POST", "/api/v1/sessions",
                                   {"client_action_id": str(uuid4())}, private=True,
                                   expected_status=201)
        sid = identifier(state.get("session_id"))
        require(state.get("revision") == 0 and state.get("selected_ref") is None,
                "FRESH_SESSION_REQUIRED")
        require(sid not in self.turns, "DISTINCT_NEW_SESSION_REQUIRED")
        self.turns[sid] = []
        return state

    async def read_session(self, sid: str, revision: int) -> dict[str, Any]:
        state = await self.request("GET", f"/api/v1/sessions/{sid}", private=True)
        require(state.get("session_id") == sid and state.get("revision") == revision,
                "SESSION_REVISION_CHANGED")
        return state

    async def turn(
        self, state: dict[str, Any], text: str, *, saving_preferences: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sid, revision = identifier(state.get("session_id")), state.get("revision")
        require(type(revision) is int, "SESSION_REVISION_REQUIRED")
        message_id = str(uuid4())
        # Deliberately no selected_ref/presentation_id: backend memory must resolve language.
        result = await self.request("POST", f"/api/v1/sessions/{sid}/messages", {
            "client_message_id": message_id, "expected_revision": revision, "text": text,
        }, private=True)
        require(result.get("client_message_id") == message_id and result.get("session_id") == sid,
                "MESSAGE_ASSOCIATION_CHANGED")
        require(result.get("state") == "answered" and result.get("persistence") == "saved",
                "ANSWERED_PERSISTED_TURN_REQUIRED")
        require(result.get("turn_revision") == revision + 1
                and type(result.get("current_revision")) is int
                and result["current_revision"] >= result["turn_revision"],
                "MESSAGE_REVISION_MISMATCH")
        require(result.get("provider_state") in {"available", "not_used"}, "PROVIDER_UNAVAILABLE")
        require(isinstance(result.get("text"), str) and result["text"].strip(), "ANSWER_TEXT_REQUIRED")
        actions = object_value(result.get("actions"))
        require(result.get("operation") is None and all(
            object_value(actions.get(name)).get("state") == "not_requested"
            for name in ("shortlist", "lead")
        ), "UNEXPECTED_UNREQUESTED_ACTION_OR_OPERATION")
        if not saving_preferences:
            require(object_value(actions.get("preferences")).get("state") == "not_requested",
                    "UNREQUESTED_PREFERENCE_ACTION")
        self.turns[sid].append(message_id)
        self.results[message_id] = result
        self.prompts[message_id] = text
        return result, await self.read_session(sid, result["current_revision"])

    def saved_entry(self, record: dict[str, Any], source_session: str) -> dict[str, Any]:
        entries = record.get("entries", [])
        require(isinstance(entries, list) and len(entries) == 1
                and record.get("collection_mode") == "explicit_save"
                and type(record.get("revision")) is int, "EXACT_EXPLICIT_PREFERENCE_RECORD_REQUIRED")
        matching = [entry for entry in entries if object_value(entry).get("preference", {}).get("key")
                    == "requirements"]
        require(len(matching) == 1, "ACTUAL_SAVED_REQUIREMENTS_MISSING")
        entry = matching[0]
        preference = object_value(entry["preference"])
        require(preference.get("value") == REQUIREMENTS and preference.get("strength") == "soft"
                and entry.get("source_session_id") == source_session
                and entry.get("applicability") == "confirmed",
                "SAVED_VALUES_OR_PROVENANCE_MISMATCH")
        identifier(entry.get("source_action_id"))
        return entry

    async def diagnostic_first_turn(self, state: dict[str, Any]) -> dict[str, Any]:
        sid = identifier(state.get("session_id"))
        revision = state.get("revision")
        require(type(revision) is int and revision == 0, "FRESH_SESSION_REQUIRED")
        message_id = str(uuid4())
        result = await self.request("POST", f"/api/v1/sessions/{sid}/messages", {
            "client_message_id": message_id, "expected_revision": revision, "text": SEARCH_TEXT,
        }, private=True)
        require(result.get("client_message_id") == message_id and result.get("session_id") == sid,
                "MESSAGE_ASSOCIATION_CHANGED")
        require(result.get("persistence") == "saved" and result.get("turn_revision") == 1
                and result.get("current_revision") == 1, "DIAGNOSTIC_PERSISTED_TURN_REQUIRED")
        require(result.get("state") in {"answered", "clarification", "provider_unavailable"}
                and result.get("provider_state") in {"available", "unavailable", "not_used"},
                "DIAGNOSTIC_TURN_STATE_INVALID")
        actions = object_value(result.get("actions"))
        require(result.get("operation") is None and all(
            object_value(actions.get(name)).get("state") == "not_requested"
            for name in ("preferences", "shortlist", "lead")
        ), "UNEXPECTED_UNREQUESTED_ACTION_OR_OPERATION")
        return {
            "status": "FIRST_TURN_DIAGNOSTIC_CAPTURED",
            "request_id": identifier(self.last_meta.get("request_id")),
            "session_id": sid, "client_message_id": message_id,
            "turn_state": result["state"], "provider_state": result["provider_state"],
            "request_count": self.count, "message_post_count": self.message_posts,
            "full_pdf_acceptance": False,
            "note": "Join the request ID to the host's allowlisted provider failure code.",
        }

    async def capture(self) -> dict[str, Any]:
        self.record({"event": "run_context", "run_id": self.run_id,
                     "backend_build_sha256_operator_declared": self.args.build_sha256,
                     "expected_snapshot_id": self.args.snapshot_id,
                     "provider_mode_operator_declared": self.args.provider_mode,
                     "provider_mode_independently_attested_by_api": False,
                     "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "source_workbook_sha256": hashlib.sha256(
                         (ROOT / "sources/Copy_of_sample_cars_dataset.xlsx").read_bytes()).hexdigest()})
        if self.first_turn_only:
            self.record({"event": "first_turn_diagnostic_limits", "maximum_message_posts": 1,
                         "maximum_http_requests": self.max_requests,
                         "work_seconds": self.run_seconds, "full_pdf_acceptance": False})
        config = await self.request("GET", "/api/v1/config")
        require(config.get("mode") == "local_simulated"
                and config.get("notice_version") == "DEMO-POLICY-1", "LOCAL_DEMO_POLICY_REQUIRED")
        health = await self.request("GET", "/api/v1/health")
        for capability in ("store", "inventory"):
            require(object_value(health.get(capability)).get("state") == "ready",
                    f"PRECONDITION_{capability.upper()}_NOT_READY")
        assistant = object_value(health.get("assistant"))
        configured_unobserved = (
            assistant.get("state") == "degraded"
            and assistant.get("reason")
            == "Assistant access is configured but not yet verified."
        )
        require(assistant.get("state") == "ready" or configured_unobserved,
                "PRECONDITION_ASSISTANT_NOT_READY_OR_CONFIGURED_UNOBSERVED")
        self.record({"event": "assistant_admission",
                     "state": "configured_unobserved" if configured_unobserved else "ready",
                     "actual_provider_turn_still_required": True})
        require(health.get("active_snapshot_id") == self.args.snapshot_id,
                "SUPPLIED_INVENTORY_SNAPSHOT_NOT_ACTIVE")
        identity = await self.request("GET", "/api/v1/identity")
        require(identity.get("state") == "anonymous", "FRESH_ANONYMOUS_CLIENT_REQUIRED")
        identity = await self.request("POST", "/api/v1/identity/bootstrap", {
            "notice_version": "DEMO-POLICY-1", "notice_acknowledged": True,
        }, expected_status=201)
        require(identity.get("state") == "recognized", "FRESH_LOCAL_ACCESS_NOT_CREATED")
        self.context, self.csrf = identifier(identity.get("context_id")), identity.get("csrf_token")
        require(isinstance(self.csrf, str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", self.csrf),
                "CSRF_CREDENTIAL_REQUIRED")
        require(self.last_meta.get("identity_context_id") == self.context,
                "BOOTSTRAP_OWNER_ASSOCIATION_MISMATCH")
        self.generation = identifier(self.last_meta.get("store_generation"))
        first = await self.session()
        sid_a = first["session_id"]
        initial_preferences = object_value(first.get("recalled_preferences"))
        require(initial_preferences.get("entries") == []
                and initial_preferences.get("revision") == 0
                and initial_preferences.get("collection_mode") == "explicit_save",
                "FRESH_OWNER_ALREADY_HAS_PREFERENCES")
        if self.first_turn_only:
            return await self.diagnostic_first_turn(first)
        found, first = await self.turn(first, SEARCH_TEXT)
        require(found.get("provider_state") == "available", "ACTUAL_PROVIDER_TURN_REQUIRED")
        search = object_value(found.get("search"))
        items = search.get("items", [])
        require(search.get("state") == "matches" and isinstance(items, list) and items,
                "NO_SUPPLIED_CARS_RETURNED")
        refs = [object_value(item).get("ref") for item in items]
        require(object_value(search.get("presentation")).get("ordered_refs") == refs
                and all(object_value(ref).get("snapshot_id") == self.args.snapshot_id for ref in refs),
                "RESULT_ORDER_OR_SNAPSHOT_MISMATCH")
        selected = refs[0]
        # The session owns a distinct ID from the public search proof.
        retained_presentation_id = identifier(first.get("active_presentation_id"))
        public_presentation_id = identifier(search["presentation"].get("presentation_id"))
        require(retained_presentation_id != public_presentation_id,
                "OWNED_PRESENTATION_ID_NOT_DISTINCT")
        for question, attribute in (
            ("What is the mileage on the first car you just showed me?", "mileage_km"),
            ("Is there a warranty on it?", "warranty"),
        ):
            reply, first = await self.turn(first, question)
            require(first.get("active_presentation_id") == retained_presentation_id,
                    "ORIGINAL_PRESENTATION_NOT_RETAINED")
            evidence = reply.get("evidence", [])
            require(isinstance(evidence, list) and evidence
                    and all(object_value(item).get("ref") == selected for item in evidence)
                    and first.get("selected_ref") == selected and any(
                item.get("ref") == selected and attribute in item.get("attributes", [])
                for item in evidence
            ), "FOLLOWUP_DID_NOT_RETAIN_EXACT_CAR_AND_ATTRIBUTE")
        self.record({"event": "inventory_conversation_captured", "session_id": sid_a,
                     "selected_ref": selected, "grounding_review": "REQUIRED"})
        require(first.get("recalled_preferences") == initial_preferences,
                "PREFERENCES_CHANGED_BEFORE_EXPLICIT_SAVE")
        saved, first = await self.turn(first, SAVE_TEXT, saving_preferences=True)
        action = object_value(object_value(saved.get("actions")).get("preferences"))
        require(action.get("state") == "succeeded", "PRECONDITION_CONVERSATIONAL_SAVE_UNAVAILABLE")
        saved_record = object_value(action.get("result"))
        entry = self.saved_entry(saved_record, sid_a)
        require(saved_record["revision"] == initial_preferences["revision"] + 1,
                "SAVE_PREFERENCE_REVISION_MISMATCH")
        require(entry["source_action_id"] == action.get("client_action_id"),
                "SAVE_ACTION_PROVENANCE_MISMATCH")
        durable = await self.request("GET", "/api/v1/preferences", private=True)
        require(durable == saved_record, "DURABLE_READ_DIFFERS_FROM_SAVE")
        second = await self.session()
        sid_b = second["session_id"]
        require(sid_b != sid_a, "DISTINCT_NEW_SESSION_REQUIRED")
        require(second.get("recalled_preferences") == saved_record,
                "NEW_SESSION_DID_NOT_RECALL_ORIGINAL_VALUES")
        recalled, second = await self.turn(second, RECALL_TEXT)
        require(all(normalized(value) in normalized(recalled["text"]) for value in REQUIREMENTS),
                "ACTUAL_CONVERSATIONAL_RECALL_VALUES_MISSING")
        require(second.get("recalled_preferences") == saved_record,
                "RECALL_MUTATED_OR_REPLACED_PREFERENCES")
        saving_message_id: str | None = None
        for sid in (sid_a, sid_b):
            page = await self.request("GET", f"/api/v1/sessions/{sid}/messages", private=True)
            turns = page.get("items", [])
            require(page.get("session_id") == sid and page.get("next_cursor") is None
                    and page.get("observed_revision") == (first if sid == sid_a else second)["revision"]
                    and [turn.get("client_message_id") for turn in turns] == self.turns[sid],
                    "CONTIGUOUS_TRANSCRIPT_NOT_OBSERVED")
            require(all(turn.get("state") == "completed" and turn.get("session_id") == sid
                        and turn.get("user_text") == self.prompts[turn["client_message_id"]]
                        and turn.get("accepted_revision") == self.results[turn["client_message_id"]]["turn_revision"]
                        and turn.get("assistant_result") == self.results[turn["client_message_id"]]
                        for turn in turns), "TRANSCRIPT_DIFFERS_FROM_OBSERVED_RESPONSES")
            for turn in turns:
                identifier(turn.get("message_id"))
                if turn["client_message_id"] == saved["client_message_id"]:
                    saving_message_id = turn["message_id"]
        require(saving_message_id, "SAVING_MESSAGE_NOT_IN_TRANSCRIPT")
        require(entry.get("source_message_id") in {None, saving_message_id},
                "SAVED_SOURCE_MESSAGE_PROVENANCE_MISMATCH")
        return {"status": "CAPTURED_REQUIRES_INDEPENDENT_REVIEW", "session_a": sid_a,
                "session_b": sid_b, "selected_ref": selected,
                "memory_source_action_id": entry["source_action_id"],
                "saving_client_message_id": saved["client_message_id"],
                "saving_server_message_id": saving_message_id,
                "memory_message_provenance": "verified" if entry.get("source_message_id") else "unavailable",
                "request_count": self.count, "provider_mode_verified": False,
                "note": "Review sanitized prose, grounding and actual backend/provider configuration."}

    async def run(self) -> int:
        outcome: dict[str, Any]
        try:
            outcome = await self.capture()
        except Unmet as error:
            outcome = {"status": "UNMET_PRECONDITION_OR_INCOMPLETE", "condition": str(error),
                       "last_request": self.last_request, "automatic_retry": False}
        except Exception:
            outcome = {"status": "INCOMPLETE", "condition": "UNEXPECTED_ERROR_DETAILS_WITHHELD",
                       "last_request": self.last_request, "automatic_retry": False}
        finally:
            try:
                async with asyncio.timeout(5):
                    await self.client.aclose()
            except Exception:
                outcome = {"status": "INCOMPLETE", "condition": "CLIENT_CLOSE_INCOMPLETE",
                           "last_request": self.last_request, "automatic_retry": False}
        self.record({"event": "outcome", **outcome})
        (self.directory / "result.json").write_text(json.dumps(outcome, indent=2), encoding="utf-8")
        captured = outcome["status"] == "CAPTURED_REQUIRES_INDEPENDENT_REVIEW"
        diagnostic_captured = (
            self.first_turn_only and outcome["status"] == "FIRST_TURN_DIAGNOSTIC_CAPTURED"
        )
        if captured and not self.first_turn_only:
            self.marker.unlink()  # Only this run's exclusive marker, after all saved evidence.
        print(json.dumps({"status": outcome["status"], "condition": outcome.get("condition"),
                          "evidence_directory": str(self.directory)}))
        return 0 if captured or diagnostic_captured else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--acknowledge-local-notice", action="store_true")
    parser.add_argument("--first-turn-only", action="store_true",
                        help="One synthetic diagnostic turn; never full PDF acceptance")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--origin", default="http://127.0.0.1:5173")
    parser.add_argument("--build-sha256", required=True, help="Accepted backend source-manifest digest")
    parser.add_argument("--snapshot-id", required=True, help="Accepted supplied-workbook snapshot")
    parser.add_argument("--provider-mode", required=True, choices=["live-free-gemini"],
                        help="Operator declaration; must be independently verified on the server")
    args = parser.parse_args()
    try:
        require(args.execute and args.acknowledge_local_notice, "EXPLICIT_DEMO_EXECUTION_REQUIRED")
        args.base_url, args.origin = local_origin(args.base_url), local_origin(args.origin)
        require(all(re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in (args.build_sha256, args.snapshot_id)), "SOURCE_DIGESTS_REQUIRED")
        return asyncio.run(Demo(args).run())
    except (Unmet, ValueError, OSError) as error:
        print(json.dumps({"status": "STOPPED_WITHOUT_COMPLETION", "condition": str(error) if isinstance(error, Unmet)
                          else "LOCAL_CONFIGURATION_OR_EVIDENCE_PATH_UNAVAILABLE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
