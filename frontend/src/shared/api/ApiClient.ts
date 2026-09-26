import {
  contractVersion,
  operationContracts,
  validateParameter,
  validateRequestBody,
  validateResponse,
} from "../../../../contracts/generated/runtime";
import { abortable } from "./abort";
import { ClientFailure } from "./ClientFailure";
import { OwnerSession } from "./OwnerSession";
import { readJson } from "./responseBody";
import { checkResponseAssociation } from "./responseAssociation";
import type {
  BodyOf,
  Operation,
  RequestOf,
  ResponseOf,
  Schema,
} from "./contracts";

const READ_DEADLINE_MS = 8_000;
const WRITE_DEADLINE_MS = 30_000;
const READ_ATTEMPTS = 2;
const READ_RETRY_DELAY_MS = 250;
const REQUEST_BYTES_MAX = 65_536;
const AUTO_HEADERS = new Set(["origin", "x-identity-context", "x-csrf-token"]);
const IDENTITY_OPERATIONS = new Set<Operation>([
  "get_identity",
  "bootstrap_identity",
]);

type TransportInput = {
  body?: unknown;
  path?: Record<string, unknown>;
  query?: Record<string, unknown>;
  headers?: Record<string, unknown>;
  signal?: AbortSignal;
};

function pause(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const cancel = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", cancel);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", cancel, { once: true });
    if (signal.aborted) cancel();
  });
}

function mayRetry(error: unknown): boolean {
  return (
    error instanceof ClientFailure &&
    (error.kind === "network" ||
      (error.kind === "api" &&
        [429, 503, 504].includes(error.status ?? 0) &&
        error.detail?.retryable === true &&
        error.detail.retry_action === "read"))
  );
}

/** Cookie authority stays with the server. This client never accepts an owner ID. */
export class ApiClient {
  readonly owner: OwnerSession;
  #fetch: typeof fetch;

  constructor(
    owner: OwnerSession,
    fetchImplementation: typeof fetch = globalThis.fetch.bind(globalThis),
  ) {
    this.owner = owner;
    this.#fetch = fetchImplementation;
  }

  async revalidateIdentity(): Promise<ResponseOf<"get_identity">> {
    const { epoch } = this.owner.capture();
    const response = await this.read("get_identity", {});
    this.owner.accept(epoch, response.data);
    return response;
  }

  async bootstrapIdentity(
    body: BodyOf<"bootstrap_identity">,
  ): Promise<ResponseOf<"bootstrap_identity">> {
    const epoch = this.owner.invalidate();
    const response = await this.mutate("bootstrap_identity", { body });
    this.owner.accept(epoch, response.data);
    return response;
  }

  endIdentity(
    body: BodyOf<"end_identity">,
  ): Promise<ResponseOf<"end_identity">> {
    return this.mutate("end_identity", { body });
  }

  read<Name extends Operation>(
    operation: Name,
    request: RequestOf<Name>,
  ): Promise<ResponseOf<Name>> {
    if (operationContracts[operation]?.mutates !== false) {
      return Promise.reject(
        new ClientFailure("invalid-request", "correct-request"),
      );
    }
    return this.#send(operation, request);
  }

  mutate<Name extends Operation>(
    operation: Name,
    request: RequestOf<Name>,
  ): Promise<ResponseOf<Name>> {
    if (operationContracts[operation]?.mutates !== true) {
      return Promise.reject(
        new ClientFailure("invalid-request", "correct-request"),
      );
    }
    return this.#send(operation, request);
  }

