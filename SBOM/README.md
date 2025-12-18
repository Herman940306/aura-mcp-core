# Software Bill of Materials (SBOM)

This directory contains SBOM artifacts generated for the Aura IA MCP project.

## Contents

- `sbom.json` - CycloneDX format SBOM
- `sbom.spdx.json` - SPDX format SBOM (optional)

## Generation

SBOMs are generated using [Syft](https://github.com/anchore/syft):

```bash
# Generate CycloneDX SBOM
syft . -o cyclonedx-json > SBOM/sbom.json

# Generate SPDX SBOM
syft . -o spdx-json > SBOM/sbom.spdx.json
```

## Verification

SBOMs should be regenerated on each release and verified against known CVE databases:

```bash
# Scan SBOM for vulnerabilities
grype sbom:SBOM/sbom.json
```

## CI Integration

The GitHub Actions workflow automatically generates and uploads SBOMs as release artifacts.

---
Last Updated: December 7, 2025
