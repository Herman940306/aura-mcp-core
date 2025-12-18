# Kiro IDE Integration Testing Guide

---
**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** 2025-11-14

---

## Overview

This guide provides comprehensive manual testing procedures for validating the MCP Server integration with Kiro IDE. These tests verify the complete workflow from IDE startup through tool discovery, invocation, and response handling.

**Prerequisites:**
- Kiro IDE installed and configured
- Backend service running on `http://127.0.0.1:8001`
- MCP configuration file at `.kiro/settings/mcp.json`
- GitHub token configured (for GitHub integration tests)
- Python environment with all dependencies installed

---

## Test Suite 1: Server Lifecycle Integration

### Test 1.1: Auto-Start on Kiro IDE Launch

**Objective:** Verify MCP server starts automatically when Kiro IDE launches

**Steps:**
1. Ensure backend service is running: `python mock_backend_server.py`
2. Close Kiro IDE completely if running
3. Launch Kiro IDE
4. Open the MCP Server view in Kiro feature panel
5. Wait up to 10 seconds

**Expected Results:**
- ✅ MCP server appears in the server list
- ✅ Server status shows "Running" or "Connected"
- ✅ Server becomes ready within 10 seconds
- ✅ No error messages in output panel
- ✅ Lifecycle log shows startup event

**Performance Requirement:** Server ready within 10 seconds (Req 12.2)

**Verification Command:**
```bash
# Check if server process is running
tasklist | findstr python  # Windows
```

---

### Test 1.2: Clean Shutdown on IDE Close

**Objective:** Verify MCP server shuts down cleanly when Kiro IDE closes

**Steps:**
1. With Kiro IDE running and MCP server connected
2. Check server process ID in task manager
3. Close Kiro IDE normally
4. Wait 5 seconds
5. Check if server process still exists

**Expected Results:**
- ✅ Server receives shutdown signal
- ✅ Server process terminates within 5 seconds
- ✅ No orphaned Python processes
- ✅ Lifecycle log shows clean shutdown event
- ✅ Telemetry file is flushed and closed properly

**Verification Command:**
```bash
# Verify no orphaned processes
tasklist | findstr python
```

---

### Test 1.3: Server Reconnection After Configuration Change

**Objective:** Verify server reconnects when configuration is modified

**Steps:**
1. With Kiro IDE running and MCP server connected
2. Open `.kiro/settings/mcp.json`
3. Change `IDE_AGENTS_ULTRA_ENABLED` from `"true"` to `"false"`
4. Save the file
5. Wait 5 seconds
6. Check MCP Server view

**Expected Results:**
- ✅ Server automatically reconnects
- ✅ Tool list updates (ML tools disappear when ULTRA disabled)
- ✅ No manual restart required
- ✅ Connection status shows "Reconnecting" then "Connected"
- ✅ Lifecycle log shows reconnection event

**Revert:** Change `IDE_AGENTS_ULTRA_ENABLED` back to `"true"` and save

---

### Test 1.4: Crash Recovery (Optional)

**Objective:** Verify IDE handles server crash gracefully

**Steps:**
1. With Kiro IDE running and MCP server connected
2. Find the MCP server process ID
3. Manually kill the process: `taskkill /PID <pid> /F`
4. Wait 10 seconds
5. Check MCP Server view and IDE behavior

**Expected Results:**
- ✅ IDE detects server crash
- ✅ Error message displayed to user
- ✅ IDE continues functioning without MCP tools
- ✅ Server auto-restart (if configured) or manual restart option shown
- ✅ Lifecycle log shows crash event

---

## Test Suite 2: Tool Discovery and Registration

### Test 2.1: Tool Discovery on Startup

**Objective:** Verify all MCP tools are discovered and registered

**Steps:**
1. Ensure `IDE_AGENTS_ULTRA_ENABLED="true"` in config
2. Restart Kiro IDE
3. Wait for MCP server to connect
4. Open MCP tools panel or command palette
5. Search for "ide_agents"

