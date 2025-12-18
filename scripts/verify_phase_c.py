import sys
import time

import requests


def test_gateway():
    base_url = "http://localhost:9200"

    # 1. Check Health
    try:
        resp = requests.get(f"{base_url}/v1/health")
        print(f"Health Check: {resp.status_code} - {resp.json()}")
        if resp.status_code != 200:
            return False
    except Exception as e:
        print(f"Health Check Failed: {e}")
        return False

    # 2. Check Chat Completion (Mock)
    payload = {
        "model": "llama3",
        "messages": [{"role": "user", "content": "Hello"}],
    }
    try:
        # Note: This might fail if Ollama is not running, but we check for the endpoint existence/handling
        resp = requests.post(f"{base_url}/v1/chat/completions", json=payload)
        print(f"Chat Completion: {resp.status_code}")
        # We expect 200 (if ollama up) or 500 (if ollama down), but not 404
        if resp.status_code == 404:
            print("Endpoint not found!")
            return False
    except Exception as e:
        print(f"Chat Completion Request Failed: {e}")
        return False

    return True


if __name__ == "__main__":
    # Wait for server to start
    time.sleep(5)
    if test_gateway():
        print("Verification PASSED")
        sys.exit(0)
    else:
        print("Verification FAILED")
        sys.exit(1)
