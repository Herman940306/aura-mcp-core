#!/usr/bin/env python3
"""
ML Integration Test Script
Tests all ML-powered MCP tools

Author: Herman Swanepoel (Godmode Developer)
"""


import requests

API_BASE = "http://127.0.0.1:8001"


def test_ml_system_status():
    """Test ML system status endpoint"""
    print("🧠 Testing ML System Status...")
    try:
        response = requests.get(
            f"{API_BASE}/ai/intelligence/status", timeout=5
        )
        response.raise_for_status()
        data = response.json()

        print("✓ ML System Status Retrieved")
        print(f"  Status: {data.get('status', 'unknown')}")
        print(f"  Engines: {len([k for k in data.keys() if 'engine' in k])}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_emotion_detection():
    """Test emotion detection"""
    print("\n😊 Testing Emotion Detection...")
    test_texts = [
        "I am feeling great today!",
        "I'm so stressed about work",
        "This is amazing and exciting!",
    ]

    for text in test_texts:
        try:
            response = requests.get(
                f"{API_BASE}/ai/intelligence/mood/analyze/{text}", timeout=5
            )
            response.raise_for_status()
            data = response.json()

            print(f'✓ "{text}"')
            print(f"  Mood: {data.get('mood', 'unknown')}")
            print(f"  Confidence: {data.get('confidence', 0):.1%}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return False

    return True


def test_predictions():
    """Test predictive engine"""
    print("\n🔮 Testing Predictive Engine...")
    try:
        response = requests.get(
            f"{API_BASE}/ai/intelligence/predictions/test_user", timeout=5
        )
        response.raise_for_status()
        data = response.json()

        predictions = data.get("predictions", [])
        print(f"✓ Predictions Retrieved: {len(predictions)} predictions")

        if predictions:
            for pred in predictions[:3]:
                title = pred.get("title", "unknown")
                confidence = pred.get("confidence", 0)
                print(f"  • {title} ({confidence:.0%})")
        else:
            print("  ⏳ No predictions yet (need 10+ interactions)")

        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_learning_insights():
    """Test learning analytics"""
    print("\n📊 Testing Learning Analytics...")
    try:
        response = requests.get(
            f"{API_BASE}/ai/intelligence/insights/test_user", timeout=5
        )
        response.raise_for_status()
        data = response.json()

        print("✓ Learning Insights Retrieved")

        progress = data.get("learning_progress", {})
        print(f"  Commands Learned: {progress.get('commands_learned', 0)}")
        print(f"  Routines Detected: {progress.get('routines_detected', 0)}")

        effectiveness = data.get("ai_effectiveness", {})
        prediction_accuracy = effectiveness.get("prediction_accuracy", 0)
        user_satisfaction = effectiveness.get("user_satisfaction_score", 0)

        print(f"  Prediction Accuracy: {prediction_accuracy:.0%}")
        print(f"  User Satisfaction: {user_satisfaction:.0%}")

        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_command_reasoning():
    """Test reasoning engine"""
    print("\n🧩 Testing Contextual Reasoning...")
    test_commands = [
        "turn on bedroom light",
        "make it cozy",
        "movie night setup",
    ]

    for command in test_commands:
        try:
            response = requests.get(
                f"{API_BASE}/entities/test/{command}", timeout=5
            )
            response.raise_for_status()
            data = response.json()

            print(f'✓ "{command}"')
            print(f"  Matched: {data.get('matched', False)}")
            if data.get("matched"):
                print(f"  Entity: {data.get('entity_name')}")
                print(f"  Action: {data.get('action')}")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return False

    return True


def test_entity_mappings():
    """Test entity mappings"""
    print("\n🏠 Testing Entity Mappings...")
    try:
        response = requests.get(f"{API_BASE}/entities/mappings", timeout=5)
        response.raise_for_status()
        data = response.json()

        print(f"✓ Entity Mappings Retrieved: {len(data)} entities")

        # Group by domain
        domains = {}
        for name, entity in data.items():
            domain = entity.get("domain", "unknown")
            domains[domain] = domains.get(domain, 0) + 1

        for domain, count in domains.items():
            print(f"  • {domain}: {count} entities")

        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def test_health_check():
    """Test basic health"""
    print("\n❤️ Testing Health Check...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        response.raise_for_status()
        data = response.json()

        print("✓ Health Check Passed")
        print(f"  Status: {data.get('status', 'unknown')}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


def main():
    """Run all ML integration tests"""
    print("=" * 60)
    print("🚀 ML-POWERED AI ASSISTANT INTEGRATION TEST")
    print("=" * 60)
    print(f"API Endpoint: {API_BASE}")
    print("=" * 60)

    tests = [
        ("Health Check", test_health_check),
        ("ML System Status", test_ml_system_status),
        ("Emotion Detection", test_emotion_detection),
        ("Predictive Engine", test_predictions),
        ("Learning Analytics", test_learning_insights),
        ("Contextual Reasoning", test_command_reasoning),
        ("Entity Mappings", test_entity_mappings),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {name}")

    print("=" * 60)
    print(
        f"Results: {passed}/{total} tests passed ({passed / total * 100:.0%})"
    )
    print("=" * 60)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! ML Integration Ready!")
        print("\n💡 Next Steps:")
        print("  1. Restart Kiro to load MCP server")
        print("  2. Try: 'Show me ML system status'")
        print("  3. Try: 'Analyze emotion: I'm feeling great!'")
        print("  4. Try: 'What predictions do you have?'")
        print("  5. Read: mcp_server/ML_INTEGRATION_GUIDE.md")
    else:
        print("\n⚠️ Some tests failed. Check:")
        print("  1. Is AI Assistant running? (python main.py)")
        print("  2. Is port 8001 accessible?")
        print("  3. Are ML engines initialized?")

    return passed == total


if __name__ == "__main__":
    import sys

    success = main()
    sys.exit(0 if success else 1)