**Expected Results:**
- ✅ All core tools visible: `ide_agents_health`, `ide_agents_command`, `ide_agents_catalog`, `ide_agents_resource`, `ide_agents_prompt`
- ✅ All GitHub tools visible: `ide_agents_github_repos`, `ide_agents_github_rank_repos`, `ide_agents_github_rank_all`
- ✅ All ML tools visible (15 tools): `ide_agents_ml_analyze_emotion`, `ide_agents_ml_get_predictions`, etc.
- ✅ Tool descriptions are clear and helpful
- ✅ Tool categories are properly labeled

**Tool Count:** Minimum 23 tools when ULTRA enabled (Req 2.5)

---

### Test 2.2: ULTRA Mode Toggle

**Objective:** Verify ML tools appear/disappear based on ULTRA mode

**Steps:**
1. With ULTRA enabled, note the tool count
2. Change `IDE_AGENTS_ULTRA_ENABLED` to `"false"` in config
3. Wait for server reconnection
4. Check tool list again
5. Re-enable ULTRA mode

**Expected Results:**
- ✅ With ULTRA enabled: 23+ tools available
- ✅ With ULTRA disabled: ~8 core tools only (no ML tools)
- ✅ Tool list updates automatically on config change
- ✅ No errors when ML tools are unavailable

---

### Test 2.3: Tool Schema Validation

**Objective:** Verify tool input schemas are properly registered

**Steps:**
1. Open chat agent in Kiro IDE
2. Try to invoke a tool with invalid arguments
3. Example: "Use ide_agents_ml_analyze_emotion without providing text"

**Expected Results:**
- ✅ IDE validates arguments before sending to server
- ✅ Clear error message about missing required field
- ✅ Tool schema shows required vs optional parameters
- ✅ Type validation works (string, number, boolean, etc.)

---

## Test Suite 3: Chat Agent Integration

### Test 3.1: Emotion Analysis via Chat

**Objective:** Verify chat agent can use ML tools seamlessly

**Chat Prompt:**
```
Analyze the emotion in this text: "I'm so excited about this new feature! It's going to be amazing!"
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_ml_analyze_emotion`
- ✅ Response shows mood: "happy" or "excited"
- ✅ Confidence score displayed (e.g., 0.85-0.95)
- ✅ Response time < 500ms for backend round-trip
- ✅ Natural language response from chat agent

**Performance Requirement:** < 500ms backend round-trip (Req 2.4)

---

### Test 3.2: Predictive Suggestions

**Chat Prompt:**
```
Show me AI predictions for my development routines
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_ml_get_predictions`
- ✅ Returns list of predicted actions with confidence scores
- ✅ Predictions are relevant to development context
- ✅ Response formatted in readable way
- ✅ No approval required (auto-approved tool)

---

### Test 3.3: Learning Insights

**Chat Prompt:**
```
What has the AI learned about my coding patterns?
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_ml_get_learning_insights`
- ✅ Returns insights about user behavior patterns
- ✅ Includes metrics like total interactions, top patterns
- ✅ Response is personalized and actionable

---

### Test 3.4: GitHub Repository Search

**Chat Prompt:**
```
Find my GitHub repositories related to machine learning
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_github_rank_repos`
- ✅ Returns ranked list of relevant repositories
- ✅ Semantic ranking (ULTRA) or heuristic fallback
- ✅ Each repo shows name, description, stars, URL
- ✅ Results are actually relevant to "machine learning"

---

### Test 3.5: Resource Access

**Chat Prompt:**
```
Show me the project structure from repo.graph
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_resource` with name="repo.graph"
- ✅ Returns repository graph JSON content
- ✅ Chat agent formats response in readable way
- ✅ No approval required (read-only operation)

---

### Test 3.6: Prompt Template Usage

**Chat Prompt:**
```
Get the diff review prompt template
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_prompt` with name="/diff_review"
- ✅ Returns prompt template content
- ✅ Template is properly formatted
- ✅ Chat agent can use template for code review

---

## Test Suite 4: Approval Workflow

### Test 4.1: Command Execution with Approval

**Chat Prompt:**
```
Run this command: echo "Hello from MCP"
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_command` with method="run"
- ✅ Approval dialog appears in Kiro IDE
- ✅ Dialog shows command details and action_id
- ✅ User can approve or deny
- ✅ On approval: command executes and returns output
- ✅ On denial: operation cancelled with clear message

