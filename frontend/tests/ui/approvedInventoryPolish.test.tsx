import { createRef, useRef, useState } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import { refKey, type InventoryRef } from "../../src/app/routes";
import { ClientFailure } from "../../src/shared/api/ClientFailure";
import { ComparisonTray } from "../../src/features/inventory/ComparisonTray";
import { InventorySkeleton } from "../../src/features/inventory/InventorySkeleton";
import {
  BrowseRoute,
  ReadFailure,
} from "../../src/features/inventory/InventoryRoutes";
import { VehicleSummaryCard } from "../../src/shared/ui/inner/VehicleSummaryCard";
import { searchResult } from "./apiFixtures";

const running: BrowserServices[] = [];
afterEach(() => running.splice(0).forEach((service) => service.dispose()));
function service() {
  const current = new BrowserServices();
  running.push(current);
  vi.spyOn(current, "start").mockImplementation(() => {});
  return current;
}
async function flush() {
  await act(async () => {
    for (let i = 0; i < 16; i++) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1);
  });
}

describe("approved inventory refinements", () => {
  test("loading placeholders have one announcement and no fake cars or actions", () => {
    const { container } = render(<InventorySkeleton />);
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent("Finding cars…");
    expect(container.querySelectorAll(".inventory-skeleton")).toHaveLength(3);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  test("a read error explains retained search and exposes one disabled-while-retrying action", () => {
    const retry = vi.fn();
    const { rerender } = render(
      <MemoryRouter initialEntries={["/cars"]}>
        <ReadFailure
          error={new ClientFailure("network", "read")}
          retry={retry}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Your search is still here/)).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
    rerender(
      <MemoryRouter initialEntries={["/cars"]}>
        <ReadFailure
          error={new ClientFailure("network", "read")}
          retry={retry}
          retrying
        />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: "Trying again…" }),
    ).toBeDisabled();
  });

  test("result wording changes without altering backend count, criteria, or source coverage", async () => {
    const current = service();
    vi.spyOn(current.api, "read").mockResolvedValue(searchResult());
    render(
      <ServicesProvider services={current}>
        <MemoryRouter initialEntries={["/cars"]}>
          <BrowseRoute selection={{ refs: [], toggle: vi.fn() }} />
        </MemoryRouter>
      </ServicesProvider>,
    );
    await flush();
    expect(screen.getByText("1 car found")).toBeInTheDocument();
    expect(screen.queryByText(/supported listings/)).not.toBeInTheDocument();
    const disclosure = screen
      .getByText("Search and source details")
      .closest("details")!;
    expect(disclosure).not.toHaveAttribute("open");
    expect(disclosure).toHaveTextContent("current availability is unknown");
  });

  test("card still displays all conflicting cash amounts, currency, year uncertainty, and original photo", () => {
    const listing = searchResult().data.items[0]!;
    listing.cash_price = {
      status: "conflicting",
      claims: [
        {
          value: { currency: "AED", minor_units: 4500000, basis: "cash" },
          qualifier: "exact",
          evidence: [],
        },
        {
          value: { currency: "AED", minor_units: 4900000, basis: "cash" },
          qualifier: "exact",
          evidence: [],
        },
      ],
    };
    listing.photo = {
      ...listing.photo,
      state: "source_present",
      url: "https://example.invalid/original-car.jpg?source=1",
      alt: "Original source photo",
    };
    listing.evidence_warnings = ["Cash prices differ in the listing."];
    render(
      <MemoryRouter>
        <VehicleSummaryCard listing={listing} href="/cars/example" />
      </MemoryRouter>,
    );
    expect(screen.getByText("AED 45,000")).toBeInTheDocument();
    expect(screen.getByText("AED 49,000")).toBeInTheDocument();
    expect(screen.getAllByText("Not stated").length).toBeGreaterThan(0);
    expect(document.querySelector("img")).toHaveAttribute(
      "src",
      listing.photo.url,
    );
    const disclosure = screen.getByText("Details to check").closest("details")!;
    expect(disclosure).toHaveTextContent(listing.evidence_warnings[0]!);
  });

  test("a known cash price preserves its currency and minor units, including a stated zero", () => {
    const listing = searchResult().data.items[0]!;
    listing.cash_price = {
      status: "known",
      value: { currency: "AED", minor_units: 12345678, basis: "cash" },
      qualifier: "exact",
      evidence: [],
    };
    const { rerender } = render(
      <MemoryRouter>
        <VehicleSummaryCard listing={listing} href="/cars/example" />
      </MemoryRouter>,
    );
    expect(screen.getByText("AED 123,456.78")).toBeInTheDocument();
    listing.cash_price = {
      status: "known",
      value: { currency: "AED", minor_units: 0, basis: "cash" },
      qualifier: "exact",
      evidence: [],
    };
    rerender(
      <MemoryRouter>
        <VehicleSummaryCard listing={listing} href="/cars/example" />
      </MemoryRouter>,
    );
    expect(screen.getByText("AED 0")).toBeInTheDocument();
  });

  test("tray reuses exact cached summaries and removes one car while retaining the next keyboard target", async () => {
    const current = service();
    const result = searchResult();
    const first = result.data.items[0]!;
    const second = structuredClone(first);
    second.ref.source_id = "two";
    result.data.items.push(second);
    current.queries.client.setQueryData(
      ["public", first.ref.snapshot_id, "search_inventory", {}],
      result,
    );
    const read = vi.spyOn(current.api, "read");
    function TrayHarness() {
      const [refs, setRefs] = useState<InventoryRef[]>([first.ref, second.ref]);
      const trayRef = useRef<HTMLElement>(null);
      return (
        <ComparisonTray
          refs={refs}
          trayRef={trayRef}
          warning={null}
          remove={(ref) =>
            setRefs((items) =>
              items.filter((item) => refKey(item) !== refKey(ref)),
            )
          }
        />
      );
    }
    render(
      <ServicesProvider services={current}>
        <MemoryRouter>
          <TrayHarness />
        </MemoryRouter>
      </ServicesProvider>,
    );
    await flush();
    const tray = screen.getByRole("complementary", {
      name: "Comparison selection",
    });
    expect(within(tray).getAllByRole("listitem")).toHaveLength(2);
    fireEvent.click(
      within(tray).getByRole("button", { name: /\(listing one\)/ }),
    );
    expect(within(tray).getAllByRole("listitem")).toHaveLength(1);
    expect(
      within(tray).getByRole("button", { name: /\(listing two\)/ }),
    ).toHaveFocus();
    expect(read).not.toHaveBeenCalled();
  });

  test("an uncached snapshot never borrows another snapshot's car details, and remains removable after read failure", async () => {
    const current = service();
    const cached = searchResult();
    const original = cached.data.items[0]!;
    original.make = {
      status: "known",
      value: "Different snapshot",
      qualifier: "exact",
      evidence: [],
    };
    current.queries.client.setQueryData(
      ["public", original.ref.snapshot_id, "search_inventory", {}],
      cached,
    );
    const selected = { ...original.ref, snapshot_id: "b".repeat(64) };
    const remove = vi.fn();
    const read = vi
      .spyOn(current.api, "read")
      .mockRejectedValue(new ClientFailure("network", "read"));
    render(
      <ServicesProvider services={current}>
        <MemoryRouter>
          <ComparisonTray
            refs={[selected]}
            trayRef={createRef<HTMLElement>()}
            warning={null}
            remove={remove}
          />
        </MemoryRouter>
      </ServicesProvider>,
    );
    await flush();
    expect(screen.queryByText(/Different snapshot/)).not.toBeInTheDocument();
    expect(screen.getByText("Details unavailable")).toBeInTheDocument();
    expect(read).toHaveBeenCalledOnce();
    expect(read).toHaveBeenCalledWith(
      "get_listing",
      expect.objectContaining({ path: selected }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Remove Listing one/ }));
    expect(remove).toHaveBeenCalledWith(selected);
  });
});
