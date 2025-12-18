# Create Desktop Shortcut for KIRO_MCP Monitor
# Project Creator: Herman Swanepoel
# Version: 1.0

Write-Host "Creating KIRO_MCP Monitor Desktop Shortcut..." -ForegroundColor Cyan

# Get current directory
$currentDir = Get-Location
$scriptPath = Join-Path $currentDir "mcp_monitor_dashboard.py"
$iconPath = Join-Path $currentDir "mcp_monitor_icon.ico"

# Get desktop path
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "KIRO_MCP Monitor.lnk"

# Get Python executable path
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Host "Python not found in PATH. Trying py launcher..." -ForegroundColor Yellow
    $pythonPath = (Get-Command py -ErrorAction SilentlyContinue).Source
}

if (-not $pythonPath) {
    Write-Host "ERROR: Python not found! Please install Python or add it to PATH." -ForegroundColor Red
    exit 1
}

Write-Host "Using Python: $pythonPath" -ForegroundColor Green

# Create WScript Shell object
$WScriptShell = New-Object -ComObject WScript.Shell

# Create shortcut
$shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonPath
$shortcut.Arguments = "`"$scriptPath`""
$shortcut.WorkingDirectory = $currentDir
$shortcut.Description = "KIRO_MCP Monitor Dashboard - Real-time monitoring for MCP Server"
$shortcut.WindowStyle = 1  # Normal window

# Set icon if it exists
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
    Write-Host "Icon set: $iconPath" -ForegroundColor Green
} else {
    Write-Host "Icon not found, using default Python icon" -ForegroundColor Yellow
}

# Save shortcut
$shortcut.Save()

Write-Host ""
Write-Host "✅ Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "   Location: $shortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now double-click 'KIRO_MCP Monitor' on your desktop to launch the monitor." -ForegroundColor Green
Write-Host ""

# Ask if user wants to launch now
$launch = Read-Host "Would you like to launch the monitor now? (Y/N)"
if ($launch -eq "Y" -or $launch -eq "y") {
    Write-Host "Launching KIRO_MCP Monitor..." -ForegroundColor Cyan
    Start-Process -FilePath $pythonPath -ArgumentList "`"$scriptPath`"" -WorkingDirectory $currentDir
}
