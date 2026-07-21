<#
Configures local Gmail SMTP credentials for NEXORA.
The Google App Password is requested interactively and is never printed.
#>

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot '.env'
$templateFile = Join-Path $projectRoot '.env.example'

if (-not (Test-Path -LiteralPath $envFile)) {
    Copy-Item -LiteralPath $templateFile -Destination $envFile
}

$securePassword = Read-Host 'Paste the 16-character Google App Password' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $appPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Replace(' ', '')
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ($appPassword.Length -lt 16) {
    throw 'The App Password looks incomplete. Nothing was changed.'
}

$secretBytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($secretBytes)
$djangoSecret = [Convert]::ToBase64String($secretBytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')

$values = [ordered]@{
    'DJANGO_DEBUG' = 'True'
    'DJANGO_SECRET_KEY' = $djangoSecret
    'DJANGO_ALLOWED_HOSTS' = 'localhost,127.0.0.1'
    'DJANGO_CSRF_TRUSTED_ORIGINS' = 'http://localhost:8020,http://127.0.0.1:8020'
    'DJANGO_CACHE_URL' = ''
    'DJANGO_EMAIL_BACKEND' = 'django.core.mail.backends.smtp.EmailBackend'
    'EMAIL_HOST' = 'smtp.gmail.com'
    'EMAIL_PORT' = '587'
    'EMAIL_HOST_USER' = 'nexora.store.ge@gmail.com'
    'EMAIL_HOST_PASSWORD' = $appPassword
    'EMAIL_USE_TLS' = 'True'
    'EMAIL_USE_SSL' = 'False'
    'EMAIL_TIMEOUT' = '10'
    'DEFAULT_FROM_EMAIL' = 'NEXORA <nexora.store.ge@gmail.com>'
}

$lines = [System.Collections.Generic.List[string]](Get-Content -LiteralPath $envFile)
foreach ($entry in $values.GetEnumerator()) {
    $pattern = '^' + [regex]::Escape($entry.Key) + '='
    $index = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) { $index = $i; break }
    }
    $line = "$($entry.Key)=$($entry.Value)"
    if ($index -ge 0) { $lines[$index] = $line } else { $lines.Add($line) }
}

Set-Content -LiteralPath $envFile -Value $lines -Encoding utf8
Write-Host 'SMTP setup saved to .env. Restart the Django server, then test Password reset.' -ForegroundColor Green
