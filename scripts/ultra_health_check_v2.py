import time

import requests

# ======= CONFIG =======
MCP_HOST = "http://127.0.0.1:8001"
HEALTH_ENDPOINT = f"{MCP_HOST}/health"
AI_HEALTH_ENDPOINT = f"{MCP_HOST}/ai/health"
COMMAND_ENDPOINT = f"{MCP_HOST}/command"
TIMEOUT = 5  # seconds

# ======= TEST QUERIES =======
TEST_COMMANDS = [
    {
        "text": "turn on bedroom light",
        "session_id": "health_check_001",
        "user_id": "health_check_user",
        "source": "ultra_health_check",
    },
    {
        "text": "what is the weather",
        "session_id": "health_check_002",
        "user_id": "health_check_user",
        "source": "ultra_health_check",
    },
]


# ======= FUNCTIONS =======
def check_server_health():
    try:
        r = requests.get(HEALTH_ENDPOINT, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            print("[✅] MCP Server is ONLINE")
            print(f"  - Status: {data.get('status', 'unknown')}")
            print(
                f"  - WebSocket Connections: {data.get('websocket_connections', 0)}"
            )
            return True
        else:
            print(f"[❌] MCP Health check failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"[❌] MCP Health check exception: {e}")
        return False


def check_ai_health():
    try:
        r = requests.get(AI_HEALTH_ENDPOINT, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            print("[✅] AI System is OPERATIONAL")
            features = data.get("features", {})
            print(
                f"  - Natural Language: {features.get('natural_language', False)}"
            )
            print(
                f"  - Command Processing: {features.get('command_processing', False)}"
            )
            print(
                f"  - Emotion Detection: {features.get('emotion_detection', False)}"
            )
            print(f"  - Learning: {features.get('learning', False)}")
            print(
                f"  - WebSocket Support: {features.get('websocket_support', False)}"
            )
            return True
        else:
            print(f"[❌] AI Health check failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"[❌] AI Health check exception: {e}")
        return False


def test_command(command_data):
    try:
        r = requests.post(
            COMMAND_ENDPOINT,
            json=command_data,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            resp_json = r.json()
            print(
                f"[✅] Command '{command_data['text']}' executed successfully"
            )
            message = resp_json.get(
                "message", resp_json.get("response", "No response")
            )
            print(f"  - Response: {message[:100]}...")
            return resp_json
        else:
            print(
                f"[❌] Command '{command_data['text']}' failed: HTTP {r.status_code}"
            )
            return None
    except Exception as e:
        print(
            f"[❌] Exception executing command '{command_data['text']}': {e}"
        )
        return None


def calculate_system_score(server_ok, ai_ok, command_results):
    score = 0.0

    if server_ok:
        score += 0.3
    if ai_ok:
        score += 0.3

    successful_commands = sum(1 for r in command_results if r is not None)
    total_commands = len(command_results)
    if total_commands > 0:
        score += (successful_commands / total_commands) * 0.4

    print(f"[⚡] ULTRA Godmode Readiness Score: {score:.2f} / 1.0")

    if score >= 0.9:
        print("[🚀] System Status: GODMODE READY")
    elif score >= 0.6:
        print("[✅] System Status: OPERATIONAL")
    elif score >= 0.3:
        print("[⚠️] System Status: DEGRADED")
    else:
        print("[❌] System Status: CRITICAL")

    return score


# ======= MAIN CHECK =======
def run_ultra_health_check():
    print("=== MCP ULTRA GODMODE HEALTH CHECK ===\n")

    print("--- Checking Server Health ---")
    server_ok = check_server_health()

    if not server_ok:
        print("\n[❌] MCP Server is offline. ULTRA check aborted.")
        return

    print("\n--- Checking AI System Health ---")
    ai_ok = check_ai_health()

    print("\n--- Running Test Commands ---")
    command_results = []
    for cmd in TEST_COMMANDS:
        result = test_command(cmd)
        command_results.append(result)
        time.sleep(0.5)

    print("\n--- Calculating System Readiness ---")
    calculate_system_score(server_ok, ai_ok, command_results)

    print("\n[✅] ULTRA MCP Health Check Complete.")


# ======= RUN =======
if __name__ == "__main__":
    run_ultra_health_check()
