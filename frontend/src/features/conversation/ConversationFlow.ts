import { ApiClient } from "../../shared/api/ApiClient";
import { ClientFailure } from "../../shared/api/ClientFailure";
import {
  OwnerSession,
  type OwnerSnapshot,
} from "../../shared/api/OwnerSession";
import type { RequestOf, ResponseOf, Schema } from "../../shared/api/contracts";
import { isLocator, refKey } from "../../app/routes";
import { checkMessageResultAssociation } from "../../shared/api/responseAssociation";

export type ConversationContext = {
  label: string;
  selectedRef: Schema<"InventoryRef"> | null;
  presentation: Schema<"PresentationProof"> | null;
};
type Command =
  | { kind: "message"; request: RequestOf<"submit_message"> }
  | { kind: "presentation"; request: RequestOf<"register_presentation"> }
  | { kind: "selection"; request: RequestOf<"select_session_listing"> };
type Pending = {
  command: Command;
  generation: string;
  uncertain: boolean;
  canRetry: boolean;
  scan?: { cursor: string; observed: number };
};
export type LocalTurn = {
  clientId: string;
  revision: number;
  text: string;
  result: Schema<"MessageResult"> | null;
};
export type ConversationSessionView = {
  sessionId: string;
  session: Schema<"SessionState"> | null;
  generation: string | null;
  text: string;
  stagedContext: ConversationContext | null;
  turns: Schema<"TranscriptTurn">[];
  localTurns: LocalTurn[];
  nextCursor: string | null;
  observedRevision: number | null;
  phase: "idle" | "reading" | "sending" | "unknown" | "blocked" | "error";
  notice: string | null;
  hasOriginal: boolean;
  canRetry: boolean;
  commandBusy: boolean;
  readSequence: number;
  turnChange: number;
};
export type ConversationView = {
  active: ConversationSessionView | null;
  recoverableSessions: string[];
};
const initial = (id: string): ConversationSessionView => ({
  sessionId: id,
  session: null,
  generation: null,
  text: "",
  stagedContext: null,
  turns: [],
  localTurns: [],
  nextCursor: null,
  observedRevision: null,
  phase: "idle",
  notice: null,
  hasOriginal: false,
  canRetry: false,
  commandBusy: false,
  readSequence: 0,
  turnChange: 0,
});

