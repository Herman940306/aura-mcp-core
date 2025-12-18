#!/usr/bin/env bash
# =============================================================================
# Aura IA V.1.9.8 - Regression Test Suite Runner
# =============================================================================
# This script runs the complete regression test suite for Aura IA.
# It includes unit tests, integration tests, and governance tests.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_DIR="$PROJECT_ROOT/tests"
REPORT_DIR="$PROJECT_ROOT/test-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Default options
RUN_UNIT=true
RUN_INTEGRATION=true
RUN_GOVERNANCE=true
RUN_E2E=false
PARALLEL=true
COVERAGE=true
VERBOSE=false
FAIL_FAST=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit-only)
            RUN_UNIT=true
            RUN_INTEGRATION=false
            RUN_GOVERNANCE=false
            shift
            ;;
        --integration-only)
            RUN_UNIT=false
            RUN_INTEGRATION=true
            RUN_GOVERNANCE=false
            shift
            ;;
        --governance-only)
            RUN_UNIT=false
            RUN_INTEGRATION=false
            RUN_GOVERNANCE=true
            shift
            ;;
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --no-parallel)
            PARALLEL=false
            shift
            ;;
        --no-coverage)
            COVERAGE=false
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --fail-fast|-x)
            FAIL_FAST=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --unit-only        Run only unit tests"
            echo "  --integration-only Run only integration tests"
            echo "  --governance-only  Run only governance tests"
            echo "  --e2e              Include E2E tests"
            echo "  --no-parallel      Disable parallel execution"
            echo "  --no-coverage      Disable coverage reporting"
            echo "  --verbose, -v      Verbose output"
            echo "  --fail-fast, -x    Stop on first failure"
            echo "  --help, -h         Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Functions
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_dependencies() {
    print_header "Checking Dependencies"
    
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed"
        exit 1
    fi
    print_success "Python found: $(python --version)"
    
    if ! python -c "import pytest" &> /dev/null; then
        print_warning "pytest not found, installing..."
        pip install pytest pytest-cov pytest-asyncio httpx
    fi
    print_success "pytest found"
    
    if $COVERAGE; then
        if ! python -c "import pytest_cov" &> /dev/null; then
            print_warning "pytest-cov not found, installing..."
            pip install pytest-cov
        fi
        print_success "pytest-cov found"
    fi
}

create_report_dir() {
    mkdir -p "$REPORT_DIR"
    mkdir -p "$REPORT_DIR/html"
    mkdir -p "$REPORT_DIR/junit"
}

build_pytest_args() {
    local args=()
    
    if $VERBOSE; then
        args+=("-v")
    fi
    
    if $FAIL_FAST; then
        args+=("-x")
    fi
    
    if $PARALLEL; then
        if python -c "import pytest_xdist" &> /dev/null; then
            args+=("-n" "auto")
        fi
    fi
    
    if $COVERAGE; then
        args+=("--cov=aura_ia_mcp")
        args+=("--cov-report=html:$REPORT_DIR/html")
        args+=("--cov-report=xml:$REPORT_DIR/coverage.xml")
        args+=("--cov-report=term-missing")
    fi
    
    args+=("--tb=short")
    args+=("--durations=10")
    args+=("--junit-xml=$REPORT_DIR/junit/results_$TIMESTAMP.xml")
    
    echo "${args[@]}"
}

run_unit_tests() {
    if $RUN_UNIT; then
        print_header "Running Unit Tests (151+ tests)"
        
        local args=$(build_pytest_args)
        
        if python -m pytest $TEST_DIR/test_unit_comprehensive.py $args; then
            print_success "Unit tests passed"
            return 0
        else
            print_error "Unit tests failed"
            return 1
        fi
    fi
}

run_integration_tests() {
    if $RUN_INTEGRATION; then
        print_header "Running Integration Tests (77+ tests)"
        
        local args=$(build_pytest_args)
        
        # Check if services are running
        if ! curl -sf http://localhost:9200/healthz &> /dev/null; then
            print_warning "Gateway service not running at :9200"
            print_warning "Some integration tests may be skipped"
        fi
        
        if python -m pytest $TEST_DIR/test_integration_enterprise.py $args; then
            print_success "Integration tests passed"
            return 0
        else
            print_error "Integration tests failed"
            return 1
        fi
    fi
}

run_governance_tests() {
    if $RUN_GOVERNANCE; then
        print_header "Running Governance Tests (80+ tests)"
        
        local args=$(build_pytest_args)
        
        if python -m pytest $TEST_DIR/test_governance_compliance.py $args; then
            print_success "Governance tests passed"
            return 0
        else
            print_error "Governance tests failed"
            return 1
        fi
    fi
}

run_e2e_tests() {
    if $RUN_E2E; then
        print_header "Running E2E Tests"
        
        # Check if Playwright is installed
        if ! python -c "from playwright.sync_api import sync_playwright" &> /dev/null; then
            print_warning "Playwright not installed, skipping E2E tests"
            return 0
        fi
        
        local args=$(build_pytest_args)
        
        if python -m pytest $TEST_DIR/test_e2e_*.py $args --browser chromium; then
            print_success "E2E tests passed"
            return 0
        else
            print_error "E2E tests failed"
            return 1
        fi
    fi
}

generate_summary() {
    print_header "Test Summary"
    
    if [ -f "$REPORT_DIR/junit/results_$TIMESTAMP.xml" ]; then
        # Parse JUnit XML for summary
        local tests=$(grep -o 'tests="[0-9]*"' "$REPORT_DIR/junit/results_$TIMESTAMP.xml" | head -1 | grep -o '[0-9]*')
        local failures=$(grep -o 'failures="[0-9]*"' "$REPORT_DIR/junit/results_$TIMESTAMP.xml" | head -1 | grep -o '[0-9]*')
        local errors=$(grep -o 'errors="[0-9]*"' "$REPORT_DIR/junit/results_$TIMESTAMP.xml" | head -1 | grep -o '[0-9]*')
        
        echo "Total Tests: $tests"
        echo "Failures: $failures"
        echo "Errors: $errors"
        
        if [ "$failures" = "0" ] && [ "$errors" = "0" ]; then
            print_success "All tests passed!"
        else
            print_error "Some tests failed"
        fi
    fi
    
    if $COVERAGE; then
        echo ""
        echo "Coverage Report: $REPORT_DIR/html/index.html"
    fi
    
    echo "JUnit Report: $REPORT_DIR/junit/results_$TIMESTAMP.xml"
}

# Main execution
main() {
    print_header "Aura IA V.1.9.8 - Regression Test Suite"
    echo "Timestamp: $TIMESTAMP"
    echo "Project Root: $PROJECT_ROOT"
    echo ""
    
    check_dependencies
    create_report_dir
    
    local exit_code=0
    
    run_unit_tests || exit_code=1
    run_integration_tests || exit_code=1
    run_governance_tests || exit_code=1
    run_e2e_tests || exit_code=1
    
    generate_summary
    
    if [ $exit_code -eq 0 ]; then
        print_header "✅ Regression Test Suite PASSED"
    else
        print_header "❌ Regression Test Suite FAILED"
    fi
    
    exit $exit_code
}

# Run main function
cd "$PROJECT_ROOT"
main
