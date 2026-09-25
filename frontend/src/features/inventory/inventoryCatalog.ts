import type { ApiClient } from "../../shared/api/ApiClient";
import type { ResponseOf, Schema } from "../../shared/api/contracts";
import { emptyCriteria, filtersFromCriteria } from "./criteria";
import { refKey } from "../../app/routes";

/** Public facet data only; never publishes or replaces the user's browse presentation. */
export async function readInventoryCatalog(
  api: Pick<ApiClient, "read">,
  snapshot: string,
  signal?: AbortSignal,
) {
  const items: Schema<"ListingSummary">[] = [];
  let cursor: string | null = null;
  let total: number | null = null;
  for (let page = 0; page < 2; page++) {
    const response: ResponseOf<"search_inventory"> = await api.read(
      "search_inventory",
      {
        signal,
        body: {
          client_request_id: crypto.randomUUID(),
          query: "",
          soft_preferences: [],
          filters: filtersFromCriteria(emptyCriteria()),
          snapshot_id: snapshot,
          cursor,
          page_size: 50,
        },
      },
    );
    const result: Schema<"SearchResult"> = response.data;
    if (
      response.meta.inventory_snapshot_id !== snapshot ||
      result.presentation.snapshot_id !== snapshot ||
      result.items.some((item) => item.ref.snapshot_id !== snapshot) ||
      (total !== null && result.supported_total !== total) ||
      result.unsupported_constraints?.length ||
      result.applied_criteria.query ||
      result.applied_criteria.soft_preferences?.length ||
      Object.values(result.applied_criteria.filters ?? {}).some((value) =>
        Array.isArray(value)
          ? value.length > 0
          : value !== null && value !== undefined,
      )
    ) {
      throw Error("Inventory choices changed while loading. Please retry.");
    }
    total = result.supported_total;
    items.push(...result.items);
    if (new Set(items.map((item) => refKey(item.ref))).size !== items.length) {
      throw Error("Inventory choices contain repeated references.");
    }
    cursor = result.next_cursor;
    if (!cursor) {
      if (items.length !== total)
        throw Error("The complete inventory choices could not be loaded.");
      return items;
    }
  }
  // Never present the bounded partial catalogue as all inventory.
  throw Error("The complete inventory choices could not be loaded.");
}
