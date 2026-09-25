# Car Shopping Assistant

A local prototype that searches the supplied car inventory, answers contextual questions, remembers explicitly saved preferences and arranges simulated viewings. The React interface includes browsing, comparison, chat and enquiry review. Product photographs come from the supplied workbook; missing or conflicting facts stay visible.

The README follows the assessment requirements first: setup and execution, technical rationale, implementation decisions and future work, then actual conversation evidence. Extra features and measured results follow afterward.

## 1. Setup and execution

Use Windows PowerShell with **Python 3.13.3**, **uv**, **Node 24.13+ within 24.x** and **npm 11.6.2+ within 11.x**. Python must already be installed; automatic Python downloads are disabled. A Google AI Studio project with confirmed free-tier access is needed for live chat. No paid fallback is configured.

This version runs locally on **Windows**. Native file locking and local SQLite persistence mean it is not a Linux-compatible or Vercel-hosted service.

Clone the repository, then open PowerShell in its root:

```powershell
git clone https://github.com/Hasan-Al-Hussein/car-shopping-assistant.git
Set-Location car-shopping-assistant
```

Alternatively, download the repository as a ZIP and extract it. Preserve the included workbook, bootstrap records and relative folders.

```powershell
Set-Location backend
uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Set-Location ../frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
Set-Location ..
```

Create one isolated local runtime for the database and CSV exports. Start from an ordinary PowerShell terminal without inherited `CSA_*`, provider-key, virtual-environment or custom `PYTHONPATH` overrides. Keep this terminal open for the backend.

```powershell
$csaProject = (Get-Location).Path
$csaCase = [guid]::NewGuid().ToString('N')
$env:CSA_RUNTIME_ROOT = Join-Path $env:LOCALAPPDATA ('CarShoppingAssistant/runtime/q11/' + $csaCase)
$env:CSA_RUNTIME_PHYSICAL_ROOT = $env:CSA_RUNTIME_ROOT
$env:CSA_STORE_PATH = Join-Path $env:CSA_RUNTIME_PHYSICAL_ROOT 'stores/demo.sqlite3'
$env:PYTHONPATH = (Join-Path $csaProject 'backend') + ';' + $csaProject
$csaEvidence = Join-Path $csaProject ('Records/build/BE-05/I7/runs/' + $csaCase)
uv run --project backend --frozen python scripts/bootstrap_inventory.py `
    --initialize-runtime-root --destination $env:CSA_STORE_PATH --evidence-directory $csaEvidence
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap failed; preserve this runtime and inspect its evidence.' }
```

Next, complete the **first activation block** in [operator setup](delivery/operator-setup.md), in this same terminal. Bootstrap alone does not activate viewing slots. If a step fails, preserve the original instance and operation for reconciliation; do not delete exports or retry with a different identity. A fresh database inside an already used runtime is insufficient: CSV exports also belong to that runtime.

The commands above are the ordinary Windows setup. A packaged execution host with redirected application data needs its own verified logical/physical mapping; internal host launchers are not a prerequisite for assessors. The recorded clean installation used that mapped host and required its physical runtime directory to be provisioned before bootstrap. Ordinary same-root initialization is supported by the source; a separate unmapped-host installation was not executed.

### Run the backend and client

From the project root in the backend terminal, enter the key through a masked prompt. The backend reads its environment directly; it does not load a `.env` file.

```powershell
$csaKey = Read-Host 'Google AI Studio key (confirmed free access)' -AsSecureString
try {
    $env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', $csaKey).Password
    uv run --project backend --frozen python main.py
} finally {
    Remove-Item Env:\GEMINI_API_KEY -ErrorAction SilentlyContinue
    $csaKey.Dispose()
}
```

In a **separate terminal** at the repository root:

```powershell
Set-Location frontend
npm run dev
```

Open **http://127.0.0.1:5173/__app** for the connected application when using `npm run dev`. Vite proxies `/api` to the FastAPI backend at `http://127.0.0.1:8000`; both ports must be free. Use these exact loopback addresses. Root `main.py` launches the complete application; `app.main:app` alone is only the foundation app. Interactive API docs are disabled; `/api/v1/health` reports capabilities. Keep credentials out of source, screenshots and frontend variables. Stop both processes with Ctrl+C when finished.

## 2. Technical choices and rationale

| Part | Choice | Reason |
| --- | --- | --- |
| Client | React, TypeScript, Vite | Responsive browsing, comparison and conversation in one interface. |
| API | Python, FastAPI, Pydantic | Typed requests and clear service boundaries. |
| Retrieval | Deterministic SQL/lexical search over the supplied workbook | Fits approximately 100 listings and preserves exact source facts. |
| Orchestration | Explicit intent routing and validated service calls | Keeps action rules and recovery inspectable without an additional agent framework. |
| State | SQLite and SQLAlchemy | Stores sessions, explicitly saved preferences and simulated transactions locally. |
| Language | Free Gemini Developer API, `gemini-3.5-flash-lite` | Interprets requests; strict backend validation and services control facts and writes. |

**Frontend decision:** The assessor approved the preferred client approach provided the setup and decision are documented. React replaces the original Notebook/Streamlit options for a richer interface; it adds a Node build step. See the [decision note](delivery/decision-note.md). SQLite is explicitly permitted. An agent framework or vector database is optional and is not required for this dataset. Dependencies are locked in `backend/uv.lock` and `frontend/package-lock.json`.

