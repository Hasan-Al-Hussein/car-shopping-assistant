import { afterEach, describe, expect, test, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ProductionApp } from "../../src/app/ProductionApp";
import type { Schema } from "../../src/shared/api/contracts";
import {
  config,
  identity,
  listingDetail,
  meta,
  searchResult,
  shortlist,
} from "./apiFixtures";

const services: BrowserServices[] = [];
const restorations: (() => void)[] = [];
afterEach(() => {
  cleanup();
  services.splice(0).forEach((service) => service.dispose());
  restorations.splice(0).forEach((restore) => restore());
});

const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 16; i++) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1);
  });
};

async function mountWorkspace(
  lifecycle: "isolated" | "anonymous" | "recognized" = "isolated",
  narrow = false,
) {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  vi.stubGlobal("matchMedia", () => ({
    matches: narrow,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  const oldScroll = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    "scrollIntoView",
  );
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
  restorations.push(() => {
    if (oldScroll)
      Object.defineProperty(HTMLElement.prototype, "scrollIntoView", oldScroll);
    else Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
  });

  const ref = listingDetail().listing.ref;
  let identityReads = 0;
  let identityGate: Promise<void> | undefined;
  const detailPath = `/api/v1/listings/${[ref.namespace, ref.snapshot_id, ref.source_id].map(encodeURIComponent).join("/")}`;
  const transport: typeof fetch = async (input, init) => {
    const path = new URL(String(input), "http://fixture.invalid").pathname;
    let payload: unknown;
    if (path === "/api/v1/identity") {
      identityReads += 1;
      if (identityGate) await identityGate;
      payload = {
        meta: meta(),
        data:
          lifecycle === "recognized"
            ? identity()
            : { state: "anonymous", notice_version: "DEMO-POLICY-1" },
      };
    } else if (path === "/api/v1/config") {
      payload = config();
    } else if (path === "/api/v1/health") {
      const capability = { state: "ready", reason: null };
      payload = {
        meta: meta(),
        data: {
          service: "car-shopping-assistant",
          active_snapshot_id: listingDetail().listing.ref.snapshot_id,
          assistant: capability,
          export: capability,
          inventory: capability,
          store: capability,
          viewing: capability,
        },
      };
    } else if (path === "/api/v1/inventory/search") {
      const body = JSON.parse(String(init?.body)) as Schema<"SearchRequest">;
      const response = searchResult();
      response.data.client_request_id = body.client_request_id;
      response.data.applied_criteria = {
        query: body.query,
        filters: body.filters,
        soft_preferences: body.soft_preferences,
      };
      payload = response;
    } else if (
      path === detailPath &&
      (!init?.method || init.method === "GET")
    ) {
      const detail = listingDetail();
      payload = {
        meta: {
          ...meta(),
          inventory_snapshot_id: detail.listing.ref.snapshot_id,
        },
        data: detail,
      };
    } else throw Error("UNSCRIPTED_HTTP_CALL");
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const service = new BrowserServices(transport);
  services.push(service);
  // Public interaction only; identity lifecycle has its own regression cases.
  if (lifecycle === "isolated")
    vi.spyOn(service, "start").mockImplementation(() => {});
  const mutate = vi.spyOn(service.api, "mutate");
  history.replaceState(null, "", "/__app/cars");
  render(<ProductionApp services={service} />);
  await flush();
  const menu = narrow ? screen.getByRole("button", { name: "Menu" }) : null;
  if (menu) fireEvent.click(menu);
  const help = screen.getByRole("button", { name: "Help" });
  help.focus();
  fireEvent.click(help);
  await flush();
  const opener = menu ?? help;
  return {
    opener,
    mutate,
    service,
    identityReads: () => identityReads,
    pauseIdentity: (gate: Promise<void>) => {
      identityGate = gate;
    },
  };
}

describe("Workspace nonmodal panel integration; painted layout needs browser proof", () => {
  test.each([false, true])(
    "recognized user can manage access without starting chat and keeps transition focus: narrow=%s",
    async (narrow) => {
      const { opener, service, mutate } = await mountWorkspace(
        "recognized",
        narrow,
      );
      expect(service.getSnapshot().session).toBeNull();
      const manage = screen.getByRole("button", {
        name: "Manage browser access",
      });
      manage.focus();
      fireEvent.click(manage);
      await flush();
      const dialog = screen.getByRole("dialog", {
        name: "Your browser access",
      });
      expect(dialog).toHaveFocus();
      expect(
        screen.getByRole("button", { name: "End browser access" }),
      ).toBeDisabled();
      expect(service.getSnapshot().session).toBeNull();
      expect(mutate).not.toHaveBeenCalled();
      fireEvent.click(screen.getByRole("button", { name: "Close" }));
      await flush();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(opener).toHaveFocus();
    },
  );

  test("public comparison remains usable with the panel open; close restores the opener and releases reserved space", async () => {
    const { opener, mutate } = await mountWorkspace();
    const dialog = screen.getByRole("dialog", {
      name: "Help and browser access",
    });
    const workspace = document.querySelector(".workspace");
    expect(workspace).toHaveAttribute("data-context-panel", "help");
    expect(dialog).not.toHaveAttribute("aria-modal", "true");

    const sourceId = listingDetail().listing.ref.source_id;
    const compare = screen.getByRole("button", {
      name: `Compare listing ${sourceId}`,
    });
    compare.focus();
    fireEvent.click(compare);
    await flush();
    expect(
      screen.getByRole("button", { name: `Remove listing ${sourceId}` }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("complementary", { name: "Comparison selection" }),
    ).toBeInTheDocument();
    expect(dialog).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await flush();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(workspace).not.toHaveAttribute("data-context-panel");
    expect(opener).toHaveFocus();
  });

  test("public detail and back navigation retain the same open panel without a domain mutation", async () => {
    const { mutate } = await mountWorkspace();
    const dialog = screen.getByRole("dialog", {
      name: "Help and browser access",
    });
    fireEvent.click(screen.getByRole("link", { name: /View car/ }));
    await flush();
    expect(
      screen.getByRole("link", { name: /Back to the cars/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Synthetic source details — not verified condition."),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBe(dialog);
    expect(document.querySelector(".workspace")).toHaveAttribute(
      "data-context-panel",
      "help",
    );

    fireEvent.click(screen.getByRole("link", { name: /Back to the cars/ }));
    await flush();
    expect(
      screen.getByRole("searchbox", { name: "Search inventory" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBe(dialog);
    expect(document.querySelector(".workspace")).toHaveAttribute(
      "data-context-panel",
      "help",
    );
    expect(mutate).not.toHaveBeenCalled();
  });

  test("anonymous window-focus revalidation retains the owner epoch and public comparison", async () => {
    const { service, identityReads, pauseIdentity, mutate } =
      await mountWorkspace("anonymous");
    expect(service.getSnapshot().phase).toBe("anonymous");
    const sourceId = listingDetail().listing.ref.source_id;
    fireEvent.click(
      screen.getByRole("button", { name: `Compare listing ${sourceId}` }),
    );
    await flush();
    const link = screen.getByRole("link", { name: "Compare cars →" });
    const href = link.getAttribute("href");
    const before = service.owner.capture().epoch;
    const beforeReads = identityReads();
    let release!: () => void;
    pauseIdentity(
      new Promise<void>((resolve) => {
        release = resolve;
      }),
    );
    act(() => window.dispatchEvent(new Event("focus")));
    expect(service.owner.capture().epoch).toBe(before);
    expect(service.getSnapshot().identity).toBeNull();
    expect(
      screen.getByRole("link", { name: "Compare cars →" }),
    ).toHaveAttribute("href", href);
    release();
    await flush();
    expect(identityReads()).toBe(beforeReads + 1);
    expect(service.owner.capture().epoch).toBe(before);
    expect(service.getSnapshot().phase).toBe("anonymous");
    expect(
      screen.getByRole("link", { name: "Compare cars →" }),
    ).toHaveAttribute("href", href);
    expect(
      screen.getByRole("button", { name: `Remove listing ${sourceId}` }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("dialog", { name: "Help and browser access" }),
    ).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  test("pending same-owner revalidation retains private cache and public comparison", async () => {
    const { service, pauseIdentity, mutate } =
      await mountWorkspace("recognized");
    expect(service.getSnapshot().phase).toBe("recognized");
    const sourceId = listingDetail().listing.ref.source_id;
    fireEvent.click(
      screen.getByRole("button", { name: `Compare listing ${sourceId}` }),
    );
    await flush();
    const href = screen
      .getByRole("link", { name: "Compare cars →" })
      .getAttribute("href");
    const key = service.queries.privateRead("get_shortlist", {}).queryKey;
    service.queries.client.setQueryData(key, shortlist());
    expect(service.queries.client.getQueryData(key)).toBeDefined();
    let release!: () => void;
    pauseIdentity(
      new Promise<void>((resolve) => {
        release = resolve;
      }),
    );
    act(() => window.dispatchEvent(new Event("focus")));
    expect(service.owner.capture().contextId).toBe(identity().context_id);
    expect(service.getSnapshot().identity?.context_id).toBe(identity().context_id);
    expect(service.queries.client.getQueryData(key)).toBeDefined();
    expect(
      screen.getByRole("link", { name: "Compare cars →" }),
    ).toHaveAttribute("href", href);
    release();
    await flush();
    expect(service.getSnapshot().phase).toBe("recognized");
    expect(service.queries.client.getQueryData(key)).toBeDefined();
    expect(
      screen.getByRole("link", { name: "Compare cars →" }),
    ).toHaveAttribute("href", href);
    expect(mutate).not.toHaveBeenCalled();
  });
});
