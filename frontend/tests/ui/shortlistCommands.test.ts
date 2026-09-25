import { afterEach, describe, expect, test, vi } from "vitest";
import { ShortlistCommands } from "../../src/features/shortlist/ShortlistCommands";
import { ApiClient } from "../../src/shared/api/ApiClient";
import { ClientFailure } from "../../src/shared/api/ClientFailure";
import { OwnerSession } from "../../src/shared/api/OwnerSession";
import type { ResponseOf, Schema } from "../../src/shared/api/contracts";
import { refKey } from "../../src/app/routes";
import { deferred } from "../harness/fixtures";
import { apiError, identity, listingDetail, meta, seed } from "./apiFixtures";

const ref = listingDetail().listing.ref;
const other = { ...ref, source_id: "other" };
const cleanups: (() => void)[] = [];
afterEach(() => cleanups.splice(0).forEach((dispose) => dispose()));

function page(
  revision = 0,
  refs: Schema<"InventoryRef">[] = [],
  next: string | null = null,
  generation = seed.synthetic_generations[0],
): ResponseOf<"get_shortlist"> {
  return {
    meta: { ...meta(identity().context_id), store_generation: generation },
    data: {
      revision,
      total: refs.length + (next ? 1 : 0),
      next_cursor: next,
      items: refs.map((item) => ({
        ref: item,
        state: "current",
        listing: { ...listingDetail().listing, ref: item },
        added_at: "2026-09-23T18:00:00Z",
        expires_at: "2026-10-23T18:00:00Z",
      })),
    },
  };
}
function membership(
  saved = true,
  revision = 1,
): ResponseOf<"add_shortlist_membership"> {
  return {
    meta: meta(identity().context_id),
    data: {
      ref,
      saved,
      current_revision: revision,
      applied_revision: 1,
      client_action_id: "90000000-0000-4000-8000-000000000123",
      changed_at_apply: true,
      replayed: false,
      reference_state: "current",
    },
  };
}
function setup() {
  const owner = new OwnerSession();
  owner.accept(0, identity());
  const api = new ApiClient(owner),
    changed = vi.fn();
  const commands = new ShortlistCommands(owner, api, changed);
  cleanups.push(() => {
    commands.dispose();
    owner.dispose();
  });
  const read = vi.spyOn(api, "read").mockResolvedValue(page());
  const write = vi.spyOn(api, "mutate").mockResolvedValue(membership());
  return { owner, api, commands, changed, read, write };
}
const loss = () => new ClientFailure("network", "reconcile-original");
const denied = () =>
  new ClientFailure("api", "reidentify", {
    status: 403,
    detail: apiError("ORIGIN_DENIED").error,
  });

