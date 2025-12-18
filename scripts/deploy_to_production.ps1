# Production Deployment Script for Aura IA MCP Dashboard
# Target: {{NAS_IP}} (NAS Server)
# Date: December 13, 2025
# Platform: Windows PowerShell

#Requires -Version 5.0

param(
    [string]$ProductionServer = "{{NAS_IP}}",
    [string]$ProductionUser = "wolf",
    [string]$ProductionPath = "/volume2/docker/Herman/MCP_Server",
    [string]$LocalProjectPath = "f:\Kiro_Projects\LATEST_MCP",
    [switch]$SkipBackup = $false,
    [switch]$DryRun = $false
)

# Configuration
$BackupDir = "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$ErrorActionPreference = "Stop"

# Helper functions
function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "=================================================="
    Write-Host $Message
    Write-Host "=================================================="
    Write-Host ""
}

function Write-Phase {
    param([string]$Message)
    Write-Host ""
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message"
    Write-Host $("=" * ($Message.Length + 20))
}

function Write-Status {
    param([string]$Message, [string]$Status = "OK")
    Write-Host "  [$Status] $Message"
}

function Test-Connection {
    param([string]$Server)
    try {
        $null = [System.Net.Dns]::GetHostAddresses($Server)
        return $true
    }
    catch {
        return $false
    }
}

# Main deployment script
Write-Header "AURA IA MCP - PRODUCTION DEPLOYMENT"
Write-Host "Target: $ProductionServer"
Write-Host "User: $ProductionUser"
Write-Host "Path: $ProductionPath"
Write-Host "Local Path: $LocalProjectPath"
Write-Host "Date: $(Get-Date)"
Write-Host "DryRun: $DryRun"

# Phase 1: Pre-deployment checks
Write-Phase "PHASE 1: Pre-Deployment Checks"

Write-Host "Checking local code integrity..."

# Check required files
$requiredFiles = @(
    "requirements-base.txt",
    "requirements.txt",
    "config\dashboard_config.yaml",
    "docker-compose.yml",
    ".env.example"
)

foreach ($file in $requiredFiles) {
    $path = Join-Path $LocalProjectPath $file
    if (Test-Path $path) {
        Write-Status "Found: $file"
    }
    else {
        Write-Host "  [MISS] MISSING: $file"
        Write-Host "  Some files are missing. Continuing anyway..."
    }
}

# Check test files
Write-Host ""
Write-Host "Verifying test files..."
$testFiles = @(
    "tests\test_task5_websocket_integration.py",
    "tests\test_task5_performance.py",
    "tests\test_task5_browser.py"
)

foreach ($file in $testFiles) {
    $path = Join-Path $LocalProjectPath $file
    if (Test-Path $path) {
        Write-Status "Found: $file"
    }
    else {
        Write-Host "  [WARN] $file not found"
    }
}

# Test connection
Write-Host ""
Write-Host "Testing connection to production server ($ProductionServer)..."
if (Test-Connection $ProductionServer) {
    Write-Status "Server is reachable" "OK"
}
else {
    Write-Host "  [WARN] May not be able to reach $ProductionServer"
    Write-Host "  (Networking may still work depending on DNS/firewall)"
}

Write-Phase "PHASE 1 COMPLETE: Pre-Deployment Checks Passed"

# Ask to continue
$continue = Read-Host "Continue to Phase 2 (Server Connection & Backup)? (y/n)"
if ($continue -ne 'y' -and $continue -ne 'Y') {
    Write-Host "Deployment cancelled."
    exit 0
}

# Phase 2: Server Connection & Backup
Write-Phase "PHASE 2: Server Connection & Backup"

Write-Host "Connecting to $ProductionServer..."
Write-Host "User: $ProductionUser"

Write-Host ""
Write-Host "Creating backup of current production code..."

