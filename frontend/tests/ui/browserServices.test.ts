import { afterEach, describe, expect, test, vi } from "vitest";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ClientFailure } from "../../src/shared/api/ClientFailure";
import type { Schema } from "../../src/shared/api/contracts";
import { deferred } from "../harness/fixtures";
import { apiError, identity, meta, schemaFixture } from "./apiFixtures";
import semantic from "../../../contracts/fixtures/semantic_cases.json";
import {
  conversationEnvelope,
  conversationSession,
  otherConversationId,
} from "./conversationFixtures";

const services: BrowserServices[] = [];
afterEach(() => services.splice(0).forEach((service) => service.dispose()));
const anonymous: Schema<"AnonymousIdentity"> = {
  state: "anonymous",
  notice_version: "DEMO-POLICY-1",
};
const flush = async () => {
  for (let i = 0; i < 8; i++) await Promise.resolve();
};
function setup(
  initial:
    Schema<"RecognizedIdentity"> | Schema<"AnonymousIdentity"> = anonymous,
) {
  const service = new BrowserServices();
  services.push(service);
  const read = vi
    .spyOn(service.api, "revalidateIdentity")
    .mockImplementation(async () => {
      service.owner.accept(service.owner.invalidate(), initial);
      return {
        meta: meta(initial.state === "recognized" ? initial.context_id : null),
        data: initial,
      };
    });
  service.start();
  return { service, read };
}
function nextIdentity(service: BrowserServices, value = identity(1)) {
  return async () => {
    service.owner.accept(service.owner.invalidate(), value);
    return { meta: meta(value.context_id), data: value };
  };
}

