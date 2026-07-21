<# Stores a Gemini key locally in .env without echoing it to the screen. #>

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot '.env'
$templateFile = Join-Path $projectRoot '.env.example'

if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $templateFile -Destination $envFile
}

$secureKey = Read-Host 'Paste the Gemini API key' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ($apiKey.Length -lt 20) {
    throw 'The Gemini API key looks incomplete. Nothing was changed.'
}

$lines = [System.Collections.Generic.List[string]](Get-Content -LiteralPath $envFile)
foreach ($entry in ([ordered]@{'GEMINI_API_KEY' = $apiKey; 'GEMINI_MODEL' = 'gemini-2.5-flash-lite'; 'GEMINI_ENABLED' = 'True'}).GetEnumerator()) {
    $pattern = '^' + [regex]::Escape($entry.Key) + '='
    $index = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) { $index = $i; break }
    }
    $line = "$($entry.Key)=$($entry.Value)"
    if ($index -ge 0) { $lines[$index] = $line } else { $lines.Add($line) }
}

Set-Content -LiteralPath $envFile -Value $lines -Encoding utf8
Write-Host 'Gemini key saved to .env. Restart Django to activate the live NEXORA GUIDE.' -ForegroundColor Green
