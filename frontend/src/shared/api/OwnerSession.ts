import { validateIdentity } from "../../../../contracts/generated/runtime";
import { ClientFailure } from "./ClientFailure";
import type { Schema } from "./contracts";

export type OwnerSnapshot = Readonly<{
  epoch: number;
  contextId: string | null;
  csrfToken: string | null;
}>;

/** Memory-only transport context. IDs remain equality guards, never credentials. */
export class OwnerSession {
  #epoch = 0;
  #identity: Schema<"RecognizedIdentity"> | null = null;
  #listeners = new Set<() => void>();
  #expiryTimer?: ReturnType<typeof setTimeout>;
  #endedContexts = new Set<string>();

  capture(): OwnerSnapshot {
    if (this.#identity && Date.parse(this.#identity.expires_at) <= Date.now())
      this.invalidate();
    return Object.freeze({
      epoch: this.#epoch,
      contextId: this.#identity?.context_id ?? null,
      csrfToken: this.#identity?.csrf_token ?? null,
    });
  }

  isCurrent(snapshot: OwnerSnapshot): boolean {
    if (this.#identity && Date.parse(this.#identity.expires_at) <= Date.now())
      this.invalidate();
    return (
      snapshot.epoch === this.#epoch &&
      snapshot.contextId === (this.#identity?.context_id ?? null)
    );
  }

  assertCurrent(snapshot: OwnerSnapshot): void {
    if (!this.isCurrent(snapshot))
      throw new ClientFailure("stale-owner", "reidentify");
  }

  subscribe(listener: () => void): () => void {
    this.#listeners.add(listener);
    return () => {
      this.#listeners.delete(listener);
    };
  }

  /** Synchronously hides private context; listeners cancel/purge before any recheck. */
  invalidate(): number {
    clearTimeout(this.#expiryTimer);
    this.#expiryTimer = undefined;
    this.#epoch += 1;
    this.#identity = null;
    for (const listener of this.#listeners) listener();
    return this.#epoch;
  }

  /** Keep a locally ended context hidden even if a focus GET races server revocation. */
  endLocally(snapshot: OwnerSnapshot): void {
    this.assertCurrent(snapshot);
    if (snapshot.contextId) this.#endedContexts.add(snapshot.contextId);
    this.invalidate();
  }

  /** Only use a validated GET identity/bootstrap result from this recheck epoch. */
  accept(
    epoch: number,
    identity: Schema<"RecognizedIdentity"> | Schema<"AnonymousIdentity">,
  ): void {
    if (epoch !== this.#epoch)
      throw new ClientFailure("stale-owner", "reidentify");
    if (!validateIdentity(identity)) {
      throw new ClientFailure("invalid-response", "reidentify");
    }
    // A deliberate later bootstrap may establish a new context, never resurrect
    // the old context whose revocation may already have committed.
    if (
      identity.state === "recognized" &&
      this.#endedContexts.has(identity.context_id)
    ) {
      throw new ClientFailure("stale-owner", "reidentify");
    }
    if (
      identity.state === "recognized" &&
      (!Number.isFinite(Date.parse(identity.expires_at)) ||
        Date.parse(identity.expires_at) <= Date.now())
    ) {
      this.invalidate();
      throw new ClientFailure("stale-owner", "reidentify");
    }
    const contextChanged =
      (identity.state === "recognized" ? identity.context_id : null) !==
      (this.#identity?.context_id ?? null);
    if (contextChanged) this.#epoch += 1;
    this.#identity =
      identity.state === "recognized" ? structuredClone(identity) : null;
    clearTimeout(this.#expiryTimer);
    this.#scheduleExpiry();
    // A successful focus check of the same browser context refreshes its expiry
    // and token without cancelling requests, emptying caches or remounting chat.
    if (contextChanged) for (const listener of this.#listeners) listener();
  }

  #scheduleExpiry(): void {
    if (!this.#identity) return;
    const remaining = Date.parse(this.#identity.expires_at) - Date.now();
    if (remaining <= 0) {
      this.invalidate();
      return;
    }
    // Browser timers cannot represent a full 30-day cookie lifetime in one call.
    this.#expiryTimer = setTimeout(
      () => this.#scheduleExpiry(),
      Math.min(remaining, 2_147_483_647),
    );
  }

  dispose(): void {
    this.invalidate();
    this.#listeners.clear();
    this.#endedContexts.clear();
  }
}
