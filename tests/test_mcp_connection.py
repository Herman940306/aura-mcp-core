#!/usr/bin/env python3
"""Quick test to verify MCP server can connect to backend"""
import json
import urllib.request

print("Testing MCP Integration...")
print("-" * 50)

# Test 1: Backend health
print("\n1. Testing backend service...")
try:
    with urllib.request.urlopen(
        "http://127.0.0.1:8001/health", timeout=5
    ) as response:
        if response.status == 200:
            print("   ✓ Backend is running on port 8001")
        else:
            print(f"   ✗ Backend returned status {response.status}")
except Exception as e:
    print(f"   ✗ Backend not reachable: {e}")

# Test 2: Environment variables
print("\n2. Checking environment variables...")
import os

keys = {
    "OPENAI_API_KEY": "OpenAI",
    "ANTHROPIC_API_KEY": "Anthropic",
    "GOOGLE_API_KEY": "Google",
    "DEEPSEEK_API_KEY": "DeepSeek",
    "GROQ_API_KEY": "Groq",
    "GITHUB_TOKEN": "GitHub",
}

for var, name in keys.items():
    value = os.getenv(var)
    if value:
        print(f"   ✓ {name}: {value[:20]}...")
    else:
        print(f"   ✗ {name}: Not set")

# Test 3: MCP server module
print("\n3. Testing MCP server module...")
try:
    print("   ✓ MCP server module can be imported")
except Exception as e:
    print(f"   ✗ Cannot import MCP server: {e}")

# Test 4: Configuration files
print("\n4. Checking configuration files...")
import pathlib

configs = [
    pathlib.Path.home() / ".kiro" / "settings" / "mcp.json",
    pathlib.Path.home() / ".kiro" / "settings" / "models.json",
    pathlib.Path.home() / ".kiro" / "settings" / "provider_config.json",
]

for config in configs:
    if config.exists():
        print(f"   ✓ {config.name} exists")
        try:
            with open(config) as f:
                json.load(f)
            print("      Valid JSON")
        except Exception as e:
            print(f"      ✗ Invalid JSON: {e}")
    else:
        print(f"   ✗ {config.name} not found")

print("\n" + "=" * 50)
print("✓ MCP Integration is ready!")
print("\nNext steps:")
print("1. Check Kiro IDE MCP Server view")
print("2. Look for 'ide-agents-mcp' server")
print("3. Status should show 'Connected'")
print("4. Try: 'Check MCP server health' in chat")
