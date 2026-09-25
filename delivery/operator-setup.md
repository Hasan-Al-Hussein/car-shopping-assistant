# Local operator setup

**Executed in a fresh extracted instance after mapped-host preparation; final release acceptance remains separate.** Run from the extracted project root after the README's dependency and bootstrap steps. Use the same runtime environment and successful bootstrap evidence directory. The recorded mapped-host bootstrap initially failed because its physical runtime directory had not been provisioned; approved same-case provisioning and first activation then succeeded. Ordinary same-root initialization is source-supported. No service automatically activates the pending configuration; preserve any original failure and activation identity.

For a newly bootstrapped instance only, the initial active viewing configuration is absent at revision zero. Read the bootstrap receipt and retain one activation identity before sending the command:

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

The operator checks the exact original receipt, generation, inventory, configuration and expected active revision. Success emits `ACTIVATION_RECORDED` and the relative activation receipt. Stop on any other result; a receipt-publication failure may follow a committed activation. Do not create another operation ID, rerun bootstrap, replace the Store or reset expectations. After restoring the same runtime environment and setting `$csaEvidence` to the original evidence directory, use this separate recovery block:

```powershell
$csaSaved = Get-Content -LiteralPath (Join-Path $csaEvidence 'activation-request.json') -Raw | ConvertFrom-Json
uv run --project backend --frozen python scripts/activate_viewing_configuration.py reconcile `
    --store $env:CSA_STORE_PATH --operation-id $csaSaved.operation_id `
    --expected-generation $csaSaved.generation --configuration-id $csaSaved.configuration_id `
    --expected-active-configuration $csaSaved.expected_active_configuration `
    --expected-revision $csaSaved.expected_revision --bundle $csaSaved.bundle `
    --receipt-sha256 $csaSaved.receipt_sha256
```

This reads the original recorded result without writing. Inspect the returned status and observation: both `RECORDED` and `NOT_RECORDED` use exit zero, so exit zero alone does not establish a committed activation. A `NOT_RECORDED` observation is not authorization for an automatic retry. Existing instances require their observed active configuration/revision, not the fresh-instance `absent/0` example.

Start the real root `main.py` only after activation is resolved. The server holds a shared Store maintenance admission for its lifetime. Before offline restore or retention work, stop that server gracefully and establish that its owned process and pending provider/workers have settled. Forced process termination is not evidence of a graceful drain. These operator tools are local commands, never buyer HTTP endpoints.

The CSV projector runs after canonical writes and at application startup. For an explicitly selected existing instance, `uv run --project backend --frozen python scripts/operations/repair_csv.py --store $env:CSA_STORE_PATH` runs repair and reports a closed status. Its `--reconcile-from-generation` option is for an independently completed fenced restore with the original generation; do not invent a generation to clear a pending result. CSV files live beneath the selected runtime's `exports` directory and are distinct from canonical SQLite state.

The bundle also includes the explicit backup, restore and retention operators and the synthetic evaluator. Their presence does not schedule or authorize destructive maintenance or live provider evaluation. The evaluator defaults to scripted transport on an empty-owner disposable test Store; it is not the required real HTTP conversation demonstration. Its live mode additionally requires separately accepted free-access evidence and a finite call budget. No local account key, DPAPI cache, live Store, operational backup/export or internal test-host launcher belongs in the submission.
