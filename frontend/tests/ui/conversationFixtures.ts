import semantic from "../../../contracts/fixtures/semantic_cases.json";
import type { RequestOf, Schema } from "../../src/shared/api/contracts";
import { identity, meta, schemaFixture } from "./apiFixtures";

export const conversationId = "00000000-0000-4000-8000-000000000001";
export const otherConversationId = "90000000-0000-4000-8000-000000000099";
export const messageId = "00000000-0000-4000-8000-000000000031";
export const conversationEnvelope = <T>(data: T) => ({
  meta: meta(identity().context_id),
  data,
});
export function conversationSession(revision = 0): Schema<"SessionState"> {
  return schemaFixture("SessionState", {
    ...semantic.baselines.SessionState,
    revision,
    pending_intent: { kind: "none" },
  });
}
export function conversationResult(
  body?: RequestOf<"submit_message">["body"],
  overrides: Partial<Schema<"MessageResult">> = {},
): Schema<"MessageResult"> {
  const revision = body ? body.expected_revision + 1 : 1;
  return schemaFixture("MessageResult", {
    ...semantic.baselines.MessageResult,
    client_message_id: body?.client_message_id ?? messageId,
    turn_revision: revision,
    current_revision: revision,
    state: "answered",
    text: "The source does not state a verified service history.",
    pending_intent: { kind: "none" },
    evidence: [],
    search: null,
    comparison: null,
    handoff_summary: null,
    operation: null,
    actions: {
      preferences: { state: "not_requested" },
      shortlist: { state: "not_requested" },
      lead: { state: "not_requested" },
    },
    ...overrides,
  });
}
export function transcriptTurn(
  result: Schema<"MessageResult">,
  state: Schema<"TranscriptTurn">["state"] = "completed",
  text = "Ask about this car",
): Schema<"TranscriptTurn"> {
  return schemaFixture("TranscriptTurn", {
    message_id: result.client_message_id,
    client_message_id: result.client_message_id,
    session_id: result.session_id,
    accepted_revision: result.turn_revision,
    accepted_at: "2026-09-24T04:00:00Z",
    user_text: text,
    state,
    historical: true,
    assistant_result: state === "completed" ? result : null,
  });
}
export function transcriptPage(
  items: Schema<"TranscriptTurn">[] = [],
  revision = 0,
  cursor: string | null = null,
  sessionId = conversationId,
): Schema<"TranscriptPage"> {
  return schemaFixture("TranscriptPage", {
    session_id: sessionId,
    observed_revision: revision,
    items,
    next_cursor: cursor,
  });
}
