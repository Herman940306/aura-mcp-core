param()

Write-Host "Checking Aura IA MCP stack health (Canonical Ports)..." -ForegroundColor Cyan

# Backend health (9201)
try {
  $backend = Invoke-RestMethod -Uri "http://localhost:9201/health" -TimeoutSec 3 -Method GET
  Write-Host "Aura IA ML Backend: OK ($($backend.service))" -ForegroundColor Green
}
catch {
  Write-Host "Aura IA ML Backend: UNAVAILABLE (http://localhost:9201)" -ForegroundColor Red
}

# Aura IA Gateway SSE port (9200)
try {
  $mcp = Test-NetConnection -ComputerName localhost -Port 9200 -WarningAction SilentlyContinue
  if ($mcp.TcpTestSucceeded) {
    Write-Host "Aura IA Gateway: LISTENING (http://localhost:9200)" -ForegroundColor Green
  }
  else {
    Write-Host "Aura IA Gateway: NOT LISTENING" -ForegroundColor Yellow
  }
}
catch { Write-Host "Aura IA Gateway: ERROR" -ForegroundColor Red }

# Aura IA Dashboard (9205)
try {
  $dash = Invoke-WebRequest -Uri "http://localhost:9205" -TimeoutSec 3 -Method GET -UseBasicParsing
  if ($dash.StatusCode -ge 200 -and $dash.StatusCode -lt 400) {
    Write-Host "Aura IA Dashboard: OK (http://localhost:9205)" -ForegroundColor Green
  }
  else {
    Write-Host "Aura IA Dashboard: ERROR ($($dash.StatusCode))" -ForegroundColor Yellow
  }
}
catch { Write-Host "Aura IA Dashboard: UNAVAILABLE (http://localhost:9205)" -ForegroundColor Yellow }

# Telemetry file presence
$telemetry = Join-Path $PSScriptRoot "..\logs\mcp_tool_spans.jsonl"
if (Test-Path $telemetry) {
  Write-Host "Telemetry: FOUND logs/mcp_tool_spans.jsonl" -ForegroundColor Green
}
else {
  Write-Host "Telemetry: NOT FOUND (yet)" -ForegroundColor Yellow
}

# Extended structural verification (Python script)
if (Test-Path "$PSScriptRoot\verify_compose_stack.py") {
  try {
    $result = python "$PSScriptRoot\verify_compose_stack.py"
    Write-Host "Compose structural verification executed" -ForegroundColor Cyan
  }
  catch {
    Write-Host "Compose structural verification error" -ForegroundColor Red
  }
}
