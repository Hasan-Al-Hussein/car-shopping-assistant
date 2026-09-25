import { createHash } from "node:crypto";
import { describe, expect, test } from "vitest";
import audit from "../../../Records/build/FE-03/source-fixture-audit.json";
import { validateSchema } from "../../../contracts/generated/runtime.schemas";
import { proofListings } from "../../src/design-proof/fixtures";
import type {
  DisplayFact,
  ProofListing,
  Schema,
} from "../../src/design-proof/types";

const workbookHash =
  "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9";
const snapshotId =
  "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217";
const selectedIds = ["4", "27", "52", "17", "35", "12", "22"];
const sourceCells = [
  ["4", "A5", "F5", "G5", "H5"],
  ["27", "A28", "F28", "G28", "H28"],
  ["52", "A53", "F53", "G53", "H53"],
  ["17", "A18", "F18", "G18", "H18"],
  ["35", "A36", "F36", "G36", "H36"],
  ["12", "A13", "F13", "G13", "H13"],
  ["22", "A23", "F23", "G23", "H23"],
] as const;
const listings: readonly ProofListing[] = proofListings;

function listing(sourceId: string): ProofListing {
  const result = listings.find(
    (item) => item.detail.listing.ref.source_id === sourceId,
  );
  if (!result) throw new Error(`Missing proof listing ${sourceId}`);
  return result;
}

function sourceRecord(sourceId: string) {
  const result = audit.records.find((item) => item.source_id === sourceId);
  if (!result) throw new Error(`Missing audited source ${sourceId}`);
  return result;
}

function evidenceOf(fact: DisplayFact): Schema<"SourceLocator">[] {
  if (fact.status === "known") return fact.evidence;
  if (fact.status === "conflicting") {
    return fact.claims.flatMap((claim) => claim.evidence);
  }
  return [];
}

describe("FE-03 audited proof fixture boundary", () => {
  test("contains exactly the seven selected source IDs, without duplicates or the spare photo candidate", () => {
    const actual = listings.map((item) => item.detail.listing.ref.source_id);
    expect(actual).toHaveLength(7);
    expect(new Set(actual).size).toBe(7);
    expect([...actual].sort()).toEqual([...selectedIds].sort());
    expect(audit.proof_dataset_source_ids).toEqual(selectedIds);
    expect(actual).not.toContain("1");
  });

  test("the proof snapshot hashes its explicit eight-key policy and is not the workbook hash", () => {
    const convention = audit.snapshot_reference_convention;
    const preimage = convention.preimage;
    expect(Object.keys(preimage).sort()).toEqual(
      [
        "namespace",
        "workbook_sha256",
        "sheet",
        "normalization_version",
        "extraction_version",
        "evidence_review_version",
        "photo_policy_version",
        "schema_version",
      ].sort(),
    );
    const canonical = JSON.stringify(preimage, Object.keys(preimage).sort());
    expect(createHash("sha256").update(canonical, "utf8").digest("hex")).toBe(
      snapshotId,
    );
    expect(convention.snapshot_id).toBe(snapshotId);
    expect(snapshotId).not.toBe(workbookHash);
    expect(preimage.workbook_sha256).toBe(workbookHash);
    expect(preimage.evidence_review_version).toBe(
      "fe03-source-fixture-audit-v1",
    );
    expect(convention.proposal_status).toContain("not published or activated");
  });

  test.each(sourceCells)(
    "listing %s validates and keeps its exact source ID/cells and immutable reference",
    (id, idCell, titleCell, descriptionCell, photoCell) => {
      const item = listing(id);
      const source = sourceRecord(id);
      expect(validateSchema("ListingDetail", item.detail)).toBe(true);
      expect(item.detail.listing.ref).toEqual({
        namespace: "provided-cars-cleaned",
        snapshot_id: snapshotId,
        source_id: id,
      });
      expect(item.detail.listing.ref).toEqual(source.proposed_design_proof_ref);
      expect(source.fields.source_id.cell).toBe(idCell);
      expect(String(source.fields.source_id.raw_value)).toBe(id);
      expect(source.source_locator).toMatchObject({
        workbook_sha256: workbookHash,
        sheet: "cleaned dataset",
        listing_id_cell: idCell,
      });
      expect(item.source).toMatchObject({
        workbook_sha256: workbookHash,
        sheet: "cleaned dataset",
        title_cell: titleCell,
        description_cell: descriptionCell,
        photo_cell: photoCell,
      });
      expect(item.detail.listing.title).toBe(source.fields.title.raw_value);
      expect(item.detail.description).toBe(source.description.raw_value);
      expect(item.detail.eligibility).toBe("simulated_eligible");
      expect(item.detail.eligibility_reason).toContain("synthetic eligibility");
    },
  );

  test("every photo retains its own exact audited URL, including the HEIC suffix and source query", () => {
    for (const item of listings) {
      const source = sourceRecord(item.detail.listing.ref.source_id);
      expect(item.detail.listing.photo).toMatchObject({
        source: "supplied_listing",
        state: "source_present",
        url: source.photo.url,
      });
      expect(item.source.photo_cell).toBe(source.photo.source_cell);
    }
    expect(listing("4").detail.listing.photo.url).toBe(
      "https://dbz-images.dubizzle.com/images/2024/05/19/c47ef9ac50f548b580033ad92d14bd0c-.heic?impolicy=dpv",
    );
  });
});

