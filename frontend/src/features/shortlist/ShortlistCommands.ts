import { ApiClient } from "../../shared/api/ApiClient";
import { ClientFailure } from "../../shared/api/ClientFailure";
import {
  OwnerSession,
  type OwnerSnapshot,
} from "../../shared/api/OwnerSession";
import type { ResponseOf, Schema } from "../../shared/api/contracts";
import { isLocator, refKey, type InventoryRef } from "../../app/routes";

type Intent = {
  ref: InventoryRef;
  saved: boolean;
  actionId: string;
  expectedRevision: number;
  generation: string;
  uncertain: boolean;
};
export type ShortlistView = {
  phase: "idle" | "reading" | "pending" | "unknown" | "blocked" | "error";
  ref: InventoryRef | null;
  notice: string | null;
  membership: Readonly<Record<string, boolean>>;
  revision: number | null;
  generation: string | null;
  changeCount: number;
};
const blank = (): ShortlistView => ({
  phase: "idle",
  ref: null,
  notice: null,
  membership: {},
  revision: null,
  generation: null,
  changeCount: 0,
});

/** Explicit commands only. Uncertain intents survive navigation in owner-scoped memory. */
export class ShortlistCommands {
  #view = blank();
  #listeners = new Set<() => void>();
  #intents = new Map<string, Intent>();
  #locks = new Set<string>();
  #readSequence = 0;
  #observedSequence = 0;
  #retiredGenerations = new Set<string>();
  #unsubscribe: () => void;
  constructor(
    private owner: OwnerSession,
    private api: ApiClient,
    private changed: () => void,
  ) {
    this.#unsubscribe = owner.subscribe(() => {
      const context = owner.capture().contextId;
      const intent = context ? this.#intents.get(context) : undefined;
      this.#retiredGenerations.clear();
      this.#observedSequence = 0;
      this.#view = intent
        ? {
            ...blank(),
            phase: "unknown",
            ref: intent.ref,
            notice:
              "The original shortlist action has not been confirmed. Check that action before making another change.",
          }
        : blank();
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
  #emit() {
    for (const listener of this.#listeners) listener();
  }
  #publish(snapshot: OwnerSnapshot, update: Partial<ShortlistView>) {
    if (this.owner.isCurrent(snapshot)) {
      this.#view = { ...this.#view, ...update };
      this.#emit();
    }
  }

