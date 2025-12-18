import json
import time

import requests

# ======= CONFIG =======
MCP_HOST = "http://127.0.0.1:8001"
HEALTH_ENDPOINT = f"{MCP_HOST}/api/v1/health"
TEST_TOOL_ENDPOINT = f"{MCP_HOST}/api/v1/tools/call"
DASHBOARD_ENDPOINT = f"{MCP_HOST}:8002/api/v1/ml/metrics"
CACHE_ENDPOINT = (
    f"{MCP_HOST}/api/v1/cache/status"  # ULTRA prefetch cache status
)
TIMEOUT = 5  # seconds

# ======= TEST QUERIES =======
TEST_TOOL_CALLS = [
    {
        "tool": "get_documentation",
        "arguments": {
            "topic": "react native performance optimization",
            "language": "typescript",
        },
    },
    {
        "tool": "search_documentation",
        "arguments": {
            "query": "React Native performance optimization memo useMemo FlatList",
            "framework": "react-native",
        },
    },
]


# ======= FUNCTIONS =======
def check_server_health():
    try:
        r = requests.get(HEALTH_ENDPOINT, timeout=TIMEOUT)
        if r.status_code == 200:
            print("[✅] MCP Server is ONLINE")
            return True
        else:
            print(f"[❌] MCP Health check failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"[❌] MCP Health check exception: {e}")
        return False


def call_tool(tool_call):
    try:
        payload = json.dumps(tool_call)
        r = requests.post(
            TEST_TOOL_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            resp_json = r.json()
            print(f"[✅] Tool '{tool_call['tool']}' executed successfully.")
            # Check ULTRA Master Prompt influence
            if resp_json.get("ultra_metadata"):
                print(
                    "  - ULTRA Master Prompt active, semantic & RLHF info detected"
                )
            return resp_json
        else:
            print(
                f"[❌] Tool '{tool_call['tool']}' failed: HTTP {r.status_code}"
            )
            return None
    except Exception as e:
        print(f"[❌] Exception calling tool '{tool_call['tool']}': {e}")
        return None


def check_ultra_metrics():
    try:
        r = requests.get(DASHBOARD_ENDPOINT, timeout=TIMEOUT)
        if r.status_code == 200:
            metrics = r.json()
            print("[✅] ULTRA metrics retrieved successfully.")
            confidence = metrics.get("prediction_confidence", 0)
            semantic_consistency = metrics.get("semantic_consistency", 0)
            auto_adapt_events = metrics.get("auto_adaptation_events", 0)
            print(f"  - Prediction Confidence: {confidence}")
            print(f"  - Semantic Consistency: {semantic_consistency}")
            print(f"  - Auto-Adaptation Events: {auto_adapt_events}")
            return metrics
        else:
            print(
                f"[❌] Failed to retrieve ULTRA metrics: HTTP {r.status_code}"
            )
            return None
    except Exception as e:
        print(f"[❌] Exception retrieving ULTRA metrics: {e}")
        return None


def check_prefetch_cache():
    try:
        r = requests.get(CACHE_ENDPOINT, timeout=TIMEOUT)
        if r.status_code == 200:
            cache_status = r.json()
            hits = cache_status.get("prefetch_hits", 0)
            queued = cache_status.get("queued_tasks", 0)
            print("[✅] ULTRA prefetch cache checked.")
            print(f"  - Prefetch Hits: {hits}")
            print(f"  - Queued Tasks: {queued}")
            return cache_status
        else:
            print(
                f"[❌] Failed to retrieve prefetch cache status: HTTP {r.status_code}"
            )
            return None
    except Exception as e:
        print(f"[❌] Exception retrieving prefetch cache: {e}")
        return None


def calculate_ultra_confidence(metrics, cache):
    score = 0
    if metrics:
        score += metrics.get("prediction_confidence", 0) * 0.4
        score += metrics.get("semantic_consistency", 0) * 0.4
        score += (
            1 if metrics.get("auto_adaptation_events", 0) > 0 else 0
        ) * 0.2
    if cache:
        score += min(
            cache.get("prefetch_hits", 0) / 10, 0.2
        )  # max 0.2 points from prefetch
    print(f"[⚡] ULTRA Godmode Readiness Score: {score:.2f} / 1.0")
    return score


# ======= MAIN CHECK =======
def run_ultra_health_check():
    print("=== MCP ULTRA GODMODE HEALTH CHECK ===")
    if not check_server_health():
        print("[❌] MCP Server is offline. ULTRA check aborted.")
        return

    print("\n--- Running Test Tool Calls ---")
    for call in TEST_TOOL_CALLS:
        call_tool(call)
        time.sleep(0.5)

    print("\n--- Checking ULTRA Metrics ---")
    metrics = check_ultra_metrics()

    print("\n--- Checking Prefetch Cache ---")
    cache = check_prefetch_cache()

    print("\n--- Calculating ULTRA Godmode Confidence ---")
    calculate_ultra_confidence(metrics, cache)

    print("\n[✅] ULTRA MCP Health Check Complete.")


# ======= RUN =======
if __name__ == "__main__":
    run_ultra_health_check()