  async #send<Name extends Operation>(
    operation: Name,
    request: RequestOf<Name>,
  ): Promise<ResponseOf<Name>> {
    const contract = operationContracts[operation];
    const supplied = request as TransportInput;
    // Snapshot caller maps before the first await, just like the serialized body.
    const input: TransportInput = {
      ...supplied,
      path: supplied.path && { ...supplied.path },
      query: supplied.query && { ...supplied.query },
      headers: supplied.headers && { ...supplied.headers },
    };
    const snapshot = this.owner.capture();
    const endingIdentity = operation === "end_identity";
    const boundToOwner =
      !endingIdentity &&
      (contract.isPrivate || IDENTITY_OPERATIONS.has(operation));
    const recovery = contract.mutates ? "reconcile-original" : "read";
    if (contract.isPrivate && (!snapshot.contextId || !snapshot.csrfToken)) {
      throw new ClientFailure("stale-owner", "reidentify");
    }
    const invalidRequest = () =>
      new ClientFailure("invalid-request", "correct-request");
    let body: string | undefined;
    let bodyValue: unknown;
    if (!validateRequestBody(operation, input.body)) throw invalidRequest();
    try {
      body = input.body === undefined ? undefined : JSON.stringify(input.body);
      if (
        body !== undefined &&
        new TextEncoder().encode(body).byteLength > REQUEST_BYTES_MAX
      )
        throw invalidRequest();
      bodyValue = body === undefined ? undefined : JSON.parse(body);
    } catch {
      throw invalidRequest();
    }
    if (!validateRequestBody(operation, bodyValue)) throw invalidRequest();

    let url = contract.path;
    const query = new URLSearchParams();
    const headers = new Headers({ Accept: "application/json" });
    if (body !== undefined) headers.set("Content-Type", "application/json");
    if (contract.isPrivate) {
      headers.set("X-Identity-Context", snapshot.contextId!);
      if (contract.mutates) headers.set("X-CSRF-Token", snapshot.csrfToken!);
    }
    for (const [location, values] of [
      ["path", input.path ?? {}],
      ["query", input.query ?? {}],
      ["header", input.headers ?? {}],
    ] as const) {
      const seen = new Set<string>();
      for (const [name, value] of Object.entries(values)) {
        if (location === "header" && AUTO_HEADERS.has(name.toLowerCase()))
          throw invalidRequest();
        const parameterName = location === "header" ? name.toLowerCase() : name;
        if (seen.has(parameterName)) throw invalidRequest();
        seen.add(parameterName);
        if (!validateParameter(operation, location, name, value))
          throw invalidRequest();
        if (location === "query" && (value === null || value === undefined))
          continue;
        if (typeof value !== "string" && typeof value !== "number")
          throw invalidRequest();
        if (location === "path") {
          if (!String(value) || value === "." || value === "..")
            throw invalidRequest();
          url = url.replace(`{${name}}`, encodeURIComponent(value));
        } else if (location === "query") query.set(name, String(value));
        else headers.set(name, String(value));
      }
    }
    for (const parameter of contract.parameters) {
      if (
        !parameter.required ||
        (parameter.in === "header" &&
          AUTO_HEADERS.has(parameter.name.toLowerCase()))
      )
        continue;
      const values =
        parameter.in === "header" ? input.headers : input[parameter.in];
      const present =
        parameter.in === "header"
          ? Object.entries(values ?? {}).some(
              ([key, value]) =>
                key.toLowerCase() === parameter.name.toLowerCase() &&
                value !== undefined,
            )
          : values?.[parameter.name] !== undefined;
      if (!present) throw invalidRequest();
    }
    if (url.includes("{") || !url.startsWith("/api/v1/"))
      throw invalidRequest();
    if (query.size) url += `?${query}`;
    if (input.signal?.aborted)
      throw new ClientFailure("cancelled", "correct-request");

    const controller = new AbortController();
    const cancel = () =>
      controller.abort(new ClientFailure("cancelled", recovery));
    input.signal?.addEventListener("abort", cancel, { once: true });
    const unsubscribe = boundToOwner
      ? this.owner.subscribe(() =>
          controller.abort(new ClientFailure("stale-owner", recovery)),
        )
      : () => undefined;
    const timeout = setTimeout(
      () => controller.abort(new ClientFailure("timeout", recovery)),
      contract.mutates ? WRITE_DEADLINE_MS : READ_DEADLINE_MS,
    );
    const attempts = contract.mutates ? 1 : READ_ATTEMPTS;
    // Clear local private state immediately but send this one revocation using the
    // already captured context. An uncertain response never restores the old owner.
    if (endingIdentity) this.owner.endLocally(snapshot);

    let completedSuccessfully = false;
    try {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        let retryDelay = READ_RETRY_DELAY_MS;
        try {
          if (boundToOwner) this.owner.assertCurrent(snapshot);
          if (controller.signal.aborted) throw controller.signal.reason;
          const response = await abortable(
            this.#fetch(url, {
              method: contract.method.toUpperCase(),
              headers,
              body,
              credentials: "same-origin",
              mode: "same-origin",
              cache: "no-store",
              redirect: "error",
              referrerPolicy: "no-referrer",
              signal: controller.signal,
            }),
            controller.signal,
          );
          if (response.status === 401) {
            // Purge immediately even when a proxy returns HTML or a malformed body.
            unsubscribe();
            if (this.owner.isCurrent(snapshot)) this.owner.invalidate();
            let detail: Schema<"ApiError"> | undefined;
            try {
              const denied = await readJson(response, controller.signal);
              if (validateResponse(operation, 401, denied))
                detail = (denied as Schema<"ErrorEnvelope">).error;
            } catch {
              /* State is already hidden; malformed or stalled diagnostics cannot restore it. */
            }
            throw new ClientFailure("api", "reidentify", {
              status: 401,
              detail,
            });
          }
          const payload = await readJson(response, controller.signal);
          if (boundToOwner) this.owner.assertCurrent(snapshot);
          if (!validateResponse(operation, response.status, payload)) {
            throw new ClientFailure("invalid-response", recovery);
          }
          // A confirmation 409 can carry the retained domain rejection envelope.
          if (
            !response.ok &&
            typeof payload === "object" &&
            payload !== null &&
            "error" in payload
          ) {
            const detail = (payload as Schema<"ErrorEnvelope">).error;
            const retryAfter = response.headers.get("Retry-After");
            if (retryAfter !== null) {
              const seconds = Number(retryAfter);
              const wait = Number.isFinite(seconds)
                ? seconds * 1000
                : Date.parse(retryAfter) - Date.now();
              if (Number.isFinite(wait) && wait > 0)
                retryDelay = Math.max(retryDelay, wait);
            }
            throw new ClientFailure("api", recovery, {
              status: response.status,
              detail,
            });
          }
          const envelope = payload as {
            meta: Schema<"ResponseMeta">;
            data: unknown;
          };
          if (
            envelope.meta.contract_version !== contractVersion ||
            envelope.meta.policy_version !== "DEMO-POLICY-1"
          ) {
            throw new ClientFailure("invalid-response", recovery);
          }
          if (
            contract.isPrivate &&
            envelope.meta.identity_context_id !== snapshot.contextId
          ) {
            if (this.owner.isCurrent(snapshot)) this.owner.invalidate();
            throw new ClientFailure("stale-owner", recovery);
          }
          checkResponseAssociation(
            operation,
            { ...input, body: bodyValue },
            envelope,
          );
          completedSuccessfully = true;
          return payload as ResponseOf<Name>;
        } catch (error) {
          const failure =
            error instanceof ClientFailure
              ? new ClientFailure(
                  error.kind,
                  contract.mutates ? recovery : error.recovery,
                  { status: error.status, detail: error.detail },
                )
              : controller.signal.aborted
                ? (controller.signal.reason as ClientFailure)
                : new ClientFailure("network", recovery);
          if (
            contract.mutates ||
            attempt + 1 === attempts ||
            !mayRetry(failure) ||
            controller.signal.aborted
          )
            throw failure;
          await pause(retryDelay, controller.signal);
        }
      }
      throw new ClientFailure("network", recovery);
    } finally {
      clearTimeout(timeout);
      unsubscribe();
      input.signal?.removeEventListener("abort", cancel);
      // Successful bodies are fully consumed; cancellation is only for failures.
      if (!completedSuccessfully) controller.abort();
    }
  }
}
