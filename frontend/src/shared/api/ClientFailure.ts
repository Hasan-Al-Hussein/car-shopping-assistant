import type { Schema } from "./contracts";

export type FailureKind =
  | "invalid-request"
  | "invalid-response"
  | "api"
  | "network"
  | "timeout"
  | "cancelled"
  | "stale-owner"
  | "superseded";

export class ClientFailure extends Error {
  readonly kind: FailureKind;
  readonly recovery:
    "correct-request" | "read" | "reconcile-original" | "reidentify";
  readonly status?: number;
  readonly detail?: Schema<"ApiError">;

  constructor(
    kind: FailureKind,
    recovery: ClientFailure["recovery"],
    options: { status?: number; detail?: Schema<"ApiError"> } = {},
  ) {
    // Never include raw responses, contacts, tokens or request bodies in an Error.
    super(`Request could not be completed (${kind}).`);
    this.name = "ClientFailure";
    this.kind = kind;
    this.recovery = recovery;
    this.status = options.status;
    this.detail = options.detail;
  }
}
