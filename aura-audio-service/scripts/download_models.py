#!/usr/bin/env python3
"""
Download Vosk model for Aura Audio Service.
Run this before starting the audio service.
"""
import sys
import urllib.request
import zipfile
from pathlib import Path

# Model configuration
VOSK_MODEL_URL = (
    "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
)
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
MODELS_DIR = Path(__file__).parent.parent / "models" / "vosk"


def download_vosk_model():
    """Download and extract Vosk model."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / VOSK_MODEL_NAME
    if model_path.exists():
        print(f"✓ Vosk model already exists: {model_path}")
        return True

    zip_path = MODELS_DIR / f"{VOSK_MODEL_NAME}.zip"

    print("Downloading Vosk model (~40MB)...")
    print(f"  URL: {VOSK_MODEL_URL}")
    print(f"  Destination: {zip_path}")

    try:
        # Download with progress
        def report_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = (
                min(100, downloaded * 100 / total_size)
                if total_size > 0
                else 0
            )
            sys.stdout.write(
                f"\r  Progress: {percent:.1f}% ({downloaded // 1024 // 1024}MB)"
            )
            sys.stdout.flush()

        urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path, report_progress)
        print()  # newline after progress

    except Exception as e:
        print(f"\n✗ Download failed: {e}")
        return False

    print("Extracting model...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(MODELS_DIR)
        print(f"✓ Model extracted to: {model_path}")

        # Clean up zip
        zip_path.unlink()
        print("✓ Cleaned up zip file")

    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        return False

    return True


def verify_model():
    """Verify model files exist."""
    model_path = MODELS_DIR / VOSK_MODEL_NAME
    required_files = [
        "am/final.mdl",
        "conf/mfcc.conf",
        "graph/phones/word_boundary.int",
    ]

    for f in required_files:
        if not (model_path / f).exists():
            print(f"✗ Missing model file: {f}")
            return False

    print("✓ Model verification passed")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("Aura Audio Service - Vosk Model Setup")
    print("=" * 50)

    if download_vosk_model() and verify_model():
        print()
        print("✓ Setup complete! You can now run:")
        print("  docker-compose up --build")
        sys.exit(0)
    else:
        print()
        print("✗ Setup failed. Check errors above.")
        sys.exit(1)
