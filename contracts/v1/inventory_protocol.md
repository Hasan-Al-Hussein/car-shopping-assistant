# Inventory version, cursor and proof protocol — v1 candidate

This resolves I0's requested seam. The Inventory lane owns readers/normalization/search/domain services; Platform owns shared DTOs/models/migrations and signing/registration. No workbook is reread or changed by this document. Studio's supplied-photo manifest remains reference evidence, not another inventory authority.

## Exact source and snapshot identity

Namespace: `provided-cars-cleaned`. Selected worksheet: exact `cleaned dataset`. Source IDs are string representations of the validated original `Listing_ID` values, never row numbers. Map Studio evidence using original workbook SHA-256 + exact sheet + source ID; preserve row/cell provenance independently. Do not assume workbook hash equals snapshot ID.

Snapshot identity is SHA-256 of UTF-8 canonical JSON containing `namespace`, `workbook_sha256`, `sheet`, `normalization_version`, `extraction_version`, `evidence_review_version`, `photo_policy_version`, and `schema_version`. Canonical JSON uses sorted object keys, compact comma/colon separators, `ensure_ascii=False`, no NaN/Infinity. Versions are nonempty bounded ASCII labels. Source or derived-fact policy change requires a new immutable snapshot; never modify fact meaning under a previously issued ref.

Import is whole-candidate rejection on missing/duplicate source IDs, missing required headers, structural/schema errors or unexpected populated columns lacking reviewed mapping. Complete nonempty-row accounting and diagnostics are required. Incomplete/invalid/conflicting **facts** and photo failures remain field-level states on a retained listing. Stage all rows, evidence and matching search index version; validate counts/identity before atomic activation. Public reads select one coherent snapshot/index pair. Referenced older snapshots remain available as history, never silently retargeted.

## Search and page continuity

Canonical criteria use `SearchCriteria` with explicitly normalized allowlisted values; criteria SHA-256 uses the same JSON encoding. Unsupported negation/attributes require a named unsupported/clarification response. Never omit a hard condition and count the resulting cars as supported matches. Budget bounds are inclusive currency minor units; only supported cash evidence in that currency qualifies, with no FX or instalment conversion. Approximate/bounded evidence must follow the reviewed matching policy, never be treated as exact by default.

Cursor payload binds namespace, snapshot ID, criteria hash, index/ranking version, stable sort tuple and page position. Use an HMAC-protected opaque cursor with bounded encoding, not a raw SQL expression or unsigned offset pretending to be immutable. Tie-break is source ID with deterministic declared ordering, after primary score; page-size changes may not switch snapshot or criteria. Inventory returns typed ordering/cursor components to Platform's signer, or uses the agreed signing service without receiving its key. Tampered/mismatched cursors fail validation. After activation, continue the retained complete original snapshot or return SNAPSHOT_STALE; never silently switch within pagination.

Coverage records report `source_total` as the selected snapshot's validated listing denominator and per-constraint supported/unknown/conflicting/unsupported-qualifier counts. These four categories are disjoint and sum exactly to that denominator. Supported means usable evidence, not necessarily matching the requested value. `unsupported_constraints` names hard conditions only; any such condition requires `no_supported_matches`, no items, zero supported total and no cursor. That state is distinct from a store/read failure. A matches page has at least one item; its supported total cannot be smaller than the page. Applied normalized criteria are returned explicitly. Comparison service validates output count, input position and each exact ref against the request, with current/historical/missing/error status per candidate; the response DTO alone cannot prove this request/response relation. An entire store failure is an API error, not three invented missing cars.

## Ephemeral public proof and owned registration

Public search never persists a session or presentation. It returns a `PresentationProof` whose ordered refs equal the response item order. The HMAC-SHA256 signature covers every proof field except signature using canonical JSON; its 32-byte digest is unpadded base64url (43 characters). Proof issue/expiry uses the injectable server clock. Proposed engineering lifetime is 1,800 seconds, explicitly configurable and unrelated to review/booking authority. A per-process random signing secret is acceptable: restart invalidates unregistered public proofs, and a fresh read can obtain another without changing stored history. Never log or serialize the signing secret.

Explicit owned registration validates the signature, expiry, snapshot/criteria/order and expected session revision before storing immutable order. It binds the presentation to authenticated owner/session. Exact `client_action_id` replay is payload-bound. Previously stored presentation references remain authoritative after the original ephemeral proof expires or process restarts; later paging cannot change their ordinals. Public search metadata proves returned order, not actual screen rendering.

## Evidence and photos

Each internal evidence row binds a parent exact ref and source manifest to workbook hash/sheet/cell, exact original value, Unicode code-point span `[start,end)`, normalized value, unit/basis/semantic role, extraction version, review status and qualifier. The public `SourceLocator.raw_text` is only that exact supporting span. `known` means supported by the supplied source, not independently verified vehicle condition. Reviewed extraction is verification of parsing/provenance, not an inspection. Contacts irrelevant to the fact must not be duplicated into the model packet.

`source_present` photo state means an approved source URL exists; it does not mean browser decoding succeeded. Preserve exact supplied URL. Parsed authority is HTTPS `dbz-images.dubizzle.com`, `/images/` source path, only observed `impolicy=dpv`, `impolicy=dpc`, or `imwidth=800`; no userinfo, explicit/arbitrary port, fragment, control character or private query. Missing/blocked/unverified DTOs have no renderable URL. Do not reject HEIC suffix alone, invent transformed URLs, fetch through backend or derive vehicle facts from the photograph. UI uses no-referrer and separate load/error state.

## Core handoff

`handoff(selected_ref, expressed_criteria) -> HandoffSummary` is a read-only Inventory service. It returns the selected ListingResult, same explicit criteria, evidence-referenced fit reasons and typed unresolved questions. Assistant may embed it in MessageResult when requested. No new endpoint, download, contact collection, inferred need, appointment promise or OPT-04 artifact is added.
