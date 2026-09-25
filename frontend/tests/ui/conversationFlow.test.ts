import { afterEach, describe, expect, test, vi } from "vitest";
import { ConversationFlow } from "../../src/features/conversation/ConversationFlow";
import { ApiClient } from "../../src/shared/api/ApiClient";
import { ClientFailure } from "../../src/shared/api/ClientFailure";
import { OwnerSession } from "../../src/shared/api/OwnerSession";
import type {
  RequestOf,
  ResponseOf,
  Schema,
} from "../../src/shared/api/contracts";
import { deferred } from "../harness/fixtures";
import { identity, searchResult, seed } from "./apiFixtures";
import {
  conversationEnvelope as envelope,
  conversationId as id,
  conversationResult,
  conversationSession,
  otherConversationId,
  transcriptPage,
  transcriptTurn,
} from "./conversationFixtures";

// Generic API spies erase the operation/request correlation; each cast below restores the named request for its scripted call.
const disposals: (() => void)[] = [];
afterEach(() => disposals.splice(0).forEach((dispose) => dispose()));
const flush = async () => {
  for (let index = 0; index < 12; index += 1) await Promise.resolve();
};
const lost = () => new ClientFailure("network", "reconcile-original");
function setup(session = conversationSession()) {
  const owner = new OwnerSession();
  owner.accept(0, identity());
  const api = new ApiClient(owner),
    changed = vi.fn(),
    flow = new ConversationFlow(owner, api, changed);
  const state = {
    session,
    page: transcriptPage([], session.revision, null, session.session_id),
  };
  const read = vi
    .spyOn(api, "read")
    .mockImplementation(async (operation) =>
      envelope(
        structuredClone(
          operation === "get_session" ? state.session : state.page,
        ),
      ),
    );
  const write = vi
    .spyOn(api, "mutate")
    .mockImplementation(async (operation, input) => {
      if (operation !== "submit_message")
        throw Error(`UNSCRIPTED_MUTATION:${operation}`);
      const body = (input as unknown as RequestOf<"submit_message">).body;
      state.session = {
        ...state.session,
        revision: body.expected_revision + 1,
      };
      return envelope(
        conversationResult(body, { session_id: state.session.session_id }),
      );
    });
  disposals.push(() => {
    flow.dispose();
    owner.dispose();
  });
  return { owner, api, changed, flow, state, read, write };
}
async function prime(
  subject: ReturnType<typeof setup>,
  text = "Ask about this car",
) {
  await subject.flow.activate(subject.state.session.session_id);
  subject.flow.setText(subject.state.session.session_id, text);
}
const historical = (revision: number) =>
  transcriptTurn(
    conversationResult(undefined, {
      client_message_id: `90000000-0000-4000-8000-${String(revision).padStart(12, "0")}`,
      turn_revision: revision,
      current_revision: revision,
    }),
    "completed",
    `Earlier message ${revision}`,
  );

