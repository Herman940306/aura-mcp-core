#!/usr/bin/env python3
"""
Download Vosk STT Model for Aura IA MCP.

Downloads the vosk-model-small-en-us-0.15 model (~40MB).
This is the recommended model for:
- Fast inference (70-120ms latency)
- Low memory footprint (50-200MB)
- 94-95% WER on CommonVoice/LibriSpeech

Usage:
    python scripts/download_vosk_model.py
"""

import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

# Model configuration
MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODEL_DIR = Path(__file__).parent.parent / "model_artifacts"


def download_progress(block_num, block_size, total_size):
    """Display download progress."""
    downloaded = block_num * block_size
    percent = min(100, (downloaded / total_size) * 100)
    bar_length = 50
    filled = int(bar_length * percent / 100)
    bar = "=" * filled + "-" * (bar_length - filled)
    sys.stdout.write(
        f"\r[{bar}] {percent:.1f}% ({downloaded // (1024*1024)}MB)"
    )
    sys.stdout.flush()


def main():
    print("=" * 60)
    print("Vosk STT Model Downloader for Aura IA MCP")
    print("=" * 60)
    print(f"\nModel: {MODEL_NAME}")
    print(f"URL: {MODEL_URL}")

    # Create model directory
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / MODEL_NAME
    zip_path = MODEL_DIR / f"{MODEL_NAME}.zip"

    # Check if already downloaded
    if model_path.exists():
        print(f"\n✅ Model already exists at: {model_path}")
        print("   Delete the folder to re-download.")
        return 0

    # Download
    print("\n📥 Downloading model (~40MB)...")
    try:
        urlretrieve(MODEL_URL, zip_path, download_progress)
        print("\n")
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        return 1

    # Extract
    print("📦 Extracting model...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(MODEL_DIR)
        print(f"✅ Extracted to: {model_path}")
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        return 1
    finally:
        # Clean up zip
        if zip_path.exists():
            zip_path.unlink()
            print("🗑️  Cleaned up zip file")

    # Verify
    if model_path.exists():
        print("\n✅ Vosk model ready!")
        print(f"   Path: {model_path}")
        print(
            f"   Size: {sum(f.stat().st_size for f in model_path.rglob('*') if f.is_file()) / (1024*1024):.1f} MB"
        )

        # List contents
        print("\n📁 Model contents:")
        for item in sorted(model_path.iterdir()):
            if item.is_file():
                print(
                    f"   - {item.name} ({item.stat().st_size / 1024:.1f} KB)"
                )
            else:
                print(f"   - {item.name}/")

        return 0
    else:
        print("❌ Model not found after extraction")
        return 1


if __name__ == "__main__":
    sys.exit(main())
