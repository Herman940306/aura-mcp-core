#!/usr/bin/env python3
"""
Download Phi-4 Mini GGUF Model for Aura MCP Chat
================================================

This script downloads the Phi-4 Mini Instruct model in GGUF format (Q4_K_M quantization)
from Hugging Face for use with the embedded chat functionality.

Model: microsoft/Phi-4-mini-instruct (GGUF variant)
Quantization: Q4_K_M (~2.2GB, good balance of quality and speed)
Runtime: llama-cpp-python

Usage:
    python scripts/download_phi4_model.py
    python scripts/download_phi4_model.py --model-dir custom/path
    python scripts/download_phi4_model.py --force  # Re-download even if exists
"""

import argparse
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlretrieve

# Model configuration
MODEL_CONFIG = {
    "name": "Phi-4-mini-instruct-Q4_K_M",
    "filename": "phi-4-mini-instruct-q4_k_m.gguf",
    # Primary source: Bartowski's GGUF quantizations (high quality, trusted)
    "url": "https://huggingface.co/bartowski/Phi-4-mini-instruct-GGUF/resolve/main/Phi-4-mini-instruct-Q4_K_M.gguf",
    "size_bytes": 2_400_000_000,  # ~2.2GB approximate
    "description": "Microsoft Phi-4 Mini Instruct (3.8B params, Q4_K_M quantization)",
}

# Alternative models if Phi-4 Mini isn't available
ALTERNATIVE_MODELS = [
    {
        "name": "Phi-3-mini-4k-instruct-Q4_K_M",
        "filename": "phi-3-mini-4k-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf",
        "size_bytes": 2_200_000_000,
        "description": "Microsoft Phi-3 Mini 4K Instruct (3.8B params, Q4 quantization)",
    },
    {
        "name": "TinyLlama-1.1B-Chat-Q4_K_M",
        "filename": "tinyllama-1.1b-chat-q4_k_m.gguf",
        "url": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "size_bytes": 670_000_000,
        "description": "TinyLlama 1.1B Chat (smallest option, ~670MB)",
    },
]


