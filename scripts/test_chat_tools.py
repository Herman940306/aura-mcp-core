#!/usr/bin/env python3
"""Test the comprehensive chat tools functionality.

This script tests the full range of tools available to the embedded LLM.

Project Creator: Herman Swanepoel
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_server.services.chat_service import MCPToolRegistry


async def test_tools():
    """Test tool execution."""
    registry = MCPToolRegistry(backend_url="http://localhost:9201")

    print("\n" + "=" * 60)
    print("  AURA MCP - Tool Functionality Test")
    print("=" * 60)

    # Test groups
    tests = [
        # Health & Status
        ("check_health", {}),
        ("get_system_status", {}),
        ("list_available_tools", {}),
        # Role Engine
        ("list_roles", {}),
        ("suggest_role", {"task_description": "write code for a new feature"}),
        (
            "check_permission",
            {"role_name": "developer", "action": "write:code"},
        ),
        # Risk Assessment
        (
            "evaluate_risk",
            {"operation": "delete_database", "context": {"env": "test"}},
        ),
        # Project Status
        ("get_project_status", {"section": "all"}),
        # Security
        (
            "check_pii",
            {
                "text": "Contact John at john@example.com or call 555-123-4567",
                "redact": True,
            },
        ),
        # Configuration
        ("get_config", {"section": "all"}),
        # Observability
        ("get_metrics", {"service": "all", "metric_type": "all"}),
        ("get_alerts", {}),
        # Futuristic
        ("get_carbon_budget", {}),
        ("list_wasm_plugins", {}),
        ("get_enclave_status", {}),
        # RAG
        ("list_collections", {}),
        # Logs
        ("get_recent_logs", {"service": "all", "lines": 5}),
    ]

    passed = 0
    failed = 0

    for tool_name, args in tests:
        print(f"\n Testing: {tool_name}")
        print(f"   Args: {args}")

        try:
            result = await registry.execute(tool_name, args)

            if result.get("success"):
                passed += 1
                print("   ✓ Success")

                # Show sample of result
                res = result.get("result", {})
                if isinstance(res, dict):
                    for key in list(res.keys())[:3]:
                        val = str(res[key])[:60]
                        print(f"     - {key}: {val}...")
                else:
                    print(f"     - {str(res)[:80]}...")
            else:
                failed += 1
                print(f"   ✗ Failed: {result.get('error')}")

        except Exception as e:
            failed += 1
            print(f"   ✗ Exception: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)
    print(f"  ✓ Passed: {passed}")
    print(f"  ✗ Failed: {failed}")
    print(f"  Total Tools: {len(registry.tools)}")
    print("=" * 60)

    # List all tool categories
    print("\n  All Available Tools by Category:")
    print("-" * 40)

    categories = {
        "Health & Status": [
            "check_health",
            "get_system_status",
            "get_model_status",
        ],
        "Data Retrieval": [
            "get_documentation",
            "list_entities",
            "get_activity_stats",
        ],
        "AI/ML": ["analyze_emotion", "semantic_rank"],
        "Debate Engine": ["start_debate", "get_debate_status"],
        "DAG Orchestration": [
            "create_workflow",
            "execute_workflow",
            "visualize_dag",
        ],
        "Risk Management": ["evaluate_risk", "request_approval"],
        "Role Engine": [
            "list_roles",
            "get_role_capabilities",
            "suggest_role",
            "check_permission",
        ],
        "Observability": [
            "get_metrics",
            "query_traces",
            "search_logs",
            "get_alerts",
            "get_dashboard_url",
        ],
        "RAG & Knowledge": [
            "semantic_search",
            "add_to_knowledge_base",
            "list_collections",
        ],
        "Security": ["check_pii", "audit_log", "get_security_audit"],
        "Green Computing": [
            "check_carbon_intensity",
            "schedule_green_job",
            "get_carbon_budget",
        ],
        "WASM Sandbox": ["list_wasm_plugins", "execute_wasm_plugin"],
        "Confidential Compute": ["get_enclave_status"],
        "Configuration": [
            "get_config",
            "get_project_status",
            "list_available_tools",
        ],
        "Debugging": ["get_recent_logs", "diagnose_issue"],
        "Commands": ["execute_command"],
        "GitHub": ["list_github_repos"],
    }

    for category, tools in categories.items():
        available = [t for t in tools if t in registry.tools]
        print(f"\n  {category}: {len(available)}/{len(tools)}")
        for t in available:
            print(f"    - {t}")

    return passed, failed


def main():
    passed, failed = asyncio.run(test_tools())
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
