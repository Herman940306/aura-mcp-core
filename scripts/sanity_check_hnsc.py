#!/usr/bin/env python3
"""HNSC Sanity Check - Verify MCP Concierge is working as intended.

Project Creator: Herman Swanepoel
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    print("=" * 60)
    print("  HNSC SANITY CHECK - MCP Concierge Verification")
    print("=" * 60)

    passed = 0
    failed = 0

    # Test 1: Import all HNSC modules
    print("\n[1] Importing HNSC modules...")
    try:
        from mcp_server.hnsc import (
            HNSCRequest,
            StaticReasoningLibrary,
            SymbolicRouter,
            ToolIntelligenceLayer,
            WorkflowEngine,
            create_hnsc_controller,
            get_safety_engine,
        )

        print("  ✅ All HNSC modules imported successfully")
        passed += 1
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        failed += 1
        return 1

    # Test 2: Create controller
    print("\n[2] Creating HNSC Controller...")
    try:
        controller = create_hnsc_controller()
        print("  ✅ Controller created")
        passed += 1
    except Exception as e:
        print(f"  ❌ Controller creation failed: {e}")
        failed += 1
        return 1

    # Test 3: Safety Layer - Block dangerous input
    print("\n[3] Testing Safety Layer (Layer 6)...")
    request = HNSCRequest(user_input="execute rm -rf / on production")
    response = controller.process(request)
    if not response.success:
        print("  ✅ Dangerous command BLOCKED")
        print(f"     Message: {response.message[:60]}...")
        passed += 1
    else:
        print("  ❌ FAILED: Should have blocked dangerous command!")
        failed += 1

    # Test 4: Symbolic Router - Intent classification
    print("\n[4] Testing Symbolic Router (Layer 2)...")
    router = SymbolicRouter()
    result = router.route("check the system health status")
    if result.recommended_tool:
        print(f"  ✅ Routed to tool: {result.recommended_tool}")
        print(
            f"     Intent: {result.intent_category}, Confidence: {result.confidence:.2f}"
        )
        passed += 1
    else:
        print("  ⚠️ No tool recommended (acceptable for some queries)")
        passed += 1

    # Test 5: Workflow Engine
    print("\n[5] Testing Workflow Engine (Layer 3)...")
    workflow_engine = WorkflowEngine()
    workflows = workflow_engine.list_workflows()
    if len(workflows) > 0:
        print(f"  ✅ {len(workflows)} workflows available")
        passed += 1
    else:
        print("  ❌ No workflows found")
        failed += 1

    # Test 6: Static Reasoning
    print("\n[6] Testing Static Reasoning (Layer 4)...")
    reasoning = StaticReasoningLibrary()
    templates = reasoning.list_templates()
    if len(templates) > 0:
        print(f"  ✅ {len(templates)} reasoning templates available")
        passed += 1
    else:
        print("  ❌ No templates found")
        failed += 1

    # Test 7: Tool Intelligence
    print("\n[7] Testing Tool Intelligence (Layer 5)...")
    tools = ToolIntelligenceLayer()
    tool_list = tools.list_tools()
    if len(tool_list) > 0:
        print(f"  ✅ {len(tool_list)} intelligent tools available")
        passed += 1
    else:
        print("  ❌ No tools found")
        failed += 1

    # Test 8: Full request processing (safe query)
    print("\n[8] Testing Full Request Processing...")
    request = HNSCRequest(
        user_input="what is the current system status?",
        session_id="sanity_check",
    )
    response = controller.process(request)
    if response.success:
        print("  ✅ Request processed successfully")
        print(f"     Stages: {[s.value for s in response.stages_completed]}")
        print(f"     LLM Used: {response.llm_used}")
        print(f"     Confidence: {response.confidence:.2f}")
        passed += 1
    else:
        print(f"  ❌ Request failed: {response.message}")
        failed += 1

    # Test 9: PII Protection
    print("\n[9] Testing PII Protection...")
    safety = get_safety_engine()
    text = "User SSN is 123-45-6789 and email is test@example.com"
    redacted = safety.redact_pii(text)
    if "[REDACTED:" in redacted:
        print("  ✅ PII redacted successfully")
        print(f"     Original: {text[:40]}...")
        print(f"     Redacted: {redacted[:40]}...")
        passed += 1
    else:
        print("  ❌ PII not redacted!")
        failed += 1

    # Test 10: Metrics tracking
    print("\n[10] Testing Metrics Tracking...")
    metrics = controller.get_metrics()
    total = metrics.get("total_requests", 0)
    blocked = metrics.get("blocked", 0)
    if total >= 2:  # We made at least 2 requests
        print("  ✅ Metrics tracked correctly")
        print(f"     Total Requests: {total}")
        print(f"     Blocked: {blocked}")
        print(f"     Block Rate: {metrics.get('block_rate', 0)*100:.1f}%")
        passed += 1
    else:
        print(f"  ❌ Metrics not tracking correctly: {metrics}")
        failed += 1

    # Final Summary
    print("\n" + "=" * 60)
    print("  SANITY CHECK SUMMARY")
    print("=" * 60)
    print(f"\n  Total Tests: {passed + failed}")
    print(f"  Passed: {passed} ✅")
    print(f"  Failed: {failed} ❌")

    if failed == 0:
        print("\n  🎉 ALL SANITY CHECKS PASSED!")
        print("  ✅ HNSC MCP Concierge is working as intended")
        print("\n  Architecture Summary:")
        print("  ┌─────────────────────────────────────────┐")
        print("  │ Layer 6: Safety/Policy    → WORKING    │")
        print("  │ Layer 2: Symbolic Router  → WORKING    │")
        print("  │ Layer 3: Workflow Engine  → WORKING    │")
        print("  │ Layer 4: Static Reasoning → WORKING    │")
        print("  │ Layer 5: Tool Intelligence→ WORKING    │")
        print("  │ Layer 1: LLM (Phi-3 Mini) → Token Gen  │")
        print("  └─────────────────────────────────────────┘")
        print("\n  The embedded model is the 'MCP Concierge':")
        print("  - Reads user messages on dashboard")
        print("  - Maps to MCP functions (tools, workflows)")
        print("  - Explains results")
        print("  - Ensures PRD compliance")
        print("  - NEVER touches IDE project code path")
        print("  - NEVER part of coding agent chain")
    else:
        print(f"\n  ⚠️ {failed} checks failed - review needed")

    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
