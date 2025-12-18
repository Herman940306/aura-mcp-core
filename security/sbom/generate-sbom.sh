#!/bin/bash
# =============================================================================
# Aura IA SBOM Generation Script
# Generates Software Bill of Materials using Syft
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
OUTPUT_DIR="${PROJECT_ROOT}/SBOM"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Check prerequisites
# =============================================================================
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v syft &> /dev/null; then
        log_error "syft not found. Install from: https://github.com/anchore/syft"
        log_info "Quick install: curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin"
        exit 1
    fi

    if ! command -v grype &> /dev/null; then
        log_warn "grype not found. Vulnerability scanning will be skipped."
        log_info "Install from: https://github.com/anchore/grype"
    fi

    log_info "Prerequisites OK"
}

# =============================================================================
# Generate SBOM for Python dependencies
# =============================================================================
generate_python_sbom() {
    log_info "Generating SBOM for Python dependencies..."

    syft dir:"${PROJECT_ROOT}" \
        --output spdx-json="${OUTPUT_DIR}/aura-ia-python-${TIMESTAMP}.spdx.json" \
        --output cyclonedx-json="${OUTPUT_DIR}/aura-ia-python-${TIMESTAMP}.cyclonedx.json" \
        --output table="${OUTPUT_DIR}/aura-ia-python-${TIMESTAMP}.txt" \
        --catalogers python

    log_info "Python SBOM generated"
}

# =============================================================================
# Generate SBOM for Docker images
# =============================================================================
generate_docker_sbom() {
    local images=(
        "aura-ia/gateway:latest"
        "aura-ia/ml-backend:latest"
        "aura-ia/dashboard:latest"
        "qdrant/qdrant:v1.11.3"
    )

    for image in "${images[@]}"; do
        local safe_name=$(echo "$image" | tr '/:' '-')
        log_info "Generating SBOM for Docker image: $image"

        # Check if image exists locally
        if docker image inspect "$image" &> /dev/null; then
            syft image:"$image" \
                --output spdx-json="${OUTPUT_DIR}/${safe_name}-${TIMESTAMP}.spdx.json" \
                --output cyclonedx-json="${OUTPUT_DIR}/${safe_name}-${TIMESTAMP}.cyclonedx.json"
            log_info "SBOM generated for $image"
        else
            log_warn "Image $image not found locally, skipping"
        fi
    done
}

# =============================================================================
# Scan for vulnerabilities with Grype
# =============================================================================
scan_vulnerabilities() {
    if ! command -v grype &> /dev/null; then
        log_warn "Skipping vulnerability scan (grype not installed)"
        return
    fi

    log_info "Scanning for vulnerabilities..."

    # Scan Python dependencies
    grype dir:"${PROJECT_ROOT}" \
        --output table \
        --fail-on critical \
        > "${OUTPUT_DIR}/vulnerabilities-${TIMESTAMP}.txt" 2>&1 || true

    # Generate JSON report
    grype dir:"${PROJECT_ROOT}" \
        --output json \
        > "${OUTPUT_DIR}/vulnerabilities-${TIMESTAMP}.json" 2>&1 || true

    log_info "Vulnerability scan complete"
}

# =============================================================================
# Generate attestation metadata
# =============================================================================
generate_attestation() {
    log_info "Generating attestation metadata..."

    cat > "${OUTPUT_DIR}/attestation-${TIMESTAMP}.json" << EOF
{
    "version": "1.0",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "project": "aura-ia-mcp",
    "generator": {
        "tool": "syft",
        "version": "$(syft version 2>/dev/null | head -1 || echo 'unknown')"
    },
    "artifacts": {
        "python_sbom": "aura-ia-python-${TIMESTAMP}.spdx.json",
        "vulnerabilities": "vulnerabilities-${TIMESTAMP}.json"
    },
    "environment": {
        "hostname": "$(hostname)",
        "user": "$(whoami)",
        "os": "$(uname -s)",
        "arch": "$(uname -m)"
    }
}
EOF

    log_info "Attestation generated"
}

# =============================================================================
# Main execution
# =============================================================================
main() {
    log_info "=========================================="
    log_info "Aura IA SBOM Generation"
    log_info "=========================================="

    mkdir -p "$OUTPUT_DIR"

    check_prerequisites
    generate_python_sbom
    generate_docker_sbom
    scan_vulnerabilities
    generate_attestation

    log_info "=========================================="
    log_info "SBOM generation complete!"
    log_info "Output directory: ${OUTPUT_DIR}"
    log_info "=========================================="

    ls -la "$OUTPUT_DIR"/*.json 2>/dev/null || log_warn "No JSON files generated"
}

main "$@"
