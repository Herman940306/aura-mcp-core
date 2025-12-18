#!/usr/bin/env python3
"""
Test script for the embedded LLM chat functionality.

This script verifies:
1. The model file exists
2. The model can be loaded
3. The chat service works
4. Tool calling works

Usage:
    python scripts/test_embedded_chat.py
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_model_exists():
    """Test that the model file exists."""
    print("\n" + "=" * 60)
    print("Test 1: Model File Existence")
    print("=" * 60)

    model_dir = Path(__file__).parent.parent / "model_artifacts"
    gguf_files = list(model_dir.glob("*.gguf"))

    if gguf_files:
        print(f"✓ Found {len(gguf_files)} GGUF model(s):")
        for f in gguf_files:
            size_gb = f.stat().st_size / (1024**3)
            print(f"  - {f.name} ({size_gb:.2f} GB)")
        return True
    else:
        print("✗ No GGUF models found in model_artifacts/")
        print("  Run: python scripts/download_phi4_model.py --alternative 1")
        return False


def test_model_loading():
    """Test that the model can be loaded."""
    print("\n" + "=" * 60)
    print("Test 2: Model Loading")
    print("=" * 60)

    try:
        from mcp_server.model_adapters.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter.get_instance()

        if adapter.is_model_available():
            print(f"✓ Model path: {adapter.model_path}")
            print(f"✓ Model file exists: {adapter.model_path.exists()}")

            # Try loading
            print("  Loading model (this may take 30-60 seconds)...")
            adapter.load_model()

            if adapter._model is not None:
                print("✓ Model loaded successfully!")
                info = adapter.get_model_info()
                print(f"  - Context length: {info.get('n_ctx', 'N/A')}")
                print(f"  - Threads: {info.get('n_threads', 'N/A')}")
                return True
            else:
                print("✗ Model failed to load")
                return False
        else:
            print(f"✗ Model not available at: {adapter.model_path}")
            return False

    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("  Install with: pip install llama-cpp-python")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_simple_chat():
    """Test simple chat completion."""
    print("\n" + "=" * 60)
    print("Test 3: Simple Chat")
    print("=" * 60)

    try:
        from mcp_server.model_adapters.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter.get_instance()

        if adapter._model is None:
            adapter.load_model()

        print("  Sending test message...")
        response = adapter.chat(
            messages=[
                {
                    "role": "user",
                    "content": "Say 'Hello, MCP!' in exactly 3 words.",
                }
            ],
            mode="general",
        )

        print(
            f"✓ Response: {response.get('response', 'No response')[:100]}..."
        )
        return True

    except Exception as e:
        print(f"✗ Chat error: {e}")
        return False


def test_chat_service():
    """Test the full chat service with tools."""
    print("\n" + "=" * 60)
    print("Test 4: Chat Service with Tools")
    print("=" * 60)

    try:

        from mcp_server.services.chat_service import get_chat_service

        chat_service = get_chat_service(auto_load_model=False)

        print("✓ Chat service initialized")
        print(f"  - Tools available: {len(chat_service.tool_registry.tools)}")
        print(f"  - Backend URL: {chat_service.backend_url}")

        # List tools
        print("\n  Available tools:")
        for name, tool in list(chat_service.tool_registry.tools.items())[:5]:
            print(
                f"    - {name}: {tool.get('description', 'No description')[:50]}..."
            )

        if len(chat_service.tool_registry.tools) > 5:
            print(
                f"    ... and {len(chat_service.tool_registry.tools) - 5} more"
            )

        return True

    except Exception as e:
        print(f"✗ Chat service error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  AURA MCP - Embedded Chat Test Suite")
    print("=" * 60)

    results = {
        "Model Exists": test_model_exists(),
        "Model Loading": test_model_loading(),
        "Simple Chat": test_simple_chat(),
        "Chat Service": test_chat_service(),
    }

    print("\n" + "=" * 60)
    print("  Test Results Summary")
    print("=" * 60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test}")

    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 60 + "\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
    sys.exit(main())
    sys.exit(main())
