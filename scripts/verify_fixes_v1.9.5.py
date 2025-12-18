import sys

import requests


def check_backend():
    print("🔍 Checking Backend Model Status...")
    try:
        response = requests.post("http://localhost:9201/chat/status", json={})
        if response.status_code == 200:
            data = response.json()
            llm_available = data.get("llm", {}).get("available", False)
            model_name = data.get("llm", {}).get("model_name", "Unknown")

            if llm_available:
                print(f"✅ Backend Healthy: LLM '{model_name}' is LOADED.")
                return True
            else:
                print(f"❌ Backend Issue: LLM is NOT loaded. Data: {data}")
                return False
        else:
            print(f"❌ Backend Error: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend Connection Failed: {e}")
        return False


def check_frontend_html():
    print("\n🔍 Checking Frontend HTML (Cache Busting)...")
    try:
        response = requests.get("http://localhost:9205/index.html")
        if response.status_code == 200:
            content = response.text
            if 'src="assets/app.js?v=2.0.1"' in content:
                print("✅ Frontend HTML: Cache busting tag found (v=2.0.1).")
                return True
            else:
                print(
                    "❌ Frontend HTML: Old script tag found. Nginx might be serving stale content."
                )
                print(f"   Snippet: {content[:500]}...")  # Print start of file
                return False
        else:
            print(f"❌ Frontend Error: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend Connection Failed: {e}")
        return False


def check_frontend_js():
    print("\n🔍 Checking Frontend JS (Syntax Fixes)...")
    try:
        response = requests.get("http://localhost:9205/assets/app.js")
        if response.status_code == 200:
            content = response.text

            # Check for the specific fix (appendChatMessage vs addChatMessage)
            if (
                "appendChatMessage('system', '❌ Microphone access denied"
                in content
            ):
                print("✅ Frontend JS: 'appendChatMessage' fix verified.")
            else:
                print(
                    "❌ Frontend JS: Fix NOT found. Still using 'addChatMessage'?"
                )
                return False

            # Check for the debug beacon
            if 'console.log("🚀 Aura Dashboard App v2.0 Loaded")' in content:
                print("✅ Frontend JS: Debug beacon found.")
                return True
            else:
                print("❌ Frontend JS: Debug beacon NOT found.")
                return False
        else:
            print(f"❌ Frontend JS Error: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend JS Connection Failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Aura IA System Verification (V.1.9.5)")
    print("=" * 50)

    backend_ok = check_backend()
    html_ok = check_frontend_html()
    js_ok = check_frontend_js()

    print("\n" + "=" * 50)
    if backend_ok and html_ok and js_ok:
        print("✅ SYSTEM VERIFIED: All fixes are deployed and active.")
        sys.exit(0)
    else:
        print("⚠️  SYSTEM VERIFICATION FAILED: See errors above.")
        sys.exit(1)
        print("⚠️  SYSTEM VERIFICATION FAILED: See errors above.")
        sys.exit(1)
