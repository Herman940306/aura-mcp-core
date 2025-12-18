param(
    [ValidateSet('sse', 'stdio')]
    [string]$Transport = 'stdio',
    [string]$McpHost = '127.0.0.1',
    [int]$Port = 9200,
    [string]$BackendUrl = 'http://127.0.0.1:9201'
)

Write-Host "Starting Aura IA MCP (Transport=$Transport) with backend..." -ForegroundColor Cyan

$env:MCP_TRANSPORT = $Transport
$env:MCP_HOST = $McpHost
$env:MCP_PORT = "$Port"
$env:IDE_AGENTS_BACKEND_URL = $BackendUrl

$logs = Join-Path $PSScriptRoot '..' | Resolve-Path | ForEach-Object { Join-Path $_ 'logs' }
if (!(Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }

# Launch backend + MCP server in a detached window to avoid blocking
$py = Join-Path (Join-Path $PSScriptRoot '..' | Resolve-Path) 'venv\Scripts\python.exe'
$starter = Join-Path $PSScriptRoot 'start_mcp_with_backend.py'

if (!(Test-Path $py)) { $py = 'python' }

Write-Host "Launching: $starter" -ForegroundColor DarkCyan
Start-Process -FilePath $py -ArgumentList $starter -WindowStyle Minimized -RedirectStandardOutput (Join-Path $logs 'dev_up_local.out.log') -RedirectStandardError (Join-Path $logs 'dev_up_local.err.log')

# Give it a moment to boot
Start-Sleep -Seconds 3

# Run readiness checks (SSE if transport=sse; otherwise direct local test)
if ($Transport -eq 'sse') {
    $env:MCP_SSE_URL = "http://$($McpHost):$($Port)"
    try {
        & $py (Join-Path $PSScriptRoot 'check_readyz.py')
    }
    catch {
        Write-Warning "SSE readiness failed: $($_.Exception.Message)"
    }
}

# Always run the local in-process health test for certainty
try {
    & $py (Join-Path $PSScriptRoot '..\tests\test_readiness_and_healthz.py')
}
catch {
    Write-Warning "Local readiness test failed: $($_.Exception.Message)"
}

# Quick security audit smoke
try {
    & $py (Join-Path $PSScriptRoot '..\tests\test_security_audit.py')
}
catch {
    Write-Warning "Security audit test encountered an error: $($_.Exception.Message)"
}

Write-Host "dev_up_local completed. See logs in $logs" -ForegroundColor Green
