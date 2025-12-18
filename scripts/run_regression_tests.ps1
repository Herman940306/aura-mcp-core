# =============================================================================
# Aura IA V.1.9.8 - Regression Test Suite Runner (PowerShell)
# =============================================================================
# This script runs the complete regression test suite for Aura IA on Windows.
# It includes unit tests, integration tests, and governance tests.
# =============================================================================

param(
    [switch]$UnitOnly,
    [switch]$IntegrationOnly,
    [switch]$GovernanceOnly,
    [switch]$E2E,
    [switch]$NoParallel,
    [switch]$NoCoverage,
    [switch]$Verbose,
    [switch]$FailFast,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$TestDir = Join-Path $ProjectRoot "tests"
$ReportDir = Join-Path $ProjectRoot "test-reports"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Colors
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) { Write-Output $args }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success { Write-Host "✅ $args" -ForegroundColor Green }
function Write-Warning { Write-Host "⚠️  $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "❌ $args" -ForegroundColor Red }
function Write-Header {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
    Write-Host "  $args" -ForegroundColor Blue
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
    Write-Host ""
}

# Help
if ($Help) {
    Write-Host "Aura IA V.1.9.8 - Regression Test Suite"
    Write-Host ""
    Write-Host "Usage: .\run_regression_tests.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -UnitOnly          Run only unit tests"
    Write-Host "  -IntegrationOnly   Run only integration tests"
    Write-Host "  -GovernanceOnly    Run only governance tests"
    Write-Host "  -E2E               Include E2E tests"
    Write-Host "  -NoParallel        Disable parallel execution"
    Write-Host "  -NoCoverage        Disable coverage reporting"
    Write-Host "  -Verbose           Verbose output"
    Write-Host "  -FailFast          Stop on first failure"
    Write-Host "  -Help              Show this help message"
    exit 0
}

# Determine which tests to run
$RunUnit = $true
$RunIntegration = $true
$RunGovernance = $true
$RunE2E = $E2E

if ($UnitOnly) {
    $RunUnit = $true
    $RunIntegration = $false
    $RunGovernance = $false
}
if ($IntegrationOnly) {
    $RunUnit = $false
    $RunIntegration = $true
    $RunGovernance = $false
}
if ($GovernanceOnly) {
    $RunUnit = $false
    $RunIntegration = $false
    $RunGovernance = $true
}

# Check dependencies
function Check-Dependencies {
    Write-Header "Checking Dependencies"
    
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python found: $pythonVersion"
    }
    catch {
        Write-Error "Python is not installed"
        exit 1
    }
    
    try {
        python -c "import pytest" 2>&1 | Out-Null
        Write-Success "pytest found"
    }
    catch {
        Write-Warning "pytest not found, installing..."
        pip install pytest pytest-cov pytest-asyncio httpx
    }
}

# Create report directory
function Create-ReportDir {
    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
    New-Item -ItemType Directory -Force -Path "$ReportDir\html" | Out-Null
    New-Item -ItemType Directory -Force -Path "$ReportDir\junit" | Out-Null
}

# Build pytest arguments
function Build-PytestArgs {
    $args = @()
    
    if ($Verbose) { $args += "-v" }
    if ($FailFast) { $args += "-x" }
    
    $args += "--tb=short"
    $args += "--durations=10"
    $args += "--junit-xml=$ReportDir\junit\results_$Timestamp.xml"
    
    if (-not $NoCoverage) {
        $args += "--cov=aura_ia_mcp"
        $args += "--cov-report=html:$ReportDir\html"
        $args += "--cov-report=xml:$ReportDir\coverage.xml"
        $args += "--cov-report=term-missing"
    }
    
    return $args
}

# Run unit tests
function Run-UnitTests {
    if (-not $RunUnit) { return $true }
    
    Write-Header "Running Unit Tests (151+ tests)"
    
    $args = Build-PytestArgs
    $testFile = Join-Path $TestDir "test_unit_comprehensive.py"
    
    $result = python -m pytest $testFile @args
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Unit tests passed"
        return $true
    }
    else {
        Write-Error "Unit tests failed"
        return $false
    }
}

# Run integration tests
function Run-IntegrationTests {
    if (-not $RunIntegration) { return $true }
    
    Write-Header "Running Integration Tests (77+ tests)"
    
    # Check if services are running
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9200/healthz" -Method Get -TimeoutSec 5 -ErrorAction SilentlyContinue
    }
    catch {
        Write-Warning "Gateway service not running at :9200"
        Write-Warning "Some integration tests may be skipped"
    }
    
    $args = Build-PytestArgs
    $testFile = Join-Path $TestDir "test_integration_enterprise.py"
    
    $result = python -m pytest $testFile @args
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Integration tests passed"
        return $true
    }
    else {
        Write-Error "Integration tests failed"
        return $false
    }
}

# Run governance tests
function Run-GovernanceTests {
    if (-not $RunGovernance) { return $true }
    
    Write-Header "Running Governance Tests (80+ tests)"
    
    $args = Build-PytestArgs
    $testFile = Join-Path $TestDir "test_governance_compliance.py"
    
    $result = python -m pytest $testFile @args
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Governance tests passed"
        return $true
    }
    else {
        Write-Error "Governance tests failed"
        return $false
    }
}

# Generate summary
function Generate-Summary {
    Write-Header "Test Summary"
    
    $junitFile = "$ReportDir\junit\results_$Timestamp.xml"
    if (Test-Path $junitFile) {
        [xml]$junitXml = Get-Content $junitFile
        $testsuite = $junitXml.testsuites.testsuite
        
        if ($testsuite) {
            Write-Host "Total Tests: $($testsuite.tests)"
            Write-Host "Failures: $($testsuite.failures)"
            Write-Host "Errors: $($testsuite.errors)"
            Write-Host "Duration: $($testsuite.time)s"
        }
    }
    
    if (-not $NoCoverage) {
        Write-Host ""
        Write-Host "Coverage Report: $ReportDir\html\index.html"
    }
    
    Write-Host "JUnit Report: $junitFile"
}

# Main execution
function Main {
    Write-Header "Aura IA V.1.9.8 - Regression Test Suite"
    Write-Host "Timestamp: $Timestamp"
    Write-Host "Project Root: $ProjectRoot"
    Write-Host ""
    
    Set-Location $ProjectRoot
    
    Check-Dependencies
    Create-ReportDir
    
    $exitCode = 0
    
    if (-not (Run-UnitTests)) { $exitCode = 1 }
    if (-not (Run-IntegrationTests)) { $exitCode = 1 }
    if (-not (Run-GovernanceTests)) { $exitCode = 1 }
    
    Generate-Summary
    
    if ($exitCode -eq 0) {
        Write-Header "✅ Regression Test Suite PASSED"
    }
    else {
        Write-Header "❌ Regression Test Suite FAILED"
    }
    
    exit $exitCode
}

# Run
Main
