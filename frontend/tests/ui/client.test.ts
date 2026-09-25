import { describe, expect, test, vi } from "vitest";
import { validateResponse } from "../../../contracts/generated/runtime";
import { validateSchema } from "../../../contracts/generated/runtime.schemas";
import { ApiClient } from "../../src/shared/api/ApiClient";
import { ClientFailure } from "../../src/shared/api/ClientFailure";
import { OwnerSession } from "../../src/shared/api/OwnerSession";
import {
  RESPONSE_BYTES_MAX,
  RESPONSE_DEPTH_MAX,
} from "../../src/shared/api/responseBody";
import type { RequestOf, Schema } from "../../src/shared/api/contracts";
import { deferred, scriptedFetch } from "../harness/fixtures";
import {
  apiError,
  config,
  confirmation,
  identity,
  listingDetail,
  meta,
  operationFixture,
  requestId,
  schemaFixture,
  searchResult,
  seed,
  shortlist,
} from "./apiFixtures";

function recognized() {
  const owner = new OwnerSession();
  owner.accept(0, identity());
  return owner;
}

async function failure(promise: Promise<unknown>): Promise<ClientFailure> {
  try {
    await promise;
  } catch (error) {
    expect(error).toBeInstanceOf(ClientFailure);
    return error as ClientFailure;
  }
  throw new Error("Expected a controlled client failure");
}

