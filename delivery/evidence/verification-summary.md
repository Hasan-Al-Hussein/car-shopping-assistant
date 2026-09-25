# Verification summary

Recorded 25 September 2026. This document summarizes executed checks on identified development snapshots. It is not a claim that every feature, deployment or possible conversation has passed. These separate runs should not be added together as one test suite or one end-to-end result.

## Functional evidence

The included [inventory conversation](multi-turn-conversation.md) contains actual live model responses across an inventory search, a first-car mileage question and a warranty follow-up. The [new-session recall](new-session-recall.md) demonstrates explicitly saved preferences recalled in a distinct session without repeating their values. These transcripts preserve their original wording; later readability changes do not rewrite historical output.

An actual [qualified-lead CSV](qualified-lead.csv) and [its explanation](qualified-enquiry.md) demonstrate a saved cash budget and buyer needs. A later, separately reviewed browser run completed enquiry correction, simulated viewing confirmation and physical CSV export: 64 validated requests, 13 writes and one booking-linked, 24-column CSV. That run used synthetic data and no live model. It is separate from the conversational lead-save evaluation below.

The [clean-setup record](clean-setup.md) and [required-delivery review](release-review.md) describe the earlier extracted-package execution, setup corrections and limits. They refer to their recorded package snapshots, not to a subsequently deployed environment.

## Automated and visual checks

| Check and snapshot date | Observed result | What it establishes—and its limit |
|---|---|---|
| Full frontend suite, 25 Sep, completed 11:40 UTC | **346 passed**, 0 failed, 0 skipped; 27 test files | Unit/component/service coverage including recovery when chat reopens after cached unavailable health. It does not itself establish live model behavior or hosted deployment correctness. |
| Frontend validation, 25 Sep, completed 11:43 UTC | Application and test TypeScript checks, lint and production build passed | Lint retained **8 warnings**. Vite retained a large-chunk warning: **824.84 kB minified, 137.75 kB gzip**. No bundle-performance improvement is claimed. |
| Backend answer-readability regression, 25 Sep, 10:23 UTC | **183 passed**, 0 failed/error/skipped | Grounded answer formatting, ordered results, qualifiers, conflicting/unknown facts, reference and evidence handling. This was a focused backend selection, not the complete backend suite or a new provider run. |
| Earlier responsive review, 25 Sep, 03:29 UTC | **215/215 controlled checks** across three frames | Reviewed layouts at 1440, 1024 and 320 px for viewing review and failed CSV status. The final screenshots did **not** show the source-reference disclosure expanded; its expanded layout remains outside this visual proof. |
| Chat-readability review, 25 Sep, completed 10:55 UTC | **49/49** layout checks, then **7/7** enlarged-text car checks, then **7/7** corrected scroll-owner checks | Separate captures support desktop/mobile readability, a single appropriate scroll owner and reachable composer. Synthetic session/response fixtures were used; these are not new AI or persistence demonstrations. The last jump-to-latest check invoked the DOM handler, not native physical input. |

The frontend run includes the later public-health refresh correction. The chat render captures precede that small recovery change; they prove their recorded layout snapshot. The backend formatting run checked renderer hashes beginning `08a8b4a1357a` and `4daf3fb6af5e`; the scroll-controller proof checked its final fourth revision. Evidence applies to these versions rather than automatically to future edits.

## Live AI evaluation

The 25 September 05:27–05:32 UTC evaluation selected **38 cases: 34 passed and 4 failed**. The four failures recorded provider timeouts affecting a make search, a search/reset sequence, an enquiry save and a saved-preference recall. Twelve other cases in the 50-case report were not selected. The original run remains **FAIL**; the timeout records do not establish a bad API key, account quota exhaustion or an exact remote cause.

The repaired mixed-request and competitor examples passed in that run. Responses retained the supported car details where appropriate and declined the unrelated or competing-platform part without performing it. This is finite-case evidence, not proof of exhaustive guardrail recognition.

A separate 25 September run, settled at 07:08 UTC, selected the four previously timed-out cases plus one control: **5 cases, 11 steps and 116 assertions passed**. It demonstrated successful search/reset, explicit qualified-enquiry save with idempotent replay, and new-session preference recall. The conversational save queued the CSV export; that evaluation did not observe physical CSV publication. Its overall report remains **INCOMPLETE** because the other 45 cases were unselected. This later successful sample does not erase the original failures or establish global provider reliability.

## Performance: target not met

The local API pilot completed on 25 September at 06:19 UTC with the provider disabled. It measured **200 requests**: 80 inventory searches, 60 listing-detail reads and 60 preference reads, with up to three overlapping requests.

| Measurement | Result |
|---|---:|
| Valid responses | 200 / 200 |
| Failed requests / timeouts | 0 / 0 |
| Median latency | 641.260 ms |
| p95 latency | **1,025.755 ms** |
| p99 latency | 1,260.971 ms |
| Maximum latency | 1,476.006 ms |
| Adopted project p95 target | 500 ms |

Percentiles use the nearest-rank estimator. The result is **PILOT_TARGET_FAILED; performance acceptance not established**. The 500 ms target is a project goal, not an assessment-PDF requirement. These are local API measurements, not AI-response latency, browser rendering speed, internet latency or a hosted-service benchmark.

Two later 30-request diagnostic runs examined where time was spent. They were too small to replace the 200-request acceptance run and did not establish an optimization or passing performance result.

## Remaining limits

- A single live-model-initiated journey from conversational viewing preparation through explicit confirmation and physical CSV publication has not been demonstrated in the reviewed evidence. The component and separate successful transaction results remain useful but are not that joined proof.
- A separate ordinary, unmapped Windows clean installation was not executed; the included setup record explains the tested host and its corrections.
- Full accessibility, native mobile keyboard/screen-reader behavior, production security and hosted persistence/reliability are not established by these checks.
- Publishing this source or producing an archive does not imply a working public deployment or full release acceptance. Any deployed URL needs its own actual functional checks.

The public summary omits credentials, machine-specific paths, private conversations and operational database contents. No new tests or provider calls were performed to write it.
