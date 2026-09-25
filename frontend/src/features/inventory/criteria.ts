import type { Schema } from "../../shared/api/contracts";
import { ClientFailure } from "../../shared/api/ClientFailure";

export const criterionFields = [
  ["make", "Make"],
  ["model", "Model"],
  ["trim", "Trim"],
  ["body", "Body type"],
  ["fuel", "Fuel type"],
  ["transmission", "Transmission"],
] as const;
export const rangeFields = [
  ["yearMin", "Earliest model year"],
  ["yearMax", "Latest model year"],
  ["mileageMin", "Minimum mileage (km)"],
  ["mileageMax", "Maximum mileage (km)"],
  ["budgetMin", "Minimum cash budget (AED)"],
  ["budgetMax", "Maximum cash budget (AED)"],
] as const;
export type CriteriaForm = Record<
  (typeof criterionFields)[number][0] | (typeof rangeFields)[number][0],
  string
>;
export const emptyCriteria = (): CriteriaForm => ({
  make: "",
  model: "",
  trim: "",
  body: "",
  fuel: "",
  transmission: "",
  yearMin: "",
  yearMax: "",
  mileageMin: "",
  mileageMax: "",
  budgetMin: "",
  budgetMax: "",
});

function integer(value: string, label: string, money = false): number | null {
  if (!value) return null;
  if (!(money ? /^\d+(?:\.\d{1,2})?$/ : /^\d+$/).test(value))
    throw Error(
      `${label}: enter a nonnegative number${money ? " with up to two decimal places" : " without decimals"}.`,
    );
  const [whole, fraction = ""] = value.split(".");
  const result = money
    ? Number(whole) * 100 + Number(fraction.padEnd(2, "0"))
    : Number(whole);
  if (!Number.isSafeInteger(result) || result > 1_000_000_000_000)
    throw Error(`${label}: this bound is too large.`);
  return result;
}
function range(min: string, max: string, label: string, money = false) {
  const minimum = integer(min, label, money),
    maximum = integer(max, label, money);
  if (minimum !== null && maximum !== null && minimum > maximum)
    throw Error(`${label}: the minimum cannot exceed the maximum.`);
  return minimum === null && maximum === null ? null : { minimum, maximum };
}
export function filtersFromCriteria(
  form: CriteriaForm,
): Schema<"SearchFilters"> {
  const terms = (value: string) => (value.trim() ? [value.trim()] : []);
  const budget = range(form.budgetMin, form.budgetMax, "Cash budget", true);
  return {
    makes: terms(form.make),
    models: terms(form.model),
    trims: terms(form.trim),
    body_types: terms(form.body),
    fuel_types: terms(form.fuel),
    transmissions: terms(form.transmission),
    years: range(form.yearMin, form.yearMax, "Model year"),
    mileage_km: range(form.mileageMin, form.mileageMax, "Mileage"),
    budget: budget ? { ...budget, currency: "AED", basis: "cash" } : null,
  };
}
export function criteriaFromFilters(
  filters?: Schema<"SearchFilters">,
): CriteriaForm {
  const form = emptyCriteria();
  if (!filters) return form;
  form.make = filters.makes?.[0] ?? "";
  form.model = filters.models?.[0] ?? "";
  form.trim = filters.trims?.[0] ?? "";
  form.body = filters.body_types?.[0] ?? "";
  form.fuel = filters.fuel_types?.[0] ?? "";
  form.transmission = filters.transmissions?.[0] ?? "";
  form.yearMin = String(filters.years?.minimum ?? "");
  form.yearMax = String(filters.years?.maximum ?? "");
  form.mileageMin = String(filters.mileage_km?.minimum ?? "");
  form.mileageMax = String(filters.mileage_km?.maximum ?? "");
  if (filters.budget?.currency === "AED") {
    form.budgetMin =
      filters.budget.minimum == null
        ? ""
        : String(filters.budget.minimum / 100);
    form.budgetMax =
      filters.budget.maximum == null
        ? ""
        : String(filters.budget.maximum / 100);
  }
  return form;
}

