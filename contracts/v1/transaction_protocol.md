# Transaction and CSV participant contract — v1 candidate

Reconciles Transactions T0 against the selected local simulated workflow. This is not runtime/fault acceptance. Platform owns schemas and persistence; Transactions owns domain logic/projector/operations. Saved source, plans and evidence remain in the canonical Desktop project. No database or CSV is created here.

## Exact reviewed action

The immutable action payload binds authenticated owner (internal), draft/review IDs, original exact ref/resource, action type, UTC interval, Dubai-local presentation, rule/eligibility version, draft revision, store generation and **reviewed lead participant**. Payload hashing excludes mutable review lifecycle state and transport request IDs, but includes all material effects. UI and chat confirmation carry identical `ConfirmRequest` fields; chat adds only its exact draft ID. A caller cannot replace car/time/contact values at confirmation.

`ReviewedLeadCreation` snapshots typed buyer `LeadValues` and source-session revision when no lead exists. It uses only explicitly supplied/confirmed data; missing/declined remains typed. At commit, verify the logical owner/Journey lead still does not exist; otherwise reject stale review rather than overwrite the newly created lead.

`ReviewedExistingLead` binds lead ID and expected revision. It preserves existing buyer values while applying the disclosed viewing-confirmed stage/link effect. Any intervening lead revision change requires fresh review. Do not reread current mutable session fields and silently save them as if the buyer reviewed them. Lead creation/update, booking, terminal outcome and projection intent commit atomically after capacity checks. A failure rolls the whole accepted action back; no network/CSV/provider work occurs under this transaction.

`POST /leads` is create-only. First deduplicate exact client-action identity; then a fresh command for an existing logical owner/Journey lead returns `LEAD_EXISTS`. It never upserts or overwrites. `GET /leads/current` retrieves only the authenticated owner's current Journey lead, or typed not-created. Corrections use PATCH with expected lead revision. Caller-provided session must belong to that same owner/Journey.

## Receipt and alternatives

`BookingCoreReceipt` preserves the immutable appointment with a consumed review. `GET /bookings/{booking_id}` returns `BookingReceipt`, adding the **immutable accepted LeadSaved ID/revision** and the **current observed CSV projection status**. `OperationSucceeded` exposes those same facts. The selected action always commits the disclosed local lead and projection intent atomically; success cannot contain lead not-saved/not-requested or CSV not-requested. For preserve-existing, accepted lead ID equals the reviewed ID and its accepted revision is exactly the expected revision plus one. Later enquiry edits never alter a booking/outcome's accepted lead ID/revision; current enquiry values/revision come separately from GET /leads/current. Lead revision is per-lead; CSV versions have global-projection scope and an observation timestamp/generation. Replay returns original booking and accepted lead facts, then composes a separately labelled current CSV observation. Persist immutable transaction facts; do not rewrite terminal authority when repairing/reobserving CSV. A repaired CSV cannot change the terminal booking or accepted lead result.

`POST /viewing-options` is a bounded **read-only** calculation. Request includes exact ref, date and 1–7 day window. Response contains at most 24 complete UTC intervals, Dubai zone, rule/eligibility versions, calculation timestamp and `no_hold=true`. It returns no private booking/owner details. Available means a current simulated observation, not a reservation. A rejected operation remains its original durable rejection; refreshed alternatives are obtained separately, never written over the stored rejection.

## Restore and credential authority

Restore quiesces writers/private routes/projector first. Verify the backup on an isolated allowed path, retain the known-good prior store, establish a **new store generation**, and record recovery point. A backup may predate credential revocation. Reconcile restored credentials with reliable current revocation evidence; when that evidence is insufficient, invalidate restored credential contexts before private routes reopen. An old signed-out cookie must not become valid after restoration. No display-name recovery or implicit record migration to a fresh owner is allowed.

Preserve review/key and unresolved intent independently of transcript/draft cleanup. If a terminal result is retained, return that owned original result. If absent after generation change, remain unresolved; prohibit automatic old replay and replacement review/draft action until reconciliation. Unknown absence is never noncommit. The default synchronous design has no durable ACCEPTED queue or in-memory finalizer.

At restore, fence projection by `(store_generation, global_projection_version)`, quiesce old publishers, mark surviving old-generation CSV stale, rebuild from restored canonical data and publish only under the new generation. Numeric projection versions alone cannot compare different generations. Do not label a newer surviving CSV current against an older restored database.

## CSV schema `leads-csv-1`

One row per canonical lead. UTF-8 with BOM for the selected Excel-oriented local export, comma delimiter, CRLF record terminator, standard CSV quoting (quote every field), explicit schema/generation/version columns. Preserve canonical Unicode in SQLite. No bulk buyer download route. Text formula neutralization occurs only on CSV export: prefix a single quote for formula-leading text, including after leading whitespace/control characters, without changing canonical buyer input. JSON array columns use compact Unicode JSON. Blank numeric/contact values are interpreted only with their paired state column; empty is not zero.

Frozen column order:

```text
schema_version,store_generation,projection_version,lead_id,lead_revision,
owner_reference,journey_reference,source_session_reference,created_at_utc,updated_at_utc,
stage,delivery_mode,budget_state,budget_minimum_minor_units,budget_maximum_minor_units,
budget_currency,budget_basis,requirements_json,selected_inventory_refs_json,
email_state,email_value,phone_state,phone_value,booking_ids_json
```

`schema_version` is `leads-csv-1`; `delivery_mode` is `local_only`. `projection_version` is the global canonical export version, stamped across the complete file; `lead_revision` is that row's canonical lead revision. Owner/Journey/session references are internal IDs for authorized local traceability, never credentials. Lead persistence retains `source_session_reference`, `created_at`, `updated_at` as immutable/sanitized provenance even when the seven-day transcript is removed; no transcript retention is implied.

Budget state is provided/missing/declined. Min/max are inclusive integer minor units with currency and cash basis; absent bounds are blank, not zero. Contact state is provided/missing/declined; non-provided values are blank. `selected_inventory_refs_json` preserves namespace/snapshot/source ID for every item. `booking_ids_json` contains only actual owned committed IDs; viewing-confirmed stage requires a real simulated booking link.

Projector captures a coherent canonical snapshot and global version, writes a complete temporary file beside its configured final path, validates serialization, rechecks generation/publication fencing and safely replaces. A single writer prevents simultaneous publishers. A crash after file replace but before acknowledgement may regenerate the same projection. Failure retains the last valid file and records pending/failed independently of booking. Publication metadata includes generation, version, byte hash and row count. Neither file existence nor a higher number in a different generation proves currentness.

Brain explicitly adopted `C:\Users\example\AppData\Local\CarShoppingAssistant\runtime\exports` for mutable projection, adjacent temporary files and publication manifest. F-04/OP configuration must enforce the same resolved-path/reparse boundary and generation fences. Only closed/sanitized deliverable copies go into the Desktop handoff package. Required later proof includes Unicode/formula cases, file-open/permission failure, stale publisher, crash and restore generation tests; all NOT RUN at F-02.