## 3. Implementation decisions and future work

The implementation separates retrieval, conversation, persistence and transaction rules. Gemini returns structured intent; the backend validates it and builds grounded replies from listing evidence. Explicit saves distinguish discussion from durable preferences or enquiries. Booking review and original-operation recovery prevent an uncertain response from becoming a duplicate appointment.

Future work could improve verified price and availability coverage, multilingual understanding and evaluation across varied buyer language. Smaller frontend bundles, lower API latency and broader accessibility checks remain useful improvements. A shared deployment would require portable storage and locking, authentication and operational changes. These are future directions, not enabled integrations or delivered features.

## 4. Required conversation demonstrations

The assessment permits screenshots **or terminal logs**. The linked transcripts contain actual live HTTP responses rather than illustrative conversations.

1. Browse the workbook cars. Ask for cars, then ask for the mileage of the first result and whether it has a warranty. The selected car stays the same; an unknown fact remains unknown.
2. Explicitly ask to remember a preference. Choose **Start a new conversation**, retaining the same browser access, and ask what was remembered without repeating its value. A new browser profile or cleared access cookie represents a different local user.
3. Select a car enabled for the demo. Gather a cash price range and needs, choose **Save enquiry details**, review the car and slot, then confirm the simulated viewing. Slots are Monday–Saturday, 08:00–20:00 Dubai time, in 30-minute intervals.
4. Inspect the saved enquiry and its separate CSV export status. Real CSV exports are stored under the selected runtime's `exports` folder. A failed export does not undo a saved enquiry or booking. Preserve an uncertain confirmation and check its original status rather than submitting again.

The [actual inventory transcript](delivery/evidence/multi-turn-conversation.md) and [new-session recall transcript](delivery/evidence/new-session-recall.md) contain the recorded live responses. The [HTTP demo guide](delivery/demo/README.md) explains the reproducible client and evidence limits. The [actual qualified CSV](delivery/evidence/qualified-lead.csv) and [its reviewed scope and limits](delivery/evidence/qualified-enquiry.md) are included. The [clean-setup record](delivery/evidence/clean-setup.md) and [independent required-delivery review](delivery/evidence/release-review.md) describe the fresh-install and connected enquiry/export evidence, setup corrections, source identities and browser timeout limits. Viewing eligibility is explicit simulation policy, not proof of real dealer management or availability. No dealer is contacted or real reservation created.

Historical transcript wording is preserved even where later answer formatting improved. The separate conversation, enquiry/export and booking demonstrations do **not** establish one uninterrupted live-model journey through booking confirmation and physical CSV publication.

## 5. Extra features

- Consistent red, white and charcoal interface with responsive layouts, hover/focus feedback, scroll reveals and reduced-motion support.
- A floating AI conversation panel with readable answers, car-result cards and one conversation scroll area.
- Car comparison, a saved shortlist, structured filters with removable selections, and spelling suggestions for inventory searches.
- Original workbook photographs for product listings, with separate decorative artwork for page headers.
- Expandable source details and clear treatment of absent or conflicting listing facts.
- Explicit preference saving, viewing review, enquiry correction and recovery for uncertain requests or failed CSV publication.

These are implemented features; their presence is separate from complete browser, accessibility or production acceptance.

## 6. Verification and measured performance

The [verification summary](delivery/evidence/verification-summary.md) records the scope, dates and remaining limits of the executed checks.

| Check | Recorded result |
| --- | --- |
| Current frontend suite | **346 passed**, 27 test files, no failures or skips. |
| Focused backend answer-readability checks | **183 passed**; not the entire backend suite. |
| Frontend types, lint and production build | Passed; **8 lint warnings** and a large-chunk warning remain. |
| Responsive checks | **215** earlier controlled checks; separate chat reviews passed **49**, **7** and **7** checks with synthetic conversation fixtures. |
| Broader live AI run | **34/38 selected cases passed; 4 provider timeouts**. |
| Later targeted live AI run | **5 cases, 11 steps, 116 assertions passed**; separate from the earlier run, not a replacement for its failures. |
| Local API pilot | **200/200 valid responses**, zero request errors/timeouts, up to three overlapping requests. |
| Local API latency | Median **641 ms**, p95 **1,026 ms**, p99 **1,261 ms**. The project's **500 ms p95 target was not met**. |

The latency pilot used the provider-disabled local API, not live AI responses or an internet deployment. The 500 ms target is an additional project goal, not a PDF requirement. The frontend build reported 824.84 kB minified / 137.75 kB gzip for the warned chunk. No passing performance target, complete security audit or universal mobile compatibility is claimed.

## Repository guide

| Path | Contents |
| --- | --- |
| `main.py`, `backend/` | Complete FastAPI entrypoint, application services, persistence and locked Python dependencies. |
| `frontend/` | React client, bundled visual assets and locked Node dependencies. |
| `contracts/` | API schema and generated runtime contracts. |
| `sources/` | Original assessment PDF and supplied workbook. |
| `scripts/`, `fixtures/`, selected `Records/` | Bootstrap inputs, simulation configuration and operator tools needed to run the app. |
| `delivery/` | Setup and decision notes, demonstrations and verification evidence. |

This is an assessment prototype, not an official dubizzle service. Branding and asset provenance are documented in `References/`; inclusion does not claim affiliation. Credentials, personal conversations, runtime databases and private operational exports are excluded. The sample lead evidence uses synthetic buyer inputs.