/** Editing one displayed value must not drop undisplayed alternatives or currency. */
export function mergeCriteria(
  original: Schema<"SearchFilters"> | undefined,
  form: CriteriaForm,
  initial: CriteriaForm,
): Schema<"SearchFilters"> {
  const next: Schema<"SearchFilters"> = original
    ? { ...original }
    : filtersFromCriteria(emptyCriteria());
  const edited = filtersFromCriteria(form);
  for (const [field, key] of [
    ["make", "makes"],
    ["model", "models"],
    ["trim", "trims"],
    ["body", "body_types"],
    ["fuel", "fuel_types"],
    ["transmission", "transmissions"],
  ] as const)
    if (form[field] !== initial[field]) next[key] = edited[key];
  if (form.yearMin !== initial.yearMin || form.yearMax !== initial.yearMax)
    next.years = edited.years;
  if (
    form.mileageMin !== initial.mileageMin ||
    form.mileageMax !== initial.mileageMax
  )
    next.mileage_km = edited.mileage_km;
  if (
    form.budgetMin !== initial.budgetMin ||
    form.budgetMax !== initial.budgetMax
  )
    next.budget = edited.budget;
  const clauses = Object.values(next).reduce<number>(
    (count, value) =>
      count + (Array.isArray(value) ? value.length : value == null ? 0 : 1),
    0,
  );
  if (clauses > 24)
    throw Error(
      "Use no more than 24 required filter conditions. Remove an existing condition before adding another.",
    );
  return next;
}

/** Display authoritative normalized criteria; never infer supported matches locally. */
export function describeCriteria(criteria: Schema<"SearchCriteria">): string[] {
  const f = criteria.filters;
  const values: string[] = [];
  if (criteria.query) values.push(`Text: ${criteria.query}`);
  for (const [label, items] of [
    ["Make", f?.makes],
    ["Model", f?.models],
    ["Trim", f?.trims],
    ["Body", f?.body_types],
    ["Fuel", f?.fuel_types],
    ["Transmission", f?.transmissions],
  ] as const)
    if (items?.length) values.push(`${label}: ${items.join(", ")}`);
  for (const [label, r] of [
    ["Year", f?.years],
    ["Mileage (km)", f?.mileage_km],
  ] as const)
    if (r) values.push(`${label}: ${r.minimum ?? "any"}–${r.maximum ?? "any"}`);
  if (f?.budget) {
    const budget = f.budget,
      divisor = budget.currency === "AED" ? 100 : 1;
    values.push(
      `Cash budget (${budget.currency}${divisor === 1 ? ", minor units" : ""}): ${budget.minimum == null ? "any" : budget.minimum / divisor}–${budget.maximum == null ? "any" : budget.maximum / divisor}`,
    );
  }
  if (criteria.soft_preferences?.length)
    values.push(`Preferences: ${criteria.soft_preferences.join("; ")}`);
  return values;
}

export function preferencesFromText(value: string): string[] {
  const preferences = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (preferences.length > 12 || preferences.some((line) => line.length > 200))
    throw Error("Use up to 12 preferences, with at most 200 characters each.");
  return preferences;
}

/** Only known public field names reach the UI, never raw rejected values. */
export function criteriaErrorLabels(error: unknown): string[] {
  if (!(error instanceof ClientFailure) || !error.detail) return [];
  const labels: Record<string, string> = {
    query: "text search",
    makes: "make",
    models: "model",
    trims: "trim",
    years: "model year",
    mileage_km: "mileage",
    budget: "cash budget",
    body_types: "body type",
    fuel_types: "fuel type",
    transmissions: "transmission",
    soft_preferences: "preferences",
  };
  return [
    ...new Set(
      (error.detail.fields ?? []).flatMap((field) =>
        field.path
          .map(String)
          .flatMap((part) =>
            Object.hasOwn(labels, part) ? [labels[part]!] : [],
          ),
      ),
    ),
  ];
}
