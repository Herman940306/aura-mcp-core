import json
import sys

# Placeholder SBOM generator; integrate cyclonedx lib later


def main(out_path: str):
    sbom = {"name": "aura-ia-mcp", "version": "0.0.1", "components": []}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sbom, f)
    print(f"Wrote SBOM to {out_path}")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "SBOM/sbom.json"
    main(target)
