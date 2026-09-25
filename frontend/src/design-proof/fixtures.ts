// Generated only from Records/build/FE-03/source-fixture-audit.json. Development proof, never production extraction.
import type { ProofListing } from "./types";
export const proofListings = [
  {
    detail: {
      state: "current",
      listing: {
        ref: {
          namespace: "provided-cars-cleaned",
          snapshot_id:
            "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217",
          source_id: "4",
        },
        title: "MERCEDES E 450 COUPE 2019 JAPANESE SPECS",
        make: {
          status: "known",
          qualifier: "exact",
          value: "mercedes-benz",
          evidence: [
            {
              category: "structured_source",
              cell: "C5",
              evidence_id: "215137f6-ef32-999c-8a50-7cb4c6353336",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "mercedes-benz",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 13,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        model: {
          status: "known",
          qualifier: "exact",
          value: "e-class",
          evidence: [
            {
              category: "structured_source",
              cell: "D5",
              evidence_id: "cac3ee79-95e8-c8da-55c1-b44894cef502",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "e-class",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 7,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        trim: {
          status: "conflicting",
          claims: [
            {
              value: "e 400",
              qualifier: "exact",
              evidence: [
                {
                  category: "structured_source",
                  cell: "E5",
                  evidence_id: "cdc8d346-5e27-82f0-0f35-da91b310d7c1",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "e 400",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 0,
                  span_end: 5,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: "E 450",
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "F5",
                  evidence_id: "512b48ae-29d3-b073-be78-0dca8f6b687d",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "E 450",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 9,
                  span_end: 14,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
          ],
        },
        year: {
          status: "known",
          qualifier: "exact",
          value: 2019,
          evidence: [
            {
              category: "structured_source",
              cell: "B5",
              evidence_id: "ba444460-cf30-2cf0-17a8-b0b727e00569",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "2019",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 4,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        cash_price: {
          status: "unknown",
          reason: "not_stated",
        },
        mileage_km: {
          status: "known",
          qualifier: "exact",
          value: 56000,
          evidence: [
            {
              category: "seller_description",
              cell: "G5",
              evidence_id: "c219d8fa-b0b8-1e40-7594-3f3c6c848be7",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "Mileage - 56,000 KM",
              review_status: "reviewed_extraction",
              semantic_role: "vehicle_mileage",
              sheet: "cleaned dataset",
              span_start: 13,
              span_end: 32,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        evidence_warnings: [
          "Trim differs: e 400 in the field; E 450 in the title.",
        ],
        photo: {
          source: "supplied_listing",
          state: "source_present",
          url: "https://dbz-images.dubizzle.com/images/2024/05/19/c47ef9ac50f548b580033ad92d14bd0c-.heic?impolicy=dpv",
          alt: "Source photograph for listing 4: mercedes-benz e-class",
        },
      },
      description:
        "Model - 2019 Mileage - 56,000 KM Grade - 4.5 B +971568992992 Japanese Specs Clean Title Scratch Less Car Fresh Import No Paint No Accident Lane assist Radar Adaptive Cruise Control Heads Up Display Auto park 360 ° Camera Sunroof AMG Rims Brumester Surround Sound System",
      eligibility: "simulated_eligible",
      eligibility_reason:
        "FE-03 synthetic eligibility only. No real stock or booking availability established.",
      body_type: {
        status: "unknown",
        reason: "unsupported",
      },
      fuel_type: {
        status: "unknown",
        reason: "unsupported",
      },
      location: {
        status: "unknown",
        reason: "unsupported",
      },
      service_history: {
        status: "unknown",
        reason: "unsupported",
      },
      transmission: {
        status: "unknown",
        reason: "unsupported",
      },
      warranty: {
        status: "unknown",
        reason: "unsupported",
      },
    },
    conflicts: [
      {
        attribute: "trim",
        label: "Trim differs: e 400 in the field; E 450 in the title.",
        fact: {
          status: "conflicting",
          claims: [
            {
              value: "e 400",
              qualifier: "exact",
              evidence: [
                {
                  category: "structured_source",
                  cell: "E5",
                  evidence_id: "cdc8d346-5e27-82f0-0f35-da91b310d7c1",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "e 400",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 0,
                  span_end: 5,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: "E 450",
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "F5",
                  evidence_id: "512b48ae-29d3-b073-be78-0dca8f6b687d",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "E 450",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 9,
                  span_end: 14,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
          ],
        },
      },
    ],
    source: {
      sheet: "cleaned dataset",
      workbook_sha256:
        "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
      title_cell: "F5",
      description_cell: "G5",
      photo_cell: "H5",
      trim_cell: "E5",
      trim_raw: "e 400",
    },
    heading: "mercedes-benz e-class",
  },
  {
    detail: {
      state: "current",
      listing: {
        ref: {
          namespace: "provided-cars-cleaned",
          snapshot_id:
            "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217",
          source_id: "27",
        },
        title: "Mercedes GLC 250 Coupe 2019 Partial Service History GCC",
        make: {
          status: "known",
          qualifier: "exact",
          value: "mercedes-benz",
          evidence: [
            {
              category: "structured_source",
              cell: "C28",
              evidence_id: "8c290eba-df14-e92e-8126-23e0783371f1",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "mercedes-benz",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 13,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        model: {
          status: "known",
          qualifier: "exact",
          value: "glc coupe",
          evidence: [
            {
              category: "structured_source",
              cell: "D28",
              evidence_id: "22c35a49-e575-3280-bdaf-b347595ab5db",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "glc coupe",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 9,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        trim: {
          status: "unknown",
          reason: "not_stated",
        },
        year: {
          status: "known",
          qualifier: "exact",
          value: 2019,
          evidence: [
            {
              category: "structured_source",
              cell: "B28",
              evidence_id: "11e6ce52-3a2f-8ef8-b8f7-80396e660dfb",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "2019",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 4,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        cash_price: {
          status: "unknown",
          reason: "not_stated",
        },
        mileage_km: {
          status: "known",
          qualifier: "exact",
          value: 75500,
          evidence: [
            {
              category: "seller_description",
              cell: "G28",
              evidence_id: "8b7801e0-7794-7e07-71bc-b16fcf9f87b4",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "75500 km",
              review_status: "reviewed_extraction",
              semantic_role: "vehicle_mileage",
              sheet: "cleaned dataset",
              span_start: 46,
              span_end: 54,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        evidence_warnings: [
          "Service history differs: partial in the title; full in the description.",
        ],
        photo: {
          source: "supplied_listing",
          state: "source_present",
          url: "https://dbz-images.dubizzle.com/images/2024/10/24/573655b8700f45efab90e162e300a669-.jpeg?impolicy=dpv",
          alt: "Source photograph for listing 27: mercedes-benz glc coupe",
        },
      },
      description:
        "- Mercedes GLC 250 Coupe - 2019 - GCC Specs - 75500 km - 2.0T 4 Cylinder - Silver exterior with Red Leather Interior - Full Service History Do not hesitate to call us for any info! • Saif (عربي - English): +971522051890 • Dhinakar (Tamil - Hindi - English): +971525368168 • Attia (عربي - English): +971525384938 • Amer (عربي - English): +971525390890 We also provide: - Car Financing, Buying and trading. - Car insurance - Worldwide export - Window Tint - Ceramic Coat & Detailing Our showroom is open all week long from 9.00am to 8.00pm Oasis Cars, Showroom 244, Dubai Auto Zone, DUCAMZ - Ras Al Khor - Dubai https://goo.gl/maps/mscP8HEQsjNVayuJ8",
      eligibility: "simulated_eligible",
      eligibility_reason:
        "FE-03 synthetic eligibility only. No real stock or booking availability established.",
      body_type: {
        status: "unknown",
        reason: "unsupported",
      },
      fuel_type: {
        status: "unknown",
        reason: "unsupported",
      },
      location: {
        status: "unknown",
        reason: "unsupported",
      },
      service_history: {
        status: "conflicting",
        claims: [
          {
            value: "Partial Service History",
            qualifier: "exact",
            evidence: [
              {
                category: "seller_description",
                cell: "F28",
                evidence_id: "f724451c-4fd8-1fe6-9ebc-e9ea8cee1513",
                extraction_version: "fe03-manual-excerpts-v1",
                raw_text: "Partial Service History",
                review_status: "reviewed_extraction",
                semantic_role: "other",
                sheet: "cleaned dataset",
                span_start: 28,
                span_end: 51,
                verification: "source_claim",
                workbook_sha256:
                  "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
              },
            ],
          },
          {
            value: "Full Service History",
            qualifier: "exact",
            evidence: [
              {
                category: "seller_description",
                cell: "G28",
                evidence_id: "4c241673-f799-e9e5-d46c-65196ee37c93",
                extraction_version: "fe03-manual-excerpts-v1",
                raw_text: "Full Service History",
                review_status: "reviewed_extraction",
                semantic_role: "other",
                sheet: "cleaned dataset",
                span_start: 119,
                span_end: 139,
                verification: "source_claim",
                workbook_sha256:
                  "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
              },
            ],
          },
        ],
      },
      transmission: {
        status: "unknown",
        reason: "unsupported",
      },
      warranty: {
        status: "unknown",
        reason: "unsupported",
      },
    },
    conflicts: [
      {
        attribute: "service_history",
        label:
          "Service history differs: partial in the title; full in the description.",
        fact: {
          status: "conflicting",
          claims: [
            {
              value: "Partial Service History",
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "F28",
                  evidence_id: "f724451c-4fd8-1fe6-9ebc-e9ea8cee1513",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "Partial Service History",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 28,
                  span_end: 51,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: "Full Service History",
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "G28",
                  evidence_id: "4c241673-f799-e9e5-d46c-65196ee37c93",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "Full Service History",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 119,
                  span_end: 139,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
          ],
        },
      },
    ],
    source: {
      sheet: "cleaned dataset",
      workbook_sha256:
        "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
      title_cell: "F28",
      description_cell: "G28",
      photo_cell: "H28",
      trim_cell: "E28",
      trim_raw: "other",
    },
    heading: "mercedes-benz glc coupe",
  },
  {
    detail: {
      state: "current",
      listing: {
        ref: {
          namespace: "provided-cars-cleaned",
          snapshot_id:
            "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217",
          source_id: "52",
        },
        title: "BENZ S63 | AMG | 2014 | CLEAN CAR | FRESH JAPAN IMPORT",
        make: {
          status: "known",
          qualifier: "exact",
          value: "mercedes-benz",
          evidence: [
            {
              category: "structured_source",
              cell: "C53",
              evidence_id: "9b5f6e1d-811c-bf47-5220-bcb310e539c3",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "mercedes-benz",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 13,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        model: {
          status: "known",
          qualifier: "exact",
          value: "s-class",
          evidence: [
            {
              category: "structured_source",
              cell: "D53",
              evidence_id: "3e4549da-b71f-a576-c738-1a291ae54be9",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "s-class",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 7,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        trim: {
          status: "known",
          qualifier: "exact",
          value: "s 63 amg 4matic",
          evidence: [
            {
              category: "structured_source",
              cell: "E53",
              evidence_id: "2834194e-e4d6-ec3f-0a73-ef3c7fdd5cca",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "s 63 amg 4matic",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 15,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        year: {
          status: "conflicting",
          claims: [
            {
              value: 2015,
              qualifier: "exact",
              evidence: [
                {
                  category: "structured_source",
                  cell: "B53",
                  evidence_id: "95f78e1c-4d77-8011-8eaa-d03b0368e7d6",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "2015.0",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 0,
                  span_end: 6,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: 2014,
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "F53",
                  evidence_id: "c6031e3f-3902-437f-c2e8-6cb3f08894df",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "2014",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 17,
                  span_end: 21,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: 2014,
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "G53",
                  evidence_id: "ec47bc26-2720-c785-22be-fdac00bb928d",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "Year Of the Model - 2014",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 26,
                  span_end: 50,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
          ],
        },
        cash_price: {
          status: "unknown",
          reason: "not_stated",
        },
        mileage_km: {
          status: "unknown",
          reason: "unsupported",
        },
        evidence_warnings: [
          "Model year differs: 2015 in the field; 2014 in the title and description.",
        ],
        photo: {
          source: "supplied_listing",
          state: "source_present",
          url: "https://dbz-images.dubizzle.com/images/2024/11/21/c6450516405b4dfeb166571e0138839a-.jpeg?impolicy=dpv",
          alt: "Source photograph for listing 52: mercedes-benz s-class",
        },
      },
      description:
        "• Mercedes Benz S63 AMG • Year Of the Model - 2014 • Black Interior • Dynamic Seats • Cooling Seats • Low Mileage • Japan Imported • Recently Arrived • Neat & Clean Car ••••••••••••••••••••••••••••••••••••••••••••••••••••••• Follow Us On Instagram For More Luxury Cars, Just Click on the Link. https://instagram.com/mirzaautomobilefze?utm_medium=copy_link ••••••••••••••••••••••••••••••••••••••••••••••••••••••• We have Direct access more then 160 Auctions in Japan. We can buy any type or any Model of the car by your Special Order, So if you are Looking for Any type of the Car, Contact with Us or visit Our Showroom Mirza Automobile FZE, ••••••••••••••••••••••••••••••••••••••••••••••••••••••• About Us : A name you can trust, Welcome to Mirza Automobile FZE, We've been in the auto industry for 16 years in UAE, and 30 years in Japan. ••••••••••••••••••••••••••••••••••••••••••••••••••••••• Contact us : ( Mob / Whatsapp ) • Ayaz Wazir : +971 54 3069550 • Mirza Faizan Baig : +971 50 8685237 ••••••••••••••••••••••••••••••••••••••••••••••••••••••• Our Service : ( VIP ) • Flexible finance and insurance options . • Expert sales and after-sales support . • Car registration assistance . ( Insurance - Registration ) . • Export deals and services available . • we can deliver the car to any where on U.A.E",
      eligibility: "simulated_eligible",
      eligibility_reason:
        "FE-03 synthetic eligibility only. No real stock or booking availability established.",
      body_type: {
        status: "unknown",
        reason: "unsupported",
      },
      fuel_type: {
        status: "unknown",
        reason: "unsupported",
      },
      location: {
        status: "unknown",
        reason: "unsupported",
      },
      service_history: {
        status: "unknown",
        reason: "unsupported",
      },
      transmission: {
        status: "unknown",
        reason: "unsupported",
      },
      warranty: {
        status: "unknown",
        reason: "unsupported",
      },
    },
    conflicts: [
      {
        attribute: "model_year",
        label:
          "Model year differs: 2015 in the field; 2014 in the title and description.",
        fact: {
          status: "conflicting",
          claims: [
            {
              value: 2015,
              qualifier: "exact",
              evidence: [
                {
                  category: "structured_source",
                  cell: "B53",
                  evidence_id: "95f78e1c-4d77-8011-8eaa-d03b0368e7d6",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "2015.0",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 0,
                  span_end: 6,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: 2014,
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "F53",
                  evidence_id: "c6031e3f-3902-437f-c2e8-6cb3f08894df",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "2014",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 17,
                  span_end: 21,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: 2014,
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "G53",
                  evidence_id: "ec47bc26-2720-c785-22be-fdac00bb928d",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "Year Of the Model - 2014",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 26,
                  span_end: 50,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
          ],
        },
      },
    ],
    source: {
      sheet: "cleaned dataset",
      workbook_sha256:
        "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
      title_cell: "F53",
      description_cell: "G53",
      photo_cell: "H53",
      trim_cell: "E53",
      trim_raw: "s 63 amg 4matic",
    },
    heading: "mercedes-benz s-class",
  },
  {
    detail: {
      state: "current",
      listing: {
        ref: {
          namespace: "provided-cars-cleaned",
          snapshot_id:
            "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217",
          source_id: "17",
        },
        title:
          "2020 | BENTLEY | CONTINENTAL | GTC | W12 | FULL OPTION | EXCELLENT CONDITION |",
        make: {
          status: "known",
          qualifier: "exact",
          value: "bentley",
          evidence: [
            {
              category: "structured_source",
              cell: "C18",
              evidence_id: "a2a783b5-9248-f16a-16a5-564b43a2e857",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "bentley",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 7,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        model: {
          status: "known",
          qualifier: "exact",
          value: "continental",
          evidence: [
            {
              category: "structured_source",
              cell: "D18",
              evidence_id: "cd8ce0a5-c330-fa6a-691b-1296a82d5dc1",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "continental",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 11,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        trim: {
          status: "known",
          qualifier: "exact",
          value: "gtc mulliner",
          evidence: [
            {
              category: "structured_source",
              cell: "E18",
              evidence_id: "041cec9f-270d-74a5-318e-1c55b521c8ba",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "gtc mulliner",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 12,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        year: {
          status: "known",
          qualifier: "exact",
          value: 2020,
          evidence: [
            {
              category: "structured_source",
              cell: "B18",
              evidence_id: "14d4ba6b-749e-8a98-0bcc-346b841cad72",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "2020",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 4,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        cash_price: {
          status: "unknown",
          reason: "not_stated",
        },
        mileage_km: {
          status: "unknown",
          reason: "unsupported",
        },
        evidence_warnings: [
          "Engine differs: W12 in the title and description opening; 4.0L V8 Twin Turbo later in the description.",
        ],
        photo: {
          source: "supplied_listing",
          state: "source_present",
          url: "https://dbz-images.dubizzle.com/images/2024/06/20/6436315e640b4dff9d204c789622c3c1-.jpeg?impolicy=dpv",
          alt: "Source photograph for listing 17: bentley continental",
        },
      },
      description:
        '2020 | BENTLEY | CONTINENTAL | GTC | W12 | FULL OPTION | EXCELLENT CONDITION | **Transmission - 8 Speed Dual Clutch Transmission with Active All-Wheel Drive Spec - European Horse power - 542 Hp Max Speed - 198 mph/ 318km/h Acceleration - 0 -100 km/h in 4.0 seconds Engine - 4.0L V8 Twin Turbo **EXTRA OPTIONS Bentley Rotating Display Welcome Lighting Ambient Lighting Coupe Convertible LED Matrix Headlamps Remote Controlled Garage Door Opener **Naim for Bentley - PREMIUM AUDIO SYSTEM - 18 Speakers - 2200w - 8 Different DSP Modes - Apple Car Play Continental GTC Specification **Touring Specification - Head Up Display - Night Vision - Active Cruise Control - Lane Assist - Lane Departure Front Seat Comfort Specification - Adjustment Headrest - Ventilation and Massage Function - Moving Headrest - Adjustable Cushion Length - Adjustable Side Bolster -Mulliner Driving Specification with - Contrast Binding to Carpet Overmats - Contrast Stitching and Seat Piping - Black and Polished Edge Wheel - Mulliner Range - Solid and Metallic - Contrast Seatbelts - by Mulliner **THE (7SEVEN LUXURY) - THE TRUE DEFINITION OF LUXURY ** Multi brand dealer with decades of experience in the UAE for new and pre-owned luxury vehicles. ** We are committed to providing exceptional service in every part of our business, as customer satisfaction is our top priority. **For more details follow us on INSTA "sevenluxury.ae" and visit our showroom in Al Quoz industrial area 3 Dubai',
      eligibility: "simulated_eligible",
      eligibility_reason:
        "FE-03 synthetic eligibility only. No real stock or booking availability established.",
      body_type: {
        status: "unknown",
        reason: "unsupported",
      },
      fuel_type: {
        status: "unknown",
        reason: "unsupported",
      },
      location: {
        status: "unknown",
        reason: "unsupported",
      },
      service_history: {
        status: "unknown",
        reason: "unsupported",
      },
      transmission: {
        status: "unknown",
        reason: "unsupported",
      },
      warranty: {
        status: "unknown",
        reason: "unsupported",
      },
    },
    conflicts: [
      {
        attribute: "engine",
        label:
          "Engine differs: W12 in the title and description opening; 4.0L V8 Twin Turbo later in the description.",
        fact: {
          status: "conflicting",
          claims: [
            {
              value: "W12",
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "F18",
                  evidence_id: "06cfa423-855e-72fc-0ec3-a5ab683a49e5",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "W12",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 37,
                  span_end: 40,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: "W12",
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "G18",
                  evidence_id: "b9263231-3cee-0858-9b4b-5683b376882f",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "W12",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 37,
                  span_end: 40,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
            {
              value: "4.0L V8 Twin Turbo",
              qualifier: "exact",
              evidence: [
                {
                  category: "seller_description",
                  cell: "G18",
                  evidence_id: "54ee5d6e-a69a-26a8-a31d-3e06c3f64e8c",
                  extraction_version: "fe03-manual-excerpts-v1",
                  raw_text: "Engine - 4.0L V8 Twin Turbo",
                  review_status: "reviewed_extraction",
                  semantic_role: "other",
                  sheet: "cleaned dataset",
                  span_start: 265,
                  span_end: 292,
                  verification: "source_claim",
                  workbook_sha256:
                    "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
                },
              ],
            },
          ],
        },
      },
    ],
    source: {
      sheet: "cleaned dataset",
      workbook_sha256:
        "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
      title_cell: "F18",
      description_cell: "G18",
      photo_cell: "H18",
      trim_cell: "E18",
      trim_raw: "gtc mulliner",
    },
    heading: "bentley continental",
  },
  {
    detail: {
      state: "current",
      listing: {
        ref: {
          namespace: "provided-cars-cleaned",
          snapshot_id:
            "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217",
          source_id: "35",
        },
        title: "ميني كوبر 2017 S",
        make: {
          status: "known",
          qualifier: "exact",
          value: "mini",
          evidence: [
            {
              category: "structured_source",
              cell: "C36",
              evidence_id: "5028d44e-18fe-fe25-be7f-faa3ba4bbdde",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "mini",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 4,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        model: {
          status: "known",
          qualifier: "exact",
          value: "cooper",
          evidence: [
            {
              category: "structured_source",
              cell: "D36",
              evidence_id: "076a6b16-a82e-d019-89fc-3b218dd70a1e",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "cooper",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 6,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        trim: {
          status: "known",
          qualifier: "exact",
          value: "s",
          evidence: [
            {
              category: "structured_source",
              cell: "E36",
              evidence_id: "0e886d44-fb20-6d4a-0a43-3125cc590f6e",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "s",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 1,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        year: {
          status: "known",
          qualifier: "exact",
          value: 2017,
          evidence: [
            {
              category: "structured_source",
              cell: "B36",
              evidence_id: "e0347136-e907-770e-b09a-a7b2b8f5c8a8",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "2017",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 4,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        cash_price: {
          status: "unknown",
          reason: "not_stated",
        },
        mileage_km: {
          status: "unknown",
          reason: "unsupported",
        },
        evidence_warnings: [],
        photo: {
          source: "supplied_listing",
          state: "source_present",
          url: "https://dbz-images.dubizzle.com/images/2024/12/04/79361b583f854d6cb6e191681ba566e7-.jpeg?impolicy=dpv",
          alt: "Source photograph for listing 35: mini cooper",
        },
      },
      description: ".",
      eligibility: "simulated_eligible",
      eligibility_reason:
        "FE-03 synthetic eligibility only. No real stock or booking availability established.",
      body_type: {
        status: "unknown",
        reason: "unsupported",
      },
      fuel_type: {
        status: "unknown",
        reason: "unsupported",
      },
      location: {
        status: "unknown",
        reason: "unsupported",
      },
      service_history: {
        status: "unknown",
        reason: "unsupported",
      },
      transmission: {
        status: "unknown",
        reason: "unsupported",
      },
      warranty: {
        status: "unknown",
        reason: "unsupported",
      },
    },
    conflicts: [],
    source: {
      sheet: "cleaned dataset",
      workbook_sha256:
        "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
      title_cell: "F36",
      description_cell: "G36",
      photo_cell: "H36",
      trim_cell: "E36",
      trim_raw: "s",
    },
    heading: "mini cooper",
  },
  {
    detail: {
      state: "current",
      listing: {
        ref: {
          namespace: "provided-cars-cleaned",
          snapshot_id:
            "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217",
          source_id: "12",
        },
        title:
          "Mazda 3 2019 Model GCC Spec Excellent Condition Single Hand Used Car For Sale",
        make: {
          status: "known",
          qualifier: "exact",
          value: "mazda",
          evidence: [
            {
              category: "structured_source",
              cell: "C13",
              evidence_id: "dd12e32a-79e4-ac32-be99-6a807d16e097",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "mazda",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 5,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        model: {
          status: "known",
          qualifier: "exact",
          value: "3",
          evidence: [
            {
              category: "structured_source",
              cell: "D13",
              evidence_id: "e82166d1-e332-5efe-1c53-0fef278df5ac",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "3",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 1,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        trim: {
          status: "known",
          qualifier: "exact",
          value: "s grade",
          evidence: [
            {
              category: "structured_source",
              cell: "E13",
              evidence_id: "bd0b2cd1-50ed-44eb-3bd5-d039ee0a07f9",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "s grade",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 7,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        year: {
          status: "known",
          qualifier: "exact",
          value: 2019,
          evidence: [
            {
              category: "structured_source",
              cell: "B13",
              evidence_id: "30baa353-8b19-aee1-46ab-08ab8258a2f4",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "2019",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 4,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        cash_price: {
          status: "known",
          qualifier: "exact",
          value: {
            minor_units: 3500000,
            currency: "AED",
            basis: "cash",
          },
          evidence: [
            {
              category: "seller_description",
              cell: "G13",
              evidence_id: "b1394309-d13c-653b-a421-83718ae5f9ac",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "PRICE REDUCED 35000 AED",
              review_status: "reviewed_extraction",
              semantic_role: "cash_price",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 23,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        mileage_km: {
          status: "unknown",
          reason: "unsupported",
        },
        evidence_warnings: [],
        photo: {
          source: "supplied_listing",
          state: "source_present",
          url: "https://dbz-images.dubizzle.com/images/2024/03/13/b16a4b5d793f4090b168dc85e51c943a-.jpeg?impolicy=dpv",
          alt: "Source photograph for listing 12: mazda 3",
        },
      },
      description:
        "PRICE REDUCED 35000 AED Mazda 3 2019 Model Scratch less exterior Model, 1.6 ltr engine less fuel Consumption car is for sale 100% Accident Free In Perfect Condition (Electrical and Mechanical) Only Single hand driven GCC Specification Cruise Control Bluetooth Systems ABS Brake Systems Parking Sensors Keyless Entry USB Pot Audio Aux In Fully Automatic Power Mirror Power Windows Power Steering Central Lock Systems Extra Clean Interior Call to view 052 7993306 Bank Auto finance can be arrange at 0% down payment and below fees also can be cover in auto finance. (Bank Processing fee, Evaluation Fee RTA Test/Registration fees, Comprehensive Insurance) Salary Required:- AED 3000/-(WPS) Saving and current both account are acceptable for Auto Loan Cheque Book not required No Salary Transfer Required Auto loan offer for Non-listed Companies also Monthly Installment is less than Monthly Car Rental Required Document:- Passport Copy and Visa Page copy Emirates ID Copy Driving License Salary Certificate (AED 3000 and More) Contact for more details Call 052 7993306",
      eligibility: "simulated_eligible",
      eligibility_reason:
        "FE-03 synthetic eligibility only. No real stock or booking availability established.",
      body_type: {
        status: "unknown",
        reason: "unsupported",
      },
      fuel_type: {
        status: "unknown",
        reason: "unsupported",
      },
      location: {
        status: "unknown",
        reason: "unsupported",
      },
      service_history: {
        status: "unknown",
        reason: "unsupported",
      },
      transmission: {
        status: "unknown",
        reason: "unsupported",
      },
      warranty: {
        status: "unknown",
        reason: "unsupported",
      },
    },
    conflicts: [],
    source: {
      sheet: "cleaned dataset",
      workbook_sha256:
        "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
      title_cell: "F13",
      description_cell: "G13",
      photo_cell: "H13",
      trim_cell: "E13",
      trim_raw: "s grade",
    },
    heading: "mazda 3",
  },
  {
    detail: {
      state: "current",
      listing: {
        ref: {
          namespace: "provided-cars-cleaned",
          snapshot_id:
            "9303532e7ac736643877459dc6cf0cdb53d6a2b38f7783601ec58575a85c9217",
          source_id: "22",
        },
        title: "TIMELESS CERTIFIED / 2 Year Warranty / 2 Year Service Contract",
        make: {
          status: "known",
          qualifier: "exact",
          value: "aston martin",
          evidence: [
            {
              category: "structured_source",
              cell: "C23",
              evidence_id: "d5b6446b-816e-1a60-e8a6-2643cb56eb4e",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "aston martin",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 12,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        model: {
          status: "known",
          qualifier: "exact",
          value: "dbx",
          evidence: [
            {
              category: "structured_source",
              cell: "D23",
              evidence_id: "be036a54-fc54-df7b-755c-d97962701744",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "dbx",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 3,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        trim: {
          status: "known",
          qualifier: "exact",
          value: "707",
          evidence: [
            {
              category: "structured_source",
              cell: "E23",
              evidence_id: "ee70c3d8-e23b-be0c-53cb-0349ed5546e0",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "707",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 3,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        year: {
          status: "known",
          qualifier: "exact",
          value: 2024,
          evidence: [
            {
              category: "structured_source",
              cell: "B23",
              evidence_id: "482bd7f1-60ae-8680-6241-4f042bc63ff8",
              extraction_version: "fe03-manual-excerpts-v1",
              raw_text: "2024",
              review_status: "reviewed_extraction",
              semantic_role: "other",
              sheet: "cleaned dataset",
              span_start: 0,
              span_end: 4,
              verification: "source_claim",
              workbook_sha256:
                "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
            },
          ],
        },
        cash_price: {
          status: "unknown",
          reason: "not_stated",
        },
        mileage_km: {
          status: "unknown",
          reason: "unsupported",
        },
        evidence_warnings: [],
        photo: {
          source: "supplied_listing",
          state: "source_present",
          url: "https://dbz-images.dubizzle.com/images/2024/06/10/43c8a73813a9474a8a12f74365db73e8-.jpeg?impolicy=dpv",
          alt: "Source photograph for listing 22: aston martin dbx",
        },
      },
      description:
        "**TIMELESS CERTIFIED PRE-OWNED PACKAGE** * 2 YEAR WARRANTY UNLIMITED KM * 2 YEAR SERVICE CONTRACT (16000 Km or 1 year, whichever comes first) * CERTIFIED HISTORY AND MILEAGE * QUALITY ASSURED ASTON MARTIN GENUINE PARTS * MULTI-POINT PRE-DELIVERY HARDWARE & SOFTWARE CHECK * SERVICING COMPLETED * 12 MONTHS OF ROADSIDE ASSISTANCE * COMPLEMENTARY REGISTRATION * Bank Finance option availalble",
      eligibility: "simulated_eligible",
      eligibility_reason:
        "FE-03 synthetic eligibility only. No real stock or booking availability established.",
      body_type: {
        status: "unknown",
        reason: "unsupported",
      },
      fuel_type: {
        status: "unknown",
        reason: "unsupported",
      },
      location: {
        status: "unknown",
        reason: "unsupported",
      },
      service_history: {
        status: "unknown",
        reason: "unsupported",
      },
      transmission: {
        status: "unknown",
        reason: "unsupported",
      },
      warranty: {
        status: "unknown",
        reason: "unsupported",
      },
    },
    conflicts: [],
    source: {
      sheet: "cleaned dataset",
      workbook_sha256:
        "94a97f84aa742ec8ed526bb14d41ca4134ab8a2e1db1ab7f3d2f03af5c38bbb9",
      title_cell: "F23",
      description_cell: "G23",
      photo_cell: "H23",
      trim_cell: "E23",
      trim_raw: "707",
    },
    heading: "aston martin dbx",
  },
] satisfies ProofListing[];
