param(
    [string]$Destination = (Join-Path $PSScriptRoot "..\NEXORA-production.zip"),
    [switch]$ExcludeMedia
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$staging = Join-Path $env:TEMP ("nexora-production-" + [guid]::NewGuid().ToString('N'))
$excluded = @(
    '.env', '.git', '.venv', 'venv', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'staticfiles', 'db.sqlite3'
)
$excludedFilePatterns = @(
    '*.log', '.codex-write-probe', 'preview*', 'catalog-sync*',
    'gallery-enrich*', 'archive-export*', 'browser-server*', 'light-archive*',
    'overnight-*'
)
if ($ExcludeMedia) {
    $excluded += 'media'
}

New-Item -ItemType Directory -Path $staging | Out-Null
try {
    Get-ChildItem -LiteralPath $projectRoot -Force |
        Where-Object {
            $item = $_
            $item.Name -notin $excluded -and
            $item.Extension -ne '.zip' -and
            -not ($excludedFilePatterns | Where-Object { $item.Name -like $_ })
        } |
        Copy-Item -Destination $staging -Recurse -Force

    # Copy-Item preserves nested directories, so remove any generated files
    # that may have appeared below an otherwise valid source directory.
    Get-ChildItem -LiteralPath $staging -Force -Recurse -Directory |
        Where-Object { $_.Name -in @('.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache') } |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $staging -Force -Recurse -File |
        Where-Object {
            $item = $_
            $item.Name -eq 'db.sqlite3' -or
            $item.Extension -eq '.zip' -or
            ($excludedFilePatterns | Where-Object { $item.Name -like $_ })
        } |
        Remove-Item -Force

    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Force
    }
    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $Destination -CompressionLevel Optimal
    Write-Output "Created production archive: $Destination"
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
