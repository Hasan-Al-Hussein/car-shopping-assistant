import {
  focusManager,
  isCancelledError,
  onlineManager,
} from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";
import { ApiClient } from "../../src/shared/api/ApiClient";
import { OwnerSession } from "../../src/shared/api/OwnerSession";
import { LatestRead } from "../../src/shared/api/LatestRead";
import { createQueryPolicy } from "../../src/app/queryPolicy";
import { bindOwnerInvalidation } from "../../src/app/ownerInvalidation";
import { deferred, scriptedFetch } from "../harness/fixtures";
import {
  apiError,
  config,
  confirmation,
  identity,
  listingDetail,
  meta,
  shortlist,
} from "./apiFixtures";

function setup(fetcher: typeof fetch = scriptedFetch([])) {
  const owner = new OwnerSession();
  owner.accept(0, identity());
  const api = new ApiClient(owner, fetcher);
  const policy = createQueryPolicy(owner, api);
  const dispose = () => {
    policy.dispose();
    owner.dispose();
  };
  cleanups.push(dispose);
  return { owner, api, policy };
}

const cleanups: (() => void)[] = [];
afterEach(() => {
  cleanups
    .splice(0)
    .reverse()
    .forEach((dispose) => dispose());
  focusManager.setFocused(undefined);
  onlineManager.setOnline(true);
});

const outcome = (promise: Promise<unknown>) =>
  promise.then(
    (value) => ({ value, error: undefined }),
    (error: unknown) => ({ value: undefined, error }),
  );

