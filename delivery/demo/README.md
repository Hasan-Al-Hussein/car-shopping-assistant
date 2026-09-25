# Actual conversation demonstrations

The assessment requests evidence of an inventory conversation and recall in a completely new session. Both are captured in the reviewed five-turn live run from 24 September 2026:

- [Inventory conversation](../evidence/multi-turn-conversation.md): search the supplied workbook, ask for the first car's mileage, then ask about its warranty without restating the vehicle.
- [New-session memory](../evidence/new-session-recall.md): explicitly save “quiet cabin” and “space for a folding bicycle”, create a distinct session under the same local access, and recall both values without repeating them in the question.

These files contain exact text from actual HTTP responses. The complete run made 19 HTTP requests and five `gemini-3.5-flash-lite` turns, each using one adapter attempt. Independent review checked the original listing identity and unknown facts, both complete transcripts, persisted preference values, revision and saving-action provenance. It was not a fixture conversation. The demonstrated car's mileage and warranty are not stated in the supplied source.

This is evidence for that recorded application snapshot, not reliability on arbitrary prompts or whole-project acceptance. The [actual qualified-enquiry CSV](../evidence/qualified-lead.csv) has its own [scoped review](../evidence/qualified-enquiry.md). A later execution of this packaged client also completed all five turns from a fresh extracted installation, including distinct-session recall. That setup needed documented mapped-host preparation, and the separate connected browser run ended before booking confirmation with a late-release timeout. These later results preserve the earlier artifacts and failures. The [clean-setup record](../evidence/clean-setup.md) and [independent required-delivery review](../evidence/release-review.md) describe their scope; broader planned acceptance is not asserted.

## Reproduce the HTTP demonstration

First complete the [main setup and run guide](../../README.md). Keep the configured backend running. This client does not start another server, install dependencies, access SQLite directly or call Gemini directly. The backend alone holds the key. Use synthetic preferences and a project whose free-tier access has been confirmed.

In another PowerShell terminal at the extracted project root, obtain the inventory snapshot from the successful bootstrap `receipt.json` and the `source_manifest_sha256` from the repository's `source-manifest.json`. Replace the two placeholders below with their actual 64-character lowercase digests. The build digest is an operator declaration about the extracted source, not remote attestation of a running binary.

```powershell
& '.\backend\.venv\Scripts\python.exe' `
  -B '.\delivery\demo\run_pdf_demo.py' `
  --execute --acknowledge-local-notice `
  --base-url 'http://127.0.0.1:8000' `
  --origin 'http://127.0.0.1:5173' `
  --build-sha256 '<actual-source-manifest-sha256>' `
  --snapshot-id '<actual-bootstrap-inventory-snapshot-sha256>' `
  --provider-mode 'live-free-gemini'
```

The client creates its own new local access context and session A, performs inventory/mileage/warranty turns, explicitly saves the two preferences, creates session B and checks recall. It then reads both server transcripts. The two sessions must differ while retaining the same owner, and the complete preference record must survive unchanged. Recall must include the actual saved values and must not create another preference save. The only assistant business action is the explicit preference save; this demonstration does not book a viewing or create a lead.

The finite run has at most 24 HTTP requests, a 240-second work budget, 35 seconds per request and no automatic HTTP retries. Five turns can use up to ten provider attempts under the backend's two-attempt limit. Exhausted quota or unavailable access remains a failure/unavailable result; there is no paid fallback. Internal development usage limits are tracked separately and do not create a fresh allowance for another run.

## Retained evidence

The runner resolves paths relative to its own project and writes to `Records/build/platform/post-guidance-full-pdf/demo-runs/<run UUID>/` beneath that project:

- `evidence.jsonl`: chronological request and sanitized response records, plus original session/message/action identities and checks.
- `result.json`: observed outcome and any incomplete step.
- `../incomplete.json`: an exclusive marker retained if a run does not complete safely.

Logs omit keys, cookies, CSRF values, access credentials, raw seller descriptions and photo URLs. Synthetic preference prose is retained; numeric-looking prose may be redacted. Original response and transcript comparison happens before sanitization. Review actual text, source facts, stored values and provenance rather than treating a status label as sufficient proof.

Exit 0 means the capture completed and needs independent review. Exit 2 means a precondition or execution was incomplete. If an incomplete marker exists, preserve it and reconcile the original request: do not delete it to hide a failure or submit the same mutation under a new identity. Successful execution leaves its synthetic preferences in the selected runtime; it does not delete buyer state afterward.

The supplied readable evidence was extracted from run `98302ac2-2afb-48bf-999b-afa75a18f8e2`, original journal SHA-256 `c91bc550bd4ebe28e8148594ed66d97b291fee316ad9d82db89fd3b79d70171f`. The independent review digest is recorded in each transcript. Earlier failed development attempts remain in the development workspace and were not relabelled as successful by this capture.