**Test Both Paths:**
1. Approve the command → verify execution
2. Deny the command → verify cancellation

---

### Test 4.2: Dry Run (No Approval)

**Chat Prompt:**
```
Explain what this command would do: rm -rf /tmp/cache
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_command` with method="dry_run"
- ✅ No approval dialog appears
- ✅ Returns simulation result without execution
- ✅ Response explains command behavior safely

---

### Test 4.3: Auto-Approved Tools

**Chat Prompt:**
```
Check the MCP server health status
```

**Expected Results:**
- ✅ Chat agent invokes `ide_agents_health`
- ✅ No approval dialog (tool is in autoApprove list)
- ✅ Returns server status immediately
- ✅ Response shows version, status, flags

---

### Test 4.4: Approval Queue Management

**Objective:** Verify multiple approval requests are handled correctly

**Steps:**
1. Queue multiple command executions rapidly
2. Example: Ask chat to run 3 different commands
3. Observe approval dialogs

**Expected Results:**
- ✅ Each command gets unique action_id
- ✅ Approvals are tracked independently
- ✅ No race conditions or duplicate approvals
- ✅ Queue status visible in telemetry

---

## Test Suite 5: Error Handling

### Test 5.1: Backend Service Unavailable

**Steps:**
1. Stop the backend service: `Ctrl+C` on mock_backend_server.py
2. Try to use an ML tool via chat
3. Example: "Analyze emotion in: test text"

**Expected Results:**
- ✅ IDE detects backend unavailable within 30 seconds
- ✅ User-friendly error message displayed
- ✅ Error message suggests checking backend service
- ✅ Chat agent continues functioning
- ✅ Other non-backend tools still work

**Error Message Should Include:**
- "Backend service is unavailable"
- "Please ensure it's running on port 8001"
- Troubleshooting suggestions

---

### Test 5.2: Invalid Tool Arguments

**Chat Prompt:**
```
Use ide_agents_ml_analyze_emotion with invalid arguments
```

**Expected Results:**
- ✅ Validation error before server invocation
- ✅ Clear error message about invalid/missing arguments
- ✅ Error shows which field is invalid
- ✅ No server-side error (caught at client)

---

### Test 5.3: Rate Limiting

**Steps:**
1. Rapidly invoke the same tool multiple times
2. Example: Ask chat to analyze emotion 10 times in a row
3. Observe behavior

**Expected Results:**
- ✅ Rate limiter enforces 250ms interval
- ✅ Requests are queued, not rejected
- ✅ All requests eventually complete
- ✅ No error messages to user
- ✅ Telemetry shows rate limiting events

---

### Test 5.4: GitHub Token Missing

**Steps:**
1. Remove `GITHUB_TOKEN` from environment
2. Try to use GitHub tool via chat
3. Example: "List my GitHub repositories"

**Expected Results:**
- ✅ Clear error message about missing token
- ✅ Instructions on how to set GITHUB_TOKEN
- ✅ No crash or undefined behavior
- ✅ Error logged in telemetry

---

### Test 5.5: ULTRA Endpoint Missing (Fallback)

**Steps:**
1. Ensure backend is running but ULTRA endpoints return 404
2. Try semantic ranking: "Rank my repos by relevance to AI"

**Expected Results:**
- ✅ System detects ULTRA unavailable
- ✅ Falls back to heuristic ranking
- ✅ Results still returned (lower quality)
- ✅ Warning logged but no error to user
- ✅ Telemetry shows fallback mode used

---

## Test Suite 6: Performance Validation

### Test 6.1: Backend Round-Trip Latency

**Objective:** Verify response time meets < 500ms requirement

**Steps:**
1. Open browser dev tools or telemetry log
2. Invoke several ML tools via chat
3. Measure time from request to response

**Tools to Test:**
- `ide_agents_ml_analyze_emotion`
- `ide_agents_ml_get_predictions`
- `ide_agents_ml_get_system_status`
- `ide_agents_github_rank_repos`

