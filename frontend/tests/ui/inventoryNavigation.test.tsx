import { afterEach, describe, expect, test, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ProductionApp } from "../../src/app/ProductionApp";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import {
  BrowseRoute,
  CompareRoute,
  DetailRoute,
} from "../../src/features/inventory/InventoryRoutes";
import { comparisonPath } from "../../src/app/routes";
import type { Schema } from "../../src/shared/api/contracts";
import { listingDetail, meta, searchResult } from "./apiFixtures";

const services: BrowserServices[] = [];
const restorations: (() => void)[] = [];
afterEach(() => {
  services.splice(0).forEach((service) => service.dispose());
  restorations.splice(0).forEach((restore) => restore());
});
const flush = async () => {
  await act(async () => {
    for (let i = 0; i < 16; i++) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1);
  });
};
const request: Schema<"SearchRequest"> = {
  client_request_id: "90000000-0000-4000-8000-000000000001",
  query: "quiet family car",
  filters: {
    makes: ["one", "two"],
    models: [],
    body_types: [],
    fuel_types: [],
    transmissions: [],
    trims: [],
  },
  soft_preferences: ["easy parking"],
  cursor: null,
  snapshot_id: null,
  page_size: 20,
};
const selection = { refs: [], toggle: vi.fn() };

function setup(path = "/cars", state?: { browseKey: string }) {
  const service = new BrowserServices();
  services.push(service);
  // Isolate public route behavior from the separately tested identity lifecycle.
  vi.spyOn(service, "start").mockImplementation(() => {});
  const read = vi.spyOn(service.api, "read");
  const write = vi.spyOn(service.api, "mutate");
  const mount = () =>
    render(
      <ServicesProvider services={service}>
        <MemoryRouter
          initialEntries={[
            {
              pathname: path.split("?")[0],
              search: path.includes("?") ? `?${path.split("?")[1]}` : "",
              key: "original",
              state,
            },
          ]}
        >
          <Routes>
            <Route
              path="/cars"
              element={<BrowseRoute selection={selection} />}
            />
            <Route
              path="/cars/:listingRef"
              element={<DetailRoute selection={selection} />}
            />
            <Route
              path="/compare"
              element={
                <CompareRoute
                  selection={selection}
                  onSelectionChange={() => {}}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ServicesProvider>,
    );
  return { service, read, write, mount };
}

describe("U1 real route components with synthetic client results", () => {
  test("the full workspace Compare tray returns to the newly submitted search, not its prior parent-render handle", async () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
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
        Object.defineProperty(
          HTMLElement.prototype,
          "scrollIntoView",
          oldScroll,
        );
      else Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
    });
    const transport: typeof fetch = async (input, init) => {
      const path = new URL(String(input), "http://fixture.invalid").pathname;
      let payload: unknown;
      if (path === "/api/v1/health") {
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
      } else if (path.includes("/inventory/")) {
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
    vi.spyOn(service, "start").mockImplementation(() => {});
    history.replaceState(null, "", "/__app/cars");
    render(<ProductionApp services={service} />);
    await flush();
    fireEvent.click(
      screen.getByRole("button", {
        name: `Compare listing ${listingDetail().listing.ref.source_id}`,
      }),
    );
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search inventory" }),
      { target: { value: "changed search B" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Find cars" }));
    await flush();
    fireEvent.click(screen.getByRole("link", { name: /Compare cars/ }));
    await flush();
    fireEvent.click(screen.getByRole("link", { name: /Add another car/ }));
    await flush();
    expect(
      screen.getByRole("searchbox", { name: "Search inventory" }),
    ).toHaveValue("changed search B");
    expect(service.currentBrowseRequest()?.query).toBe("changed search B");
  });
  test("detail's Back link restores the visible committed text and all alternatives", async () => {
    const { service, read, write, mount } = setup();
    service.setBrowseRequest("original", request);
    read
      .mockResolvedValueOnce(searchResult())
      .mockResolvedValueOnce({ meta: meta(), data: listingDetail() });
    mount();
    await flush();
    expect(
      screen.getByRole("searchbox", { name: "Search inventory" }),
    ).toHaveValue(request.query);
    fireEvent.click(screen.getByRole("link", { name: /View car/ }));
    await flush();
    fireEvent.click(screen.getByRole("link", { name: /Back to the cars/ }));
    await flush();
    expect(
      screen.getByRole("searchbox", { name: "Search inventory" }),
    ).toHaveValue(request.query);
    expect(service.currentBrowseRequest()?.filters?.makes).toEqual([
      "one",
      "two",
    ]);
    expect(write).not.toHaveBeenCalled();
  });

  test("Next page carries unchanged criteria and the returned snapshot/cursor", async () => {
    const { service, read, write, mount } = setup();
    service.setBrowseRequest("original", request);
    const first = searchResult();
    first.data.next_cursor = "opaque-page-two";
    read.mockResolvedValueOnce(first).mockResolvedValueOnce(searchResult());
    mount();
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await flush();
    const browseReads = read.mock.calls.filter(
      ([operation, options]) =>
        operation === "search_inventory" &&
        (options?.body as Schema<"SearchRequest"> | undefined)?.page_size ===
          request.page_size,
    );
    expect(browseReads).toHaveLength(2);
    expect(browseReads[1]?.[1]).toMatchObject({
      body: {
        query: request.query,
        filters: request.filters,
        soft_preferences: request.soft_preferences,
        cursor: "opaque-page-two",
        snapshot_id: first.data.presentation.snapshot_id,
      },
    });
    expect(
      screen.getByRole("searchbox", { name: "Search inventory" }),
    ).toHaveValue(request.query);
    expect(write).not.toHaveBeenCalled();
  });

  test("removing the last comparison preserves its original browse handle", async () => {
    const { service, read, write, mount } = setup(
      comparisonPath([listingDetail().listing.ref]),
      { browseKey: "search-context" },
    );
    service.setBrowseRequest("search-context", request);
    read
      .mockResolvedValueOnce({ meta: meta(), data: listingDetail() })
      .mockResolvedValueOnce(searchResult());
    mount();
    await flush();
    fireEvent.click(
      screen.getByRole("button", {
        name: `Remove listing ${listingDetail().listing.ref.source_id} from comparison`,
      }),
    );
    await flush();
    fireEvent.click(screen.getByRole("link", { name: /Explore the cars/ }));
    await flush();
    expect(
      screen.getByRole("searchbox", { name: "Search inventory" }),
    ).toHaveValue(request.query);
    expect(service.currentBrowseRequest()?.soft_preferences).toEqual([
      "easy parking",
    ]);
    expect(write).not.toHaveBeenCalled();
  });

  test.each([
    [`/cars?snapshot=${"a".repeat(64)}&cursor=old-cursor`, undefined],
    ["/cars", { browseKey: "lost-after-reload" }],
  ] as const)(
    "missing original search is explicit and does not submit substituted criteria",
    async (path, state) => {
      const { read, write, mount } = setup(path, state);
      mount();
      await flush();
      expect(
        screen.getByText("This page needs its original search."),
      ).toBeInTheDocument();
      expect(read).not.toHaveBeenCalled();
      expect(write).not.toHaveBeenCalled();
    },
  );
});
