import { describe, expect, test } from "vitest";
import type { Schema } from "../../src/shared/api/contracts";
import {
  getInventoryFacets,
  suggestInventoryQuery,
} from "../../src/features/inventory/inventoryFacets";

type ListingSummary = Schema<"ListingSummary">;
const unknown: Schema<"UnknownFact"> = {
  status: "unknown",
  reason: "not_stated",
};

function known<T extends string | number>(value: T) {
  const evidence: Schema<"SourceLocator">[] = [
    {
      category: "structured_source",
      cell: "A2",
      evidence_id: "10000000-0000-4000-8000-000000000001",
      extraction_version: "synthetic-facet-test",
      raw_text: String(value),
      review_status: "reviewed_extraction",
      sheet: "Synthetic",
      span_start: 0,
      span_end: String(value).length,
      verification: "source_claim",
      workbook_sha256: "a".repeat(64),
    },
  ];
  return {
    status: "known" as const,
    qualifier: "exact" as const,
    value,
    evidence,
  };
}

function listing(overrides: Partial<ListingSummary> = {}): ListingSummary {
  return {
    ref: {
      namespace: "synthetic",
      snapshot_id: "b".repeat(64),
      source_id: "1",
    },
    title: "Synthetic facet test listing",
    make: unknown,
    model: unknown,
    trim: unknown,
    year: unknown,
    cash_price: unknown,
    mileage_km: unknown,
    photo: {
      state: "missing",
      url: null,
      alt: "No photo",
      source: "supplied_listing",
    },
    evidence_warnings: [],
    ...overrides,
  };
}

const conflict: ListingSummary["make"] = {
  status: "conflicting",
  claims: [known("Nissan"), known("Toyota")],
};

describe("inventory facets from supplied known facts", () => {
  test("empty catalogs have no invented options", () => {
    expect(getInventoryFacets([])).toEqual({
      makes: [],
      models: [],
      trims: [],
      years: [],
    });
    expect(suggestInventoryQuery("Nisan", [])).toBeNull();
  });

  test("counts each known field and excludes unknown/conflicting claims", () => {
    const items = [
      listing({
        make: known("Nissan"),
        model: known("Altima"),
        trim: known("SL"),
        year: known(2022),
      }),
      listing({
        make: known("Nissan"),
        model: known("Altima"),
        trim: known("SV"),
        year: known(2022),
      }),
      listing({
        make: known("Toyota"),
        model: known("Corolla"),
        trim: known("GLI"),
        year: known(2023),
      }),
      listing({
        make: conflict,
        model: conflict,
        trim: conflict,
        year: { status: "conflicting", claims: [known(2018), known(2019)] },
      }),
      listing(),
    ];
    expect(getInventoryFacets(items)).toEqual({
      makes: [
        { value: "Nissan", label: "Nissan", count: 2 },
        { value: "Toyota", label: "Toyota", count: 1 },
      ],
      models: [
        { value: "Altima", label: "Altima", count: 2 },
        { value: "Corolla", label: "Corolla", count: 1 },
      ],
      trims: [
        { value: "GLI", label: "GLI", count: 1 },
        { value: "SL", label: "SL", count: 1 },
        { value: "SV", label: "SV", count: 1 },
      ],
      years: [
        { value: 2023, label: "2023", count: 1 },
        { value: 2022, label: "2022", count: 2 },
      ],
    });
  });

  test("selected make limits models/trims, while make/year counts retain catalog scope", () => {
    const items = [
      listing({
        make: known("Nissan"),
        model: known("Altima"),
        trim: known("SL"),
        year: known(2022),
      }),
      listing({
        make: known("Toyota"),
        model: known("Corolla"),
        trim: known("GLI"),
        year: known(2023),
      }),
      listing({
        make: conflict,
        model: known("Unattributed"),
        trim: known("Unattributed"),
      }),
    ];
    const all = getInventoryFacets(items);
    expect(getInventoryFacets(items, " ＮＩＳＳＡＮ ")).toEqual({
      ...all,
      models: [{ value: "Altima", label: "Altima", count: 1 }],
      trims: [{ value: "SL", label: "SL", count: 1 }],
    });
    expect(getInventoryFacets(items, "absent")).toEqual({
      ...all,
      models: [],
      trims: [],
    });
    expect(getInventoryFacets(items, "  ")).toEqual(all);
    expect(all.models.map((option) => option.value)).toContain("Unattributed");
  });

  test("equivalent names combine while source values and input facts stay intact", () => {
    const items = [
      listing({
        make: known("Nissan"),
        model: known("Café"),
        trim: known("glc"),
      }),
      listing({
        make: known("ＮＩＳＳＡＮ"),
        model: known("Cafe\u0301"),
        trim: known("GLC"),
      }),
      listing({ make: known("  ") }),
    ];
    const before = structuredClone(items);
    const facets = getInventoryFacets(items);
    expect(facets.makes).toEqual([
      { value: "Nissan", label: "Nissan", count: 2 },
    ]);
    expect(facets.models).toEqual([{ value: "Café", label: "Café", count: 2 }]);
    expect(facets.trims).toEqual([{ value: "glc", label: "GLC", count: 2 }]);
    facets.makes[0]!.count = 999;
    expect(items).toEqual(before);
    expect(getInventoryFacets(items).makes[0]!.count).toBe(2);
  });
});

