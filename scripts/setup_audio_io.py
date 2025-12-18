#!/usr/bin/env python3
"""
Audio I/O Setup Script for Aura IA MCP.

ENTERPRISE DEPLOYMENT SCRIPT

This script:
1. Verifies Python package requirements (vosk, TTS)
2. Downloads Vosk STT model if needed
3. Downloads/initializes Coqui TTS model if needed
4. Runs verification tests
5. Reports deployment readiness

Usage:
    python scripts/setup_audio_io.py           # Full setup
    python scripts/setup_audio_io.py --check   # Verify only, no download
    python scripts/setup_audio_io.py --test    # Run tests after setup
"""

import argparse
import asyncio
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

# Configuration
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"

PROJECT_ROOT = Path(__file__).parent.parent
MODEL_DIR = PROJECT_ROOT / "model_artifacts"
VOSK_MODEL_PATH = MODEL_DIR / VOSK_MODEL_NAME


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_status(name: str, status: bool, message: str = ""):
    """Print a status line."""
    icon = "✅" if status else "❌"
    msg = f" - {message}" if message else ""
    print(f"  {icon} {name}{msg}")


def check_package(package: str) -> tuple[bool, str]:
    """Check if a Python package is installed."""
    try:
        if package == "vosk":
            import vosk

            return True, vosk.__file__
        elif package == "TTS":
            from TTS.api import TTS

            return True, "Coqui TTS available"
        else:
            __import__(package)
            return True, ""
    except ImportError as e:
        return False, str(e)


def download_progress(block_num, block_size, total_size):
    """Display download progress."""
    downloaded = block_num * block_size
    percent = min(100, (downloaded / total_size) * 100)
    bar_length = 40
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    mb_down = downloaded // (1024 * 1024)
    mb_total = total_size // (1024 * 1024)
    sys.stdout.write(f"\r  [{bar}] {percent:.1f}% ({mb_down}/{mb_total}MB)")
    sys.stdout.flush()


