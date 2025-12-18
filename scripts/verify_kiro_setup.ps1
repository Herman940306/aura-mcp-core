# Kiro IDE Setup Verification Script
# Project Creator: Herman Swanepoel

Write-Host "`n======================================" -ForegroundColor Cyan
Write-Host "  KIRO IDE SETUP VERIFICATION" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

$allGood = $true
$hasAtLeastOne = $false

# Check Configuration Files
Write-Host "1. Configuration Files" -ForegroundColor Yellow
if (Test-Path "C:\Users\herma\.kiro\settings\provider_config.json") {
    Write-Host "   ✓ provider_config.json" -ForegroundColor Green
} else {
    Write-Host "   ✗ provider_config.json missing" -ForegroundColor Red
    $allGood = $false
}

if (Test-Path "C:\Users\herma\.kiro\settings\models.json") {
    Write-Host "   ✓ models.json" -ForegroundColor Green
} else {
    Write-Host "   ✗ models.json missing" -ForegroundColor Red
    $allGood = $false
}

if (Test-Path ".kiro\settings\mcp.json") {
    Write-Host "   ✓ mcp.json" -ForegroundColor Green
} else {
    Write-Host "   ✗ mcp.json missing" -ForegroundColor Red
    $allGood = $false
}

# Check API Keys
Write-Host "`n2. API Keys" -ForegroundColor Yellow
if ($env:OPENAI_API_KEY) {
    Write-Host "   ✓ OpenAI: $($env:OPENAI_API_KEY.Substring(0,10))..." -ForegroundColor Green
    $hasAtLeastOne = $true
} else {
    Write-Host "   ○ OpenAI not set" -ForegroundColor Gray
}

if ($env:ANTHROPIC_API_KEY) {
    Write-Host "   ✓ Anthropic: $($env:ANTHROPIC_API_KEY.Substring(0,10))..." -ForegroundColor Green
    $hasAtLeastOne = $true
} else {
    Write-Host "   ○ Anthropic not set" -ForegroundColor Gray
}

if ($env:GOOGLE_API_KEY) {
    Write-Host "   ✓ Google: $($env:GOOGLE_API_KEY.Substring(0,10))..." -ForegroundColor Green
    $hasAtLeastOne = $true
} else {
    Write-Host "   ○ Google not set" -ForegroundColor Gray
}

if ($env:DEEPSEEK_API_KEY) {
    Write-Host "   ✓ DeepSeek: $($env:DEEPSEEK_API_KEY.Substring(0,10))..." -ForegroundColor Green
    $hasAtLeastOne = $true
} else {
    Write-Host "   ○ DeepSeek not set" -ForegroundColor Gray
}

if (-not $hasAtLeastOne) {
    Write-Host "   ⚠ No API keys set!" -ForegroundColor Yellow
}

# Check GitHub Token
Write-Host "`n3. GitHub Integration" -ForegroundColor Yellow
if ($env:GITHUB_TOKEN) {
    Write-Host "   ✓ GitHub Token: $($env:GITHUB_TOKEN.Substring(0,15))..." -ForegroundColor Green
} else {
    Write-Host "   ○ GitHub Token not set" -ForegroundColor Gray
}

# Check Backend
Write-Host "`n4. MCP Backend Service" -ForegroundColor Yellow
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "   ✓ Backend running on port 8001" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Backend not running" -ForegroundColor Red
    $allGood = $false
}

# Check Python
Write-Host "`n5. Python Environment" -ForegroundColor Yellow
try {
    $ver = python --version 2>&1
    Write-Host "   ✓ Python: $ver" -ForegroundColor Green
} catch {
    Write-Host "   ✗ Python not found" -ForegroundColor Red
    $allGood = $false
}

# Summary
Write-Host "`n======================================" -ForegroundColor Cyan
if ($allGood -and $hasAtLeastOne) {
    Write-Host "  ✓ ALL SYSTEMS READY!" -ForegroundColor Green
    Write-Host "`nNext: Launch Kiro IDE and start chatting!" -ForegroundColor White
} elseif ($hasAtLeastOne) {
    Write-Host "  ⚠ MOSTLY READY" -ForegroundColor Yellow
    Write-Host "`nFix issues marked with ✗" -ForegroundColor White
} else {
    Write-Host "  ✗ SETUP REQUIRED" -ForegroundColor Red
    Write-Host "`nSet at least one API key to continue" -ForegroundColor White
    Write-Host "See: KIRO_API_KEYS_SETUP.md" -ForegroundColor Cyan
}
Write-Host "======================================`n" -ForegroundColor Cyan
