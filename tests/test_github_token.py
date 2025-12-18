#!/usr/bin/env python3
"""Quick script to test GitHub token"""
import json
import os
import urllib.request

token = os.getenv("GITHUB_TOKEN")

if not token:
    print("❌ GITHUB_TOKEN not found in environment")
    print("Set it with: set GITHUB_TOKEN=your_token_here")
    exit(1)

print(f"✓ Token found: {token[:10]}...")

# Test token
try:
    req = urllib.request.Request("https://api.github.com/user")
    req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        print("✓ Token is valid!")
        print(f"✓ Authenticated as: {data['login']}")
        print(f"✓ Name: {data.get('name', 'N/A')}")
        print(f"✓ Public repos: {data['public_repos']}")

except urllib.error.HTTPError as e:
    if e.code == 401:
        print("❌ Token is invalid or expired")
    else:
        print(f"❌ Error: {e.code} - {e.reason}")
except Exception as e:
    print(f"❌ Error: {e}")
