import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { InventoryFilters } from "../../src/features/inventory/InventoryFilters";
import {
  filtersFromCriteria,
  emptyCriteria,
} from "../../src/features/inventory/criteria";
import { listingDetail } from "./apiFixtures";

describe("inline criteria preserve strict source requests", () => {
  const criteria = {
    query: "Nisan",
    soft_preferences: ["easy parking", "quiet"],
    filters: {
      ...filtersFromCriteria(emptyCriteria()),
      makes: ["BMW", "Audi"],
      body_types: ["SUV"],
      years: { minimum: 2018, maximum: 2022 },
      mileage_km: { minimum: null, maximum: 40000 },
      budget: {
        minimum: 5000000,
        maximum: 8000000,
        currency: "AED",
        basis: "cash" as const,
      },
    },
  };
  function mount() {
    const apply = vi.fn(),
      listing = listingDetail().listing;
    listing.make = {
      status: "known",
      value: "Nissan",
      qualifier: "exact",
      evidence: [],
    };
    render(
      <InventoryFilters
        criteria={criteria}
        catalog={[listing]}
        loading={false}
        failed={false}
        retry={() => {}}
        apply={apply}
        advanced={() => {}}
      />,
    );
    return apply;
  }
  test("adding a source make preserves existing alternatives, ranges, query and preferences", () => {
    const apply = mount();
    fireEvent.change(screen.getByLabelText("Make"), {
      target: { value: "Nissan" },
    });
    expect(apply).toHaveBeenCalledWith({
      ...criteria,
      filters: { ...criteria.filters, makes: ["BMW", "Audi", "Nissan"] },
    });
  });
  test("one chip removes only that value, including when multiple alternatives exist", () => {
    const apply = mount();
    fireEvent.click(screen.getByRole("button", { name: "Remove Make: BMW" }));
    expect(apply).toHaveBeenCalledWith({
      ...criteria,
      filters: { ...criteria.filters, makes: ["Audi"] },
    });
  });
  test("query and preference removal are independent from required ranges", () => {
    const apply = mount();
    fireEvent.click(
      screen.getByRole("button", { name: "Remove Search: Nisan" }),
    );
    expect(apply).toHaveBeenLastCalledWith({ ...criteria, query: "" });
    fireEvent.click(
      screen.getByRole("button", { name: "Remove Preference: quiet" }),
    );
    expect(apply).toHaveBeenLastCalledWith({
      ...criteria,
      soft_preferences: ["easy parking"],
    });
  });
});