describe("FE-03 conflicting source claims survive fixture mapping", () => {
  const conflicts = [
    {
      id: "4",
      attribute: "trim",
      values: ["e 400", "E 450"],
      cells: ["E5", "F5"],
    },
    {
      id: "27",
      attribute: "service_history",
      values: ["Partial Service History", "Full Service History"],
      cells: ["F28", "G28"],
    },
    {
      id: "52",
      attribute: "model_year",
      values: [2015, 2014, 2014],
      cells: ["B53", "F53", "G53"],
    },
    {
      id: "17",
      attribute: "engine",
      values: ["W12", "W12", "4.0L V8 Twin Turbo"],
      cells: ["F18", "G18", "G18"],
    },
  ];

  test.each(conflicts)(
    "$id preserves every $attribute claim, original evidence cell and exact supporting span",
    ({ id, attribute, values, cells }) => {
      const item = listing(id);
      const source = sourceRecord(id);
      const conflict = item.conflicts.find(
        (value) => value.attribute === attribute,
      );
      const audited = source.material_conflicts.find(
        (value) => value.attribute === attribute,
      );
      expect(item.conflicts).toHaveLength(1);
      if (!conflict || !audited)
        throw new Error(`Missing ${attribute} conflict`);
      expect(conflict.fact.status).toBe("conflicting");
      expect(conflict.fact.claims.map((claim) => claim.value)).toEqual(values);
      const evidence = conflict.fact.claims.flatMap((claim) => claim.evidence);
      expect(evidence.map((value) => value.cell)).toEqual(cells);
      expect(evidence).toHaveLength(audited.claims.length);
      audited.claims.forEach((claim, index) => {
        const original = claim.evidence;
        const text =
          "raw_text" in original
            ? original.raw_text
            : "xml_value" in original
              ? original.xml_value
              : undefined;
        if (text === undefined) throw new Error("Missing exact source claim");
        const span = "span" in original ? original.span : undefined;
        expect(evidence[index]).toMatchObject({
          workbook_sha256: workbookHash,
          sheet: "cleaned dataset",
          cell: original.cell,
          raw_text: text,
          span_start: span?.start ?? 0,
          span_end: span?.end ?? Array.from(text).length,
          verification: "source_claim",
          review_status: "reviewed_extraction",
        });
      });
      expect(item.detail.listing.evidence_warnings).toContain(conflict.label);
      if (attribute === "trim") {
        expect(item.detail.listing.trim).toEqual(conflict.fact);
      } else if (attribute === "service_history") {
        expect(item.detail.service_history).toEqual(conflict.fact);
      } else if (attribute === "model_year") {
        expect(item.detail.listing.year).toEqual(conflict.fact);
      } else {
        // Engine evidence is supplemental; do not invent a new frozen DTO field.
        expect(item.detail).not.toHaveProperty("engine");
        expect(
          validateSchema(
            "ConflictingFact_Annotated_str__StringConstraints__",
            conflict.fact,
          ),
        ).toBe(true);
      }
    },
  );

  test("records without audited conflicts do not acquire invented conflict claims", () => {
    for (const id of ["35", "12", "22"]) {
      expect(listing(id).conflicts).toEqual([]);
    }
  });
});

