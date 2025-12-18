param([switch]$Rebuild)

$cmd = "docker compose up -d";
if ($Rebuild) { $cmd = "docker compose up -d --build" }
Write-Host "Running: $cmd" -ForegroundColor Cyan
Invoke-Expression $cmd

# Brief wait and verify
Start-Sleep -Seconds 2
powershell -ExecutionPolicy Bypass -File scripts/verify_stack.ps1
