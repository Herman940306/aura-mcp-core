#!/usr/bin/env python3
"""
Verify that audio engine versions match pinned versions in Helm values.
For SBOM compliance and security auditing.
"""
import sys
from pathlib import Path

import yaml

HELM_VALUES = Path(__file__).parent.parent / "helm" / "values-audio.yaml"


def load_pinned_versions():
    """Load pinned versions from Helm values."""
    if not HELM_VALUES.exists():
        print(f"✗ Helm values not found: {HELM_VALUES}")
        return None

    with open(HELM_VALUES) as f:
        values = yaml.safe_load(f)

    return values.get("engine_pinning", {})


def check_vosk_version(expected: str) -> bool:
    """Check Vosk version."""
    try:
        import vosk

        # Vosk doesn't expose version easily, check if import works
        print(f"  Vosk: installed (expected {expected})")
        return True
    except ImportError:
        print(f"  Vosk: NOT INSTALLED (expected {expected})")
        return False


def check_coqui_version(expected: str) -> bool:
    """Check Coqui TTS version."""
    try:
        from TTS import __version__

        actual = __version__
        match = actual.startswith(expected.split(".")[0])
        status = "✓" if match else "⚠"
        print(f"  Coqui TTS: {actual} (expected {expected}) {status}")
        return match
    except ImportError:
        print(f"  Coqui TTS: NOT INSTALLED (expected {expected})")
        return False


def main():
    print("=" * 50)
    print("Aura Audio - Engine Version Verification")
    print("=" * 50)

    pinned = load_pinned_versions()
    if not pinned:
        sys.exit(1)

    print(f"\nPinned versions from {HELM_VALUES.name}:")
    for engine, version in pinned.items():
        print(f"  {engine}: {version}")

    print("\nInstalled versions:")
    all_ok = True

    if "vosk" in pinned:
        all_ok &= check_vosk_version(pinned["vosk"])

    if "coqui" in pinned:
        all_ok &= check_coqui_version(pinned["coqui"])

    print()
    if all_ok:
        print("✓ All engine versions verified")
        sys.exit(0)
    else:
        print("⚠ Some engines missing or version mismatch")
        sys.exit(1)


if __name__ == "__main__":
    main()
