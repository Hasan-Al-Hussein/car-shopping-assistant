# Actual qualified-enquiry CSV

The accompanying `qualified-lead.csv` is a byte-for-byte copy of a real application export, containing synthetic demonstration data only. Its SHA-256 is `c45346619ed420d8ad89eb87f2f192eb94b01b1a1f2a0e31b7c87b215d2c6d33` (1013 bytes, one data row, 24 columns).

An actual browser submitted AED 10,000–20,000 as a cash budget and `Synthetic original requirement` as a need. The backend returned HTTP 201 and saved lead `1100ade1-7233-4fb7-b713-76897575159d`, revision 1. Exact response/readback checks, independent canonical-row reconstruction and the observed CSV publication agree. Email and phone were explicitly declined. The exported budget uses minor units: 1,000,000–2,000,000. This was a local enquiry, with no dealer delivery and no booking in this attempt.

Capture: `q2s-t-d172af2cdf3b-r2`, 24 September 2026, 22:44:55–22:46:06 UTC. The row's 04:00 UTC business timestamps come from the configured synthetic clock. Original result SHA-256: `ba42fbff57cce487ac6f40c17c8749460c711b71f2c3b3f8704d5d0d4c883350`. Canonical lead-row digest: `5f5e821799b8d5a63429cc368538e399cd8d2eea830c0a656686c928b7e32a74`.

Independent review supports the PDF requirement to capture a price range and needs in an actual local CSV. The full browser case still failed at a later edit-and-reload field lookup. Its unchanged full-case validator remains failed; later correction, Unicode/formula cases and combined booking checks were not reached. This successful first-save evidence does not claim those broader checks passed, or that the whole project is release-ready. Simulated booking is demonstrated separately.

The original detailed review, raw result, publication manifest, capture receipt and closure evidence are retained in the development workspace under `Records/build/quality-review/affected-three-case-followup/browser-refresh/`. No credential, real contact detail or raw seller description is included in this export.