describe("U1 shortlist controller, synthetic client seam; not live persistence evidence", () => {
  test("reading membership never writes or establishes absence from a partial page", async () => {
    const { commands, owner, read, write } = setup();
    read.mockResolvedValueOnce(page(1, [ref], "next"));
    await commands.readPage(null, 1, owner.capture());
    expect(commands.getSnapshot().membership[refKey(ref)]).toBe(true);
    expect(commands.getSnapshot().membership[refKey(other)]).toBeUndefined();
    read.mockResolvedValueOnce(page(2, [other], "next"));
    await commands.readPage(null, 1, owner.capture());
    expect(commands.getSnapshot().membership[refKey(ref)]).toBeUndefined();
    read.mockResolvedValueOnce(page(3));
    await commands.readPage(null, 20, owner.capture());
    expect(commands.getSnapshot().membership[refKey(other)]).toBe(false);
    expect(write).not.toHaveBeenCalled();
  });

  test("unknown action survives failed observation and denied retry, then uses its exact original identity", async () => {
    const { commands, read, write } = setup();
    write.mockRejectedValueOnce(loss());
    await commands.change(ref, true);
    const original = structuredClone(write.mock.calls[0]);
    read.mockRejectedValueOnce(denied());
    await commands.reconcile();
    await commands.change(other, false);
    expect(write).toHaveBeenCalledTimes(1);
    expect(commands.getSnapshot().phase).toBe("unknown");
    write.mockRejectedValueOnce(denied());
    await commands.reconcile();
    expect(write.mock.calls[1]).toEqual(original);
    expect(commands.getSnapshot().phase).toBe("unknown");
    write.mockResolvedValueOnce({
      ...membership(false, 4),
      data: { ...membership(false, 4).data, replayed: true },
    });
    await commands.reconcile();
    expect(write.mock.calls[2]).toEqual(original);
    expect(commands.getSnapshot()).toMatchObject({
      phase: "idle",
      revision: 4,
      membership: { [refKey(ref)]: false },
    });
  });

  test("changed generation blocks the old action without replay or replacement", async () => {
    const { commands, read, write } = setup();
    write.mockRejectedValueOnce(loss());
    await commands.change(ref, true);
    read.mockResolvedValueOnce(
      page(0, [], null, seed.synthetic_generations[1]),
    );
    await commands.reconcile();
    await commands.change(other, true);
    expect(write).toHaveBeenCalledTimes(1);
    expect(commands.getSnapshot().phase).toBe("blocked");
  });

  test("double click is serialized and the clicked exact ref is captured before preflight", async () => {
    const { commands, read, write } = setup();
    const gate = deferred<ResponseOf<"get_shortlist">>();
    read.mockReturnValueOnce(gate.promise);
    const clicked = { ...ref };
    const first = commands.change(clicked, true);
    clicked.source_id = "changed-after-click";
    await commands.change(other, true);
    expect(write).not.toHaveBeenCalled();
    gate.resolve(page());
    await first;
    expect(write).toHaveBeenCalledTimes(1);
    expect(write.mock.calls[0]).toEqual([
      "add_shortlist_membership",
      {
        path: ref,
        body: { client_action_id: expect.any(String), expected_revision: 0 },
      },
    ]);
  });

  test("remove uses exact historical identity and original action headers, never a DELETE body", async () => {
    const { commands, write } = setup();
    write.mockRejectedValueOnce(loss());
    const historical = { ...ref, snapshot_id: "b".repeat(64) };
    await commands.change(historical, false);
    await commands.reconcile();
    expect(write.mock.calls[0]).toEqual(write.mock.calls[1]);
    expect(write.mock.calls[0]).toEqual([
      "remove_shortlist_membership",
      {
        path: historical,
        headers: {
          "X-Client-Action-ID": expect.any(String),
          "X-Expected-Revision": 0,
        },
      },
    ]);
  });

  test("late successful add cannot overwrite a newer authoritative removal", async () => {
    const { commands, owner, read, write, changed } = setup();
    const gate = deferred<ResponseOf<"add_shortlist_membership">>();
    write.mockReturnValueOnce(gate.promise);
    const pending = commands.change(ref, true);
    await vi.waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    read.mockResolvedValueOnce(page(3));
    await commands.readPage(null, 20, owner.capture());
    gate.resolve(membership(true, 1));
    await pending;
    expect(commands.getSnapshot().revision).toBe(3);
    expect(commands.getSnapshot().membership[refKey(ref)]).not.toBe(true);
    expect(commands.getSnapshot().notice).toContain(
      "newer shortlist observation",
    );
    expect(changed).toHaveBeenCalledTimes(1);
  });

  test("a delayed old-generation read cannot overwrite a newer generation", async () => {
    const { commands, owner, read } = setup();
    const gate = deferred<ResponseOf<"get_shortlist">>();
    read.mockReturnValueOnce(gate.promise);
    const oldRead = commands.readPage(null, 20, owner.capture());
    const rejected = expect(oldRead).rejects.toMatchObject({
      kind: "superseded",
    });
    read.mockResolvedValueOnce(
      page(1, [other], null, seed.synthetic_generations[1]),
    );
    await commands.readPage(null, 20, owner.capture());
    gate.resolve(page(100, [ref]));
    await rejected;
    expect(commands.getSnapshot()).toMatchObject({
      generation: seed.synthetic_generations[1],
      revision: 1,
    });
    expect(commands.getSnapshot().membership[refKey(ref)]).toBeUndefined();
  });

  test.each(["same", "different"])(
    "prior %s owner-epoch reply remains hidden",
    async (variant) => {
      const { commands, owner, read, write } = setup();
      const gate = deferred<ResponseOf<"get_shortlist">>();
      read.mockReturnValueOnce(gate.promise);
      const oldRead = commands.readPage(null, 20, owner.capture());
      const rejected = expect(oldRead).rejects.toMatchObject({
        kind: "stale-owner",
      });
      owner.accept(owner.invalidate(), identity(variant === "same" ? 0 : 1));
      gate.resolve(page(8, [ref]));
      await rejected;
      expect(commands.getSnapshot().membership).toEqual({});
      expect(write).not.toHaveBeenCalled();
    },
  );

  test("lower revision and retired generation reads cannot revive stale membership", async () => {
    const { commands, owner, read } = setup();
    read.mockResolvedValueOnce(page(4, [other]));
    await commands.readPage(null, 20, owner.capture());
    read.mockResolvedValueOnce(page(3, [ref]));
    await expect(
      commands.readPage(null, 20, owner.capture()),
    ).rejects.toMatchObject({ kind: "superseded" });
    read.mockResolvedValueOnce(
      page(1, [], null, seed.synthetic_generations[1]),
    );
    await commands.readPage(null, 20, owner.capture());
    read.mockResolvedValueOnce(page(100, [ref]));
    await expect(
      commands.readPage(null, 20, owner.capture()),
    ).rejects.toMatchObject({ kind: "superseded" });
    expect(commands.getSnapshot()).toMatchObject({
      generation: seed.synthetic_generations[1],
      revision: 1,
    });
  });

  test("a changed-generation mutation reply does not confirm membership or unlock a new command", async () => {
    const { commands, write, changed } = setup();
    write.mockResolvedValueOnce({
      ...membership(),
      meta: {
        ...meta(identity().context_id),
        store_generation: seed.synthetic_generations[1],
      },
    });
    await commands.change(ref, true);
    expect(commands.getSnapshot()).toMatchObject({
      phase: "blocked",
      membership: {},
    });
    await commands.change(other, true);
    expect(write).toHaveBeenCalledTimes(1);
    expect(changed).not.toHaveBeenCalled();
  });

  test("owner A's delayed write cannot publish or notify success under owner B", async () => {
    const { commands, owner, write, changed } = setup();
    const gate = deferred<ResponseOf<"add_shortlist_membership">>();
    write.mockReturnValueOnce(gate.promise);
    const pending = commands.change(ref, true);
    await vi.waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    owner.accept(owner.invalidate(), identity(1));
    gate.resolve(membership());
    await pending;
    expect(commands.getSnapshot()).toMatchObject({
      phase: "idle",
      ref: null,
      membership: {},
    });
    expect(changed).not.toHaveBeenCalled();
    owner.accept(owner.invalidate(), identity());
    expect(commands.getSnapshot().phase).toBe("unknown");
  });

  test("unknown owner A intent cannot be replayed under B and survives A revalidation", async () => {
    const { commands, owner, write } = setup();
    write.mockRejectedValueOnce(loss());
    await commands.change(ref, true);
    const original = structuredClone(write.mock.calls[0]);
    owner.accept(owner.invalidate(), identity(1));
    expect(commands.getSnapshot().ref).toBeNull();
    await commands.reconcile();
    expect(write).toHaveBeenCalledTimes(1);
    owner.accept(owner.invalidate(), identity());
    expect(commands.getSnapshot().phase).toBe("unknown");
    await commands.reconcile();
    expect(write.mock.calls[1]).toEqual(original);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
