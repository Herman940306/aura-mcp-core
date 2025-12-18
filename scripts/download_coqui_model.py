#!/usr/bin/env python3
"""
Download/Initialize Coqui TTS Model for Aura IA MCP.

Initializes Coqui TTS with Glow-TTS + HiFi-GAN vocoder.
This is the recommended setup for:
- Near-human quality (MOS 4.2-4.4)
- 30x faster than Tacotron2
- Real-time inference on CPU

Usage:
    python scripts/download_coqui_model.py
"""

import os
import sys
from pathlib import Path

# Model configuration
MODEL_NAME = "tts_models/en/ljspeech/glow-tts"
VOCODER_NAME = "vocoder_models/en/ljspeech/hifigan_v2"


def main():
    print("=" * 60)
    print("Coqui TTS Model Initializer for Aura IA MCP")
    print("=" * 60)
    print(f"\nTTS Model: {MODEL_NAME}")
    print(f"Vocoder: {VOCODER_NAME}")

    # Check if TTS is installed
    try:
        from TTS.api import TTS

        print("\n✅ Coqui TTS package is installed")
    except ImportError:
        print("\n❌ Coqui TTS not installed. Run:")
        print("   pip install TTS")
        return 1

    # List available models
    print("\n📋 Available TTS models:")
    try:
        models = TTS.list_models()
        en_models = [m for m in models if "/en/" in m][:10]
        for m in en_models:
            marker = " 👈" if m == MODEL_NAME else ""
            print(f"   - {m}{marker}")
        print(f"   ... and {len(models) - 10} more")
    except Exception as e:
        print(f"   (Could not list models: {e})")

    # Initialize model (this downloads if needed)
    print("\n📥 Initializing TTS model...")
    print("   (First run will download ~100MB of models)")

    try:
        tts = TTS(
            model_name=MODEL_NAME,
            vocoder_name=VOCODER_NAME,
            progress_bar=True,
        )
        print("\n✅ TTS model loaded successfully!")
    except Exception as e:
        print(f"\n❌ Model initialization failed: {e}")
        return 1

    # Test synthesis
    print("\n🔊 Testing speech synthesis...")
    test_text = "Hello, I am Aura, your intelligent assistant."

    try:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        tts.tts_to_file(text=test_text, file_path=tmp_path)

        # Check output
        file_size = os.path.getsize(tmp_path)
        print("✅ Test synthesis successful!")
        print(f"   Text: '{test_text}'")
        print(f"   Output: {tmp_path}")
        print(f"   Size: {file_size / 1024:.1f} KB")

        # Get duration
        try:
            import wave

            with wave.open(tmp_path, "rb") as wf:
                duration = wf.getnframes() / wf.getframerate()
                print(f"   Duration: {duration:.2f} seconds")
        except:
            pass

        # Cleanup
        os.unlink(tmp_path)

    except Exception as e:
        print(f"❌ Test synthesis failed: {e}")
        return 1

    # Show model location
    print("\n📁 Model cache location:")
    cache_dir = Path.home() / ".local" / "share" / "tts"
    if cache_dir.exists():
        print(f"   {cache_dir}")
        total_size = sum(
            f.stat().st_size for f in cache_dir.rglob("*") if f.is_file()
        )
        print(f"   Total size: {total_size / (1024*1024):.1f} MB")
    else:
        # Try Windows location
        cache_dir = Path.home() / "AppData" / "Local" / "tts"
        if cache_dir.exists():
            print(f"   {cache_dir}")

    print("\n" + "=" * 60)
    print("✅ Coqui TTS is ready for Aura IA MCP!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
