# Supplied listing photos

Studio S0, 23 September 2026. Use the workbook's per-car photo URL as the primary image. No external replacement photos or generated cars were sourced.

- [Listing-photo manifest](listing_photo_manifest.json): all 100 cleaned mappings, with the 100 raw rows isolated as audit evidence. Exact source hash, sheet, ID, row/cells, unchanged URL, syntax check, limited network observations and provenance limits are recorded separately.
- [Frontend integration guidance](frontend_integration.md): safe mapping, rendering/fallback states and concrete source fixtures.
- [Audit and completion evidence](../../Records/build/studio/S0_report.md): checks performed, source/artifact identity and outstanding proof.
- [Independent review](../../Records/build/studio/independent_photo_review.md).

The current Brain decision DEMO-POLICY-1 selects the cleaned sheet; raw remains audit-only. This source-evidence manifest is not a shared API schema, live inventory activation or card acceptance. Platform/Inventory own the backend InventoryRef mapping; Frontend owns components.

All 200 source rows have a photo URL. Each sheet has 100 unique URLs; one URL is shared across sheets, leaving 199 distinct URL strings. Every URL uses HTTPS and the exact host `dbz-images.dubizzle.com`. No username/password, explicit port, fragment, whitespace or control character was found. Source query strings are retained exactly: `impolicy=dpv`, `impolicy=dpc`, or `imwidth=800`.

Eight distinct URLs were checked sequentially at **2026-09-23 18:27 UTC**: eight HEAD responses were HTTP 200 with `image/webp`; two bounded GETs were HTTP 206 with WebP prefixes. The 191 other distinct URLs remain **NOT_CHECKED**. Only five cleaned URLs were sampled; the other 95 cleaned URLs were not fetched. No image files were saved and no browser rendering was tested.

The source includes two cleaned `.heic` paths, IDs 4 and 72. Both sampled HEAD responses described WebP, so the filename extension is not a reliable display-format verdict. Preserve the supplied URL, including its query. Actual browser loading/decode/fallback must be tested by Frontend.

The manifest establishes which URL the workbook associates with which record. It does not establish the photographer, rights holder, permission, image content, actual-vehicle identity, condition or live availability. Use source attribution without an invented copyright/license statement. A neutral **Photo unavailable** state is the fallback.