/** Conversation state is owner-scoped memory; every write is an explicit original intent. */
export class ConversationFlow {
  #sessions = new Map<string, ConversationSessionView>();
  #pending = new Map<string, Pending>();
  #locks = new Set<string>();
  #activeId: string | null = null;
  #view: ConversationView = { active: null, recoverableSessions: [] };
  #listeners = new Set<() => void>();
  #sequence = 0;
  #historyChains = new Map<string, number>();
  #pageReads = new Map<string, number>();
  #sessionReads = new Map<string, number>();
  #unsubscribe: () => void;
  constructor(
    private owner: OwnerSession,
    private api: ApiClient,
    private changed: (sessionId: string) => void,
  ) {
    this.#unsubscribe = owner.subscribe(() => {
      this.#sessions.clear();
      this.#historyChains.clear();
      this.#pageReads.clear();
      this.#sessionReads.clear();
      this.#activeId = null;
      this.#emit();
    });
  }
  getSnapshot = () => this.#view;
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  };
  #key(owner: OwnerSnapshot, id: string) {
    return `${owner.contextId}:${id}`;
  }
  #emit() {
    const owner = this.owner.capture(),
      prefix = `${owner.contextId}:`,
      active = this.#activeId ? this.#sessions.get(this.#activeId) : null;
    const pending = active
      ? this.#pending.get(this.#key(owner, active.sessionId))
      : undefined;
    this.#view = {
      active: active
        ? {
            ...active,
            hasOriginal: !!pending,
            canRetry: pending?.canRetry ?? false,
            commandBusy: this.#locks.has(this.#key(owner, active.sessionId)),
          }
        : null,
      recoverableSessions: owner.contextId
        ? [...this.#pending.keys()]
            .filter((key) => key.startsWith(prefix))
            .map((key) => key.slice(prefix.length))
        : [],
    };
    for (const listener of this.#listeners) listener();
  }
  #entry(id: string) {
    let entry = this.#sessions.get(id);
    if (!entry) {
      entry = initial(id);
      this.#sessions.set(id, entry);
    }
    return entry;
  }
  #publish(
    owner: OwnerSnapshot,
    id: string,
    patch: Partial<ConversationSessionView>,
  ) {
    if (this.owner.isCurrent(owner)) {
      Object.assign(this.#entry(id), patch);
      this.#emit();
    }
  }
  #generation(
    owner: OwnerSnapshot,
    id: string,
    generation: string | null | undefined,
  ) {
    this.owner.assertCurrent(owner);
    if (!isLocator(generation))
      throw new ClientFailure("invalid-response", "read");
    const entry = this.#entry(id);
    if (entry.generation && entry.generation !== generation) {
      this.#publish(owner, id, {
        phase: "blocked",
        notice:
          "The local store changed. Keep original message identities for operator reconciliation.",
      });
      throw new ClientFailure("superseded", "read");
    }
    entry.generation = generation;
    return generation;
  }
  #acceptSession(
    owner: OwnerSnapshot,
    id: string,
    response: ResponseOf<"get_session">,
    sequence: number,
  ) {
    this.#generation(owner, id, response.meta.store_generation);
    const entry = this.#entry(id),
      session = response.data;
    if (
      session.session_id !== id ||
      session.revision < (entry.session?.revision ?? 0) ||
      (session.revision === entry.session?.revision &&
        sequence < entry.readSequence)
    )
      throw new ClientFailure("superseded", "read");
    entry.session = session;
    entry.readSequence = sequence;
    this.#emit();
    return session;
  }
  async #readSession(owner: OwnerSnapshot, id: string) {
    const sequence = ++this.#sequence;
    this.#sessionReads.set(id, sequence);
    try {
      const response = await this.api.read("get_session", {
        path: { session_id: id },
      });
      this.#acceptSession(owner, id, response, sequence);
      return response;
    } catch (error) {
      if (
        this.#sessionReads.get(id) !== sequence ||
        sequence < this.#entry(id).readSequence
      )
        throw new ClientFailure("superseded", "read");
      throw error;
    }
  }
  #merge(owner: OwnerSnapshot, id: string, page: Schema<"TranscriptPage">) {
    this.owner.assertCurrent(owner);
    const entry = this.#entry(id),
      turns = new Map(
        entry.turns.map((turn) => [turn.client_message_id, turn]),
      );
    if (page.session_id !== id)
      throw new ClientFailure("invalid-response", "read");
    for (const turn of page.items) {
      if (
        turn.session_id !== id ||
        turn.accepted_revision > page.observed_revision
      )
        throw new ClientFailure("invalid-response", "read");
      const result = turn.assistant_result;
      if (result) checkMessageResultAssociation(result);
      if (
        (turn.state === "completed") !== !!result ||
        (result &&
          (result.session_id !== id ||
            result.client_message_id !== turn.client_message_id ||
            result.turn_revision !== turn.accepted_revision ||
            result.current_revision < result.turn_revision))
      )
        throw new ClientFailure("invalid-response", "read");
      const original = this.#pending.get(this.#key(owner, id));
      if (
        original?.command.kind === "message" &&
        original.command.request.body.client_message_id ===
          turn.client_message_id &&
        (turn.accepted_revision !==
          original.command.request.body.expected_revision + 1 ||
          turn.user_text !== original.command.request.body.text ||
          entry.generation !== original.generation)
      )
        throw new ClientFailure("invalid-response", "read");
      const previous = turns.get(turn.client_message_id);
      if (
        previous &&
        (previous.message_id !== turn.message_id ||
          previous.accepted_revision !== turn.accepted_revision)
      )
        throw new ClientFailure("invalid-response", "read");
      if (previous?.state === "completed") continue;
      turns.set(turn.client_message_id, turn);
    }
    const ordered = [...turns.values()].sort(
      (a, b) => a.accepted_revision - b.accepted_revision,
    );
    if (
      new Set(ordered.map((turn) => turn.accepted_revision)).size !==
      ordered.length
    )
      throw new ClientFailure("invalid-response", "read");
    entry.turns = ordered;
    entry.localTurns = entry.localTurns.filter(
      (local) =>
        !turns.has(local.clientId) ||
        (!!local.result && turns.get(local.clientId)?.state !== "completed"),
    );
    entry.turnChange += 1;
    const pending = this.#pending.get(this.#key(owner, id));
    if (pending?.command.kind === "message") {
      const completed = turns.get(
        pending.command.request.body.client_message_id,
      );
      if (completed?.state === "completed" && completed.assistant_result) {
        if (entry.generation !== pending.generation)
          throw new ClientFailure("superseded", "read");
        this.#acceptResult(owner, id, pending, completed.assistant_result);
      }
    }
    this.#emit();
  }
  setText(id: string, text: string) {
    if (
      !this.owner.capture().contextId ||
      this.#activeId !== id ||
      !this.#sessions.has(id)
    )
      return;
    this.#entry(id).text = text;
    this.#emit();
  }
  stageContext(id: string, context: ConversationContext) {
    const owner = this.owner.capture(),
      key = this.#key(owner, id);
    if (
      !owner.contextId ||
      this.#activeId !== id ||
      !this.#sessions.has(id) ||
      this.#pending.has(key) ||
      this.#locks.has(key)
    )
      return;
    this.#entry(id).stagedContext = structuredClone(context);
    this.#emit();
  }
  async activate(id: string) {
    if (!isLocator(id) || !this.owner.capture().contextId) return;
    this.#activeId = id;
    this.#entry(id);
    this.#emit();
    await this.refresh(id);
  }
  async refresh(id: string) {
    const owner = this.owner.capture();
    if (!owner.contextId) return;
    const entry = this.#entry(id),
      sequence = ++this.#sequence;
    this.#historyChains.set(id, sequence);
    this.#pageReads.delete(id);
    this.#publish(owner, id, {
      phase: this.#pending.has(this.#key(owner, id)) ? "unknown" : "reading",
      notice: null,
    });
    try {
      await this.#readSession(owner, id);
      const response = await this.api.read("get_session_messages", {
        path: { session_id: id },
        query: { page_size: 50, cursor: null },
      });
      this.#generation(owner, id, response.meta.store_generation);
      if (this.#historyChains.get(id) !== sequence) return;
      if ((entry.observedRevision ?? 0) > response.data.observed_revision)
        throw new ClientFailure("superseded", "read");
      this.#merge(owner, id, response.data);
      this.#publish(owner, id, {
        nextCursor: response.data.next_cursor,
        observedRevision: response.data.observed_revision,
        phase: this.#pending.has(this.#key(owner, id)) ? "unknown" : "idle",
        notice: null,
      });
    } catch (error) {
      if (this.#historyChains.get(id) === sequence)
        this.#readFailure(owner, id, error);
    }
  }
  async loadMore(id: string) {
    const owner = this.owner.capture(),
      entry = this.#entry(id),
      cursor = entry.nextCursor,
      observed = entry.observedRevision,
      chain = this.#historyChains.get(id),
      sequence = ++this.#sequence;
    if (!cursor) return;
    this.#pageReads.set(id, sequence);
    const current = () =>
      this.#historyChains.get(id) === chain &&
      this.#pageReads.get(id) === sequence &&
      entry.nextCursor === cursor &&
      entry.observedRevision === observed;
    try {
      const response = await this.api.read("get_session_messages", {
        path: { session_id: id },
        query: { page_size: 50, cursor },
      });
      this.#generation(owner, id, response.meta.store_generation);
      if (!current()) return;
      if (
        response.data.observed_revision !== observed ||
        response.data.next_cursor === cursor
      )
        throw new ClientFailure("invalid-response", "read");
      this.#merge(owner, id, response.data);
      this.#publish(owner, id, { nextCursor: response.data.next_cursor });
    } catch (error) {
      if (current()) this.#readFailure(owner, id, error);
    }
  }
  #readFailure(owner: OwnerSnapshot, id: string, error: unknown) {
    if (!this.owner.isCurrent(owner)) return;
    if (error instanceof ClientFailure && error.kind === "superseded") return;
    const entry = this.#entry(id);
    if (entry.phase === "blocked") return;
    if (error instanceof ClientFailure && error.status === 404)
      this.#publish(owner, id, { session: null });
    this.#publish(owner, id, {
      phase: this.#pending.has(this.#key(owner, id)) ? "unknown" : "error",
      notice:
        "The current conversation could not be read. Original unresolved messages remain retained; browsing and original viewing status are still available.",
    });
  }
  async send(
    id: string,
    initialContext: ConversationContext | null,
    reply: Schema<"ClarificationReply"> | null,
  ) {
    const owner = this.owner.capture(),
      key = this.#key(owner, id),
      entry = this.#entry(id);
    if (
      !owner.contextId ||
      this.#locks.has(key) ||
      this.#pending.has(key) ||
      entry.phase === "blocked"
    )
      return;
    const text = entry.text.trim();
    if (!text || text.length > 4000) {
      this.#publish(owner, id, {
        notice: !text
          ? "Enter a message before sending."
          : "Keep the message within 4,000 characters.",
      });
      return;
    }
    if (
      entry.turns.some(
        (turn) =>
          turn.state !== "completed" &&
          !entry.localTurns.some(
            (local) =>
              local.clientId === turn.client_message_id && local.result,
          ),
      )
    ) {
      this.#publish(owner, id, {
        notice:
          "An original turn is pending or interrupted. Refresh its transcript before sending another message; a new ID cannot restart it.",
      });
      return;
    }
    const context = structuredClone(
        entry.stagedContext ??
          (!entry.session?.active_presentation_id &&
          !entry.session?.selected_ref
            ? initialContext
            : null),
      ),
      clarification = structuredClone(reply);
    const displayed = entry.session
      ? {
          selected: entry.session.selected_ref
            ? refKey(entry.session.selected_ref)
            : null,
          presentation: entry.session.active_presentation_id,
        }
      : null;
    this.#locks.add(key);
    this.#publish(owner, id, {
      phase: "sending",
      notice: "Preparing this message and its original car context…",
    });
    try {
      let session = (await this.#readSession(owner, id)).data;
      const generation = entry.generation!;
      if (
        !context &&
        displayed &&
        (displayed.selected !==
          (session.selected_ref ? refKey(session.selected_ref) : null) ||
          displayed.presentation !== session.active_presentation_id)
      )
        throw new ClientFailure("superseded", "read");
      if (session.pending_intent.kind === "operation_unresolved") {
        this.#publish(owner, id, {
          phase: "idle",
          notice:
            "Read the original viewing outcome before starting another conversational action.",
        });
        return;
      }
      if (
        clarification &&
        (session.pending_intent.kind !== "clarification" ||
          session.pending_intent.intent_id !== clarification.intent_id ||
          session.pending_intent.created_revision !==
            clarification.created_revision)
      ) {
        this.#publish(owner, id, {
          phase: "idle",
          notice:
            "The clarification changed. Read the current question before sending your retained text.",
        });
        return;
      }
      if (
        context?.presentation &&
        !context.selectedRef &&
        session.selected_ref &&
        !context.presentation.ordered_refs.some(
          (ref) => refKey(ref) === refKey(session.selected_ref!),
        )
      ) {
        this.#publish(owner, id, {
          phase: "idle",
          notice:
            "This result order does not contain the conversation's selected car. Choose an exact car from these results or start a new conversation; no selection has been cleared.",
        });
        return;
      }
      // An existing server selection is history, not a fresh user instruction.
      // Only explicit staged/page context should override language such as
      // “which of these is newest?” on this turn.
      let selected = context?.selectedRef ?? null,
        presentationId = session.active_presentation_id;
      if (context?.presentation) {
        const request: RequestOf<"register_presentation"> = {
          path: { session_id: id },
          body: {
            client_action_id: crypto.randomUUID(),
            expected_revision: session.revision,
            presentation: context.presentation,
          },
        };
        const expected = session.revision;
        session = await this.#contextCommand(
          owner,
          id,
          { kind: "presentation", request },
          generation,
        );
        if (
          session.revision !== expected + 1 ||
          !session.active_presentation_id
        )
          throw new ClientFailure("superseded", "read");
        presentationId = session.active_presentation_id;
        if (
          selected &&
          !context.presentation.ordered_refs.some(
            (ref) => refKey(ref) === refKey(selected!),
          )
        )
          selected = context.selectedRef;
      } else if (context?.selectedRef) presentationId = null;
      if (context?.selectedRef && !clarification) {
        const request: RequestOf<"select_session_listing"> = {
          path: { session_id: id },
          body: {
            client_action_id: crypto.randomUUID(),
            expected_revision: session.revision,
            selected_ref: context.selectedRef,
            presentation_id: presentationId,
          },
        };
        const expected = session.revision;
        session = await this.#contextCommand(
          owner,
          id,
          { kind: "selection", request },
          generation,
        );
        if (
          session.revision !== expected + 1 ||
          !session.selected_ref ||
          refKey(session.selected_ref) !== refKey(context.selectedRef)
        )
          throw new ClientFailure("superseded", "read");
        selected = session.selected_ref;
        presentationId = session.active_presentation_id;
      }
      const command: Command = {
        kind: "message",
        request: {
          path: { session_id: id },
          body: {
            client_message_id: crypto.randomUUID(),
            expected_revision: session.revision,
            text,
            selected_ref: selected,
            presentation_id: presentationId,
            clarification_reply: clarification,
            explicit_confirmation: null,
          },
        },
      };
      this.#pending.set(key, {
        command,
        generation,
        uncertain: false,
        canRetry: false,
      });
      entry.localTurns.push({
        clientId: command.request.body.client_message_id,
        revision: command.request.body.expected_revision + 1,
        text,
        result: null,
      });
      entry.turnChange += 1;
      await this.#submit(owner, id, this.#pending.get(key)!);
    } catch (error) {
      this.#writeFailure(owner, id, error);
    } finally {
      this.#locks.delete(key);
      this.#emit();
    }
  }
  async #contextCommand(
    owner: OwnerSnapshot,
    id: string,
    command: Extract<Command, { kind: "presentation" | "selection" }>,
    generation: string,
  ) {
    const key = this.#key(owner, id);
    if (!this.#pending.has(key))
      this.#pending.set(key, {
        command,
        generation,
        uncertain: false,
        canRetry: false,
      });
    const sequence = ++this.#sequence;
    const response =
      command.kind === "presentation"
        ? await this.api.mutate("register_presentation", command.request)
        : await this.api.mutate("select_session_listing", command.request);
    if (response.meta.store_generation !== generation)
      throw new ClientFailure("invalid-response", "reconcile-original");
    const session = this.#acceptSession(owner, id, response, sequence);
    this.#pending.delete(key);
    return session;
  }
  #acceptResult(
    owner: OwnerSnapshot,
    id: string,
    pending: Pending,
    result: Schema<"MessageResult">,
  ) {
    checkMessageResultAssociation(result);
    this.owner.assertCurrent(owner);
    if (pending.command.kind !== "message")
      throw new ClientFailure("invalid-response", "read");
    const body = pending.command.request.body;
    if (
      result.session_id !== id ||
      result.client_message_id !== body.client_message_id ||
      result.turn_revision !== body.expected_revision + 1 ||
      result.current_revision < result.turn_revision
    )
      throw new ClientFailure("invalid-response", "reconcile-original");
    const entry = this.#entry(id);
    entry.localTurns = entry.localTurns.filter(
      (turn) => turn.clientId !== result.client_message_id,
    );
    if (
      !entry.turns.some(
        (turn) =>
          turn.client_message_id === result.client_message_id &&
          turn.state === "completed",
      )
    )
      entry.localTurns.push({
        clientId: result.client_message_id,
        revision: result.turn_revision,
        text: body.text,
        result,
      });
    if (entry.text.trim() === body.text) entry.text = "";
    entry.stagedContext = null;
    entry.turnChange += 1;
    this.#pending.delete(this.#key(owner, id));
    this.#publish(owner, id, {
      phase: "idle",
      notice:
        result.state === "provider_unavailable"
          ? "The assistant could not complete this answer. Your direct car tools remain available."
          : result.state === "superseded"
            ? "This reply belongs to an earlier conversation revision. Current selections and filters were not replaced."
            : "A response to the original message is available.",
    });
    this.changed(id);
  }
  async #submit(owner: OwnerSnapshot, id: string, pending: Pending) {
    if (pending.command.kind !== "message") return;
    this.#publish(owner, id, {
      phase: "sending",
      notice: "Waiting for the original message result…",
    });
    let response: ResponseOf<"submit_message">;
    try {
      response = await this.api.mutate(
        "submit_message",
        pending.command.request,
      );
    } catch (error) {
      if (this.#pending.get(this.#key(owner, id)) !== pending) return;
      throw error;
    }
    if (this.#pending.get(this.#key(owner, id)) !== pending) return;
    if (response.meta.store_generation !== pending.generation)
      throw new ClientFailure("invalid-response", "reconcile-original");
    this.#acceptResult(owner, id, pending, response.data);
    try {
      await this.#readSession(owner, id);
    } catch (error) {
      this.#readFailure(owner, id, error);
    }
  }
  #writeFailure(owner: OwnerSnapshot, id: string, error: unknown) {
    const key = this.#key(owner, id);
    let pending = this.#pending.get(key);
    const boundaryRejected =
      error instanceof ClientFailure &&
      (error.kind === "invalid-request" ||
        (error.kind === "api" &&
          !!error.detail &&
          (
            {
              HOST_DENIED: 400,
              ORIGIN_DENIED: 403,
              INPUT_TOO_LARGE: 413,
              UNSUPPORTED_CONTENT_TYPE: 415,
            } as Record<string, number>
          )[error.detail.code] === error.status));
    if (
      pending &&
      !pending.uncertain &&
      boundaryRejected &&
      this.owner.isCurrent(owner)
    ) {
      this.#pending.delete(key);
      if (pending.command.kind === "message") {
        const rejectedId = pending.command.request.body.client_message_id;
        this.#entry(id).localTurns = this.#entry(id).localTurns.filter(
          (turn) => turn.clientId !== rejectedId,
        );
      }
      pending = undefined;
    }
    if (pending) {
      pending.uncertain = true;
      pending.canRetry = false;
    }
    if (this.owner.isCurrent(owner) && this.#entry(id).phase === "blocked")
      return;
    this.#publish(owner, id, {
      phase: pending ? "unknown" : "error",
      notice: pending
        ? "The original submission outcome is unknown. Check its original conversation before any retry; no replacement message has been sent."
        : error instanceof ClientFailure && error.kind === "superseded"
          ? "Conversation context changed before sending. Check the current context and explicitly send your retained text again."
          : "The message was not sent because its context could not be prepared. Your text is retained.",
    });
  }
  async checkOriginal(id: string) {
    const owner = this.owner.capture(),
      key = this.#key(owner, id),
      pending = this.#pending.get(key);
    if (!pending || this.#locks.has(key)) return;
    this.#locks.add(key);
    pending.canRetry = false;
    this.#publish(owner, id, {
      phase: "reading",
      notice: "Reading the original session and ordered transcript…",
    });
    try {
      const session = await this.#readSession(owner, id);
      if (session.meta.store_generation !== pending.generation) {
        this.#publish(owner, id, {
          phase: "blocked",
          notice:
            "The store generation changed. The original submission requires operator reconciliation.",
        });
        return;
      }
      if (pending.command.kind !== "message") {
        pending.canRetry = true;
        this.#publish(owner, id, {
          phase: "unknown",
          notice:
            "The original context command is retained. An explicit retry uses the exact same action and does not send your message.",
        });
        return;
      }
      const originalMessageId = pending.command.request.body.client_message_id;
      let cursor = pending.scan?.cursor ?? null,
        observed = pending.scan?.observed ?? null;
      for (let pageNumber = 0; pageNumber < 10; pageNumber += 1) {
        const response = await this.api.read("get_session_messages", {
          path: { session_id: id },
          query: { page_size: 50, cursor },
        });
        this.#generation(owner, id, response.meta.store_generation);
        if (observed !== null && response.data.observed_revision !== observed)
          throw new ClientFailure("invalid-response", "read");
        observed = response.data.observed_revision;
        this.#merge(owner, id, response.data);
        if (this.#pending.get(key) !== pending) {
          await this.#readSession(owner, id);
          return;
        }
        const found = response.data.items.find(
          (turn) => turn.client_message_id === originalMessageId,
        );
        if (found) {
          pending.scan = undefined;
          if (found.state === "completed" && found.assistant_result) {
            this.#acceptResult(owner, id, pending, found.assistant_result);
            await this.#readSession(owner, id);
          } else
            this.#publish(owner, id, {
              phase: "unknown",
              notice:
                found.state === "pending"
                  ? "The original message is still pending. Read its status again; replay will not restart it."
                  : "The original message was interrupted. It may contain unresolved effects; retry cannot restart it. Keep the original session for reconciliation.",
            });
          return;
        }
        cursor = response.data.next_cursor;
        if (!cursor) {
          const latest = await this.#readSession(owner, id);
          pending.scan = undefined;
          pending.canRetry =
            latest.meta.store_generation === pending.generation &&
            latest.data.revision === observed;
          this.#publish(owner, id, {
            phase: "unknown",
            notice: pending.canRetry
              ? "The complete observed transcript does not contain this message. This does not prove noncommit. You may explicitly retry its identical original request; it may start if never accepted."
              : "The conversation changed while checking. Read the original message again before retrying.",
          });
          return;
        }
        pending.scan = { cursor, observed };
      }
      this.#publish(owner, id, {
        phase: "unknown",
        notice:
          "More historical pages remain. Check the original message again to continue; absence from these pages does not permit replay.",
      });
    } catch (error) {
      this.#readFailure(owner, id, error);
    } finally {
      this.#locks.delete(key);
      this.#emit();
    }
  }
  async retryOriginal(id: string) {
    const owner = this.owner.capture(),
      key = this.#key(owner, id),
      pending = this.#pending.get(key);
    if (!pending?.canRetry || this.#locks.has(key)) return;
    this.#locks.add(key);
    pending.uncertain = true;
    pending.canRetry = false;
    try {
      const observed = await this.#readSession(owner, id);
      if (observed.meta.store_generation !== pending.generation)
        throw new ClientFailure("superseded", "read");
      if (pending.command.kind === "message")
        await this.#submit(owner, id, pending);
      else {
        await this.#contextCommand(
          owner,
          id,
          pending.command,
          pending.generation,
        );
        this.#publish(owner, id, {
          phase: "idle",
          notice:
            "The original context command is resolved. Inspect the current context before explicitly sending your retained message.",
        });
      }
    } catch (error) {
      this.#writeFailure(owner, id, error);
    } finally {
      this.#locks.delete(key);
      this.#emit();
    }
  }
  dispose() {
    this.#unsubscribe();
    this.#sessions.clear();
    this.#historyChains.clear();
    this.#pageReads.clear();
    this.#sessionReads.clear();
    this.#pending.clear();
    this.#locks.clear();
    this.#listeners.clear();
    this.#activeId = null;
    this.#view = { active: null, recoverableSessions: [] };
  }
}
