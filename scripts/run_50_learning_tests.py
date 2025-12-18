#!/usr/bin/env python3
"""Run 50 diverse learning tests against the MCP server."""
import json

import httpx

BASE_URL = "http://localhost:9200"  # Docker gateway
results = {"passed": 0, "failed": 0, "tests": []}


def test(
    num: int,
    name: str,
    method: str,
    path: str,
    body: dict | None = None,
    expected: int = 200,
):
    """Run a single test."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            r = httpx.get(url, timeout=10)
        else:
            r = httpx.post(url, json=body or {}, timeout=10)

        status = "✅" if r.status_code == expected else "⚠️"
        passed = r.status_code == expected
        data = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else {}
        )
    except Exception as e:
        status = "❌"
        passed = False
        data = {"error": str(e)}

    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1

    results["tests"].append(
        {"num": num, "name": name, "passed": passed, "data": data}
    )
    print(f"{status} [{num:02d}/50] {name}")
    return data


print("\n" + "=" * 60)
print("🧪 AURA MCP LEARNING TEST SUITE - 50 TESTS")
print("=" * 60)

# === HEALTH & READINESS (1-5) ===
print("\n📋 HEALTH & READINESS TESTS")
test(1, "Health check", "GET", "/healthz")
test(2, "Readiness probe", "GET", "/readyz")
test(3, "Detailed health", "GET", "/health/detailed")
test(4, "Readiness endpoint", "GET", "/readiness")
test(5, "Metrics endpoint", "GET", "/metrics")

# === TRAINING STARTS (6-15) ===
print("\n🎓 TRAINING START TESTS")
test(6, "Training - default", "POST", "/training/start")
test(7, "Training - 1 episode", "POST", "/training/start", {"episodes": 1})
test(8, "Training - 3 episodes", "POST", "/training/start", {"episodes": 3})
test(9, "Training - dry run", "POST", "/training/start", {"dry_run": True})
test(
    10,
    "Training - with task",
    "POST",
    "/training/start",
    {"task_description": "Learn API patterns"},
)
r11 = test(
    11,
    "Training - custom run_id",
    "POST",
    "/training/start",
    {"run_id": "learn-50-001"},
)
test(
    12,
    "Training - 5 episodes dry",
    "POST",
    "/training/start",
    {"episodes": 5, "dry_run": True},
)
test(
    13,
    "Training - complex config",
    "POST",
    "/training/start",
    {"episodes": 2, "task_description": "Multi-step reasoning"},
)
test(
    14,
    "Training - batch learning",
    "POST",
    "/training/start",
    {"episodes": 10, "task_description": "Batch processing patterns"},
)
test(
    15,
    "Training - micro episode",
    "POST",
    "/training/start",
    {"episodes": 1, "task_description": "Quick inference test"},
)

# === EPISODE QUERIES (16-20) ===
print("\n📊 EPISODE QUERY TESTS")
test(16, "List episodes - run 001", "GET", "/training/episodes/learn-50-001")
test(17, "Run summary - run 001", "GET", "/training/runs/learn-50-001/summary")
test(
    18,
    "Episode detail",
    "GET",
    f"/training/episodes/learn-50-001/{r11.get('episode_id', 'learn-50-001_ep0001')}",
)
test(
    19, "List episodes - nonexistent", "GET", "/training/episodes/fake-run-xyz"
)
test(
    20,
    "Run summary - nonexistent",
    "GET",
    "/training/runs/fake-run-xyz/summary",
)

# === ROLE MUTATION (21-25) ===
print("\n🔄 ROLE MUTATION TESTS")
test(21, "Role mutate - approved", "POST", "/roles/mutate", {"approved": True})
test(
    22,
    "Role mutate - with context",
    "POST",
    "/roles/mutate",
    {"approved": True, "context": {"source": "learning"}},
)
test(23, "Role load", "GET", "/roles/load")
test(
    24,
    "Role mutate - dry run",
    "POST",
    "/roles/mutate",
    {"approved": True, "dry_run": True},
)
test(
    25,
    "Role mutate - denied",
    "POST",
    "/roles/mutate",
    {"approved": False},
    expected=403,
)

# === LLM PROXY (26-30) ===
print("\n🤖 LLM PROXY TESTS")
test(26, "LLM health", "GET", "/llm/health")
test(27, "LLM generate - simple", "POST", "/llm/generate", {"prompt": "Hello"})
test(
    28,
    "LLM generate - code",
    "POST",
    "/llm/generate",
    {"prompt": "Write a Python function"},
)
test(
    29,
    "LLM generate - long",
    "POST",
    "/llm/generate",
    {"prompt": "Explain machine learning in detail"},
)
test(
    30,
    "LLM generate - structured",
    "POST",
    "/llm/generate",
    {"prompt": "List 3 items", "max_tokens": 100},
)

# === EMBEDDINGS (31-35) ===
print("\n📐 EMBEDDING TESTS")
test(31, "Embed health", "GET", "/embed/health")
test(32, "Embed - single text", "POST", "/embed", {"texts": ["Hello world"]})
test(
    33,
    "Embed - multiple texts",
    "POST",
    "/embed",
    {"texts": ["Hello", "World", "Test"]},
)
test(
    34,
    "Embed vectors - single",
    "POST",
    "/embed/vectors",
    {"texts": ["Machine learning"]},
)
test(
    35,
    "Embed vectors - batch",
    "POST",
    "/embed/vectors",
    {"texts": ["AI", "ML", "DL", "NLP", "CV"]},
)

# === RAG SERVICE (36-40) ===
print("\n🔍 RAG SERVICE TESTS")
test(36, "RAG health", "GET", "/rag/health")
test(37, "RAG query - simple", "POST", "/rag/query", {"query": "What is MCP?"})
test(
    38,
    "RAG query - code",
    "POST",
    "/rag/query",
    {"query": "Show training routes"},
)
test(
    39,
    "RAG upsert - doc",
    "POST",
    "/rag/upsert",
    {"documents": [{"id": "test-1", "content": "Test document"}]},
)
test(
    40,
    "RAG query - complex",
    "POST",
    "/rag/query",
    {"query": "Explain safe mode configuration", "top_k": 5},
)

# === ROLE ENGINE (41-45) ===
print("\n👤 ROLE ENGINE TESTS")
test(41, "Roles health", "GET", "/roles/health")
test(42, "Active roles", "GET", "/roles/active")
test(
    43, "Role evaluate - action", "POST", "/roles/evaluate", {"action": "read"}
)
test(
    44,
    "Guards check - simple",
    "POST",
    "/roles/guards/check",
    {"action": "write"},
)
test(
    45,
    "Guards check - sensitive",
    "POST",
    "/roles/guards/check",
    {"action": "delete", "resource": "config"},
)

# === CHAT COMPLETIONS (46-48) ===
print("\n💬 CHAT COMPLETION TESTS")
test(46, "Chat health", "GET", "/v1/health")
test(
    47,
    "Chat completion",
    "POST",
    "/v1/chat/completions",
    {"messages": [{"role": "user", "content": "Hi"}]},
)
test(
    48,
    "Chat dual",
    "POST",
    "/v1/chat/dual",
    {"messages": [{"role": "user", "content": "Test"}]},
)

# === PERFORMANCE & OBSERVABILITY (49-50) ===
print("\n📈 OBSERVABILITY TESTS")
test(49, "Performance summary", "GET", "/performance")
test(50, "Metrics prometheus", "GET", "/metrics")

# === SUMMARY ===
print("\n" + "=" * 60)
print(f"🏁 RESULTS: {results['passed']} PASSED | {results['failed']} FAILED")
print(f"📊 Success Rate: {results['passed']/50*100:.1f}%")
print("=" * 60)

# Save results
with open("data/learning_50_tests_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\n💾 Results saved to data/learning_50_tests_results.json")
print("\n💾 Results saved to data/learning_50_tests_results.json")
