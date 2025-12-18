param()

# Ensure .env exists from template
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"
if (-not (Test-Path $envFile)) {
  if (Test-Path $envExample) { Copy-Item $envExample $envFile -Force }
  else { New-Item -ItemType File -Path $envFile -Force | Out-Null }
}

Write-Host "Paste your GitHub Personal Access Token (it will be written to .env)" -ForegroundColor Cyan
$token = Read-Host "GITHUB_TOKEN"

if ([string]::IsNullOrWhiteSpace($token)) {
  Write-Host "No token entered. Aborting." -ForegroundColor Yellow
  exit 1
}

# Read existing .env, remove any existing GITHUB_TOKEN line, prepend new one
$lines = @()
if (Test-Path $envFile) { $lines = Get-Content $envFile }
$filtered = $lines | Where-Object { $_ -notmatch '^\s*GITHUB_TOKEN\s*=' }
$newContent = @("GITHUB_TOKEN=$token") + $filtered
$newContent | Set-Content -Path $envFile -Encoding UTF8

# Also export for current session so docker compose picks it up from this shell
$env:GITHUB_TOKEN = $token

Write-Host "Saved GITHUB_TOKEN to .env and exported for current session." -ForegroundColor Green
