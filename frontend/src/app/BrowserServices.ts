import { ApiClient } from "../shared/api/ApiClient";
import { ClientFailure } from "../shared/api/ClientFailure";
import { OwnerSession } from "../shared/api/OwnerSession";
import type { Schema } from "../shared/api/contracts";
import { bindOwnerInvalidation } from "./ownerInvalidation";
import { createQueryPolicy } from "./queryPolicy";
import { ShortlistCommands } from "../features/shortlist/ShortlistCommands";
import { ViewingFlow } from "../features/viewings/ViewingFlow";
import { ConversationFlow } from "../features/conversation/ConversationFlow";
import { isLocator } from "./routes";

export type IdentityView = {
  phase: "checking" | "anonymous" | "recognized" | "unavailable" | "lost";
  epoch: number;
  identity: Omit<Schema<"RecognizedIdentity">, "csrf_token"> | null;
  session: Schema<"SessionState"> | null;
  pending: boolean;
  notice: string | null;
};

export function failureMessage(error: unknown): string {
  if (!(error instanceof ClientFailure))
    return "The service could not be reached. Try checking again.";
  if (error.status === 401 || error.kind === "stale-owner")
    return "Local access is no longer available. Private information has been hidden. A name cannot restore access.";
  if (error.status === 403)
    return "This request was not allowed. Check local access before trying an explicit action again.";
  if (error.status === 404)
    return "This record is unavailable in your current context. Nothing has been recreated.";
  if (error.kind === "invalid-response")
    return "The service returned an incompatible response. No result can be confirmed.";
  return "The service is unavailable or the request could not be confirmed. Check again when it is available.";
}

