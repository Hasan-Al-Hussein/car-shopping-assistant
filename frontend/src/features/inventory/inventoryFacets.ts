import type { Schema } from "../../shared/api/contracts";
import { displayCarName } from "../../shared/ui/displayNames";

type ListingSummary = Schema<"ListingSummary">;

export type InventoryFacetOption<T extends string | number = string> = {
  value: T;
  label: string;
  count: number;
};

export type InventoryFacets = {
  makes: InventoryFacetOption[];
  models: InventoryFacetOption[];
  trims: InventoryFacetOption[];
  years: InventoryFacetOption<number>[];
};

export type InventoryQuerySuggestion = { query: string; label: string };

function normalizeName(value: string): string {
  return value.normalize("NFKC").trim().replace(/\s+/gu, " ").toLowerCase();
}

function textOptions(
  items: readonly ListingSummary[],
  field: "make" | "model" | "trim",
): InventoryFacetOption[] {
  const options = new Map<string, InventoryFacetOption>();
  for (const item of items) {
    const fact = item[field];
    if (fact.status !== "known") continue;
    const key = normalizeName(fact.value);
    if (!key) continue;
    const existing = options.get(key);
    if (existing) existing.count += 1;
    else
      options.set(key, {
        value: fact.value,
        label: displayCarName(fact.value.trim()),
        count: 1,
      });
  }
  return [...options.values()].sort((a, b) =>
    a.label.localeCompare(b.label, "en", {
      numeric: true,
      sensitivity: "base",
    }),
  );
}

/**
 * Counts known facts in the supplied catalog, not server-filtered match totals.
 * Callers fetch a complete, coherent catalog before presenting global counts.
 * Makes/years use all items; models/trims use the selected make when nonblank.
 * Unknown/conflicting facts contribute nothing to that field. Source values are
 * preserved; equivalent casing/Unicode spellings share their first source value.
 */
export function getInventoryFacets(
  items: readonly ListingSummary[],
  selectedMake?: string,
): InventoryFacets {
  const make = normalizeName(selectedMake ?? "");
  const dependent = make
    ? items.filter(
        (item) =>
          item.make.status === "known" &&
          normalizeName(item.make.value) === make,
      )
    : items;
  const years = new Map<number, InventoryFacetOption<number>>();
  for (const item of items) {
    if (item.year.status !== "known") continue;
    const value = item.year.value;
    const existing = years.get(value);
    if (existing) existing.count += 1;
    else years.set(value, { value, label: String(value), count: 1 });
  }
  return {
    makes: textOptions(items, "make"),
    models: textOptions(dependent, "model"),
    trims: textOptions(dependent, "trim"),
    years: [...years.values()].sort((a, b) => b.value - a.value),
  };
}

/** One insertion, deletion, substitution, or adjacent transposition of code points. */
function isOneEdit(left: string, right: string): boolean {
  const a = Array.from(left),
    b = Array.from(right);
  if (Math.abs(a.length - b.length) > 1) return false;
  let i = 0,
    j = 0,
    edits = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      i += 1;
      j += 1;
      continue;
    }
    if (++edits > 1) return false;
    if (a.length < b.length) j += 1;
    else if (a.length > b.length) i += 1;
    else if (a[i] === b[j + 1] && a[i + 1] === b[j]) {
      i += 2;
      j += 2;
    } else {
      i += 1;
      j += 1;
    }
  }
  return edits + Number(i < a.length || j < b.length) === 1;
}

/**
 * Offer a whole make/model name only when exactly one known name is one edit away.
 * This is an explicit-click suggestion, never a search/filter mutation. Exact
 * normalized names, short inputs, numeric names, and ambiguous typos return null.
 * Free-text phrases are not token-corrected; no vocabulary is invented.
 */
export function suggestInventoryQuery(
  query: string,
  items: readonly ListingSummary[],
): InventoryQuerySuggestion | null {
  const normalized = normalizeName(query);
  const lettersOnly = /^[\p{L}\p{M}]+(?:[ -][\p{L}\p{M}]+)*$/u;
  if (
    !lettersOnly.test(normalized) ||
    (normalized.match(/\p{L}/gu)?.length ?? 0) < 4
  )
    return null;

  const names = new Map<string, InventoryQuerySuggestion>();
  for (const item of items) {
    for (const fact of [item.make, item.model]) {
      if (fact.status !== "known") continue;
      const key = normalizeName(fact.value);
      if (key === normalized) return null;
      if (lettersOnly.test(key) && !names.has(key))
        names.set(key, {
          query: fact.value,
          label: displayCarName(fact.value.trim()),
        });
    }
  }
  let suggestion: InventoryQuerySuggestion | null = null;
  for (const [name, candidate] of names) {
    if (!isOneEdit(normalized, name)) continue;
    if (suggestion) return null;
    suggestion = candidate;
  }
  return suggestion;
}