describe("U3 synthetic controller regressions; no live provider or persistence proof", () => {
  test("opening is read-only; unsent text survives same-session activation, not owner reset", async () => {
    const subject = setup();
    await prime(subject, "Same-owner draft");
    await subject.flow.activate(id);
    expect(subject.flow.getSnapshot().active?.text).toBe("Same-owner draft");
    expect(subject.write).not.toHaveBeenCalled();
    subject.owner.accept(subject.owner.invalidate(), identity(1));
    expect(subject.flow.getSnapshot().active).toBeNull();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
  test("empty and oversized messages never dispatch", async () => {
    const subject = setup();
    await prime(subject, "  ");
    await subject.flow.send(id, null, null);
    expect(subject.flow.getSnapshot().active?.notice).toContain(
      "Enter a message",
    );
    subject.flow.setText(id, "x".repeat(4001));
    await subject.flow.send(id, null, null);
    expect(subject.flow.getSnapshot().active?.notice).toContain("4,000");
    expect(subject.write).not.toHaveBeenCalled();
  });
  test("registration uses the new owned presentation and original ordered proof before the exact message", async () => {
    const subject = setup();
    await prime(subject);
    const proof = searchResult().data.presentation,
      owned = otherConversationId;
    subject.write.mockImplementation(async (operation, input) => {
      if (operation === "register_presentation") {
        subject.state.session = {
          ...subject.state.session,
          revision: 1,
          active_presentation_id: owned,
        };
        return envelope(subject.state.session);
      }
      const body = (input as unknown as RequestOf<"submit_message">).body;
      subject.state.session = { ...subject.state.session, revision: 2 };
      return envelope(conversationResult(body));
    });
    await subject.flow.send(
      id,
      { label: "Original order", selectedRef: null, presentation: proof },
      null,
    );
    expect(subject.write.mock.calls.map((call) => call[0])).toEqual([
      "register_presentation",
      "submit_message",
    ]);
    expect(subject.write.mock.calls[0]?.[1]).toMatchObject({
      body: { presentation: proof, expected_revision: 0 },
    });
    expect(subject.write.mock.calls[1]?.[1]).toMatchObject({
      path: { session_id: id },
      body: {
        expected_revision: 1,
        presentation_id: owned,
        explicit_confirmation: null,
      },
    });
  });
  test("preflight changing the displayed selected car stops before mutation", async () => {
    const ref = searchResult().data.presentation.ordered_refs[0]!,
      subject = setup({ ...conversationSession(), selected_ref: ref });
    await prime(subject);
    subject.state.session = {
      ...subject.state.session,
      revision: 1,
      selected_ref: { ...ref, source_id: "different" },
    };
    await subject.flow.send(id, null, null);
    expect(subject.write).not.toHaveBeenCalled();
    expect(subject.flow.getSnapshot().active?.text).toBe("Ask about this car");
    expect(subject.flow.getSnapshot().active?.notice).toContain(
      "context changed",
    );
  });
  test("a proof-only change cannot silently clear an unrelated selected car", async () => {
    const proof = searchResult().data.presentation,
      subject = setup({
        ...conversationSession(),
        selected_ref: { ...proof.ordered_refs[0]!, source_id: "outside" },
      });
    await prime(subject);
    subject.flow.stageContext(id, {
      label: "New result order",
      selectedRef: null,
      presentation: proof,
    });
    await subject.flow.send(id, null, null);
    expect(subject.write).not.toHaveBeenCalled();
    expect(subject.flow.getSnapshot().active?.notice).toContain(
      "no selection has been cleared",
    );
  });
  test("clarification binds the exact original tuple and carries selection atomically without clearing it first", async () => {
    const pending: Schema<"ClarificationIntent"> = {
      kind: "clarification",
      intent_id: otherConversationId,
      created_revision: 0,
      purpose: "listing_reference",
      targets: ["selected_ref"],
      question: "Which exact listing?",
    };
    const subject = setup({
        ...conversationSession(),
        pending_intent: pending,
      }),
      ref = searchResult().data.presentation.ordered_refs[0]!;
    await prime(subject);
    subject.flow.stageContext(id, {
      label: "This exact car",
      selectedRef: ref,
      presentation: null,
    });
    const reply = { intent_id: pending.intent_id, created_revision: 0 };
    await subject.flow.send(id, null, reply);
    expect(subject.write).toHaveBeenCalledTimes(1);
    expect(subject.write.mock.calls[0]).toMatchObject([
      "submit_message",
      {
        body: {
          clarification_reply: reply,
          selected_ref: ref,
          presentation_id: null,
        },
      },
    ]);
  });
  test("unknown message checks the entire oldest-first chain and retries its immutable request", async () => {
    const subject = setup(conversationSession(2));
    await prime(subject);
    subject.write.mockRejectedValueOnce(lost());
    await subject.flow.send(id, null, null);
    const original = structuredClone(subject.write.mock.calls[0]);
    subject.flow.setText(id, "Later unsent words");
    subject.read.mockImplementation(async (operation, input) => {
      if (operation === "get_session") return envelope(subject.state.session);
      const later = !!(input as unknown as RequestOf<"get_session_messages">)
        .query?.cursor;
      return envelope(
        transcriptPage(
          [historical(later ? 2 : 1)],
          2,
          later ? null : "next-signed-page",
        ),
      );
    });
    await subject.flow.checkOriginal(id);
    expect(subject.flow.getSnapshot().active?.canRetry).toBe(true);
    expect(
      subject.read.mock.calls.some(
        (call) =>
          call[0] === "get_session_messages" &&
          (call[1] as unknown as RequestOf<"get_session_messages">).query
            ?.cursor === "next-signed-page",
      ),
    ).toBe(true);
    await subject.flow.retryOriginal(id);
    expect(subject.write.mock.calls[1]).toEqual(original);
    expect(subject.flow.getSnapshot().active?.text).toBe("Later unsent words");
  });
  test.each(["pending", "interrupted"] as const)(
    "an accepted %s turn never offers restart by replay",
    async (state) => {
      const subject = setup();
      await prime(subject);
      subject.write.mockRejectedValueOnce(lost());
      await subject.flow.send(id, null, null);
      const body = (
          subject.write.mock
            .calls[0]![1] as unknown as RequestOf<"submit_message">
        ).body,
        result = conversationResult(body);
      subject.state.session.revision = 1;
      subject.state.page = transcriptPage([transcriptTurn(result, state)], 1);
      await subject.flow.checkOriginal(id);
      await subject.flow.retryOriginal(id);
      expect(subject.flow.getSnapshot().active?.canRetry).toBe(false);
      expect(subject.write).toHaveBeenCalledTimes(1);
    },
  );
  test("a completed transcript settles the original before a late POST transport failure", async () => {
    const subject = setup();
    await prime(subject);
    const post = deferred<ResponseOf<"submit_message">>();
    subject.write.mockReturnValueOnce(post.promise);
    const sending = subject.flow.send(id, null, null);
    await flush();
    const body = (
        subject.write.mock
          .calls[0]![1] as unknown as RequestOf<"submit_message">
      ).body,
      result = conversationResult(body);
    subject.state.session.revision = 1;
    subject.state.page = transcriptPage([transcriptTurn(result)], 1);
    await subject.flow.refresh(id);
    expect(subject.flow.getSnapshot().active).toMatchObject({
      hasOriginal: false,
      commandBusy: true,
    });
    post.reject(lost());
    await sending;
    expect(subject.flow.getSnapshot().active).toMatchObject({
      hasOriginal: false,
      phase: "idle",
    });
    expect(subject.changed).toHaveBeenCalledTimes(1);
  });
  test("a POST completion survives a delayed pending transcript and a later unavailable session", async () => {
    const subject = setup();
    await prime(subject);
    await subject.flow.send(id, null, null);
    const result = subject.flow.getSnapshot().active!.localTurns[0]!.result!;
    subject.state.page = transcriptPage([transcriptTurn(result, "pending")], 1);
    await subject.flow.refresh(id);
    expect(subject.flow.getSnapshot().active?.localTurns[0]?.result).toEqual(
      result,
    );
    subject.read.mockRejectedValueOnce(
      new ClientFailure("api", "read", { status: 404 }),
    );
    await subject.flow.refresh(id);
    expect(subject.flow.getSnapshot().active?.localTurns[0]?.result).toEqual(
      result,
    );
  });
  test("pending transcript arriving before POST completion cannot discard its later validated answer", async () => {
    const subject = setup();
    await prime(subject);
    const gate = deferred<ResponseOf<"submit_message">>();
    subject.write.mockReturnValueOnce(gate.promise);
    const sending = subject.flow.send(id, null, null);
    await flush();
    const body = (
        subject.write.mock
          .calls[0]![1] as unknown as RequestOf<"submit_message">
      ).body,
      result = conversationResult(body);
    subject.state.session.revision = 1;
    subject.state.page = transcriptPage([transcriptTurn(result, "pending")], 1);
    await subject.flow.refresh(id);
    expect(subject.flow.getSnapshot().active?.localTurns).toEqual([]);
    gate.resolve(envelope(result));
    await sending;
    expect(subject.flow.getSnapshot().active?.localTurns[0]?.result).toEqual(
      result,
    );
    expect(subject.flow.getSnapshot().active?.hasOriginal).toBe(false);
  });
  test("shape-valid but cross-associated transcript result is never displayed", async () => {
    const subject = setup();
    await prime(subject);
    const turn = transcriptTurn(conversationResult());
    turn.assistant_result = {
      ...turn.assistant_result!,
      session_id: otherConversationId,
    };
    subject.state.page = transcriptPage([turn], 1);
    subject.state.session.revision = 1;
    await subject.flow.refresh(id);
    expect(subject.flow.getSnapshot().active?.turns).toEqual([]);
    expect(subject.flow.getSnapshot().active?.phase).toBe("error");
  });
  test("an older failed refresh cannot replace a newer successful transcript", async () => {
    const subject = setup();
    await prime(subject);
    const old = deferred<ResponseOf<"get_session_messages">>();
    subject.read
      .mockImplementationOnce(async () => envelope(subject.state.session))
      .mockReturnValueOnce(old.promise);
    const first = subject.flow.refresh(id);
    await flush();
    await subject.flow.refresh(id);
    old.reject(lost());
    await first;
    expect(subject.flow.getSnapshot().active?.phase).toBe("idle");
  });
  test("a failed trailing POST session read cannot hide a later successful current read", async () => {
    const subject = setup();
    await prime(subject);
    const trailing = deferred<ResponseOf<"get_session">>();
    subject.read
      .mockImplementationOnce(async () => envelope(subject.state.session))
      .mockReturnValueOnce(trailing.promise);
    const sending = subject.flow.send(id, null, null);
    await flush();
    await subject.flow.refresh(id);
    trailing.reject(new ClientFailure("api", "read", { status: 404 }));
    await sending;
    expect(subject.flow.getSnapshot().active?.session?.session_id).toBe(id);
    expect(subject.flow.getSnapshot().active?.phase).toBe("idle");
  });
  test("late duplicate page cannot rewind the cursor after a later page", async () => {
    const subject = setup(conversationSession(4));
    subject.state.page = transcriptPage([historical(1)], 4, "cursor-one");
    await prime(subject);
    const old = deferred<ResponseOf<"get_session_messages">>();
    subject.read
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(
        envelope(transcriptPage([historical(2)], 4, "cursor-two")),
      );
    const first = subject.flow.loadMore(id);
    await subject.flow.loadMore(id);
    subject.read.mockResolvedValueOnce(
      envelope(transcriptPage([historical(3)], 4, "cursor-three")),
    );
    await subject.flow.loadMore(id);
    old.resolve(envelope(transcriptPage([historical(2)], 4, "cursor-two")));
    await first;
    expect(subject.flow.getSnapshot().active?.nextCursor).toBe("cursor-three");
  });
  test("changed generation blocks exact retry without replacing the original message", async () => {
    const subject = setup();
    await prime(subject);
    subject.write.mockRejectedValueOnce(lost());
    await subject.flow.send(id, null, null);
    const response = envelope(subject.state.session);
    response.meta.store_generation = seed.synthetic_generations[1]!;
    subject.read.mockResolvedValueOnce(response);
    await subject.flow.checkOriginal(id);
    await subject.flow.retryOriginal(id);
    expect(subject.flow.getSnapshot().active).toMatchObject({
      phase: "blocked",
      hasOriginal: true,
      canRetry: false,
    });
    expect(subject.write).toHaveBeenCalledTimes(1);
  });
  test("a reply after owner replacement cannot restore its text, result or recovery control", async () => {
    const subject = setup();
    await prime(subject);
    const gate = deferred<ResponseOf<"submit_message">>();
    subject.write.mockReturnValueOnce(gate.promise);
    const sending = subject.flow.send(id, null, null);
    await flush();
    const body = (
      subject.write.mock.calls[0]![1] as unknown as RequestOf<"submit_message">
    ).body;
    subject.owner.accept(subject.owner.invalidate(), identity(1));
    gate.resolve(envelope(conversationResult(body)));
    await sending;
    expect(subject.flow.getSnapshot()).toEqual({
      active: null,
      recoverableSessions: [],
    });
    expect(subject.changed).not.toHaveBeenCalled();
  });
  test("context-command recovery replays only the original command and never auto-sends the retained text", async () => {
    const subject = setup();
    await prime(subject);
    const proof = searchResult().data.presentation;
    subject.write.mockRejectedValueOnce(lost());
    await subject.flow.send(
      id,
      { label: "Original order", selectedRef: null, presentation: proof },
      null,
    );
    const original = structuredClone(subject.write.mock.calls[0]);
    await subject.flow.checkOriginal(id);
    subject.write.mockResolvedValueOnce(
      envelope({
        ...conversationSession(3),
        active_presentation_id: otherConversationId,
      }),
    );
    await subject.flow.retryOriginal(id);
    expect(subject.write.mock.calls[1]).toEqual(original);
    expect(
      subject.write.mock.calls.every(
        (call) => call[0] === "register_presentation",
      ),
    ).toBe(true);
    expect(subject.flow.getSnapshot().active?.text).toBe("Ask about this car");
    expect(subject.flow.getSnapshot().active?.hasOriginal).toBe(false);
  });
  test("a ten-page scan stops with its signed continuation and no absence-based retry", async () => {
    const subject = setup(conversationSession(11));
    await prime(subject);
    subject.write.mockRejectedValueOnce(lost());
    await subject.flow.send(id, null, null);
    let page = 0;
    subject.read.mockImplementation(async (operation) =>
      operation === "get_session"
        ? envelope(subject.state.session)
        : envelope(
            transcriptPage([historical(++page)], 11, `signed-page-${page}`),
          ),
    );
    await subject.flow.checkOriginal(id);
    expect(page).toBe(10);
    expect(subject.flow.getSnapshot().active?.canRetry).toBe(false);
    expect(subject.flow.getSnapshot().active?.notice).toContain(
      "More historical pages remain",
    );
  });
  test("late old-session reply stays with that session and owner reset hides all private content", async () => {
    const subject = setup();
    await prime(subject);
    const gate = deferred<ResponseOf<"submit_message">>();
    subject.write.mockReturnValueOnce(gate.promise);
    const sending = subject.flow.send(id, null, null);
    await flush();
    const body = (
      subject.write.mock.calls[0]![1] as unknown as RequestOf<"submit_message">
    ).body;
    subject.state.session = {
      ...conversationSession(),
      session_id: otherConversationId,
    };
    subject.state.page = transcriptPage([], 0, null, otherConversationId);
    await subject.flow.activate(otherConversationId);
    gate.resolve(envelope(conversationResult(body)));
    await sending;
    expect(subject.flow.getSnapshot().active?.sessionId).toBe(
      otherConversationId,
    );
    expect(subject.flow.getSnapshot().active?.localTurns).toEqual([]);
    subject.owner.accept(subject.owner.invalidate(), identity(1));
    expect(subject.flow.getSnapshot().active).toBeNull();
    expect(subject.flow.getSnapshot().recoverableSessions).toEqual([]);
  });
});
