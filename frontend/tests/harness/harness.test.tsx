// A test-only probe verifies React/test transport injection. It is not product UI acceptance.
import { useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import sourceFacts from "../../../fixtures/shared/source-facts.json";
import { deferred, frozenClock, newSeed, scriptedFetch } from "./fixtures";

function ReadProbe({
  request,
  contextId,
  clock,
}: {
  request: typeof fetch;
  contextId: string;
  clock: ReturnType<typeof frozenClock>;
}) {
  const [message, setMessage] = useState("Ready");
  async function check() {
    setMessage("Checking synthetic response");
    try {
      const response = await request("/observation", {
        headers: { "X-Identity-Context": contextId },
      });
      const result = (await response.json()) as { message: string };
      setMessage(
        response.ok
          ? result.message
          : "Provider unavailable; browsing remains available",
      );
    } catch {
      setMessage("Response lost; outcome is unknown");
    }
  }
  return (
    <section aria-label="Harness probe">
      <time dateTime={clock.now().toISOString()}>
        {clock.now().toISOString()}
      </time>
      <button
        onClick={() => {
          void check();
        }}
      >
        Check synthetic response
      </button>
      <p role="status">{message}</p>
    </section>
  );
}

describe("F-03 stateless harness", () => {
  test("allows explicit dirty browser state only within this test", () => {
    localStorage.setItem("synthetic-owner", "A");
    sessionStorage.setItem("synthetic-context", "A");
    document.cookie = "synthetic_owner=A; path=/";
    history.replaceState(null, "", "/synthetic");
    expect(localStorage.getItem("synthetic-owner")).toBe("A");
    expect(document.cookie).toContain("synthetic_owner=A");
  });

  test("starts the next case without prior storage cookies or route state", () => {
    expect(localStorage.getItem("synthetic-owner")).toBeNull();
    expect(sessionStorage.getItem("synthetic-context")).toBeNull();
    expect(document.cookie).toBe("");
    expect(location.pathname).toBe("/");
  });

  test("isolates same-name owners and clocks without ambient time", () => {
    const first = newSeed();
    const second = newSeed();
    const a = first.owners[0]!;
    const b = first.owners[1]!;
    expect(a.display_name).toBe(b.display_name);
    expect(a.context_id).not.toBe(b.context_id);
    a.display_name = "Changed in one fixture";
    expect(second.owners[0]!.display_name).toBe("Synthetic Buyer");
    const clockA = frozenClock();
    const clockB = frozenClock();
    clockA.advance(300);
    expect(clockA.now().toISOString()).toBe("2026-09-24T04:05:00.000Z");
    expect(clockB.now().toISOString()).toBe("2026-09-24T04:00:00.000Z");
    expect(new Date().toISOString()).toBe("2026-09-24T04:00:00.000Z");
  });

  test("renders an injected response and exact source Unicode through semantic controls", async () => {
    const owner = newSeed().owners[0]!;
    const title = sourceFacts.cases.find(
      (item) => item.cell === "F36",
    )!.raw_value;
    const request = scriptedFetch([
      {
        method: "GET",
        path: "/observation",
        contextId: owner.context_id,
        body: { message: title },
      },
    ]);
    render(
      <ReadProbe
        request={request}
        contextId={owner.context_id}
        clock={frozenClock()}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Ready");
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Check synthetic response" }),
      );
    });
    expect(screen.getByRole("status")).toHaveTextContent("ميني كوبر 2017 S");
    await expect(request("/unscripted")).rejects.toThrow(
      "UNSCRIPTED_HTTP_CALL",
    );
  });

  test("keeps provider failure distinguishable from a saved action", async () => {
    const owner = newSeed().owners[1]!;
    const request = scriptedFetch([
      {
        method: "GET",
        path: "/observation",
        contextId: owner.context_id,
        status: 503,
        body: { message: "Synthetic provider failure" },
      },
    ]);
    render(
      <ReadProbe
        request={request}
        contextId={owner.context_id}
        clock={frozenClock()}
      />,
    );
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: "Check synthetic response" }),
      );
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Provider unavailable; browsing remains available",
    );
  });

  test("controls reply ordering and old revisions without real sleeps", async () => {
    const gate = deferred<void>();
    const request = scriptedFetch([
      {
        method: "GET",
        path: "/state",
        gate: gate.promise,
        body: { revision: 1 },
      },
      { method: "GET", path: "/state", body: { revision: 2 } },
    ]);
    let oldSettled = false;
    const old = request("/state").then((response) => {
      oldSettled = true;
      return response;
    });
    const latest = await request("/state");
    expect(await latest.json()).toEqual({ revision: 2 });
    expect(oldSettled).toBe(false);
    gate.resolve();
    expect(await (await old).json()).toEqual({ revision: 1 });
  });

  test("retains simulated acceptance when the response is lost", async () => {
    const accepted: string[] = [];
    const request = scriptedFetch([
      {
        method: "POST",
        path: "/action",
        body: null,
        loseResponse: true,
        onAccept: () => accepted.push("original-action"),
      },
      {
        method: "GET",
        path: "/projection",
        body: { state: "failed", canonical_version: 2 },
      },
      {
        method: "POST",
        path: "/storage",
        status: 503,
        body: { code: "STORE_UNAVAILABLE" },
      },
    ]);
    await expect(request("/action", { method: "POST" })).rejects.toThrow(
      "RESPONSE_LOST_AFTER_ACCEPT",
    );
    expect(accepted).toEqual(["original-action"]);
    expect(await (await request("/projection")).json()).toEqual({
      state: "failed",
      canonical_version: 2,
    });
    expect((await request("/storage", { method: "POST" })).status).toBe(503);
  });

  test("does not silently deliver a reply to another credential context", async () => {
    const owners = newSeed().owners;
    const request = scriptedFetch([
      {
        method: "GET",
        path: "/private",
        contextId: owners[0]!.context_id,
        body: { synthetic: true },
      },
    ]);
    await expect(
      request("/private", {
        headers: { "X-Identity-Context": owners[1]!.context_id },
      }),
    ).rejects.toThrow("UNEXPECTED_HTTP_COMMAND");
  });

  test("blocks unscripted fetch and restores controlled timers between tests", async () => {
    await expect(fetch("https://example.invalid")).rejects.toThrow(
      "UNSCRIPTED_HTTP_CALL",
    );
    const callback = vi.fn();
    setTimeout(callback, 5000);
    expect(callback).not.toHaveBeenCalled();
    vi.advanceTimersByTime(5000);
    expect(callback).toHaveBeenCalledOnce();
  });
});
