param(
  [string]$Destination = "F:\Kiro_Projects\LATEST_MCP",
  [switch]$Mirror,
  [switch]$DryRun,
  [switch]$IncludeEnv
)

$ErrorActionPreference = 'Stop'

# Resolve source to repo root (this script lives in /scripts)
$Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not (Test-Path $Destination)) {
  New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}

$excludeDirs  = @('.git', '.venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.vs', '.idea', 'node_modules')
$excludeFiles = @('*.pyc', '*.pyo', '*.log', '*.tmp')

# Build robocopy options
$opts = @('/R:0','/W:0','/MT:16','/TEE')
if ($Mirror.IsPresent) { $opts += '/MIR' } else { $opts += '/E' }
if ($DryRun.IsPresent) { $opts += '/L'; $opts += '/NJH'; $opts += '/NJS' }
foreach ($d in $excludeDirs) { $opts += '/XD'; $opts += $d }
foreach ($f in $excludeFiles) { $opts += '/XF'; $opts += $f }

Write-Host "Source     : $Source"
Write-Host "Destination: $Destination"
Write-Host "Mode       : " -NoNewline; if ($Mirror) { Write-Host 'MIRROR (/MIR)' } else { Write-Host 'COPY (/E)' }
if ($DryRun) { Write-Host "Dry Run   : yes (/L)" }

# Run robocopy
& robocopy $Source $Destination @opts | Write-Host
$rc = $LASTEXITCODE

# Optionally copy .env after robocopy (it might be excluded depending on your filters)
if ($IncludeEnv.IsPresent) {
  $envSrc = Join-Path $Source '.env'
  if (Test-Path $envSrc) {
    Copy-Item $envSrc (Join-Path $Destination '.env') -Force
    Write-Host "Copied .env"
  }
}

# Interpret robocopy exit code (0-7 considered success)
if ($rc -le 7) {
  Write-Host "Clone completed (robocopy code $rc)"
  exit 0
} else {
  Write-Error "Robocopy failed with code $rc"
  exit $rc
}