describe("FE-02 real generated runtime validation", () => {
  test("default browser transport preserves the native global receiver", async () => {
    const payload = config();
    const transport = vi.fn(function (this: unknown) {
      if (this !== globalThis) throw new TypeError("Illegal invocation");
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", transport);
    const owner = new OwnerSession();
    try {
      expect(await new ApiClient(owner).read("get_config", {})).toEqual(
        payload,
      );
      expect(transport).toHaveBeenCalledTimes(1);
      expect(transport).toHaveBeenCalledWith(
        "/api/v1/config",
        expect.objectContaining({ method: "GET", credentials: "same-origin" }),
      );
    } finally {
      vi.unstubAllGlobals();
      owner.dispose();
    }
  });

  test("valid configuration remains unchanged; unknown versions and optional capabilities fail", async () => {
    const payload = config();
    const transport = vi.fn(
      scriptedFetch([{ method: "GET", path: "/api/v1/config", body: payload }]),
    );
    const result = await new ApiClient(new OwnerSession(), transport).read(
      "get_config",
      {},
    );
    expect(result).toEqual(payload);
    expect(result.data.limits).toEqual({}); // No generated default insertion.
    expect(
      validateSchema("PublicConfig", { ...payload.data, mode: "live_dealer" }),
    ).toBe(false);
    expect(
      validateSchema("PublicConfig", {
        ...payload.data,
        optional_features: ["analytics"],
      }),
    ).toBe(false);
    expect(
      validateSchema("Capability", {
        state: "ready",
        reason: null,
        owner_id: "injected",
      }),
    ).toBe(false);
    expect(
      validateSchema("Capability", { state: "verified_live", reason: null }),
    ).toBe(false);
  });

  test.each(["contract_version", "policy_version"] as const)(
    "missing explicit wire %s is not supplied from schema defaults",
    async (field) => {
      const payload = config();
      Reflect.deleteProperty(payload.meta, field);
      const request = scriptedFetch([
        { method: "GET", path: "/api/v1/config", body: payload },
      ]);
      expect(
        await failure(
          new ApiClient(new OwnerSession(), request).read("get_config", {}),
        ),
      ).toMatchObject({ kind: "invalid-response" });
    },
  );

  test.each([
    ["not-observed-is-uncertain", true],
    ["not-observed-is-not-failure", false],
    ["restore-generation-unresolved", true],
    ["restore-may-not-auto-replay", false],
    ["durable-rejection", true],
    ["rejection-cannot-have-booking", false],
  ] as const)("validates the operation union: %s", (id, valid) => {
    expect(
      validateResponse("get_operation", 200, {
        meta: meta(identity().context_id),
        data: operationFixture(id),
      }),
    ).toBe(valid);
  });

  test("real zero stays a numeric value; a string revision and fabricated fact union fail", () => {
    expect(
      validateSchema("PreferenceRecord", {
        entries: [],
        revision: 0,
        collection_mode: "explicit_save",
      }),
    ).toBe(true);
    expect(
      validateSchema("PreferenceRecord", {
        entries: [],
        revision: "0",
        collection_mode: "explicit_save",
      }),
    ).toBe(false);
    expect(
      validateSchema("UnknownFact", {
        status: "unknown",
        reason: "not_stated",
        value: 0,
      }),
    ).toBe(false);
  });
});

describe("FE-02 transport errors and request boundaries", () => {
  test.each([
    [401, "IDENTITY_REQUIRED"],
    [403, "CSRF_DENIED"],
    [404, "NOT_FOUND"],
    [409, "REVISION_CONFLICT"],
    [413, "INPUT_TOO_LARGE"],
    [422, "VALIDATION_ERROR"],
    [429, "RATE_LIMITED"],
    [503, "STORE_UNAVAILABLE"],
  ] as const)(
    "keeps HTTP %i distinct without a generic retry",
    async (status, code) => {
      const owner = recognized();
      const request = vi.fn(
        scriptedFetch([
          {
            method: "GET",
            path: "/api/v1/shortlist",
            status,
            body: apiError(code),
          },
        ]),
      );
      const error = await failure(
        new ApiClient(owner, request).read("get_shortlist", {}),
      );
      expect(error).toMatchObject({ kind: "api", status });
      expect(error.detail).toMatchObject({
        code,
        request_id: requestId,
        fields: [{ path: ["filters", "budget"], code: "invalid_range" }],
      });
      if (status === 401) expect(owner.capture().contextId).toBeNull();
      expect(request).toHaveBeenCalledOnce();
    },
  );

  test.each([
    () =>
      new Response("{", { headers: { "Content-Type": "application/json" } }),
    () =>
      new Response("<html>not JSON</html>", {
        headers: { "Content-Type": "text/html" },
      }),
    () =>
      new Response(JSON.stringify({ data: {}, meta: meta() }), {
        headers: { "Content-Type": "application/json" },
      }),
    () =>
      new Response("{}", {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
  ])(
    "malformed/unreadable/unexpected success is never empty success",
    async (reply) => {
      const request = vi.fn(async () => reply());
      expect(
        await failure(
          new ApiClient(new OwnerSession(), request).read("get_config", {}),
        ),
      ).toMatchObject({ kind: "invalid-response" });
      expect(request).toHaveBeenCalledOnce();
    },
  );

  test("oversized and deeply nested response bodies fail closed", async () => {
    for (const response of [
      new Response(" ".repeat(RESPONSE_BYTES_MAX + 1), {
        headers: { "Content-Type": "application/json" },
      }),
      new Response(
        "[".repeat(RESPONSE_DEPTH_MAX + 1) +
          "0" +
          "]".repeat(RESPONSE_DEPTH_MAX + 1),
        { headers: { "Content-Type": "application/json" } },
      ),
    ]) {
      expect(
        await failure(
          new ApiClient(new OwnerSession(), async () => response).read(
            "get_config",
            {},
          ),
        ),
      ).toMatchObject({ kind: "invalid-response" });
    }
  });

  test("private mutation uses current headers, same-origin credentials, unchanged action/review identity", async () => {
    const owner = recognized();
    const body = confirmation();
    const response = {
      meta: meta(identity().context_id),
      data: operationFixture("not-observed-is-uncertain"),
    };
    const request = vi.fn(
      scriptedFetch([
        {
          method: "POST",
          path: "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000011/confirm",
          contextId: identity().context_id,
          body: response,
        },
      ]),
    );
    const result = await new ApiClient(owner, request).mutate(
      "confirm_booking_draft",
      { path: { draft_id: "00000000-0000-4000-8000-000000000011" }, body },
    );
    expect(result.data.state).toBe("not_observed");
    const init = request.mock.calls[0]![1]!;
    const headers = new Headers(init.headers);
    expect(headers.get("X-Identity-Context")).toBe(identity().context_id);
    expect(headers.get("X-CSRF-Token")).toBe(identity().csrf_token);
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.has("Origin")).toBe(false); // The browser supplies its real Origin.
    expect(init).toMatchObject({
      credentials: "same-origin",
      mode: "same-origin",
      cache: "no-store",
      redirect: "error",
    });
    expect(init.signal?.aborted).toBe(false);
    expect(JSON.parse(String(init.body))).toEqual(body);
    expect(request).toHaveBeenCalledOnce();
  });

  test.each([
    "Origin",
    "origin",
    "X-Identity-Context",
    "x-identity-context",
    "X-CSRF-Token",
    "x-csrf-token",
  ])("rejects caller override of %s before dispatch", async (header) => {
    const request = vi.fn(scriptedFetch([]));
    const api = new ApiClient(recognized(), request);
    const input = {
      headers: { [header]: "override" },
    } as unknown as RequestOf<"get_shortlist">;
    expect(await failure(api.read("get_shortlist", input))).toMatchObject({
      kind: "invalid-request",
    });
    expect(request).not.toHaveBeenCalled();
  });

  test("rejects injected owner fields and request-size overflow without sending", async () => {
    const request = vi.fn(scriptedFetch([]));
    const api = new ApiClient(new OwnerSession(), request);
    for (const body of [
      {
        notice_version: "DEMO-POLICY-1",
        notice_acknowledged: true,
        owner_id: seed.owners[1]!.owner_id,
      },
      {
        notice_version: "DEMO-POLICY-1",
        notice_acknowledged: true,
        display_name: "x".repeat(70_000),
      },
    ]) {
      expect(
        await failure(
          api.mutate("bootstrap_identity", {
            body,
          } as RequestOf<"bootstrap_identity">),
        ),
      ).toMatchObject({ kind: "invalid-request" });
    }
    expect(request).not.toHaveBeenCalled();
  });

  test.each([undefined, null])(
    "omits an optional %s query value without coercing it to text",
    async (cursor) => {
      const request = vi.fn(
        scriptedFetch([
          { method: "GET", path: "/api/v1/shortlist", body: shortlist() },
        ]),
      );
      await new ApiClient(recognized(), request).read("get_shortlist", {
        query: { cursor, page_size: undefined },
      });
      expect(String(request.mock.calls[0]![0])).toBe("/api/v1/shortlist");
    },
  );

  test("accepts lowercase caller-owned DELETE headers, preserves zero revision, and rejects duplicate casing", async () => {
    const ref = listingDetail().listing.ref;
    const data = schemaFixture("MembershipResult", {
      ref,
      client_action_id: identity().context_id,
      applied_revision: 0,
      current_revision: 0,
      changed_at_apply: false,
      reference_state: "current",
      replayed: false,
      saved: false,
    });
    const request = vi.fn(
      scriptedFetch([
        {
          method: "DELETE",
          path: `/api/v1/shortlist/${ref.namespace}/${ref.snapshot_id}/${ref.source_id}`,
          body: { meta: meta(identity().context_id), data },
        },
      ]),
    );
    const api = new ApiClient(recognized(), request);
    const headers = {
      "x-client-action-id": data.client_action_id,
      "x-expected-revision": 0,
    };
    const input = {
      path: ref,
      headers,
    } as unknown as RequestOf<"remove_shortlist_membership">;
    expect(
      (await api.mutate("remove_shortlist_membership", input)).data,
    ).toEqual(data);
    expect(
      new Headers(request.mock.calls[0]![1]!.headers).get(
        "X-Expected-Revision",
      ),
    ).toBe("0");
    const duplicate = {
      path: ref,
      headers: { ...headers, "X-Client-Action-ID": identity(1).context_id },
    } as unknown as RequestOf<"remove_shortlist_membership">;
    expect(
      await failure(api.mutate("remove_shortlist_membership", duplicate)),
    ).toMatchObject({ kind: "invalid-request" });
    expect(request).toHaveBeenCalledOnce();
  });
});

describe("FE-02 completed transport cleanup", () => {
  test("a successful identity read never emits a cleanup abort or retains cancellation hooks", async () => {
    const owner = new OwnerSession();
    const caller = new AbortController();
    const payload = { meta: meta(identity().context_id), data: identity() };
    const request = vi.fn(
      scriptedFetch([
        { method: "GET", path: "/api/v1/identity", body: payload },
      ]),
    );
    try {
      expect(
        await new ApiClient(owner, request).read("get_identity", {
          signal: caller.signal,
        }),
      ).toEqual(payload);
      const signal = request.mock.calls[0]![1]!.signal!;
      expect(signal.aborted).toBe(false);
      caller.abort();
      owner.invalidate();
      await vi.advanceTimersByTimeAsync(8_001);
      expect(signal.aborted).toBe(false);
      expect(request).toHaveBeenCalledOnce();
    } finally {
      owner.dispose();
    }
  });

  test("a response rejected before consuming its body still aborts transport", async () => {
    const request = vi.fn<typeof fetch>(
      async () =>
        new Response("<html>not JSON</html>", {
          headers: { "Content-Type": "text/html" },
        }),
    );
    const owner = new OwnerSession();
    try {
      expect(
        await failure(new ApiClient(owner, request).read("get_identity", {})),
      ).toMatchObject({ kind: "invalid-response", recovery: "read" });
      expect(request.mock.calls[0]![1]!.signal?.aborted).toBe(true);
      expect(request).toHaveBeenCalledOnce();
    } finally {
      owner.dispose();
    }
  });

  test.each([
    ["caller", "cancelled"],
    ["owner", "stale-owner"],
    ["deadline", "timeout"],
  ] as const)(
    "%s still cancels an incomplete identity body",
    async (trigger, kind) => {
      const owner = new OwnerSession();
      const caller = new AbortController();
      const cancelled = vi.fn();
      const response = new Response(
        new ReadableStream<Uint8Array>({ cancel: cancelled }),
        { headers: { "Content-Type": "application/json" } },
      );
      const request = vi.fn<typeof fetch>(async () => response);
      try {
        const pending = failure(
          new ApiClient(owner, request).read("get_identity", {
            signal: caller.signal,
          }),
        );
        await vi.advanceTimersByTimeAsync(0);
        expect(request.mock.calls[0]![1]!.signal?.aborted).toBe(false);
        if (trigger === "caller") caller.abort();
        else if (trigger === "owner") owner.invalidate();
        else await vi.advanceTimersByTimeAsync(8_001);
        expect(await pending).toMatchObject({ kind, recovery: "read" });
        expect(request.mock.calls[0]![1]!.signal?.aborted).toBe(true);
        expect(cancelled).toHaveBeenCalledOnce();
        expect(request).toHaveBeenCalledOnce();
      } finally {
        owner.dispose();
      }
    },
  );
});

describe("FE-02 bounded retries, cancellation and exact associations", () => {
  test("read-only POST retries the same request at most once", async () => {
    const result = searchResult();
    const request = vi.fn(
      scriptedFetch([
        {
          method: "POST",
          path: "/api/v1/inventory/search",
          status: 503,
          body: apiError("STORE_UNAVAILABLE", true),
        },
        { method: "POST", path: "/api/v1/inventory/search", body: result },
      ]),
    );
    const pending = new ApiClient(new OwnerSession(), request).read(
      "search_inventory",
      {
        body: {
          client_request_id: result.data.client_request_id,
          snapshot_id: result.data.presentation.snapshot_id,
          page_size: 12,
          query: "",
          soft_preferences: [],
        },
      },
    );
    await vi.advanceTimersByTimeAsync(250);
    expect(await pending).toEqual(result);
    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls[0]![1]!.body).toBe(
      request.mock.calls[1]![1]!.body,
    );
  });

  test("transient reads stop after two attempts", async () => {
    const request = vi.fn(
      scriptedFetch(
        Array.from({ length: 2 }, () => ({
          method: "GET",
          path: "/api/v1/config",
          status: 503,
          body: apiError("STORE_UNAVAILABLE", true),
        })),
      ),
    );
    const pending = failure(
      new ApiClient(new OwnerSession(), request).read("get_config", {}),
    );
    await vi.advanceTimersByTimeAsync(250);
    expect(await pending).toMatchObject({ kind: "api", status: 503 });
    expect(request).toHaveBeenCalledTimes(2);
  });

  test("a Retry-After beyond the total deadline cannot extend a read or cause another request", async () => {
    const request = vi.fn(
      async () =>
        new Response(JSON.stringify(apiError("RATE_LIMITED", true)), {
          status: 429,
          headers: { "Content-Type": "application/json", "Retry-After": "60" },
        }),
    );
    const pending = failure(
      new ApiClient(new OwnerSession(), request).read("get_config", {}),
    );
    await vi.advanceTimersByTimeAsync(8_001);
    expect(await pending).toMatchObject({ kind: "timeout", recovery: "read" });
    expect(request).toHaveBeenCalledOnce();
  });

  test("lost mutation response cannot replay or mint a new operation identity", async () => {
    const body = confirmation();
    const accepted = vi.fn();
    const request = vi.fn(
      scriptedFetch([
        {
          method: "POST",
          path: "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000011/confirm",
          body: {},
          onAccept: accepted,
          loseResponse: true,
        },
      ]),
    );
    const error = await failure(
      new ApiClient(recognized(), request).mutate("confirm_booking_draft", {
        path: { draft_id: "00000000-0000-4000-8000-000000000011" },
        body,
      }),
    );
    await vi.advanceTimersByTimeAsync(30_001);
    expect(error).toMatchObject({
      kind: "network",
      recovery: "reconcile-original",
    });
    expect(accepted).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledOnce();
    expect(JSON.parse(String(request.mock.calls[0]![1]!.body))).toEqual(body);
  });

  test("abort after dispatch preserves unknown outcome even when the finite fake completes later", async () => {
    const gate = deferred<void>();
    const accepted = vi.fn();
    const request = vi.fn(
      scriptedFetch([
        {
          method: "POST",
          path: "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000011/confirm",
          body: {},
          gate: gate.promise,
          onAccept: accepted,
        },
      ]),
    );
    const controller = new AbortController();
    const pending = failure(
      new ApiClient(recognized(), request).mutate("confirm_booking_draft", {
        path: { draft_id: "00000000-0000-4000-8000-000000000011" },
        body: confirmation(),
        signal: controller.signal,
      }),
    );
    controller.abort();
    expect(await pending).toMatchObject({
      kind: "cancelled",
      recovery: "reconcile-original",
    });
    gate.resolve();
    await Promise.resolve();
    expect(accepted).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledOnce();
  });

  test("valid detail uses nested listing.ref; a different car is rejected", async () => {
    const detail = listingDetail();
    const ref = detail.listing.ref;
    const path = `/api/v1/listings/${ref.namespace}/${ref.snapshot_id}/${ref.source_id}`;
    const mismatched = listingDetail();
    mismatched.listing.ref.source_id = "different";
    const request = scriptedFetch([
      { method: "GET", path, body: { meta: meta(), data: detail } },
      { method: "GET", path, body: { meta: meta(), data: mismatched } },
    ]);
    const api = new ApiClient(new OwnerSession(), request);
    expect((await api.read("get_listing", { path: ref })).data).toEqual(detail);
    expect(await failure(api.read("get_listing", { path: ref }))).toMatchObject(
      { kind: "invalid-response" },
    );
  });

  test("comparison preserves current/missing variants and rejects swapped candidate order", async () => {
    const detail = listingDetail();
    const second = { ...detail.listing.ref, source_id: "second" };
    const items = [detail, { state: "missing", ref: second }];
    const request = scriptedFetch([
      {
        method: "POST",
        path: "/api/v1/comparisons",
        body: { meta: meta(), data: { items } },
      },
      {
        method: "POST",
        path: "/api/v1/comparisons",
        body: { meta: meta(), data: { items: [...items].reverse() } },
      },
    ]);
    const api = new ApiClient(new OwnerSession(), request);
    const body = { refs: [detail.listing.ref, second] };
    expect((await api.read("compare_listings", { body })).data.items).toEqual(
      items,
    );
    expect(await failure(api.read("compare_listings", { body }))).toMatchObject(
      { kind: "invalid-response" },
    );
  });

  test("durable 409 rejection is a typed outcome, and a mismatched review never replaces this request", async () => {
    const body = confirmation();
    const rejected = {
      ...(operationFixture("durable-rejection") as Schema<"OperationRejected">),
      review_id: body.review_id,
      original_store_generation: body.store_generation,
    };
    const request = scriptedFetch([
      {
        method: "POST",
        path: "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000011/confirm",
        status: 409,
        body: { meta: meta(identity().context_id), data: rejected },
      },
      {
        method: "POST",
        path: "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000011/confirm",
        status: 409,
        body: {
          meta: meta(identity().context_id),
          data: { ...rejected, review_id: seed.owners[0]!.context_id },
        },
      },
    ]);
    const api = new ApiClient(recognized(), request);
    expect(
      (
        await api.mutate("confirm_booking_draft", {
          path: { draft_id: "00000000-0000-4000-8000-000000000011" },
          body,
        })
      ).data,
    ).toEqual(rejected);
    expect(
      await failure(
        api.mutate("confirm_booking_draft", {
          path: { draft_id: "00000000-0000-4000-8000-000000000011" },
          body,
        }),
      ),
    ).toMatchObject({
      kind: "invalid-response",
      recovery: "reconcile-original",
    });
  });

  test("a private response for another context is discarded and local context purged", async () => {
    const owner = recognized();
    const request = scriptedFetch([
      {
        method: "GET",
        path: "/api/v1/shortlist",
        body: shortlist(identity(1).context_id),
      },
    ]);
    expect(
      await failure(new ApiClient(owner, request).read("get_shortlist", {})),
    ).toMatchObject({ kind: "stale-owner" });
    expect(owner.capture().contextId).toBeNull();
  });
});
