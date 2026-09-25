import { describe, expect, test, vi } from "vitest";
import { readInventoryCatalog } from "../../src/features/inventory/inventoryCatalog";
import {
  filtersFromCriteria,
  emptyCriteria,
} from "../../src/features/inventory/criteria";
import { searchResult } from "./apiFixtures";

function page(
  start: number,
  count: number,
  total: number,
  next: string | null,
) {
  const response = searchResult();
  const original = response.data.items[0]!;
  response.data.items = Array.from({ length: count }, (_, index) => ({
    ...structuredClone(original),
    ref: { ...original.ref, source_id: String(start + index) },
  }));
  response.data.supported_total = total;
  response.data.next_cursor = next;
  response.data.applied_criteria = {
    query: "",
    soft_preferences: [],
    filters: filtersFromCriteria(emptyCriteria()),
  };
  return response;
}

describe("complete public facet catalog", () => {
  test("joins two bounded 50-item pages with the same snapshot and no browse presentation writes", async () => {
    const first = page(1, 50, 100, "next"),
      second = page(51, 50, 100, null);
    const api = {
      read: vi.fn().mockResolvedValueOnce(first).mockResolvedValueOnce(second),
    };
    const signal = new AbortController().signal;
    const result = await readInventoryCatalog(
      api,
      first.meta.inventory_snapshot_id!,
      signal,
    );
    expect(result).toHaveLength(100);
    expect(api.read).toHaveBeenCalledTimes(2);
    expect(api.read.mock.calls[0]![1]).toEqual(
      expect.objectContaining({
        signal,
        body: expect.objectContaining({
          page_size: 50,
          query: "",
          cursor: null,
          snapshot_id: first.meta.inventory_snapshot_id,
        }),
      }),
    );
    expect(api.read.mock.calls[1]![1].body.cursor).toBe("next");
    expect(api.read.mock.calls[1]![1].body.snapshot_id).toBe(
      first.meta.inventory_snapshot_id,
    );
  });
  test.each(["partial", "snapshot", "repeated", "third-page", "changed-total"])(
    "rejects %s catalogs rather than presenting partial counts",
    async (kind) => {
      const first = page(1, 50, 100, "next"),
        second = page(51, 50, 100, null);
      if (kind === "partial") second.data.items.pop();
      if (kind === "snapshot")
        second.meta.inventory_snapshot_id = "b".repeat(64);
      if (kind === "repeated") second.data.items[0] = first.data.items[0]!;
      if (kind === "third-page") second.data.next_cursor = "another";
      if (kind === "changed-total") second.data.supported_total = 101;
      const api = {
        read: vi
          .fn()
          .mockResolvedValueOnce(first)
          .mockResolvedValueOnce(second),
      };
      await expect(
        readInventoryCatalog(api, first.meta.inventory_snapshot_id!),
      ).rejects.toThrow();
      expect(api.read).toHaveBeenCalledTimes(2);
    },
  );
});
