# KIRO_MCP Real-Time Monitor with ULTRA Mode Toggle
# Project Creator: Herman Swanepoel

$Host.UI.RawUI.WindowTitle = "KIRO_MCP Monitor"
$Host.UI.RawUI.BackgroundColor = "Black"
$Host.UI.RawUI.ForegroundColor = "Green"
Clear-Host

$mcpPath = "C:\Users\herma\AppData\Local\Programs\Kiro\mcp-servers\kiro_mcp"
$dataPath = "$mcpPath\data"
$logsPath = "$mcpPath\logs"
$envFile = "$mcpPath\.env"

function Get-UltraMode {
    if (Test-Path $envFile) {
        $content = Get-Content $envFile -Raw
        if ($content -match "IDE_AGENTS_ULTRA_ENABLED=(\w+)") {
            return $matches[1] -eq "true"
        }
    }
    return $false
}

function Set-UltraMode {
    param([bool]$enabled)
    
    if (Test-Path $envFile) {
        $content = Get-Content $envFile -Raw
        $newValue = if ($enabled) { "true" } else { "false" }
        $content = $content -replace "IDE_AGENTS_ULTRA_ENABLED=\w+", "IDE_AGENTS_ULTRA_ENABLED=$newValue"
        $content | Set-Content $envFile -NoNewline
        
        Write-Host ""
        Write-Host "ULTRA MODE " -NoNewline
        if ($enabled) {
            Write-Host "ENABLED" -ForegroundColor Green
        } else {
            Write-Host "DISABLED" -ForegroundColor Red
        }
        Write-Host "Restart KIRO_MCP for changes to take effect" -ForegroundColor Yellow
        Write-Host ""
        Start-Sleep -Seconds 2
    }
}

function Get-LatestFiles {
    param($path, $count = 5)
    if (Test-Path $path) {
        Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue | 
            Sort-Object LastWriteTime -Descending | 
            Select-Object -First $count
    }
}

function Show-BackendStatus {
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
        Write-Host "[BACKEND] " -NoNewline -ForegroundColor Green
        Write-Host "Status: $($response.status) | Service: $($response.service)" -ForegroundColor White
    } catch {
        Write-Host "[BACKEND] " -NoNewline -ForegroundColor Red
        Write-Host "OFFLINE" -ForegroundColor Red
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   KIRO_MCP REAL-TIME MONITOR" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Monitoring: $mcpPath" -ForegroundColor Gray
Write-Host ""
Write-Host "Controls:" -ForegroundColor Cyan
Write-Host "  [U] Toggle ULTRA Mode" -ForegroundColor White
Write-Host "  [R] Refresh Now" -ForegroundColor White
Write-Host "  [Q] Quit" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

while ($true) {
    Clear-Host
    
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   KIRO_MCP REAL-TIME MONITOR" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Time: $(Get-Date -Format ''yyyy-MM-dd HH:mm:ss'')" -ForegroundColor Gray
    Write-Host ""
    
    # ULTRA Mode Status
    $ultraEnabled = Get-UltraMode
    Write-Host "[ULTRA MODE] " -NoNewline -ForegroundColor Cyan
    if ($ultraEnabled) {
        Write-Host "ENABLED" -ForegroundColor Green
    } else {
        Write-Host "DISABLED" -ForegroundColor Red
    }
    Write-Host ""
    
    # Backend Status
    Show-BackendStatus
    Write-Host ""
    
    # Data Folder Stats
    Write-Host "[DATA FOLDER]" -ForegroundColor Cyan
    if (Test-Path $dataPath) {
        $interactions = (Get-ChildItem "$dataPath\interactions" -File -ErrorAction SilentlyContinue).Count
        $patterns = (Get-ChildItem "$dataPath\patterns" -File -ErrorAction SilentlyContinue).Count
        $knowledge = (Get-ChildItem "$dataPath\knowledge" -File -ErrorAction SilentlyContinue).Count
        $optimizations = (Get-ChildItem "$dataPath\optimizations" -File -ErrorAction SilentlyContinue).Count
        $cycles = (Get-ChildItem "$dataPath\reasoning_cycles" -File -ErrorAction SilentlyContinue).Count
        
        Write-Host "  Interactions: $interactions" -ForegroundColor White
        Write-Host "  Patterns: $patterns" -ForegroundColor White
        Write-Host "  Knowledge: $knowledge" -ForegroundColor White
        Write-Host "  Optimizations: $optimizations" -ForegroundColor White
        Write-Host "  Reasoning Cycles: $cycles" -ForegroundColor White
    }
    Write-Host ""
    
    # Latest Interactions
    Write-Host "[LATEST INTERACTIONS]" -ForegroundColor Cyan
    $latest = Get-LatestFiles "$dataPath\interactions" 3
    if ($latest) {
        foreach ($file in $latest) {
            Write-Host "  $($file.LastWriteTime.ToString(''HH:mm:ss'')) - $($file.Name)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  No interactions yet" -ForegroundColor Gray
    }
    Write-Host ""
    
    # Latest Logs
    Write-Host "[LATEST LOGS]" -ForegroundColor Cyan
    $latestLogs = Get-LatestFiles $logsPath 3
    if ($latestLogs) {
        foreach ($log in $latestLogs) {
            Write-Host "  $($log.LastWriteTime.ToString(''HH:mm:ss'')) - $($log.Name)" -ForegroundColor Magenta
        }
    } else {
        Write-Host "  No logs yet" -ForegroundColor Gray
    }
    Write-Host ""
    
    # MCP Process Status
    Write-Host "[MCP PROCESS]" -ForegroundColor Cyan
    $pythonProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like "*Python311*"
    }
    if ($pythonProcs) {
        Write-Host "  Running: $($pythonProcs.Count) Python process(es)" -ForegroundColor Green
    } else {
        Write-Host "  No Python processes detected" -ForegroundColor Red
    }
    Write-Host ""
    
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "[U] Toggle ULTRA | [R] Refresh | [Q] Quit" -ForegroundColor Gray
    Write-Host "Auto-refresh in 5 seconds..." -ForegroundColor Gray
    
    # Check for key press with timeout
    $timeout = 5
    $startTime = Get-Date
    $keyPressed = $false
    
    while (((Get-Date) - $startTime).TotalSeconds -lt $timeout) {
        if ($Host.UI.RawUI.KeyAvailable) {
            $key = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            $keyPressed = $true
            
            switch ($key.Character.ToString().ToUpper()) {
                "U" {
                    $currentMode = Get-UltraMode
                    Set-UltraMode -enabled (-not $currentMode)
                    break
                }
                "R" {
                    # Just refresh immediately
                    break
                }
                "Q" {
                    Clear-Host
                    Write-Host "KIRO_MCP Monitor stopped." -ForegroundColor Yellow
                    exit
                }
            }
            
            if ($keyPressed) { break }
        }
        Start-Sleep -Milliseconds 100
    }
}
