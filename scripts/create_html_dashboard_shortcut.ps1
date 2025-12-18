# Create Desktop Shortcut for KIRO_MCP HTML Dashboard
# Project Creator: Herman Swanepoel

Write-Host "Creating KIRO_MCP HTML Dashboard Shortcut..." -ForegroundColor Cyan

$currentDir = Get-Location
$htmlPath = Join-Path $currentDir "mcp_monitor_dashboard.html"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "KIRO_MCP Dashboard.url"

# Create URL shortcut
$urlContent = @"
[InternetShortcut]
URL=file:///$($htmlPath -replace '\\', '/')
IconIndex=0
"@

$urlContent | Out-File -FilePath $shortcutPath -Encoding ASCII

Write-Host ""
Write-Host "✅ HTML Dashboard shortcut created!" -ForegroundColor Green
Write-Host "   Location: $shortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Double-click 'KIRO_MCP Dashboard' on your desktop to open!" -ForegroundColor Green
Write-Host ""

# Ask if user wants to launch now
$launch = Read-Host "Would you like to open the dashboard now? (Y/N)"
if ($launch -eq "Y" -or $launch -eq "y") {
    Start-Process $htmlPath
}