**Expected Results:**
- ✅ Average response time < 500ms
- ✅ 95th percentile < 1000ms
- ✅ No timeouts (30 second limit)
- ✅ Telemetry shows duration_ms for each call

**Performance Requirement:** < 500ms backend round-trip (Req 2.4)

---

### Test 6.2: Concurrent Tool Invocations

**Steps:**
1. Ask chat agent to perform multiple operations simultaneously
2. Example: "Analyze emotion, get predictions, and list GitHub repos"
3. Observe if operations run in parallel

**Expected Results:**
- ✅ Multiple tools can run concurrently
- ✅ No blocking between independent operations
- ✅ Total time < sum of individual times
- ✅ No race conditions or conflicts

---

### Test 6.3: Memory and CPU Usage

**Steps:**
1. Open Task Manager / Resource Monitor
2. Monitor MCP server process
3. Perform various operations for 5 minutes
4. Check resource usage

**Expected Results:**
- ✅ Memory usage < 200MB
- ✅ CPU usage < 5% when idle
- ✅ CPU spikes < 50% during operations
- ✅ No memory leaks over time
- ✅ Process remains stable

---

## Test Suite 7: Telemetry and Debugging

### Test 7.1: Telemetry Span Recording

**Steps:**
1. Perform various tool invocations
2. Open `logs/mcp_tool_spans.jsonl`
3. Verify span data

**Expected Results:**
- ✅ Each tool invocation creates a span
- ✅ Spans include: timestamp, tool_name, method, duration_ms, success
- ✅ Failed operations include error_code
- ✅ JSON Lines format (one JSON object per line)
- ✅ File is append-only and not corrupted

**Sample Span:**
```json
{
  "timestamp_ms": 1699999999000,
  "tool_name": "ide_agents_ml_analyze_emotion",
  "method": "POST /ai/intelligence/mood/analyze",
  "duration_ms": 145,
  "success": true,
  "error_code": null,
  "extra": {"text_length": 42}
}
```

---

### Test 7.2: Telemetry Usefulness for Debugging

**Steps:**
1. Cause an intentional error (e.g., stop backend)
2. Try to use ML tool
3. Check telemetry log

**Expected Results:**
- ✅ Error span recorded with error_code
- ✅ Timestamp allows correlation with user action
- ✅ Duration shows where timeout occurred
- ✅ Extra data provides debugging context
- ✅ Can trace full request lifecycle

---

### Test 7.3: Telemetry File Rotation

**Steps:**
1. Generate many tool invocations (100+)
2. Check telemetry file size
3. Verify batching behavior

**Expected Results:**
- ✅ Spans are batched (flush every 100 spans or 10 seconds)
- ✅ File doesn't grow unbounded
- ✅ Async writes don't block operations
- ✅ No data loss on server shutdown

---

## Test Suite 8: Configuration Management

### Test 8.1: Environment Variable Substitution

**Steps:**
1. Set `GITHUB_TOKEN` environment variable
2. Use `${GITHUB_TOKEN}` in mcp.json
3. Restart Kiro IDE
4. Try GitHub tool

**Expected Results:**
- ✅ Token is properly substituted
- ✅ GitHub API calls succeed
- ✅ Token not logged in plain text
- ✅ Works with system env vars and .env file

---

### Test 8.2: Disabled Flag

**Steps:**
1. Set `"disabled": true` in mcp.json
2. Restart Kiro IDE
3. Check MCP server status

**Expected Results:**
- ✅ Server does not start
- ✅ No error messages (expected behavior)
- ✅ MCP tools not available in chat
- ✅ IDE functions normally otherwise

**Revert:** Set `"disabled": false` and restart

---

### Test 8.3: Auto-Approve List Customization

**Steps:**
1. Remove `ide_agents_health` from autoApprove list
2. Restart Kiro IDE
3. Try to use health check tool

**Expected Results:**
- ✅ Approval dialog appears (tool no longer auto-approved)
- ✅ Can approve or deny
- ✅ Other auto-approved tools still work without approval

**Revert:** Add `ide_agents_health` back to autoApprove list

---

## Test Suite 9: End-to-End Workflows