  /** Read under the private query's captured owner; stale reads cannot reach the view. */
  async readPage(
    cursor: string | null,
    pageSize: number,
    snapshot: OwnerSnapshot,
    signal?: AbortSignal,
  ): Promise<ResponseOf<"get_shortlist">> {
    this.owner.assertCurrent(snapshot);
    const sequence = ++this.#readSequence;
    const response = await this.api.read("get_shortlist", {
      query: { page_size: pageSize, cursor },
      signal,
    });
    this.owner.assertCurrent(snapshot);
    const { revision, items, next_cursor } = response.data,
      generation = response.meta.store_generation;
    if (
      !isLocator(generation) ||
      response.meta.identity_context_id !== snapshot.contextId
    )
      throw new ClientFailure("invalid-response", "read");
    const sameGeneration = generation === this.#view.generation;
    if (
      this.#retiredGenerations.has(generation) ||
      (!sameGeneration && sequence < this.#observedSequence) ||
      (sameGeneration &&
        this.#view.revision !== null &&
        revision < this.#view.revision)
    )
      throw new ClientFailure("superseded", "read");
    if (!sameGeneration && this.#view.generation)
      this.#retiredGenerations.add(this.#view.generation);
    this.#observedSequence = Math.max(sequence, this.#observedSequence);
    const sameVersion = sameGeneration && revision === this.#view.revision;
    const membership: Record<string, boolean> = sameVersion
      ? { ...this.#view.membership }
      : {};
    if (cursor === null && next_cursor === null)
      for (const key of Object.keys(this.#view.membership))
        membership[key] = false;
    for (const item of items) membership[refKey(item.ref)] = true;
    if (
      !sameVersion ||
      JSON.stringify(membership) !== JSON.stringify(this.#view.membership)
    )
      this.#publish(snapshot, { membership, revision, generation });
    return response;
  }

  async change(ref: InventoryRef, saved: boolean) {
    const snapshot = this.owner.capture(),
      context = snapshot.contextId;
    if (!context || this.#locks.has(context) || this.#intents.has(context))
      return;
    const exactRef = structuredClone(ref);
    this.#locks.add(context);
    this.#publish(snapshot, {
      phase: "reading",
      ref: exactRef,
      notice: "Checking the current shortlist before this action…",
    });
    try {
      const current = await this.readPage(null, 1, snapshot);
      this.owner.assertCurrent(snapshot);
      if (!isLocator(current.meta.store_generation))
        throw new ClientFailure("invalid-response", "read");
      const intent: Intent = {
        ref: exactRef,
        saved,
        actionId: crypto.randomUUID(),
        expectedRevision: current.data.revision,
        generation: current.meta.store_generation,
        uncertain: false,
      };
      this.#intents.set(context, intent);
      await this.#send(snapshot, intent);
    } catch (error) {
      this.#fail(snapshot, error);
    } finally {
      this.#locks.delete(context);
    }
  }
  async reconcile() {
    const snapshot = this.owner.capture(),
      context = snapshot.contextId;
    const intent = context ? this.#intents.get(context) : undefined;
    if (!context || !intent || this.#locks.has(context)) return;
    intent.uncertain = true;
    this.#locks.add(context);
    this.#publish(snapshot, {
      phase: "reading",
      ref: intent.ref,
      notice: "Checking the original shortlist action…",
    });
    try {
      const current = await this.readPage(null, 1, snapshot);
      this.owner.assertCurrent(snapshot);
      if (current.meta.store_generation !== intent.generation) {
        this.#publish(snapshot, {
          phase: "blocked",
          notice:
            "The local store changed. The original shortlist action needs operator reconciliation; it has not been replayed or replaced.",
        });
        return;
      }
      // GET membership cannot establish noncommit. Only this explicit exact replay
      // can obtain its retained result; neither its key nor revision is refreshed.
      await this.#send(snapshot, intent);
    } catch (error) {
      this.#fail(snapshot, error);
    } finally {
      this.#locks.delete(context);
    }
  }
  async #send(snapshot: OwnerSnapshot, intent: Intent) {
    this.owner.assertCurrent(snapshot);
    this.#publish(snapshot, {
      phase: "pending",
      notice: intent.saved
        ? "Saving this exact car…"
        : "Removing this exact saved reference…",
    });
    const response = intent.saved
      ? await this.api.mutate("add_shortlist_membership", {
          path: intent.ref,
          body: {
            client_action_id: intent.actionId,
            expected_revision: intent.expectedRevision,
          },
        })
      : await this.api.mutate("remove_shortlist_membership", {
          path: intent.ref,
          headers: {
            "X-Client-Action-ID": intent.actionId,
            "X-Expected-Revision": intent.expectedRevision,
          },
        });
    this.owner.assertCurrent(snapshot);
    if (response.meta.store_generation !== intent.generation) {
      intent.uncertain = true;
      this.#publish(snapshot, {
        phase: "blocked",
        notice:
          "The response came from a changed local store. The original action needs reconciliation; no membership result has been assumed.",
      });
      return;
    }
    this.#intents.delete(snapshot.contextId!);
    const result: Schema<"MembershipResult"> = response.data;
    const current =
      this.#view.generation === intent.generation &&
      (this.#view.revision === null ||
        result.current_revision >= this.#view.revision);
    this.#publish(snapshot, {
      phase: "idle",
      ref: intent.ref,
      changeCount: this.#view.changeCount + 1,
      ...(current
        ? {
            revision: result.current_revision,
            generation: intent.generation,
            membership: { [refKey(intent.ref)]: result.saved },
          }
        : {}),
      notice: !current
        ? "The original action is resolved. A newer shortlist observation is retained; open saved cars for its current state."
        : result.saved
          ? "This car is in your saved shortlist. Saving does not reserve it."
          : "This car is not in your saved shortlist. The original listing is unchanged.",
    });
    this.changed();
  }
  #fail(snapshot: OwnerSnapshot, error: unknown) {
    const context = snapshot.contextId!;
    const rejected =
      this.owner.isCurrent(snapshot) &&
      error instanceof ClientFailure &&
      (error.kind === "invalid-request" ||
        (error.kind === "api" &&
          error.detail !== undefined &&
          [400, 401, 403, 404, 409, 422].includes(error.status ?? 0)));
    const intent = this.#intents.get(context);
    if (rejected && intent && !intent.uncertain) this.#intents.delete(context);
    else if (intent) intent.uncertain = true;
    const uncertain = this.#intents.has(context);
    this.#publish(snapshot, {
      phase: uncertain ? "unknown" : "error",
      notice: uncertain
        ? "The shortlist action has an unknown outcome. Its original identity is retained; checking membership alone does not prove it failed."
        : "The shortlist change was not confirmed. Refresh the shortlist and check local access before another explicit action.",
    });
  }
  dispose() {
    this.#unsubscribe();
    this.#intents.clear();
    this.#locks.clear();
    this.#retiredGenerations.clear();
    this.#view = blank();
    this.#listeners.clear();
  }
}
