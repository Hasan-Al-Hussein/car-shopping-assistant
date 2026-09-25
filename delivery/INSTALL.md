# Install and run the complete product on Windows

Follow these steps in order. Use two PowerShell windows: the first runs the backend, and the second runs the website. Keep both open while using the app.

## 1. Download the ZIP

Download [Car-Shopping-Assistant-Submission.zip](https://github.com/Hasan-Al-Hussein/car-shopping-assistant/releases/download/assessment-submission-2026-09-25/Car-Shopping-Assistant-Submission.zip). This is the complete submission, including the source, supplied inventory, screenshots and setup documents.

## 2. Extract it

In File Explorer, right-click the downloaded ZIP and choose **Extract All**. Extract into a new folder, for example `C:\Users\YOUR_NAME\Documents\Car-Shopping-Assistant`. Open that folder. You should see `README.md`, `main.py`, `backend`, `frontend` and `sources`. Do not run it from inside the ZIP or move individual files out of their folders.

## 3. Install the prerequisites

Use Windows with Python **3.13.3**, Node.js **24.13 or newer within version 24**, npm **11.6.2 or newer within version 11**, and uv. Install them from the official [Python](https://www.python.org/downloads/release/python-3133/), [Node.js](https://nodejs.org/en/download) and [uv installation](https://docs.astral.sh/uv/getting-started/installation/) pages. npm comes with Node.js. Python must be installed before the next step because this project disables automatic Python downloads.

Open a fresh PowerShell window and check:

```powershell
python --version
uv --version
node --version
npm --version
```

If a command is not found, finish installing it and reopen PowerShell. You also need a Google AI Studio API key with confirmed free-tier access for live AI. Do not enable billing to follow this guide. Inventory browsing can run without a working provider, but live AI cannot.

## 4. Open PowerShell in the extracted folder

Open the folder containing `main.py` in File Explorer, click its address bar, type `powershell`, and press Enter. Check that this is the correct folder:

```powershell
Get-Location
Test-Path .\main.py
Test-Path .\backend
Test-Path .\frontend
```

The three checks should say `True`. This is **Terminal 1**. Keep using this terminal for steps 5 through 8 so its runtime variables stay available.

## 5. Install the backend and frontend dependencies

```powershell
Set-Location backend
uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Set-Location ../frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
Set-Location ..
```

Let each command finish. Stop if an installation reports an error; do not continue with partially installed dependencies.

## 6. Initialize a fresh local database

Run this once for a new installation. It imports the supplied cars and creates an isolated runtime for the database and CSV exports. Start with an ordinary terminal without inherited `CSA_*`, provider-key or custom `PYTHONPATH` overrides.

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

Do not repeat initialization just to restart the app: it creates a different runtime. Keep the printed evidence and the original runtime paths if a step fails.

## 7. Activate the simulated viewing schedule

Still in Terminal 1, copy this complete block. A successful result includes `ACTIVATION_RECORDED`.

```powershell
$csaReceiptPath = Join-Path $csaEvidence 'receipt.json'
$csaReceipt = Get-Content -LiteralPath $csaReceiptPath -Raw | ConvertFrom-Json
if ($csaReceipt.status -ne 'INVENTORY_ACTIVATED_RULES_ACTIVATION_PENDING') {
    throw 'A successful original bootstrap receipt is required.'
}
$csaBundle = 'Records/build/BE-05/I7/runs/' + (Split-Path $csaEvidence -Leaf)
$csaActivation = @{
    operation_id = [guid]::NewGuid().ToString()
    generation = $csaReceipt.store_generation
    configuration_id = $csaReceipt.configuration_id
    expected_active_configuration = 'absent'
    expected_revision = 0
    bundle = $csaBundle
    receipt_sha256 = (Get-FileHash -LiteralPath $csaReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
}
$csaActivationPath = Join-Path $csaEvidence 'activation-request.json'
$csaStream = [System.IO.File]::Open($csaActivationPath, [System.IO.FileMode]::CreateNew)
try {
    $csaBytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($csaActivation | ConvertTo-Json))
    $csaStream.Write($csaBytes, 0, $csaBytes.Length)
} finally { $csaStream.Dispose() }
$csaArguments = @(
    '--store', $env:CSA_STORE_PATH,
    '--operation-id', $csaActivation.operation_id,
    '--expected-generation', $csaActivation.generation,
    '--configuration-id', $csaActivation.configuration_id,
    '--expected-active-configuration', $csaActivation.expected_active_configuration,
    '--expected-revision', [string]$csaActivation.expected_revision,
    '--bundle', $csaActivation.bundle,
    '--receipt-sha256', $csaActivation.receipt_sha256
)
uv run --project backend --frozen python scripts/activate_viewing_configuration.py activate @csaArguments
if ($LASTEXITCODE -ne 0) { throw 'Activation needs reconciliation; preserve this request and instance.' }
```

If activation reports a failure, stop and follow the reconciliation instructions in [operator setup](operator-setup.md). Preserve the original operation and runtime; do not generate a replacement activation to bypass the error.

## 8. Enter your API key and start the backend

Paste the following block into Terminal 1. Enter your own Google AI Studio key at the masked prompt. The application reads the environment directly; creating a `.env` file is not enough.

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

Leave this terminal running. The backend uses `http://127.0.0.1:8000`. If port 8000 is busy, stop your previous instance before starting a second one.

## 9. Start the website in a second terminal

Open another PowerShell window in the same extracted project folder, as in step 4. Run:

```powershell
Set-Location frontend
npm run dev
```

Keep this **Terminal 2** running. Port 5173 must be available. The frontend forwards API requests to the backend, so both terminals are needed.

## 10. Open and use the product

Open **http://127.0.0.1:5173/__app** in your browser.

1. Browse the homepage inventory or search for `Nissan`.
2. Open a listing to see its real photo and available facts.
3. Add two cars to Compare and open the Compare page.
4. Click **Ask AI**. Complete the displayed first-use browser-access consent to create a local user identity. Keep using the same browser identity to retain saved preferences.
5. Try `Show me Nissan cars`, then ask a follow-up about one of the results. A phrase such as `My budget is 20k dirhams` sets an AED 20,000 purchase limit; cars without a stated price cannot be assumed to fit it.
6. Use explicit save/confirmation controls for preferences, enquiries and simulated viewings. The viewing schedule runs Monday to Saturday, 08:00-20:00 Dubai time. No dealer is contacted.

The runtime's `exports` folder contains enquiry CSV exports. The [demo guide](demo/README.md) and [recorded evidence](evidence/qualified-enquiry.md) show the transaction flow.

## 11. Stop the product

Press **Ctrl+C** in each terminal. Keep the database and exports if you want to retain your data. For a later restart, restore the same runtime environment and start steps 8 and 9; do not rerun the fresh-instance bootstrap or activation. The [operator setup](operator-setup.md) explains existing-instance recovery.

## If something does not work

| What you see | What to check |
| --- | --- |
| Website cannot connect | Both terminals must be running, with ports 8000 and 5173 available. Use the exact `/__app` URL. |
| Cars fail to load | Check Terminal 1 and the bootstrap result. A running frontend alone does not provide inventory. |
| AI is unavailable | Check your free-tier key and provider availability. Temporary provider failures can occur; browsing and comparing remain separate functions. |
| Viewing schedule unavailable | Finish step 7 successfully before starting the backend. |
| Private features ask for access | Complete the first-use access flow in that browser; another browser identity is a different local user. |

These commands preserve the documented setup sequence. The recorded clean-install run used a mapped Windows execution host; a separate installation on an ordinary unmapped machine was not executed. See the [clean-install evidence](evidence/clean-setup.md) for that scope.
