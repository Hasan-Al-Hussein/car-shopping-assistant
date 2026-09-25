import type { components } from "../../../contracts/generated/api";

export type Schema<N extends keyof components["schemas"]> =
  components["schemas"][N];
export type Ref = Schema<"InventoryRef">;
export type DisplayFact =
  | Schema<"ListingSummary">["make"]
  | Schema<"ListingSummary">["year"]
  | Schema<"ListingSummary">["cash_price"];
export type ProofListing = {
  detail: Schema<"ListingDetail">;
  conflicts: {
    attribute: string;
    label: string;
    fact:
      | Schema<"ConflictingFact_Annotated_str__StringConstraints__">
      | Schema<"ConflictingFact_Annotated_int__Strict_strict_True___">;
  }[];
  source: {
    sheet: string;
    workbook_sha256: string;
    title_cell: string;
    description_cell: string;
    photo_cell: string;
    trim_cell: string;
    trim_raw: string;
  };
  heading: string;
};

export const refKey = (ref: Ref) =>
  JSON.stringify([ref.namespace, ref.snapshot_id, ref.source_id]);
export const listingPath = (ref: Ref) =>
  `/listing/${encodeURIComponent(ref.namespace)}/${encodeURIComponent(ref.snapshot_id)}/${encodeURIComponent(ref.source_id)}`;