describe("FE-03 absent values, money roles and source labels", () => {
  test("GLC trim other is unknown/not_stated while its raw source and cell remain inspectable", () => {
    const item = listing("27");
    expect(item.detail.listing.trim).toEqual({
      status: "unknown",
      reason: "not_stated",
    });
    expect(item.source).toMatchObject({ trim_raw: "other", trim_cell: "E28" });
    expect(sourceRecord("27").fields.trim.raw_value).toBe("other");
  });

  test("the Mini dot description stays in source copy and supports no invented descriptive fact", () => {
    const item = listing("35");
    expect(item.detail.description).toBe(".");
    expect(item.source.description_cell).toBe("G36");
    expect(item.detail.listing.cash_price.status).toBe("unknown");
    expect(item.detail.listing.mileage_km.status).toBe("unknown");
    for (const fact of [
      item.detail.body_type,
      item.detail.fuel_type,
      item.detail.location,
      item.detail.service_history,
      item.detail.transmission,
      item.detail.warranty,
    ]) {
      expect(fact.status).toBe("unknown");
      expect(evidenceOf(fact)).toEqual([]);
    }
  });

  test("Mazda cash price is AED 35000, with cash evidence rather than the AED 3000 salary requirement", () => {
    const item = listing("12");
    expect(item.detail.listing.cash_price).toMatchObject({
      status: "known",
      qualifier: "exact",
      value: { minor_units: 3_500_000, currency: "AED", basis: "cash" },
    });
    expect(evidenceOf(item.detail.listing.cash_price)).toEqual([
      expect.objectContaining({
        cell: "G13",
        raw_text: "PRICE REDUCED 35000 AED",
        semantic_role: "cash_price",
        verification: "source_claim",
      }),
    ]);
    expect(item.detail.description).toContain(
      "Salary Required:- AED 3000/-(WPS)",
    );
    for (const other of listings.filter((value) => value !== item)) {
      expect(other.detail.listing.cash_price).toEqual({
        status: "unknown",
        reason: "not_stated",
      });
    }
  });

  test("numeric Mazda model and Aston Martin trim remain categorical labels with their original cells", () => {
    const model = listing("12").detail.listing.model;
    const trim = listing("22").detail.listing.trim;
    expect(model).toMatchObject({ status: "known", value: "3" });
    expect(trim).toMatchObject({ status: "known", value: "707" });
    expect(evidenceOf(model)).toEqual([
      expect.objectContaining({ cell: "D13", raw_text: "3" }),
    ]);
    expect(evidenceOf(trim)).toEqual([
      expect.objectContaining({ cell: "E23", raw_text: "707" }),
    ]);
    expect(sourceRecord("12").fields.model).toMatchObject({
      raw_value: 3,
      raw_type: "float",
    });
    expect(sourceRecord("22").fields.trim).toMatchObject({
      raw_value: 707,
      raw_type: "float",
    });
    expect(listing("22").detail.listing.mileage_km.status).toBe("unknown");
  });

  test("the complete Arabic title survives without translation, normalization or dropped numeric tokens", () => {
    expect(listing("35").detail.listing.title).toBe("ميني كوبر 2017 S");
    expect(listing("35").source.title_cell).toBe("F36");
    expect(Array.from(listing("35").detail.listing.title)).toHaveLength(16);
  });
});
