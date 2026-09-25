import seed from "../../../fixtures/shared/harness-seed.json";

export function newSeed() {
  return structuredClone(seed);
}

export function frozenClock(iso: string = seed.clock_utc) {
  let instant = Date.parse(iso);
  if (!iso.endsWith("Z") || !Number.isFinite(instant))
    throw new Error("Explicit UTC required");
  return {
    now: () => new Date(instant),
    advance: (seconds: number) => {
      if (!Number.isFinite(seconds) || seconds < 0)
        throw new Error("Advance must be nonnegative");
      instant += seconds * 1000;
    },
  };
}

export function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

export interface ReplyStep {
  method: string;
  path: string;
  contextId?: string;
  status?: number;
  body: unknown;
  gate?: Promise<void>;
  onAccept?: () => void;
  loseResponse?: boolean;
}

export function scriptedFetch(script: readonly ReplyStep[]): typeof fetch {
  const steps = [...script];
  return async (input, init) => {
    const request =
      input instanceof Request
        ? input
        : new Request(new URL(String(input), "http://fixture.invalid"), init);
    const url = new URL(request.url);
    const step = steps.shift();
    if (!step || url.hostname !== "fixture.invalid")
      throw new Error("UNSCRIPTED_HTTP_CALL");
    const headers = new Headers(init?.headers ?? request.headers);
    if (
      (init?.method ?? request.method) !== step.method ||
      url.pathname !== step.path ||
      (step.contextId !== undefined &&
        headers.get("X-Identity-Context") !== step.contextId)
    ) {
      throw new Error("UNEXPECTED_HTTP_COMMAND");
    }
    step.onAccept?.();
    if (step.gate) await step.gate;
    if (step.loseResponse)
      throw new TypeError("SYNTHETIC_RESPONSE_LOST_AFTER_ACCEPT");
    return new Response(JSON.stringify(step.body), {
      status: step.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  };
}