/** Same-origin API only. Identity credentials and all private state stay in memory. */
export class BrowserServices {
  readonly owner = new OwnerSession();
  readonly api: ApiClient;
  readonly queries: ReturnType<typeof createQueryPolicy>;
  readonly shortlist: ShortlistCommands;
  readonly viewings: ViewingFlow;
  readonly conversation: ConversationFlow;
  #view: IdentityView = {
    phase: "checking",
    epoch: 0,
    identity: null,
    session: null,
    pending: false,
    notice: null,
  };
  #listeners = new Set<() => void>();
  #sequence = 0;
  #sessionReadSequence = 0;
  #commandPending = false;
  #recheckRequested = false;
  #invalidation?: ReturnType<typeof bindOwnerInvalidation>;
  #unsubscribe?: () => void;
  #sessionLocator: { context: string; id: string } | null = null;
  #uncertainSessions = new Map<
    string,
    { action: string; generation: string }
  >();
  #identityGeneration: string | null = null;
  #browseRequests = new Map<string, Schema<"SearchRequest">>();
  #browsePresentations = new Map<string, Schema<"PresentationProof">>();
  #nextBrowseRequest: Schema<"SearchRequest"> | null = null;
  #activeBrowseKey: string | null = null;
  get currentBrowseKey() {
    return this.#activeBrowseKey;
  }
  browsePresentation(key: unknown = this.#activeBrowseKey) {
    const value =
      typeof key === "string" ? this.#browsePresentations.get(key) : undefined;
    return value ? structuredClone(value) : null;
  }
  retainBrowsePresentation(key: string, value: Schema<"PresentationProof">) {
    this.#browsePresentations.set(key, structuredClone(value));
    if (this.#browsePresentations.size > 30)
      this.#browsePresentations.delete(
        this.#browsePresentations.keys().next().value!,
      );
  }
  get hasUncertainSession() {
    const context = this.owner.capture().contextId;
    return !!context && this.#uncertainSessions.has(context);
  }
  currentBrowseRequest() {
    const request = this.#activeBrowseKey
      ? this.#browseRequests.get(this.#activeBrowseKey)
      : undefined;
    return request ? structuredClone(request) : undefined;
  }
  hasBrowseRequest(key: unknown) {
    return typeof key === "string" && this.#browseRequests.has(key);
  }
  get hasQueuedBrowseRequest() {
    return this.#nextBrowseRequest !== null;
  }
  queueBrowseRequest(request: Schema<"SearchRequest">) {
    this.#nextBrowseRequest = structuredClone(request);
  }

  browseRequest(
    key: string,
    initial: Schema<"SearchRequest">,
    restoreKey?: unknown,
  ) {
    this.#activeBrowseKey = key;
    const existing = this.#browseRequests.get(key);
    if (existing) return structuredClone(existing);
    const request =
      this.#nextBrowseRequest ??
      (typeof restoreKey === "string"
        ? this.#browseRequests.get(restoreKey)
        : undefined) ??
      initial;
    this.#nextBrowseRequest = null;
    this.setBrowseRequest(key, request);
    return structuredClone(request);
  }
  setBrowseRequest(key: string, request: Schema<"SearchRequest">) {
    this.#activeBrowseKey = key;
    this.#browseRequests.set(key, structuredClone(request));
    if (this.#browseRequests.size > 30)
      this.#browseRequests.delete(this.#browseRequests.keys().next().value!);
  }

  constructor(fetchImplementation?: typeof fetch) {
    this.api = new ApiClient(this.owner, fetchImplementation);
    this.queries = createQueryPolicy(this.owner, this.api);
    this.shortlist = new ShortlistCommands(this.owner, this.api, () => {
      void this.queries.client.invalidateQueries({
        predicate: (query) =>
          query.queryKey[0] === "private" &&
          query.queryKey[3] === "get_shortlist",
      });
      this.#invalidation?.notifyOtherTabs();
    });
    this.viewings = new ViewingFlow(this.owner, this.api, () => {
      void this.queries.client.invalidateQueries({
        predicate: (query) =>
          query.queryKey[0] === "private" &&
          [
            "get_booking_draft",
            "get_operation",
            "get_current_local_enquiry",
            "get_local_enquiry",
            "get_session",
          ].includes(String(query.queryKey[3])),
      });
      this.#invalidation?.notifyOtherTabs();
      const session = this.#view.session;
      if (session) void this.readSession(session.session_id);
    });
    this.conversation = new ConversationFlow(
      this.owner,
      this.api,
      (sessionId) => {
        void this.queries.client.invalidateQueries({
          predicate: (query) =>
            query.queryKey[0] === "private" &&
            [
              "get_preferences",
              "get_shortlist",
              "get_current_local_enquiry",
              "get_booking_draft",
              "get_operation",
              "get_session_messages",
            ].includes(String(query.queryKey[3])),
        });
        this.#invalidation?.notifyOtherTabs();
        if (this.#view.session?.session_id === sessionId)
          void this.readSession(sessionId);
      },
    );
  }

  getSnapshot = () => this.#view;
  subscribe = (listener: () => void) => {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  };
  #publish(update: Partial<IdentityView>) {
    // capture() can synchronously expire the owner and notify us again.
    const snapshot = this.owner.capture();
    this.#view = {
      ...this.#view,
      ...update,
      epoch: snapshot.epoch,
    };
    if (this.#view.identity?.context_id !== snapshot.contextId) {
      this.#view = {
        ...this.#view,
        identity: null,
        session: null,
        phase: this.#view.phase === "recognized" ? "lost" : this.#view.phase,
      };
    }
    for (const listener of this.#listeners) listener();
  }

  start(target?: Window) {
    if (this.#unsubscribe) return;
    this.#unsubscribe = this.owner.subscribe(() => {
      this.#browseRequests.clear();
      this.#browsePresentations.clear();
      this.#identityGeneration = null;
      this.#nextBrowseRequest = null;
      this.#activeBrowseKey = null;
      this.#publish({
        phase: this.#view.identity ? "lost" : "checking",
        identity: null,
        session: null,
      });
    });
    if (target) {
      let channel: BroadcastChannel | undefined;
      try {
        channel = new BroadcastChannel("car-shopping-owner");
      } catch {
        /* Focus revalidation remains available. */
      }
      this.#invalidation = bindOwnerInvalidation(
        this.owner,
        () => this.revalidate(),
        target,
        channel,
      );
    }
    void this.revalidate();
  }

  stop() {
    this.#sequence += 1;
    this.#sessionReadSequence += 1;
    this.#recheckRequested = false;
    this.#invalidation?.dispose();
    this.#invalidation = undefined;
    this.owner.invalidate();
    this.#unsubscribe?.();
    this.#unsubscribe = undefined;
  }

  dispose() {
    this.stop();
    this.queries.dispose();
    this.shortlist.dispose();
    this.viewings.dispose();
    this.conversation.dispose();
    this.#uncertainSessions.clear();
    this.owner.dispose();
    this.#listeners.clear();
  }

  async revalidate() {
    // Ordinary focus checks retain confirmed state. Logout, expiry, cross-tab
    // invalidation and 401 still synchronously clear it through OwnerSession.
    if (this.#commandPending) {
      this.#recheckRequested = true;
      return;
    }
    const sequence = ++this.#sequence;
    const retained = this.#view.phase === "recognized" && this.#view.identity;
    if (!retained)
      this.#publish({
        phase: "checking",
        pending: false,
        identity: null,
        session: null,
        notice: null,
      });
    try {
      const response = await this.api.revalidateIdentity();
      if (sequence !== this.#sequence) return;
      this.#accept(response.data, response.meta.store_generation ?? null);
    } catch (error) {
      if (sequence === this.#sequence) {
        const stillRecognized =
          retained && this.owner.capture().contextId === retained.context_id;
        this.#publish({
          phase: stillRecognized
            ? "recognized"
            : error instanceof ClientFailure && error.status === 401
              ? "lost"
              : "unavailable",
          notice: failureMessage(error),
        });
      }
    }
  }

  #accept(
    identity: Schema<"RecognizedIdentity"> | Schema<"AnonymousIdentity">,
    generation: string | null,
  ) {
    const sameContext =
      identity.state === "recognized" &&
      this.#view.identity?.context_id === identity.context_id &&
      this.#identityGeneration === generation;
    if (
      identity.state === "recognized" &&
      this.#identityGeneration &&
      generation !== this.#identityGeneration
    )
      this.owner.accept(this.owner.invalidate(), identity);
    this.#identityGeneration = generation;
    const safeIdentity =
      identity.state === "recognized"
        ? {
            state: identity.state,
            context_id: identity.context_id,
            display_name: identity.display_name,
            continuity: identity.continuity,
            expires_at: identity.expires_at,
          }
        : null;
    this.#publish({
      phase: identity.state,
      identity: safeIdentity,
      session: sameContext ? this.#view.session : null,
      notice: null,
    });
    if (
      identity.state === "recognized" &&
      this.#sessionLocator?.context === identity.context_id
    )
      void this.readSession(this.#sessionLocator.id);
  }

  #finishCommand(notifyOtherTabs = false) {
    this.#commandPending = false;
    if (!this.#unsubscribe) return;
    if (notifyOtherTabs) this.#invalidation?.notifyOtherTabs();
    // Pending reflects the single command lock, even across stop/start. No old
    // response is published; queued lifecycle/focus checks perform only a GET.
    this.#publish({ pending: false });
    if (this.#recheckRequested) {
      this.#recheckRequested = false;
      void this.revalidate();
    }
  }

  async bootstrap(
    noticeVersion: "DEMO-POLICY-1",
    acknowledged: boolean,
    displayName: string,
  ) {
    if (this.#commandPending || !acknowledged) return;
    this.#commandPending = true;
    const sequence = ++this.#sequence;
    this.#publish({ pending: true, notice: null });
    try {
      const response = await this.api.bootstrapIdentity({
        notice_version: noticeVersion,
        notice_acknowledged: true,
        display_name: displayName.trim() || null,
      });
      if (sequence === this.#sequence)
        this.#accept(response.data, response.meta.store_generation ?? null);
    } catch (error) {
      if (sequence === this.#sequence)
        this.#publish({
          phase:
            error instanceof ClientFailure && error.status === 401
              ? "lost"
              : "unavailable",
          identity: null,
          session: null,
          notice:
            error instanceof ClientFailure && error.status === 401
              ? "Local access was denied and private information is hidden. Old records cannot be recovered by name. Check local access before starting another context."
              : `${failureMessage(error)} Use Check local access before starting another context.`,
        });
    } finally {
      this.#finishCommand(true);
    }
  }

  async end(acknowledged: boolean) {
    if (
      !acknowledged ||
      this.#commandPending ||
      this.#view.phase !== "recognized"
    )
      return;
    this.#commandPending = true;
    const sequence = ++this.#sequence;
    this.#publish({ pending: true, notice: null });
    this.#invalidation?.notifyOtherTabs();
    try {
      await this.api.endIdentity({ acknowledge_loss_of_access: true });
      if (sequence !== this.#sequence) return;
      this.#publish({
        phase: "anonymous",
        identity: null,
        session: null,
        notice: "Local access ended. Existing records were not deleted.",
      });
    } catch (error) {
      if (sequence !== this.#sequence) return;
      this.#publish({
        phase: "unavailable",
        identity: null,
        session: null,
        notice: `Local information is hidden. Ending access could not be confirmed. ${failureMessage(error)}`,
      });
    } finally {
      this.#finishCommand(true);
    }
  }

  async createSession() {
    await this.#createSession(false);
  }
  async retryOriginalSession() {
    await this.#createSession(true);
  }
  async #createSession(retry: boolean) {
    if (this.#commandPending || this.#view.phase !== "recognized") return;
    const snapshot = this.owner.capture(),
      context = snapshot.contextId!;
    const original = this.#uncertainSessions.get(context);
    if (!retry && original) {
      this.#publish({
        notice:
          "The original conversation request has an unknown outcome. Check or explicitly retry its original request; no replacement has been created.",
      });
      return;
    }
    if (retry && !original) return;
    this.#commandPending = true;
    this.#sessionReadSequence += 1;
    this.#publish({
      pending: true,
      notice: retry ? "Checking the original conversation request…" : null,
    });
    let dispatched = false;
    try {
      let generation = original?.generation ?? this.#identityGeneration;
      if (retry || !generation) {
        const observed = await this.api.read("get_preferences", {});
        this.owner.assertCurrent(snapshot);
        if (
          original &&
          observed.meta.store_generation !== original.generation
        ) {
          this.#publish({
            notice:
              "The local store changed. Operator reconciliation is required for the original conversation request; nothing has been replayed.",
          });
          return;
        }
        generation = observed.meta.store_generation ?? null;
      }
      if (!isLocator(generation))
        throw new ClientFailure("invalid-response", "read");
      const command = original ?? { action: crypto.randomUUID(), generation };
      this.#uncertainSessions.set(context, command);
      dispatched = true;
      const response = await this.api.mutate("create_session", {
        body: { client_action_id: command.action },
      });
      this.owner.assertCurrent(snapshot);
      if (response.meta.store_generation !== command.generation)
        throw new ClientFailure("invalid-response", "reconcile-original");
      this.#sessionReadSequence += 1;
      this.#sessionLocator = { context, id: response.data.session_id };
      this.#uncertainSessions.delete(context);
      this.#publish({
        session: response.data,
        notice: retry
          ? "The original conversation request is resolved. Current retained session details are shown."
          : "A new local conversation has started. Saved preferences remain separate; no earlier selected car has been imported.",
      });
    } catch (error) {
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
      if (!original && boundaryRejected && this.owner.isCurrent(snapshot))
        this.#uncertainSessions.delete(context);
      if (this.owner.isCurrent(snapshot))
        this.#publish({
          notice: `${failureMessage(error)} ${!dispatched ? "No conversation request was sent." : !original && boundaryRejected ? "The conversation request was rejected before acceptance." : "The original conversation request is retained without automatic retry."}`,
        });
    } finally {
      this.#finishCommand();
    }
  }
  async readSession(id: string) {
    if (this.#commandPending) return;
    const sequence = ++this.#sessionReadSequence;
    const snapshot = this.owner.capture();
    try {
      const result = await this.queries.client.fetchQuery(
        this.queries.privateRead(
          "get_session",
          { path: { session_id: id } },
          { sessionId: id },
        ),
      );
      this.owner.assertCurrent(snapshot);
      if (sequence !== this.#sessionReadSequence) return;
      this.#sessionLocator = { context: snapshot.contextId!, id };
      this.#publish({ session: result.data });
    } catch (error) {
      if (
        sequence === this.#sessionReadSequence &&
        this.owner.isCurrent(snapshot)
      ) {
        const keepCurrent =
          this.#view.session?.session_id === id &&
          error instanceof ClientFailure &&
          (error.kind === "network" ||
            error.kind === "timeout" ||
            (error.kind === "api" &&
              [429, 503, 504].includes(error.status ?? 0)));
        this.#publish({
          session: keepCurrent ? this.#view.session : null,
          notice: failureMessage(error),
        });
      }
    }
  }
}