describe("FE-02 owner epochs and memory-only cache", () => {
  test("focus retains cached private state while checking and after the same owner is confirmed", async () => {
    const gate = deferred<void>();
    const { owner, api, policy } = setup(
      scriptedFetch([
        {
          method: "GET",
          path: "/api/v1/identity",
          body: { meta: meta(identity().context_id), data: identity() },
          gate: gate.promise,
        },
      ]),
    );
    const snapshot = owner.capture();
    const key = policy.privateRead("get_shortlist", {}).queryKey;
    policy.client.setQueryData(key, shortlist());
    const changed = vi.fn();
    const unsubscribe = owner.subscribe(changed);
    const binding = bindOwnerInvalidation(
      owner,
      () => api.revalidateIdentity(),
      window,
    );
    cleanups.push(() => {
      binding.dispose();
      unsubscribe();
    });
    window.dispatchEvent(new Event("focus"));
    expect(owner.capture()).toEqual(snapshot);
    expect(policy.client.getQueryData(key)).toEqual(shortlist());
    gate.resolve();
    await vi.advanceTimersByTimeAsync(0);
    expect(owner.capture()).toEqual(snapshot);
    expect(policy.client.getQueryData(key)).toEqual(shortlist());
    expect(changed).not.toHaveBeenCalled();
  });

  test("a different owner returned by revalidation still purges the former owner's cache", async () => {
    const { owner, api, policy } = setup(
      scriptedFetch([
        {
          method: "GET",
          path: "/api/v1/identity",
          body: { meta: meta(identity(1).context_id), data: identity(1) },
        },
      ]),
    );
    const key = policy.privateRead("get_shortlist", {}).queryKey;
    policy.client.setQueryData(key, shortlist());
    await api.revalidateIdentity();
    expect(owner.capture().contextId).toBe(identity(1).context_id);
    expect(policy.client.getQueryData(key)).toBeUndefined();
  });
  test("late A response cannot refill cache after switching to B with the same display name", async () => {
    const gate = deferred<void>();
    const fetcher = vi.fn(
      scriptedFetch([
        {
          method: "GET",
          path: "/api/v1/shortlist",
          contextId: identity().context_id,
          body: shortlist(),
          gate: gate.promise,
        },
        {
          method: "GET",
          path: "/api/v1/shortlist",
          contextId: identity(1).context_id,
          body: shortlist(identity(1).context_id),
        },
      ]),
    );
    const { owner, policy } = setup(fetcher);
    const privateA = policy.privateRead(
      "get_shortlist",
      {},
      { entityRevision: 1 },
    );
    policy.client.setQueryData(["public", "snapshot", "fixture"], config());
    const old = outcome(policy.client.fetchQuery(privateA));
    owner.accept(owner.invalidate(), identity(1));
    expect(policy.client.getQueryData(privateA.queryKey)).toBeUndefined();
    const privateB = policy.privateRead(
      "get_shortlist",
      {},
      { entityRevision: 1 },
    );
    expect(privateB.queryKey).not.toEqual(privateA.queryKey);
    expect(await policy.client.fetchQuery(privateB)).toEqual(
      shortlist(identity(1).context_id),
    );
    gate.resolve();
    expect((await old).error).toBeDefined();
    await Promise.resolve();
    await Promise.resolve();
    expect(policy.client.getQueryData(privateA.queryKey)).toBeUndefined();
    expect(policy.client.getQueryData(privateB.queryKey)).toEqual(
      shortlist(identity(1).context_id),
    );
    expect(
      policy.client.getQueryData(["public", "snapshot", "fixture"]),
    ).toEqual(config());
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test("expiry purges cached data and cancels a pending private reply without another capture", async () => {
    const gate = deferred<void>();
    const { owner, api, policy } = setup(
      scriptedFetch([
        {
          method: "GET",
          path: "/api/v1/shortlist",
          body: shortlist(),
          gate: gate.promise,
        },
      ]),
    );
    owner.accept(owner.invalidate(), {
      ...identity(),
      expires_at: new Date(Date.now() + 500).toISOString(),
    });
    const key = policy.privateRead("get_shortlist", {}).queryKey;
    policy.client.setQueryData(key, shortlist());
    const pending = outcome(api.read("get_shortlist", {}));
    await vi.advanceTimersByTimeAsync(501);
    expect(policy.client.getQueryData(key)).toBeUndefined();
    expect((await pending).error).toMatchObject({ kind: "stale-owner" });
    gate.resolve();
    expect(owner.capture().contextId).toBeNull();
  });

  test("30-day expiry is chunked and a previous timer cannot invalidate the replacement", async () => {
    const { owner } = setup();
    owner.accept(owner.invalidate(), {
      ...identity(),
      expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
    });
    await vi.advanceTimersByTimeAsync(2_147_483_648);
    expect(owner.capture().contextId).toBe(identity().context_id);
    owner.accept(owner.invalidate(), {
      ...identity(1),
      expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
    });
    await vi.advanceTimersByTimeAsync(5 * 86_400_000);
    expect(owner.capture().contextId).toBe(identity(1).context_id);
    owner.dispose();
    expect(vi.getTimerCount()).toBe(0);
  });

  test.each(["html", "malformed", "oversized", "hanging"] as const)(
    "a %s 401 purges before parsing diagnostics",
    async (variant) => {
      const response =
        variant === "hanging"
          ? new Response(new ReadableStream<Uint8Array>({ start() {} }), {
              status: 401,
              headers: { "Content-Type": "application/json" },
            })
          : new Response(
              variant === "html"
                ? "<html>denied</html>"
                : variant === "malformed"
                  ? "{"
                  : " ".repeat(4 * 1024 * 1024 + 1),
              {
                status: 401,
                headers: {
                  "Content-Type":
                    variant === "html" ? "text/html" : "application/json",
                },
              },
            );
      const { owner, api, policy } = setup(async () => response);
      const key = policy.privateRead("get_shortlist", {}).queryKey;
      policy.client.setQueryData(key, shortlist());
      const pending = outcome(api.read("get_shortlist", {}));
      await vi.advanceTimersByTimeAsync(0);
      expect(owner.capture().contextId).toBeNull();
      expect(policy.client.getQueryData(key)).toBeUndefined();
      if (variant === "hanging") await vi.advanceTimersByTimeAsync(8_001);
      expect((await pending).error).toMatchObject({ kind: "api", status: 401 });
    },
  );

  test("an old 401 cannot purge a replacement owner", async () => {
    const gate = deferred<void>();
    const { owner, api } = setup(
      scriptedFetch([
        {
          method: "GET",
          path: "/api/v1/shortlist",
          status: 401,
          body: {},
          gate: gate.promise,
        },
      ]),
    );
    const pending = outcome(api.read("get_shortlist", {}));
    owner.accept(owner.invalidate(), identity(1));
    gate.resolve();
    expect((await pending).error).toMatchObject({ kind: "stale-owner" });
    expect(owner.capture().contextId).toBe(identity(1).context_id);
  });

  test("a composed private-query 401 cancels the removed query while the owner boundary hides data", async () => {
    const { owner, policy } = setup(
      scriptedFetch([
        {
          method: "GET",
          path: "/api/v1/shortlist",
          status: 401,
          body: apiError("IDENTITY_REQUIRED"),
        },
      ]),
    );
    const options = policy.privateRead("get_shortlist", {});
    const result = await outcome(policy.client.fetchQuery(options));
    expect(result.value).toBeUndefined();
    expect(isCancelledError(result.error)).toBe(true);
    expect(owner.capture().contextId).toBeNull();
    expect(policy.client.getQueryData(options.queryKey)).toBeUndefined();
    // The cancelled query must not be repopulated to display its safe error reference.
    // Direct ApiClient callers have separate structured-error coverage.
  });

  test.each([false, true])(
    "ending identity stays hidden across focus even when response is lost=%s",
    async (lost) => {
      const gate = deferred<void>();
      const fetcher = vi.fn(
        scriptedFetch([
          {
            method: "POST",
            path: "/api/v1/identity/end",
            contextId: identity().context_id,
            body: {
              meta: meta(identity().context_id),
              data: { state: "ended" },
            },
            gate: gate.promise,
            loseResponse: lost,
          },
          {
            method: "GET",
            path: "/api/v1/identity",
            body: { meta: meta(identity().context_id), data: identity() },
          },
          {
            method: "POST",
            path: "/api/v1/identity/bootstrap",
            body: { meta: meta(identity(1).context_id), data: identity(1) },
          },
        ]),
      );
      const { owner, api, policy } = setup(fetcher);
      const binding = bindOwnerInvalidation(
        owner,
        () => api.revalidateIdentity(),
        window,
      );
      cleanups.push(() => binding.dispose());
      const key = policy.privateRead("get_shortlist", {}).queryKey;
      policy.client.setQueryData(key, shortlist());
      const pending = outcome(
        api.endIdentity({ acknowledge_loss_of_access: true }),
      );
      expect(owner.capture().contextId).toBeNull();
      expect(policy.client.getQueryData(key)).toBeUndefined();
      window.dispatchEvent(new Event("focus"));
      await vi.advanceTimersByTimeAsync(0);
      expect(owner.capture().contextId).toBeNull(); // GET of A must not resurrect A.
      await api.bootstrapIdentity({
        notice_version: "DEMO-POLICY-1",
        notice_acknowledged: true,
      });
      expect(owner.capture().contextId).toBe(identity(1).context_id);
      gate.resolve();
      const result = await pending;
      if (lost)
        expect(result.error).toMatchObject({ recovery: "reconcile-original" });
      else expect(result.value).toMatchObject({ data: { state: "ended" } });
      expect(owner.capture().contextId).toBe(identity(1).context_id); // Late end cannot clear B.
      expect(fetcher).toHaveBeenCalledTimes(3);
    },
  );

  test("public keys normalize criteria and snapshot the request while preserving source characters", async () => {
    const detail = listingDetail();
    const ref = detail.listing.ref;
    const fetcher = vi.fn(
      scriptedFetch([
        {
          method: "GET",
          path: `/api/v1/listings/${ref.namespace}/${ref.snapshot_id}/${ref.source_id}`,
          body: { meta: meta(), data: detail },
        },
      ]),
    );
    const { policy } = setup(fetcher);
    const request = { path: { ...ref } };
    const first = policy.publicRead("get_listing", request, ref.snapshot_id);
    const second = policy.publicRead(
      "get_listing",
      {
        path: {
          source_id: ref.source_id,
          snapshot_id: ref.snapshot_id,
          namespace: ref.namespace,
        },
      },
      ref.snapshot_id,
    );
    expect(first.queryKey).toEqual(second.queryKey);
    expect(
      policy.publicRead("get_listing", request, "other-snapshot").queryKey,
    ).not.toEqual(first.queryKey);
    request.path.source_id = "changed after key creation";
    expect((await policy.client.fetchQuery(first)).data).toEqual(detail);
  });

  test("focus/reconnect never resume or repeat an uncertain mutation", async () => {
    const fetcher = vi.fn(
      scriptedFetch([
        {
          method: "POST",
          path: "/api/v1/booking-drafts/00000000-0000-4000-8000-000000000011/confirm",
          body: {},
          loseResponse: true,
        },
      ]),
    );
    const { api, policy } = setup(fetcher);
    policy.client.mount();
    cleanups.push(() => policy.client.unmount());
    onlineManager.setOnline(false);
    const mutation = policy.client.getMutationCache().build(policy.client, {
      mutationFn: () =>
        api.mutate("confirm_booking_draft", {
          path: { draft_id: "00000000-0000-4000-8000-000000000011" },
          body: confirmation(),
        }),
    });
    expect((await outcome(mutation.execute(undefined))).error).toMatchObject({
      recovery: "reconcile-original",
    });
    expect(mutation.state.isPaused).toBe(false);
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    onlineManager.setOnline(true);
    window.dispatchEvent(new PopStateEvent("popstate"));
    await vi.advanceTimersByTimeAsync(30_001);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(policy.client.getDefaultOptions().queries).toMatchObject({
      retry: false,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      refetchOnMount: false,
    });
  });
});

describe("FE-02 lifecycle integration seams", () => {
  test("a newer read rejects the older result even if its transport ignores abort", async () => {
    const old = deferred<string>();
    const latest = new LatestRead();
    const first = outcome(latest.run(() => old.promise));
    expect(await latest.run(async () => "new result")).toBe("new result");
    old.resolve("obsolete result");
    expect((await first).error).toMatchObject({ kind: "superseded" });
  });

  test("cross-tab messages carry only invalidation and BFCache restore rechecks identity", async () => {
    const events = new EventTarget();
    const channel = {
      addEventListener: events.addEventListener.bind(events),
      removeEventListener: events.removeEventListener.bind(events),
      postMessage: vi.fn(),
      close: vi.fn(),
    };
    const { owner } = setup();
    const revalidate = vi.fn(async () => undefined);
    const binding = bindOwnerInvalidation(owner, revalidate, window, channel);
    cleanups.push(() => binding.dispose());
    events.dispatchEvent(
      new MessageEvent("message", {
        data: {
          context_id: identity(1).context_id,
          csrf_token: "never accept",
        },
      }),
    );
    expect(owner.capture().contextId).toBe(identity().context_id);
    expect(revalidate).not.toHaveBeenCalled();
    events.dispatchEvent(new MessageEvent("message", { data: "invalidate" }));
    expect(owner.capture().contextId).toBeNull();
    await vi.advanceTimersByTimeAsync(0);
    window.dispatchEvent(
      new PageTransitionEvent("pageshow", { persisted: true }),
    );
    await vi.advanceTimersByTimeAsync(0);
    expect(revalidate).toHaveBeenCalledTimes(2);
    binding.notifyOtherTabs();
    expect(channel.postMessage).toHaveBeenCalledWith("invalidate");
    binding.dispose();
    window.dispatchEvent(new Event("focus"));
    expect(revalidate).toHaveBeenCalledTimes(2);
  });
});
