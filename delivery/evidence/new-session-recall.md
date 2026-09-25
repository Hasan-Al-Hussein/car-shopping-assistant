# Actual saved-preference recall in a new session

These excerpts come from the five live turns recorded on 24 September 2026 at 21:27:56–21:28:14 UTC through the real FastAPI application and Gemini Developer API. The complete 19-request capture ran from 21:27:55.405925 to 21:28:15.047421 UTC. These are exact user/assistant text fields extracted from the already sanitized, independently reviewed HTTP journal; they are not a rewritten conversation or a new execution.

The first turn explicitly saves two synthetic requirements in session A. The second turn occurs after creating distinct session B under the same local access. The question does not repeat either saved value. The original action and subsequent persisted/new-session records all retain preference revision 1; recall creates no additional save.

## Recorded turn — request 12

Session: 134e842b-74a9-49d4-ab3f-bd7cc08f15cc. HTTP 200; provider available; response retained at 09/24/2026 21:28:11.

**User**

Please explicitly remember these two soft requirements for future conversations: "quiet cabin" and "space for a folding bicycle". Save these preferences now.

**Assistant**

Your preference update is recorded.

## Recorded turn — request 16

Session: cf3f7d22-c09d-477a-9948-10efb9920bcc. HTTP 200; provider available; response retained at 09/24/2026 21:28:14.

**User**

What requirements did I ask you to remember in my earlier conversation? Tell me the saved values.

**Assistant**

You saved requirements in another session (soft preference): "quiet cabin", "space for a folding bicycle".
These saved values have not changed your current search or saved new preferences.

## Provenance and scope

Capture run: 98302ac2-2afb-48bf-999b-afa75a18f8e2. Model: gemini-3.5-flash-lite. The complete run contains 19 HTTP requests and five actual provider turns, each with one adapter attempt. Independent review compared both full transcripts, the supplied listing evidence, original selection, persisted preferences and their provenance. No API key, access cookie or personal buyer details are included here.

Original sanitized journal SHA-256: c91bc550bd4ebe28e8148594ed66d97b291fee316ad9d82db89fd3b79d70171f.
Independent actual-output review SHA-256: 34a93bc226653d3369256fbb043849ec84604a34cd4db705610a38cd4eac9429.
This demonstrates the recorded flow on its reviewed source snapshot. It does not by itself prove a fresh installation, reliability across arbitrary prompts, or whole-project release acceptance.

