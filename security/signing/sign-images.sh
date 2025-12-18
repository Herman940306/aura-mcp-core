#!/bin/bash
# =============================================================================
# Aura IA Container Image Signing Script
# Signs container images using Cosign (Sigstore)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Configuration
REGISTRY="${AURA_IA_REGISTRY:-ghcr.io/aura-ia}"
KEY_PATH="${COSIGN_KEY_PATH:-${PROJECT_ROOT}/security/signing/cosign.key}"
CERT_PATH="${COSIGN_CERT_PATH:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# =============================================================================
# Check prerequisites
# =============================================================================
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v cosign &> /dev/null; then
        log_error "cosign not found. Install from: https://docs.sigstore.dev/cosign/installation"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "docker not found"
        exit 1
    fi

    log_info "Prerequisites OK (cosign $(cosign version 2>&1 | head -1))"
}

# =============================================================================
# Generate signing key pair (if not exists)
# =============================================================================
generate_keypair() {
    local key_dir=$(dirname "$KEY_PATH")
    mkdir -p "$key_dir"

    if [[ -f "$KEY_PATH" ]]; then
        log_info "Using existing signing key: $KEY_PATH"
        return
    fi

    log_step "Generating new signing key pair..."

    # For CI/CD, use COSIGN_PASSWORD env var
    if [[ -z "${COSIGN_PASSWORD:-}" ]]; then
        log_warn "COSIGN_PASSWORD not set. You will be prompted for a password."
    fi

    cosign generate-key-pair --output-key-prefix="${key_dir}/cosign"

    log_info "Key pair generated:"
    log_info "  Private: ${key_dir}/cosign.key"
    log_info "  Public:  ${key_dir}/cosign.pub"
}

# =============================================================================
# Sign a container image
# =============================================================================
sign_image() {
    local image="$1"
    local annotations="${2:-}"

    log_step "Signing image: $image"

    # Get image digest
    local digest=$(docker inspect --format='{{index .RepoDigests 0}}' "$image" 2>/dev/null || echo "")

    if [[ -z "$digest" ]]; then
        # Image might not be pushed yet, use local reference
        digest="$image"
        log_warn "Image not pushed to registry, signing local reference"
    fi

    # Sign with key
    if [[ -f "$KEY_PATH" ]]; then
        cosign sign \
            --key "$KEY_PATH" \
            --annotations "project=aura-ia" \
            --annotations "signed-by=aura-ia-ci" \
            --annotations "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            ${annotations:+--annotations "$annotations"} \
            "$digest"

        log_info "Image signed successfully: $image"
    else
        # Keyless signing (uses OIDC)
        log_info "Using keyless signing (Sigstore OIDC)"
        cosign sign \
            --annotations "project=aura-ia" \
            --annotations "signed-by=aura-ia-ci" \
            --annotations "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            ${annotations:+--annotations "$annotations"} \
            "$digest"
    fi
}

# =============================================================================
# Verify image signature
# =============================================================================
verify_image() {
    local image="$1"
    local pub_key="${KEY_PATH%.key}.pub"

    log_step "Verifying image signature: $image"

    if [[ -f "$pub_key" ]]; then
        cosign verify \
            --key "$pub_key" \
            "$image"
    else
        # Keyless verification
        cosign verify \
            --certificate-identity-regexp=".*" \
            --certificate-oidc-issuer-regexp=".*" \
            "$image"
    fi

    log_info "Signature verified successfully"
}

# =============================================================================
# Attach SBOM to image
# =============================================================================
attach_sbom() {
    local image="$1"
    local sbom_path="$2"

    if [[ ! -f "$sbom_path" ]]; then
        log_warn "SBOM not found: $sbom_path"
        return
    fi

    log_step "Attaching SBOM to image: $image"

    cosign attach sbom \
        --sbom "$sbom_path" \
        "$image"

    # Sign the SBOM attestation
    if [[ -f "$KEY_PATH" ]]; then
        cosign attest \
            --key "$KEY_PATH" \
            --predicate "$sbom_path" \
            --type spdxjson \
            "$image"
    fi

    log_info "SBOM attached and attested"
}

# =============================================================================
# Sign all Aura IA images
# =============================================================================
sign_all_images() {
    local tag="${1:-latest}"

    local images=(
        "${REGISTRY}/gateway:${tag}"
        "${REGISTRY}/ml-backend:${tag}"
        "${REGISTRY}/dashboard:${tag}"
    )

    for image in "${images[@]}"; do
        if docker image inspect "$image" &> /dev/null; then
            sign_image "$image"

            # Attach SBOM if available
            local safe_name=$(echo "$image" | tr '/:' '-')
            local sbom_path="${PROJECT_ROOT}/SBOM/${safe_name}.spdx.json"
            attach_sbom "$image" "$sbom_path"
        else
            log_warn "Image not found locally: $image"
        fi
    done
}

# =============================================================================
# Usage
# =============================================================================
usage() {
    echo "Aura IA Container Image Signing"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  generate-key       Generate a new signing key pair"
    echo "  sign <image>       Sign a specific image"
    echo "  sign-all [tag]     Sign all Aura IA images (default: latest)"
    echo "  verify <image>     Verify an image signature"
    echo "  attach-sbom <image> <sbom>  Attach SBOM to image"
    echo ""
    echo "Environment Variables:"
    echo "  AURA_IA_REGISTRY   Container registry (default: ghcr.io/aura-ia)"
    echo "  COSIGN_KEY_PATH    Path to signing key"
    echo "  COSIGN_PASSWORD    Password for signing key"
    echo ""
}

# =============================================================================
# Main
# =============================================================================
main() {
    local command="${1:-}"

    case "$command" in
        generate-key)
            check_prerequisites
            generate_keypair
            ;;
        sign)
            check_prerequisites
            [[ -z "${2:-}" ]] && { log_error "Image required"; usage; exit 1; }
            sign_image "$2"
            ;;
        sign-all)
            check_prerequisites
            sign_all_images "${2:-latest}"
            ;;
        verify)
            check_prerequisites
            [[ -z "${2:-}" ]] && { log_error "Image required"; usage; exit 1; }
            verify_image "$2"
            ;;
        attach-sbom)
            check_prerequisites
            [[ -z "${2:-}" || -z "${3:-}" ]] && { log_error "Image and SBOM path required"; usage; exit 1; }
            attach_sbom "$2" "$3"
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