def get_default_model_dir() -> Path:
    """Get the default model artifacts directory."""
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    return project_root / "model_artifacts"


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def download_progress(
    block_num: int, block_size: int, total_size: int
) -> None:
    """Display download progress."""
    downloaded = block_num * block_size
    if total_size > 0:
        percent = min(100, (downloaded / total_size) * 100)
        downloaded_str = format_size(downloaded)
        total_str = format_size(total_size)
        bar_width = 40
        filled = int(bar_width * percent / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(
            f"\r  [{bar}] {percent:5.1f}% ({downloaded_str} / {total_str})",
            end="",
            flush=True,
        )
    else:
        print(f"\r  Downloaded: {format_size(downloaded)}", end="", flush=True)


def verify_file_size(
    filepath: Path, expected_size: int, tolerance: float = 0.1
) -> bool:
    """Verify downloaded file size is within tolerance."""
    actual_size = filepath.stat().st_size
    min_size = expected_size * (1 - tolerance)
    max_size = expected_size * (1 + tolerance)
    return min_size <= actual_size <= max_size


def download_model(
    model_config: dict,
    model_dir: Path,
    force: bool = False,
) -> Path:
    """
    Download GGUF model from Hugging Face.

    Args:
        model_config: Model configuration dict with url, filename, etc.
        model_dir: Directory to save the model
        force: Force re-download even if file exists

    Returns:
        Path to the downloaded model file
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / model_config["filename"]

    # Check if already exists
    if model_path.exists() and not force:
        print(f"✓ Model already exists: {model_path}")
        actual_size = model_path.stat().st_size
        print(f"  Size: {format_size(actual_size)}")

        # Verify size
        if verify_file_size(model_path, model_config["size_bytes"]):
            print("  Size verification: OK")
            return model_path
        else:
            print("  ⚠ Size mismatch - file may be corrupted or incomplete")
            print("  Use --force to re-download")
            return model_path

    print(f"\n{'='*60}")
    print(f"Downloading: {model_config['name']}")
    print(f"{'='*60}")
    print(f"  Description: {model_config['description']}")
    print(f"  Expected size: {format_size(model_config['size_bytes'])}")
    print(f"  Destination: {model_path}")
    print(f"  URL: {model_config['url'][:80]}...")
    print()

    # Create temp file for download
    temp_path = model_path.with_suffix(".downloading")

    try:
        print("  Starting download (this may take a few minutes)...")
        urlretrieve(
            model_config["url"], temp_path, reporthook=download_progress
        )
        print()  # New line after progress bar

        # Rename to final path
        if model_path.exists():
            model_path.unlink()
        temp_path.rename(model_path)

        # Verify
        actual_size = model_path.stat().st_size
        print("\n✓ Download complete!")
        print(f"  Saved to: {model_path}")
        print(f"  Size: {format_size(actual_size)}")

        if verify_file_size(model_path, model_config["size_bytes"]):
            print("  Size verification: OK")
        else:
            print("  ⚠ Size differs from expected - model variant may differ")

        return model_path

    except HTTPError as e:
        print(f"\n✗ HTTP Error: {e.code} - {e.reason}")
        if e.code == 404:
            print(
                "  Model not found at URL. The model may have been moved or renamed."
            )
        raise
    except URLError as e:
        print(f"\n✗ Network Error: {e.reason}")
        print("  Check your internet connection and try again.")
        raise
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


def create_model_config_file(model_dir: Path, model_config: dict) -> None:
    """Create a config file with model metadata."""
    import json

    config_path = model_dir / "model_config.json"
    config_data = {
        "model_name": model_config["name"],
        "model_file": model_config["filename"],
        "model_description": model_config["description"],
        "chat_format": "chatml",  # Phi-4 uses ChatML format
        "context_length": 4096,
        "model_type": "phi",
        "quantization": "Q4_K_M",
        "source_url": model_config["url"],
    }

    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)

    print(f"\n✓ Model config saved: {config_path}")


def test_model_loading(model_path: Path) -> bool:
    """Test that the model can be loaded with llama-cpp-python."""
    print("\n" + "=" * 60)
    print("Testing model loading...")
    print("=" * 60)

    try:
        from llama_cpp import Llama

        print("  Loading model (this may take 30-60 seconds)...")
        llm = Llama(
            model_path=str(model_path),
            n_ctx=512,  # Small context for testing
            n_threads=4,
            verbose=False,
        )

        print("  Running test inference...")
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "Say 'Hello, MCP!' in exactly 3 words.",
                },
            ],
            max_tokens=20,
            temperature=0.1,
        )

        reply = response["choices"][0]["message"]["content"]
        print(f"  Test response: {reply.strip()}")
        print("\n✓ Model loaded and working correctly!")

        # Clean up
        del llm

        return True

    except ImportError:
        print("  ⚠ llama-cpp-python not installed")
        print("  Install with: pip install llama-cpp-python")
        return False
    except Exception as e:
        print(f"  ✗ Error loading model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download Phi-4 Mini GGUF model for Aura MCP Chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/download_phi4_model.py              # Download to default location
  python scripts/download_phi4_model.py --force      # Force re-download
  python scripts/download_phi4_model.py --test       # Download and test loading
  python scripts/download_phi4_model.py --list       # List available models
        """,
    )

    parser.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help="Directory to save the model (default: model_artifacts/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if file exists",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test model loading after download",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available models and exit",
    )
    parser.add_argument(
        "--alternative",
        type=int,
        choices=[1, 2],
        help="Download alternative model (1=Phi-3-mini, 2=TinyLlama)",
    )

    args = parser.parse_args()

    # List models and exit
    if args.list:
        print("\nAvailable Models:")
        print("=" * 60)
        print(f"\n[Default] {MODEL_CONFIG['name']}")
        print(f"  {MODEL_CONFIG['description']}")
        print(f"  Size: {format_size(MODEL_CONFIG['size_bytes'])}")

        for i, alt in enumerate(ALTERNATIVE_MODELS, 1):
            print(f"\n[Alternative {i}] {alt['name']}")
            print(f"  {alt['description']}")
            print(f"  Size: {format_size(alt['size_bytes'])}")

        print("\n" + "=" * 60)
        return 0

    # Select model
    if args.alternative:
        model_config = ALTERNATIVE_MODELS[args.alternative - 1]
    else:
        model_config = MODEL_CONFIG

    # Get model directory
    model_dir = args.model_dir or get_default_model_dir()

    print("\n" + "=" * 60)
    print("  AURA MCP - Embedded LLM Model Downloader")
    print("=" * 60)
    print(f"\nModel: {model_config['name']}")
    print(f"Target: {model_dir}")

    try:
        # Download model
        model_path = download_model(model_config, model_dir, force=args.force)

        # Create config file
        create_model_config_file(model_dir, model_config)

        # Test if requested
        if args.test:
            test_model_loading(model_path)

        print("\n" + "=" * 60)
        print("  Setup Complete!")
        print("=" * 60)
        print(f"\nModel ready at: {model_path}")
        print("\nTo use in Aura MCP:")
        print("  1. Set MODEL_PATH environment variable (optional)")
        print(f"     export MODEL_PATH={model_path}")
        print("  2. Start the MCP server")
        print("     python scripts/start_mcp_with_backend.py")
        print("  3. Open the dashboard and start chatting!")
        print()

        return 0

    except (HTTPError, URLError) as e:
        print(f"\n✗ Download failed: {e}")
        print("\nAlternative options:")
        print(
            "  1. Try an alternative model: python scripts/download_phi4_model.py --alternative 1"
        )
        print(
            "  2. Download manually from Hugging Face and place in model_artifacts/"
        )
        return 1
    except KeyboardInterrupt:
        print("\n\n✗ Download cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
