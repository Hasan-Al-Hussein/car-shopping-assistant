import type { Schema } from "../shared/api/contracts";
import {
  criterionFields,
  rangeFields,
  emptyCriteria,
  filtersFromCriteria,
  type CriteriaForm,
} from "../features/inventory/criteria";

export type InventoryRef = Schema<"InventoryRef">;
export const refKey = (ref: InventoryRef) =>
  JSON.stringify([ref.namespace, ref.snapshot_id, ref.source_id]);
export const encodeRef = (ref: InventoryRef) =>
  [ref.namespace, ref.snapshot_id, ref.source_id].join("~");
export const listingPath = (ref: InventoryRef) => `/cars/${encodeRef(ref)}`;
export const isLocator = (value: string | null | undefined): value is string =>
  !!value && /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value);

export function decodeRef(value: string | undefined): InventoryRef | null {
  if (!value || value.length > 258) return null;
  const parts = value.split("~");
  // URL grammar for the frozen scoped reference, before any API request is built.
  if (
    parts.length !== 3 ||
    !/^[a-z0-9_-]{1,64}$/.test(parts[0]!) ||
    !/^[0-9a-f]{64}$/.test(parts[1]!) ||
    !/^[A-Za-z0-9._-]{1,128}$/.test(parts[2]!)
  )
    return null;
  const ref = {
    namespace: parts[0]!,
    snapshot_id: parts[1]!,
    source_id: parts[2]!,
  };
  return ref;
}

export type BrowseRoute = CriteriaForm & {
  snapshot: string | null;
  cursor: string | null;
  valid: boolean;
};
const browseKeys = new Set<string>([
  ...criterionFields.map(([key]) => key),
  ...rangeFields.map(([key]) => key),
  "snapshot",
  "cursor",
]);
const hasControlCharacter = (value: string) =>
  [...value].some((character) => character.charCodeAt(0) < 32);

/** Free text stays in memory; only structured public inventory filters enter history. */
export function parseBrowseQuery(search: string): BrowseRoute {
  const query = new URLSearchParams(search);
  let valid = [...query.keys()].every(
    (key) => browseKeys.has(key) && query.getAll(key).length === 1,
  );
  const text = (key: string) => {
    const value = query.get(key) ?? "";
    if (value.length > 200 || hasControlCharacter(value)) valid = false;
    return value;
  };
  const criteria = emptyCriteria();
  for (const [key] of [...criterionFields, ...rangeFields])
    criteria[key] = text(key);
  try {
    filtersFromCriteria(criteria);
  } catch {
    valid = false;
  }
  const snapshot = query.get("snapshot"),
    cursor = query.get("cursor");
  if (snapshot !== null && !/^[0-9a-f]{64}$/.test(snapshot)) valid = false;
  if (
    cursor !== null &&
    (!snapshot ||
      !cursor ||
      cursor.length > 2048 ||
      hasControlCharacter(cursor))
  )
    valid = false;
  return { ...criteria, snapshot, cursor, valid };
}

export function browseQuery(
  route: Partial<Omit<BrowseRoute, "valid">>,
): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(route))
    if (browseKeys.has(key) && value) query.set(key, value);
  return query.size ? `?${query}` : "";
}

export function parseOperationQuery(search: string): {
  valid: boolean;
  generation: string | null;
} {
  const query = new URLSearchParams(search),
    generation = query.get("submitted_store_generation");
  return {
    valid:
      [...query.keys()].every((key) => key === "submitted_store_generation") &&
      query.getAll("submitted_store_generation").length <= 1 &&
      (generation === null || isLocator(generation)),
    generation,
  };
}
/** Recovery locators are noncredentials. No contact, review token or authority enters a URL. */
export function operationPath(
  operationKey: string,
  submittedStoreGeneration: string,
): string {
  if (
    !/^[A-Za-z0-9_-]{43}$/.test(operationKey) ||
    !isLocator(submittedStoreGeneration)
  )
    throw Error("Invalid original operation locator");
  return `/operations/${operationKey}?submitted_store_generation=${submittedStoreGeneration}`;
}

export function parseComparison(search: string): InventoryRef[] | null {
  const query = new URLSearchParams(search);
  if ([...query.keys()].some((key) => key !== "ref")) return null;
  const values = query.getAll("ref");
  if (values.length > 3) return null;
  const refs = values.map(decodeRef);
  if (refs.some((ref) => !ref) || new Set(values).size !== values.length)
    return null;
  return refs as InventoryRef[];
}

export function comparisonPath(refs: InventoryRef[]): string {
  const query = new URLSearchParams();
  for (const ref of refs) query.append("ref", encodeRef(ref));
  return `/compare${query.size ? `?${query}` : ""}`;
}

export function safeReturnPath(value: unknown): string {
  if (
    typeof value !== "string" ||
    !value.startsWith("/cars") ||
    value.includes("#")
  )
    return "/cars";
  const [path, search = ""] = value.split("?");
  return path === "/cars" && parseBrowseQuery(search).valid ? value : "/cars";
}
