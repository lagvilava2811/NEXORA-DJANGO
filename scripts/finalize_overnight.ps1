$ErrorActionPreference = 'Continue'
$root = 'C:\Users\DANI\Documents\Codex\2026-07-10\new-chat\work\nexora-final'
$python = 'C:\Users\DANI\Desktop\musea-premium-store\.venv\Scripts\python.exe'
$log = Join-Path $root 'overnight-finalize.log'
$statusFile = Join-Path $root 'overnight-status.json'
function Write-Log([string]$message) {
    $line = "$(Get-Date -Format o) $message"
    Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}
function Enrichment-Running {
    return [bool](Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*manage.py enrich_product_galleries*' })
}
function Write-Status([string]$state, [int]$auditCode = -1, [int]$testCode = -1) {
    $payload = [ordered]@{ state=$state; updated_at=(Get-Date).ToString('o'); audit_exit=$auditCode; test_exit=$testCode }
    $payload | ConvertTo-Json | Set-Content -LiteralPath $statusFile -Encoding UTF8
}
Set-Location -LiteralPath $root
Write-Status 'waiting-for-primary-enrichment'
Write-Log 'Waiting for the active 1,040-product enrichment pass.'
while (Enrichment-Running) { Start-Sleep -Seconds 30 }
Write-Log 'Primary enrichment pass finished.'
$auditCode = 1
for ($attempt = 1; $attempt -le 3; $attempt++) {
    Write-Log "Strict audit attempt $attempt."
    & $python manage.py audit_catalog --strict --minimum-products 1000 --minimum-images 4 *>> $log
    $auditCode = $LASTEXITCODE
    if ($auditCode -eq 0) { break }
    if ($attempt -lt 3) {
        Write-Status "retry-$attempt" $auditCode -1
        if ($attempt -eq 1) {
            Write-Log 'Adding the remaining exact manifest records as an unpublished buffer before retry.'
            & $python manage.py sync_wikidata_catalog --target 1197 --metadata-only --apply --verbosity 1 *>> $log
        }
        Write-Log "Retrying incomplete galleries (pass $attempt)."
        & $python -u manage.py enrich_product_galleries --min-images 4 --workers 12 --apply --publish-ready-only --verbosity 1 *>> $log
    }
}
if ($auditCode -ne 0) {
    Write-Status 'audit-failed' $auditCode -1
    Write-Log 'Strict 1,000-product audit did not pass; ZIP intentionally not created.'
    exit $auditCode
}
Write-Status 'testing' 0 -1
Write-Log 'Strict audit passed. Running full test suite.'
& $python manage.py test --verbosity 1 *>> $log
$testCode = $LASTEXITCODE
if ($testCode -ne 0) {
    Write-Status 'tests-failed' 0 $testCode
    Write-Log 'Tests failed; ZIP intentionally not created.'
    exit $testCode
}
$zip = Join-Path $root 'NEXORA-premium-complete.zip'
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Write-Status 'packaging' 0 0
Write-Log 'Audit and tests passed. Creating clean ZIP.'
& tar.exe -a -c -f $zip --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude='*.pyc' --exclude='*.log' --exclude='media/.wikidata-staging' --exclude='NEXORA-premium-complete.zip' . *>> $log
$zipCode = $LASTEXITCODE
if ($zipCode -eq 0 -and (Test-Path -LiteralPath $zip)) {
    Write-Status 'complete' 0 0
    Write-Log "Complete ZIP created: $zip"
    exit 0
}
Write-Status 'zip-failed' 0 0
Write-Log "ZIP creation failed with exit code $zipCode."
exit $zipCode