def download_vosk_model() -> bool:
    """Download and extract Vosk model."""
    print("\n📥 Downloading Vosk model...")
    print(f"   Model: {VOSK_MODEL_NAME}")
    print(f"   URL: {VOSK_MODEL_URL}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = MODEL_DIR / f"{VOSK_MODEL_NAME}.zip"

    try:
        urlretrieve(VOSK_MODEL_URL, zip_path, download_progress)
        print("\n")
    except Exception as e:
        print(f"\n   ❌ Download failed: {e}")
        return False

    print("   📦 Extracting model...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(MODEL_DIR)
        print(f"   ✅ Extracted to: {VOSK_MODEL_PATH}")
    except Exception as e:
        print(f"   ❌ Extraction failed: {e}")
        return False
    finally:
        if zip_path.exists():
            zip_path.unlink()

    return VOSK_MODEL_PATH.exists()


def initialize_coqui_tts() -> bool:
    """Initialize Coqui TTS (downloads models on first use)."""
    print("\n📥 Initializing Coqui TTS...")
    print("   Model: tts_models/en/ljspeech/glow-tts")
    print("   Vocoder: vocoder_models/en/ljspeech/hifigan_v2")
    print("   (First run downloads ~100MB)")

    try:
        from TTS.api import TTS

        # This will download models if not present
        tts = TTS(
            model_name="tts_models/en/ljspeech/glow-tts",
            vocoder_name="vocoder_models/en/ljspeech/hifigan_v2",
            progress_bar=True,
        )

        # Quick test
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tts.tts_to_file(text="Hello", file_path=tmp.name)
            if os.path.getsize(tmp.name) > 0:
                print("   ✅ Coqui TTS initialized and tested")
                return True

        return False

    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        return False


async def test_stt_service() -> bool:
    """Test STT service with real model."""
    print("\n🧪 Testing STT service...")

    try:
        from aura_ia_mcp.services.audio_io.stt_service import (
            VoskConfig,
            VoskSTTService,
        )

        config = VoskConfig(model_path=str(VOSK_MODEL_PATH))
        service = VoskSTTService(config)

        await service.initialize()

        # Test with silence
        audio_data = b"\x00\x00" * 16000  # 1 second of silence
        result = await service.transcribe(audio_data)

        await service.shutdown()

        print("   ✅ STT service working")
        print(f"      Latency: {result.processing_time_ms:.0f}ms")
        return True

    except Exception as e:
        print(f"   ❌ STT test failed: {e}")
        return False


async def test_tts_service() -> bool:
    """Test TTS service with real model."""
    print("\n🧪 Testing TTS service...")

    try:
        from aura_ia_mcp.services.audio_io.tts_service import (
            CoquiTTSConfig,
            CoquiTTSService,
        )

        config = CoquiTTSConfig()
        service = CoquiTTSService(config)

        await service.initialize()

        # Test synthesis
        audio_data, result = await service.synthesize("Hello world")

        await service.shutdown()

        rtf = result.processing_time_ms / 1000 / result.audio_duration_seconds

        print("   ✅ TTS service working")
        print(f"      Audio: {result.audio_duration_seconds:.2f}s")
        print(f"      RTF: {rtf:.2f}x (< 1.0 = faster than realtime)")
        return True

    except Exception as e:
        print(f"   ❌ TTS test failed: {e}")
        return False


def run_pytest() -> bool:
    """Run the test suite."""
    print("\n🧪 Running test suite...")

    test_file = PROJECT_ROOT / "tests" / "test_audio_io.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
        cwd=PROJECT_ROOT,
        check=False,
    )

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Setup Audio I/O for Aura IA MCP"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify only, no download",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run full test suite after setup",
    )
    args = parser.parse_args()

    print_header("Aura IA MCP - Audio I/O Setup")
    print(f"Project Root: {PROJECT_ROOT}")

    all_passed = True

    # =========================================================================
    # Check Python Packages
    # =========================================================================
    print_header("1. Checking Python Packages")

    vosk_ok, vosk_msg = check_package("vosk")
    print_status("vosk", vosk_ok, vosk_msg if not vosk_ok else "")

    tts_ok, tts_msg = check_package("TTS")
    print_status("TTS (Coqui)", tts_ok, tts_msg if not tts_ok else "")

    if not vosk_ok or not tts_ok:
        print("\n⚠️  Missing packages. Install with:")
        if not vosk_ok:
            print("   pip install vosk>=0.3.45")
        if not tts_ok:
            print("   pip install TTS>=0.22.0")

        if args.check:
            return 1
        all_passed = False

    # =========================================================================
    # Check/Download Vosk Model
    # =========================================================================
    print_header("2. Checking Vosk Model")

    vosk_model_ok = VOSK_MODEL_PATH.exists()
    print_status(
        f"Model: {VOSK_MODEL_NAME}",
        vosk_model_ok,
        str(VOSK_MODEL_PATH) if vosk_model_ok else "Not found",
    )

    if not vosk_model_ok:
        if args.check:
            print("\n⚠️  Vosk model not downloaded")
            all_passed = False
        elif vosk_ok:
            if download_vosk_model():
                vosk_model_ok = True
            else:
                all_passed = False
        else:
            print("   ⚠️  Install vosk package first")
            all_passed = False

    # =========================================================================
    # Check/Initialize Coqui TTS
    # =========================================================================
    print_header("3. Checking Coqui TTS Models")

    if tts_ok:
        if args.check:
            print_status("Coqui TTS", True, "Package installed")
        elif initialize_coqui_tts():
            print_status("Coqui TTS", True, "Initialized")
        else:
            all_passed = False
    else:
        print_status("Coqui TTS", False, "Package not installed")
        all_passed = False

    # =========================================================================
    # Service Tests
    # =========================================================================
    if vosk_ok and vosk_model_ok and tts_ok and not args.check:
        print_header("4. Service Integration Tests")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            stt_ok = loop.run_until_complete(test_stt_service())
            tts_svc_ok = loop.run_until_complete(test_tts_service())
            all_passed = all_passed and stt_ok and tts_svc_ok
        finally:
            loop.close()

    # =========================================================================
    # Run Full Test Suite
    # =========================================================================
    if args.test:
        print_header("5. Full Test Suite")
        if run_pytest():
            print_status("Test Suite", True, "All tests passed")
        else:
            print_status("Test Suite", False, "Some tests failed")
            all_passed = False

    # =========================================================================
    # Summary
    # =========================================================================
    print_header("Setup Summary")

    if all_passed:
        print("✅ Audio I/O is ready for enterprise deployment!")
        print("\nEndpoints will be available at:")
        print("  - POST /api/stt/transcribe  (Speech-to-Text)")
        print("  - POST /api/tts/synthesize  (Text-to-Speech)")
        print("  - GET  /api/stt/status")
        print("  - GET  /api/tts/status")
        return 0
    else:
        print("❌ Setup incomplete. Please resolve issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