describe("explicit inventory query suggestions", () => {
  const items = [
    listing({ make: known("Nissan"), model: known("Altima") }),
    listing({ make: known("Nissan"), model: known("Patrol") }),
    listing({ make: known("Renault"), model: known("Clio") }),
  ];

  test.each(["Nisan", "Nissann", "Nisaan", "Nissna", " Ｎｉｓａｎ "])(
    "a unique close make typo offers its exact known source name: %s",
    (query) => {
      expect(suggestInventoryQuery(query, items)).toEqual({
        query: "Nissan",
        label: "Nissan",
      });
    },
  );

  test("known models and adjacent transpositions are eligible", () => {
    expect(suggestInventoryQuery("Altma", items)).toEqual({
      query: "Altima",
      label: "Altima",
    });
    expect(suggestInventoryQuery("Reanult", items)).toEqual({
      query: "Renault",
      label: "Renault",
    });
  });

  test.each(["Nissan", " nIsSaN ", "Ｎｉｓｓａｎ", "Altima", ""])(
    "normalized exact input is unchanged: %s",
    (query) => expect(suggestInventoryQuery(query, items)).toBeNull(),
  );

  test("equally close names are ambiguous; a known exact name wins", () => {
    const alternatives = [
      listing({ model: known("Corsa") }),
      listing({ model: known("Corso") }),
    ];
    expect(suggestInventoryQuery("Corsx", alternatives)).toBeNull();
    expect(suggestInventoryQuery("Corsa", alternatives)).toBeNull();
  });

  test.each([
    "Nis",
    "Nisan 2020",
    "Nisan ٢٠٢٠",
    "Nisan２",
    "Buy Nisan",
    "zzzz",
    "Nissaann",
  ])(
    "short, numeric, free-text, and distant inputs do not get guessed: %s",
    (query) => expect(suggestInventoryQuery(query, items)).toBeNull(),
  );

  test("numeric model names are never changed or suggested", () => {
    const numeric = [
      listing({ model: known("500") }),
      listing({ model: known("CX-5") }),
    ];
    expect(suggestInventoryQuery("501", numeric)).toBeNull();
    expect(suggestInventoryQuery("CX-6", numeric)).toBeNull();
    expect(suggestInventoryQuery("500", numeric)).toBeNull();
  });

  test("unknown/conflicting facts and trim values do not become a suggestion vocabulary", () => {
    const unsupported = [
      listing(),
      listing({ make: conflict, model: conflict, trim: known("Nissan") }),
    ];
    expect(suggestInventoryQuery("Nisan", unsupported)).toBeNull();
  });

  test("canonical Unicode equivalence is exact and a whole known name can be corrected", () => {
    const unicode = [
      listing({ make: known("Citroën"), model: known("Land Cruiser") }),
    ];
    expect(suggestInventoryQuery("Citroe\u0308n", unicode)).toBeNull();
    expect(suggestInventoryQuery("Land Cruier", unicode)).toEqual({
      query: "Land Cruiser",
      label: "Land Cruiser",
    });
  });

  test("the four-letter minimum limits input, without inventing longer brand names", () => {
    const shortBrand = [listing({ make: known("BMW") })];
    expect(suggestInventoryQuery("BMW", shortBrand)).toBeNull();
    expect(suggestInventoryQuery("BMMW", shortBrand)).toEqual({
      query: "BMW",
      label: "BMW",
    });
  });
});
