import { describe, expect, test } from "vitest";
import {
  criteriaErrorLabels,
  criteriaFromFilters,
  describeCriteria,
  emptyCriteria,
  filtersFromCriteria,
  mergeCriteria,
  preferencesFromText,
} from "../../src/features/inventory/criteria";
import { ClientFailure } from "../../src/shared/api/ClientFailure";
import { apiError } from "./apiFixtures";
import {
  browseQuery,
  parseBrowseQuery,
  operationPath,
  parseOperationQuery,
} from "../../src/app/routes";
import type { Schema } from "../../src/shared/api/contracts";

describe("U1 committed criteria and recovery locator boundaries", () => {
  test("all structured fields survive links with zero and exact AED decimals", () => {
    const form = {
      ...emptyCriteria(),
      make: "Mercedes-Benz",
      model: "500",
      trim: "E 400",
      body: "sedan",
      fuel: "petrol",
      transmission: "automatic",
      yearMin: "2010",
      yearMax: "2020",
      mileageMin: "0",
      mileageMax: "90000",
      budgetMin: "0",
      budgetMax: "70000.01",
    };
    const parsed = parseBrowseQuery(
      browseQuery({ ...form, snapshot: null, cursor: null }),
    );
    expect(parsed.valid).toBe(true);
    const filters = filtersFromCriteria(parsed);
    expect(filters.budget).toEqual({
      currency: "AED",
      basis: "cash",
      minimum: 0,
      maximum: 7000001,
    });
    expect(criteriaFromFilters(filters)).toEqual(form);
    expect(browseQuery(parsed)).not.toContain("valid=");
  });
  test.each([
    [{ yearMin: "2025", yearMax: "2020" }, "Model year"],
    [{ mileageMin: "-1" }, "Mileage"],
    [{ budgetMax: "12.001" }, "Cash budget"],
    [{ budgetMin: "5e4" }, "Cash budget"],
  ] as const)(
    "invalid ranges retain a field-specific explanation",
    (fields, label) => {
      expect(() =>
        filtersFromCriteria({ ...emptyCriteria(), ...fields }),
      ).toThrow(label);
      expect(
        parseBrowseQuery(browseQuery({ ...emptyCriteria(), ...fields })).valid,
      ).toBe(false);
    },
  );
  test("an unrelated edit retains multiple alternatives and a non-AED cash budget", () => {
    const original: Schema<"SearchFilters"> = {
      body_types: [],
      fuel_types: [],
      transmissions: [],
      trims: [],
      makes: ["a", "b"],
      models: ["3", "500"],
      budget: { currency: "JPY", basis: "cash", minimum: 100, maximum: 200 },
    };
    const initial = criteriaFromFilters(original);
    const next = mergeCriteria(
      original,
      { ...initial, yearMin: "2018" },
      initial,
    );
    expect(next).toEqual({
      ...original,
      years: { minimum: 2018, maximum: null },
    });
    expect(
      describeCriteria({ filters: next, query: "", soft_preferences: [] }),
    ).toContain("Cash budget (JPY, minor units): 100–200");
    expect(original).not.toHaveProperty("years");
  });
  test("soft preferences are preserved without filters and cannot exceed the frozen bounds", () => {
    expect(
      describeCriteria({ query: "", soft_preferences: ["easy parking"] }),
    ).toEqual(["Preferences: easy parking"]);
    expect(preferencesFromText(" easy parking \n\n quiet cabin ")).toEqual([
      "easy parking",
      "quiet cabin",
    ]);
    expect(() => preferencesFromText(Array(13).fill("one").join("\n"))).toThrow(
      "12 preferences",
    );
    expect(() => preferencesFromText("a".repeat(201))).toThrow(
      "200 characters",
    );
  });
  test("adding a bound to a retained 24-clause search fails before committing filters", () => {
    const original: Schema<"SearchFilters"> = {
      body_types: [],
      fuel_types: [],
      transmissions: [],
      trims: [],
      makes: Array.from({ length: 12 }, (_, i) => `make-${i}`),
      models: Array.from({ length: 12 }, (_, i) => `model-${i}`),
    };
    const initial = criteriaFromFilters(original);
    expect(mergeCriteria(original, initial, initial)).toEqual(original);
    expect(() =>
      mergeCriteria(original, { ...initial, yearMin: "2020" }, initial),
    ).toThrow("24 required filter conditions");
    expect(original).not.toHaveProperty("years");
  });
  test("original generation survives a recovery link; no private fields are accepted", () => {
    const generation = "00000000-0000-4000-8000-000000000005";
    const path = operationPath("a".repeat(43), generation);
    expect(parseOperationQuery(path.slice(path.indexOf("?")))).toEqual({
      valid: true,
      generation,
    });
    expect(parseOperationQuery("")).toEqual({ valid: true, generation: null });
    for (const query of [
      "csrf_token=secret",
      "review_token=secret",
      "contact=private",
      `submitted_store_generation=${generation}&submitted_store_generation=${generation}`,
      "submitted_store_generation=current",
    ])
      expect(parseOperationQuery(query).valid).toBe(false);
    expect(() => operationPath("bad", generation)).toThrow();
  });
  test("server field feedback exposes allowlisted labels without raw rejected values", () => {
    const detail = apiError("VALIDATION_ERROR").error;
    detail.fields = [
      { path: ["filters", "budget", "minimum"], code: "invalid_range" },
      {
        path: ["private-contact-value", "constructor", "toString", "__proto__"],
        code: "invalid",
      },
    ];
    expect(
      criteriaErrorLabels(
        new ClientFailure("api", "correct-request", { status: 422, detail }),
      ),
    ).toEqual(["cash budget"]);
  });
});