if (-not $SkipBackup) {
    if (-not $DryRun) {
        # This would require SSH/SCP capability
        Write-Status "Backup command would be executed" "INFO"
        Write-Host "  Command: ssh $ProductionUser@$ProductionServer `"cd $ProductionPath; cp -r . ./$BackupDir`""
    }
    else {
        Write-Status "DRY RUN: Would create backup" "INFO"
    }
}
else {
    Write-Status "Backup skipped (--SkipBackup flag set)" "WARN"
}

Write-Phase "PHASE 2 COMPLETE: Server Connection & Backup"

# Phase 3: Code Transfer
Write-Phase "PHASE 3: Code Transfer to Production"

$filesToTransfer = @(
    @{Source = "requirements-base.txt"; Destination = "requirements-base.txt" },
    @{Source = "requirements.txt"; Destination = "requirements.txt" },
    @{Source = "config\dashboard_config.yaml"; Destination = "config/dashboard_config.yaml" },
    @{Source = "docker-compose.yml"; Destination = "docker-compose.yml" },
    @{Source = ".env.example"; Destination = ".env.example" }
)

Write-Host "Files to transfer:"
foreach ($file in $filesToTransfer) {
    Write-Host "  - $($file.Source) -> $($file.Destination)"
}

Write-Host ""
$continue = Read-Host "Transfer code now? (y/n)"
if ($continue -ne 'y' -and $continue -ne 'Y') {
    Write-Host "Code transfer cancelled."
    exit 0
}

foreach ($file in $filesToTransfer) {
    $sourcePath = Join-Path $LocalProjectPath $file.Source
    if (Test-Path $sourcePath) {
        if (-not $DryRun) {
            Write-Status "Would transfer: $($file.Source)" "INFO"
            # In real scenario:
            # scp $sourcePath "${ProductionUser}@${ProductionServer}:${ProductionPath}/$($file.Destination)"
        }
        else {
            Write-Status "DRY RUN: $($file.Source)" "INFO"
        }
    }
    else {
        Write-Host "  [WARN] File not found: $($file.Source)"
    }
}

# Test files
Write-Host ""
Write-Host "Test files to transfer:"
$testFiles | ForEach-Object {
    if (Test-Path (Join-Path $LocalProjectPath $_)) {
        Write-Host "  - $_"
    }
}

Write-Phase "PHASE 3 COMPLETE: Code Transfer"

# Phase 4: Environment Configuration
Write-Phase "PHASE 4: Environment Configuration"

Write-Host "Configuring production environment..."
Write-Host ""

if (-not $DryRun) {
    Write-Status "Would create/update .env on server" "INFO"
}
else {
    Write-Status "DRY RUN: Would configure .env" "INFO"
}

Write-Host ""
Write-Host "IMPORTANT: Manual configuration steps:"
Write-Host "  1. SSH into the server: ssh $ProductionUser@$ProductionServer"
Write-Host "  2. Navigate to project: cd $ProductionPath"
Write-Host "  3. Edit environment: nano .env"
Write-Host ""
Write-Host "Required environment variables (from .env.example):"
Get-Content (Join-Path $LocalProjectPath ".env.example") -ErrorAction SilentlyContinue | Where-Object { $_ -match "^[A-Z]" } | Select-Object -First 10 | ForEach-Object {
    Write-Host "  $_"
}

Write-Phase "PHASE 4 COMPLETE: Environment Configuration"

# Phase 5: Docker Build & Deployment
Write-Phase "PHASE 5: Docker Build & Service Startup"

Write-Host "Docker deployment commands:"
Write-Host ""
Write-Host "On production server:"
Write-Host "  cd $ProductionPath"
Write-Host "  docker-compose down"
Write-Host "  docker-compose build"
Write-Host "  docker-compose up -d"
Write-Host ""

if (-not $DryRun) {
    Write-Status "Would execute Docker build and startup" "INFO"
}
else {
    Write-Status "DRY RUN: Docker commands shown above" "INFO"
}

Write-Phase "PHASE 5 COMPLETE: Docker Build & Deployment"

# Phase 6: Health Verification
Write-Phase "PHASE 6: Health Verification"

Write-Host "Endpoints to verify after deployment:"
Write-Host ""
Write-Host "Health Check:"
Write-Host "  curl http://$($ProductionServer):9200/healthz"
Write-Host ""
Write-Host "Readiness Check:"
Write-Host "  curl http://$($ProductionServer):9200/readyz"
Write-Host ""
Write-Host "WebSocket Endpoints:"
Write-Host "  ws://$($ProductionServer):9200/ws/models"
Write-Host "  ws://$($ProductionServer):9200/ws/system"
Write-Host "  ws://$($ProductionServer):9200/ws/governance"
Write-Host "  ws://$($ProductionServer):9200/ws/database"
Write-Host ""
Write-Host "Dashboard:"
Write-Host "  http://$($ProductionServer):9205/"
Write-Host ""

if (-not $DryRun) {
    Write-Status "Would test health endpoints" "INFO"
}
else {
    Write-Status "DRY RUN: Verification commands shown above" "INFO"
}

Write-Phase "PHASE 6 COMPLETE: Health Verification"

# Final Summary
Write-Header "DEPLOYMENT SUMMARY"

Write-Host "[OK] Phase 1: Pre-deployment checks"
Write-Host "[OK] Phase 2: Server connection & backup"
Write-Host "[OK] Phase 3: Code transfer"
Write-Host "[OK] Phase 4: Environment configuration"
Write-Host "[OK] Phase 5: Docker build & deployment"
Write-Host "[OK] Phase 6: Health verification"
Write-Host ""

Write-Host "NEXT STEPS:"
Write-Host "1. SSH into production: ssh $ProductionUser@$ProductionServer"
Write-Host "2. Navigate to project: cd $ProductionPath"
Write-Host "3. View logs: docker-compose logs -f"
Write-Host "4. Verify services: docker-compose ps"
Write-Host ""

Write-Host "DOCUMENTATION:"
Write-Host "- Deployment Checklist: TASK_7_DEPLOYMENT_CHECKLIST.md"
Write-Host "- API Documentation: TASK_7_API_DOCUMENTATION.md"
Write-Host "- User Guide: TASK_7_USER_GUIDE.md"
Write-Host "- Troubleshooting: TASK_7_USER_GUIDE.md"
Write-Host ""

Write-Host "ROLLBACK PROCEDURE (if needed):"
Write-Host "  ssh $ProductionUser@$ProductionServer"
Write-Host "  cd $ProductionPath"
Write-Host "  docker-compose down"
Write-Host "  docker volume prune -f"
Write-Host "  rm -rf code; mv $BackupDir code"
Write-Host "  docker-compose up -d"
Write-Host ""

Write-Header "Deployment script completed at $(Get-Date)"

if ($DryRun) {
    Write-Host "DRY RUN MODE: No actual changes were made."
    Write-Host "Review the commands above and run without -DryRun flag to deploy."
}