### Test 9.1: Complete Development Workflow

**Scenario:** Developer wants AI assistance for code review

**Steps:**
1. Open a file with recent changes
2. Ask chat: "Review my recent changes using the diff review prompt"
3. Chat agent should:
   - Get diff review prompt template
   - Analyze code changes
   - Provide feedback using ML insights

**Expected Results:**
- ✅ Multiple tools used seamlessly
- ✅ No manual intervention required
- ✅ Results are coherent and useful
- ✅ Performance is acceptable

---

### Test 9.2: GitHub Analysis Workflow

**Scenario:** Developer wants to find relevant repositories

**Steps:**
1. Ask chat: "Find my most active repositories from the last month"
2. Chat agent should:
   - List GitHub repos with filters
   - Rank by activity and relevance
   - Present top results

**Expected Results:**
- ✅ GitHub token used correctly
- ✅ Semantic ranking applied (if ULTRA enabled)
- ✅ Results are accurate and relevant
- ✅ Response time acceptable

---

### Test 9.3: Predictive Automation Workflow

**Scenario:** Developer wants AI to suggest next actions

**Steps:**
1. Ask chat: "What should I work on next based on my patterns?"
2. Chat agent should:
   - Get predictions
   - Get learning insights
   - Analyze reasoning
   - Provide personalized suggestions

**Expected Results:**
- ✅ Multiple ML tools used together
- ✅ Suggestions are contextual and relevant
- ✅ Confidence scores help prioritize
- ✅ User can act on suggestions

---

## Test Suite 10: Security Validation

### Test 10.1: Token Security

**Steps:**
1. Check telemetry logs
2. Check IDE output panel
3. Check server logs

**Expected Results:**
- ✅ GITHUB_TOKEN never logged in plain text
- ✅ Sensitive data redacted in logs
- ✅ Token only used for authorized requests
- ✅ No token leakage in error messages

---

### Test 10.2: Approval Gating

**Steps:**
1. Try to execute potentially dangerous command
2. Example: "Delete all files in /tmp"

**Expected Results:**
- ✅ Approval required before execution
- ✅ Clear warning about operation
- ✅ User can review command details
- ✅ Denial prevents execution completely

---

### Test 10.3: Input Sanitization

**Steps:**
1. Try to inject malicious input
2. Example: SQL injection, path traversal, command injection

**Expected Results:**
- ✅ Input validation prevents injection
- ✅ Error message about invalid input
- ✅ No execution of malicious code
- ✅ System remains secure

---

## Test Results Template

Use this template to record test results:

```markdown
## Test Execution Report

**Date:** [YYYY-MM-DD]
**Tester:** [Name]
**Kiro IDE Version:** [Version]
**MCP Server Version:** [Version]
**Backend Version:** [Version]

### Test Suite 1: Server Lifecycle Integration
- [ ] Test 1.1: Auto-Start - PASS / FAIL / SKIP
- [ ] Test 1.2: Clean Shutdown - PASS / FAIL / SKIP
- [ ] Test 1.3: Reconnection - PASS / FAIL / SKIP
- [ ] Test 1.4: Crash Recovery - PASS / FAIL / SKIP

### Test Suite 2: Tool Discovery
- [ ] Test 2.1: Tool Discovery - PASS / FAIL / SKIP
- [ ] Test 2.2: ULTRA Toggle - PASS / FAIL / SKIP
- [ ] Test 2.3: Schema Validation - PASS / FAIL / SKIP

### Test Suite 3: Chat Agent Integration
- [ ] Test 3.1: Emotion Analysis - PASS / FAIL / SKIP
- [ ] Test 3.2: Predictions - PASS / FAIL / SKIP
- [ ] Test 3.3: Learning Insights - PASS / FAIL / SKIP
- [ ] Test 3.4: GitHub Search - PASS / FAIL / SKIP
- [ ] Test 3.5: Resource Access - PASS / FAIL / SKIP
- [ ] Test 3.6: Prompt Templates - PASS / FAIL / SKIP

### Test Suite 4: Approval Workflow
- [ ] Test 4.1: Command Approval - PASS / FAIL / SKIP
- [ ] Test 4.2: Dry Run - PASS / FAIL / SKIP
- [ ] Test 4.3: Auto-Approved - PASS / FAIL / SKIP
- [ ] Test 4.4: Queue Management - PASS / FAIL / SKIP

### Test Suite 5: Error Handling
- [ ] Test 5.1: Backend Unavailable - PASS / FAIL / SKIP
- [ ] Test 5.2: Invalid Arguments - PASS / FAIL / SKIP
- [ ] Test 5.3: Rate Limiting - PASS / FAIL / SKIP
- [ ] Test 5.4: Missing Token - PASS / FAIL / SKIP
- [ ] Test 5.5: ULTRA Fallback - PASS / FAIL / SKIP

### Test Suite 6: Performance
- [ ] Test 6.1: Latency < 500ms - PASS / FAIL / SKIP
- [ ] Test 6.2: Concurrent Operations - PASS / FAIL / SKIP
- [ ] Test 6.3: Resource Usage - PASS / FAIL / SKIP

### Test Suite 7: Telemetry
- [ ] Test 7.1: Span Recording - PASS / FAIL / SKIP
- [ ] Test 7.2: Debugging Usefulness - PASS / FAIL / SKIP
- [ ] Test 7.3: File Rotation - PASS / FAIL / SKIP

### Test Suite 8: Configuration
- [ ] Test 8.1: Env Var Substitution - PASS / FAIL / SKIP
- [ ] Test 8.2: Disabled Flag - PASS / FAIL / SKIP
- [ ] Test 8.3: Auto-Approve List - PASS / FAIL / SKIP

### Test Suite 9: End-to-End Workflows
- [ ] Test 9.1: Code Review - PASS / FAIL / SKIP
- [ ] Test 9.2: GitHub Analysis - PASS / FAIL / SKIP
- [ ] Test 9.3: Predictive Automation - PASS / FAIL / SKIP

### Test Suite 10: Security
- [ ] Test 10.1: Token Security - PASS / FAIL / SKIP
- [ ] Test 10.2: Approval Gating - PASS / FAIL / SKIP
- [ ] Test 10.3: Input Sanitization - PASS / FAIL / SKIP

### Summary
- **Total Tests:** [X]
- **Passed:** [X]
- **Failed:** [X]
- **Skipped:** [X]
- **Pass Rate:** [X%]

### Issues Found
1. [Issue description]
2. [Issue description]

### Recommendations
1. [Recommendation]
2. [Recommendation]
```

---

## Quick Start Checklist

Before starting integration testing:

- [ ] Backend service running: `python mock_backend_server.py`
- [ ] MCP config exists: `.kiro/settings/mcp.json`
- [ ] ULTRA mode enabled: `IDE_AGENTS_ULTRA_ENABLED="true"`
- [ ] GitHub token set: `GITHUB_TOKEN` environment variable
- [ ] Telemetry directory exists: `./logs/`
- [ ] Python dependencies installed: `pip install -r requirements.txt`
- [ ] Kiro IDE updated to latest version

---

## Troubleshooting Common Issues

### Server Won't Start
1. Check Python path in mcp.json
2. Verify dependencies: `pip list`
3. Check IDE output panel for errors
4. Test standalone: `python -m ide_agents_mcp_server`

### Tools Not Appearing
1. Verify ULTRA mode enabled
2. Check server connection status
3. Restart Kiro IDE
4. Check logs for plugin loading errors

### Backend Connection Fails
1. Verify backend running: `curl http://127.0.0.1:8001/health`
2. Check firewall settings
3. Review backend logs
4. Test with mock mode: `IDE_AGENTS_ULTRA_MOCK="true"`

### Performance Issues
1. Check backend response times
2. Review telemetry for slow operations
3. Verify network latency
4. Check resource usage (CPU/memory)

---

## Next Steps

After completing all tests:

1. **Document Results:** Fill out test results template
2. **Report Issues:** Create tickets for any failures
3. **Performance Tuning:** Optimize slow operations
4. **User Feedback:** Gather feedback from beta testers
5. **Production Readiness:** Sign off on deployment

---

**End of Integration Testing Guide**