describe("V5 shell identity lifecycle, fake transport only", () => {
  test("reads attempted during session creation cannot select the old session after the new one publishes", async () => {
    const { service } = setup(identity());
    await flush();
    const old = conversationSession(),
      next = { ...old, session_id: otherConversationId };
    const read = vi
      .spyOn(service.api, "read")
      .mockResolvedValue(conversationEnvelope(old));
    await service.readSession(old.session_id);
    read.mockClear();
    const gate =
      deferred<
        ReturnType<typeof conversationEnvelope<Schema<"SessionState">>>
      >();
    vi.spyOn(service.api, "mutate").mockReturnValue(gate.promise);
    const creating = service.createSession();
    await service.readSession(old.session_id);
    expect(read).not.toHaveBeenCalled();
    gate.resolve(conversationEnvelope(next));
    await creating;
    expect(service.getSnapshot().session?.session_id).toBe(otherConversationId);
  });
  test("unknown session retry keeps the exact original action and never treats a later denial as noncommit", async () => {
    const { service } = setup(identity());
    await flush();
    const write = vi
      .spyOn(service.api, "mutate")
      .mockRejectedValueOnce(
        new ClientFailure("network", "reconcile-original"),
      );
    await service.createSession();
    const original = structuredClone(write.mock.calls[0]);
    vi.spyOn(service.api, "read").mockResolvedValue(
      conversationEnvelope(conversationSession().recalled_preferences),
    );
    write.mockRejectedValueOnce(
      new ClientFailure("api", "reidentify", {
        status: 403,
        detail: apiError("ORIGIN_DENIED").error,
      }),
    );
    await service.retryOriginalSession();
    expect(service.hasUncertainSession).toBe(true);
    write.mockResolvedValueOnce(conversationEnvelope(conversationSession()));
    await service.retryOriginalSession();
    expect(write.mock.calls[1]).toEqual(original);
    expect(write.mock.calls[2]).toEqual(original);
    expect(service.hasUncertainSession).toBe(false);
  });
  test("a changed store fences session-creation replay", async () => {
    const { service } = setup(identity());
    await flush();
    const write = vi
      .spyOn(service.api, "mutate")
      .mockRejectedValue(new ClientFailure("network", "reconcile-original"));
    await service.createSession();
    const current = conversationEnvelope(
      conversationSession().recalled_preferences,
    );
    current.meta.store_generation = otherConversationId;
    vi.spyOn(service.api, "read").mockResolvedValue(current);
    await service.retryOriginalSession();
    expect(write).toHaveBeenCalledTimes(1);
    expect(service.getSnapshot().notice).toContain("store changed");
    expect(service.hasUncertainSession).toBe(true);
  });
  test("search return handles preserve committed text and criteria without rewriting earlier history", () => {
    const service = new BrowserServices();
    services.push(service);
    const initial: Schema<"SearchRequest"> = {
      client_request_id: "90000000-0000-4000-8000-000000000001",
      query: "family needs",
      filters: {
        makes: ["a", "b"],
        models: [],
        body_types: [],
        fuel_types: [],
        transmissions: [],
        trims: [],
      },
      soft_preferences: ["quiet cabin"],
      page_size: 20,
      cursor: null,
      snapshot_id: null,
    };
    service.setBrowseRequest("first", initial);
    service.queueBrowseRequest({
      ...initial,
      query: "revised needs",
      client_request_id: "90000000-0000-4000-8000-000000000002",
    });
    expect(service.browseRequest("second", initial, "first").query).toBe(
      "revised needs",
    );
    expect(
      service.browseRequest("returned", { ...initial, query: "" }, "first"),
    ).toEqual(initial);
    expect(service.currentBrowseRequest()?.filters?.makes).toEqual(["a", "b"]);
    expect(service.hasBrowseRequest("absent")).toBe(false);
    expect(service.hasQueuedBrowseRequest).toBe(false);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
  test("mount performs a read and never creates local identity or a conversation", async () => {
    const { service, read } = setup();
    const bootstrap = vi.spyOn(service.api, "bootstrapIdentity");
    const write = vi.spyOn(service.api, "mutate");
    await flush();
    expect(read).toHaveBeenCalledTimes(1);
    expect(service.getSnapshot().phase).toBe("anonymous");
    expect(bootstrap).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test("a bootstrap crossing stop/start cannot lock the new view or publish its old identity", async () => {
    const { service, read } = setup();
    await flush();
    const gate =
      deferred<Awaited<ReturnType<typeof service.api.bootstrapIdentity>>>();
    const write = vi
      .spyOn(service.api, "bootstrapIdentity")
      .mockReturnValue(gate.promise);
    const pending = service.bootstrap("DEMO-POLICY-1", true, "Synthetic Buyer");
    service.stop();
    read.mockImplementation(nextIdentity(service));
    service.start();
    expect(read).toHaveBeenCalledTimes(1);
    gate.resolve({ meta: meta(identity().context_id), data: identity() });
    await pending;
    await flush();
    expect(read).toHaveBeenCalledTimes(2);
    expect(write).toHaveBeenCalledTimes(1);
    expect(service.getSnapshot()).toMatchObject({
      phase: "recognized",
      pending: false,
      identity: { context_id: identity(1).context_id },
    });
    expect(service.getSnapshot().identity).not.toHaveProperty("csrf_token");
  });

  test("a focus check during bootstrap queues one GET and never replays the POST", async () => {
    const { service, read } = setup();
    await flush();
    const gate =
      deferred<Awaited<ReturnType<typeof service.api.bootstrapIdentity>>>();
    const write = vi
      .spyOn(service.api, "bootstrapIdentity")
      .mockReturnValue(gate.promise);
    const pending = service.bootstrap("DEMO-POLICY-1", true, "Synthetic Buyer");
    read.mockImplementation(nextIdentity(service));
    await service.revalidate();
    await service.revalidate();
    gate.resolve({ meta: meta(identity().context_id), data: identity() });
    await pending;
    await flush();
    expect(read).toHaveBeenCalledTimes(2);
    expect(write).toHaveBeenCalledTimes(1);
    expect(service.getSnapshot().pending).toBe(false);
  });

  test("bootstrap settling while stopped cannot leave the next mount pending", async () => {
    const { service, read } = setup();
    await flush();
    const gate =
      deferred<Awaited<ReturnType<typeof service.api.bootstrapIdentity>>>();
    const write = vi
      .spyOn(service.api, "bootstrapIdentity")
      .mockReturnValue(gate.promise);
    const pending = service.bootstrap("DEMO-POLICY-1", true, "");
    service.stop();
    gate.resolve({ meta: meta(identity().context_id), data: identity() });
    await pending;
    read.mockImplementation(nextIdentity(service));
    service.start();
    await flush();
    expect(service.getSnapshot()).toMatchObject({
      phase: "recognized",
      pending: false,
      identity: { context_id: identity(1).context_id },
    });
    expect(write).toHaveBeenCalledTimes(1);
    expect(read).toHaveBeenCalledTimes(2);
  });

  test("late end-access failure cannot overwrite a restarted recognized context", async () => {
    const { service, read } = setup(identity());
    await flush();
    const gate =
      deferred<Awaited<ReturnType<typeof service.api.endIdentity>>>();
    vi.spyOn(service.api, "endIdentity").mockReturnValue(gate.promise);
    const ending = service.end(true);
    service.stop();
    read.mockImplementation(nextIdentity(service));
    service.start();
    gate.reject(new ClientFailure("network", "reidentify"));
    await ending;
    await flush();
    expect(service.getSnapshot()).toMatchObject({
      phase: "recognized",
      pending: false,
      notice: null,
      identity: { context_id: identity(1).context_id },
    });
    expect(read).toHaveBeenCalledTimes(2);
  });

  test("unparsed bootstrap denial does not claim that the server cleared a cookie", async () => {
    const { service } = setup();
    await flush();
    vi.spyOn(service.api, "bootstrapIdentity").mockRejectedValue(
      new ClientFailure("api", "reidentify", { status: 401 }),
    );
    await service.bootstrap("DEMO-POLICY-1", true, "");
    expect(service.getSnapshot().notice).toContain(
      "private information is hidden",
    );
    expect(service.getSnapshot().notice).not.toMatch(
      /credential has been cleared|cookie.*cleared/i,
    );
  });

  test.each([false, true])(
    "conversation uncertainty is retained unless denial is validated (%s)",
    async (validated) => {
      const { service } = setup(identity());
      await flush();
      const failure = new ClientFailure("api", "reidentify", {
        status: 403,
        ...(validated ? { detail: apiError("ORIGIN_DENIED").error } : {}),
      });
      const write = vi.spyOn(service.api, "mutate").mockRejectedValue(failure);
      await service.createSession();
      expect(service.getSnapshot().notice).toContain(
        validated
          ? "rejected before acceptance"
          : "retained without automatic retry",
      );
      await service.createSession();
      expect(write).toHaveBeenCalledTimes(validated ? 2 : 1);
    },
  );

  test("expiry while publishing never exposes the previous identity under the new epoch", async () => {
    const { service } = setup(identity());
    await flush();
    const observed: ReturnType<typeof service.getSnapshot>[] = [];
    service.subscribe(() => observed.push(service.getSnapshot()));
    vi.setSystemTime(new Date(Date.parse(identity().expires_at) + 1));
    vi.spyOn(service.api, "bootstrapIdentity").mockRejectedValue(
      new ClientFailure("network", "reidentify"),
    );
    await service.bootstrap("DEMO-POLICY-1", true, "");
    expect(observed.length).toBeGreaterThan(0);
    expect(
      observed.every((view) => view.identity === null && view.session === null),
    ).toBe(true);
  });

  test.each(["success", "failure"])(
    "late old-session %s cannot overwrite an explicitly created conversation",
    async (outcome) => {
      const { service } = setup(identity());
      await flush();
      const oldSession = schemaFixture(
        "SessionState",
        semantic.baselines.SessionState,
      );
      const nextSession = {
        ...oldSession,
        session_id: "90000000-0000-4000-8000-000000000099",
      };
      const gate = deferred<{
        meta: Schema<"ResponseMeta">;
        data: Schema<"SessionState">;
      }>();
      vi.spyOn(service.api, "read").mockReturnValue(gate.promise);
      const oldRead = service.readSession(oldSession.session_id);
      vi.spyOn(service.api, "mutate").mockResolvedValue({
        meta: meta(identity().context_id),
        data: nextSession,
      });
      await service.createSession();
      if (outcome === "success")
        gate.resolve({ meta: meta(identity().context_id), data: oldSession });
      else gate.reject(new ClientFailure("invalid-response", "read"));
      await oldRead;
      await flush();
      expect(service.getSnapshot().session?.session_id).toBe(
        nextSession.session_id,
      );
    },
  );
});
