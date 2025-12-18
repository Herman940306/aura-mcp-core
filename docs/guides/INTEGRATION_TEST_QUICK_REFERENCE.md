# MCP Integration Testing - Quick Reference Card

---
**Project Creator:** Herman Swanepoel  
**Version:** 1.0  
**Last Updated:** 2025-11-14

---

## 🚀 Quick Start (5 Minutes)

### 1. Start Backend Service
```bash
python mock_backend_server.py
```
**Expected:** Server running on http://127.0.0.1:8001

### 2. Verify MCP Configuration
```bash
type .kiro\settings\mcp.json
```
**Check:** `"disabled": false` and `"IDE_AGENTS_ULTRA_ENABLED": "true"`

### 3. Launch Kiro IDE
- Open Kiro IDE
- Wait 10 seconds for MCP server to connect
- Check MCP Server view shows "Connected"

### 4. Test Basic Tool
**Chat Prompt:** "Check MCP server health"
**Expected:** Returns server status with version info

---

## 🎯 Essential Test Commands

### Health Check
```
Check the MCP server health status
```
**Tool:** `ide_agents_health`  
**Expected:** Status OK, version info, flags

### Emotion Analysis
```
Analyze the emotion in: "I love this new feature!"
```
**Tool:** `ide_agents_ml_analyze_emotion`  
**Expected:** Mood "happy", confidence > 0.8

### Predictions
```
Show me AI predictions for my routines
```
**Tool:** `ide_agents_ml_get_predictions`  
**Expected:** List of predictions with confidence scores

### GitHub Search
```
Find my GitHub repositories related to Python
```
**Tool:** `ide_agents_github_rank_repos`  
**Expected:** Ranked list of relevant repos

### Resource Access
```
Show me the project structure from repo.graph
```
**Tool:** `ide_agents_resource`  
**Expected:** Repository graph JSON content

### Command Execution (Approval Test)
```
Run this command: echo "Hello MCP"
```
**Tool:** `ide_agents_command`  
**Expected:** Approval dialog appears

---

## ✅ Critical Success Criteria

| Requirement | Target | How to Verify |
|-------------|--------|---------------|
| Server Startup | < 10 seconds | Time from IDE launch to "Connected" |
| Backend Latency | < 500ms | Check telemetry duration_ms |
| Tool Count (ULTRA) | 23+ tools | Count tools in MCP panel |
| Auto-Approval | No prompts for read-only | Test emotion analysis |
| Approval Gating | Prompt for commands | Test command execution |
| Error Handling | User-friendly messages | Stop backend, try ML tool |
| Telemetry | All calls logged | Check logs/mcp_tool_spans.jsonl |
| Clean Shutdown | No orphaned processes | Close IDE, check task manager |

---

## 🔍 Quick Diagnostics

### Server Not Starting?
```bash
# Test standalone
python -m ide_agents_mcp_server

# Check dependencies
pip list | findstr fastmcp

# View logs
type logs\mcp_server_lifecycle.log
```

### Backend Not Responding?
```bash
# Test health endpoint
curl http://127.0.0.1:8001/health

# Check if running
netstat -ano | findstr 8001
```

### Tools Not Appearing?
1. Check ULTRA mode: `IDE_AGENTS_ULTRA_ENABLED="true"`
2. Restart Kiro IDE
3. Check server status in MCP panel
4. Review IDE output panel for errors

### Performance Issues?
```bash
# Check telemetry
type logs\mcp_tool_spans.jsonl | findstr duration_ms

# Monitor resources
tasklist | findstr python
```

---

## 📊 Test Coverage Matrix

| Category | Tests | Priority | Time |
|----------|-------|----------|------|
| Server Lifecycle | 4 | HIGH | 10 min |
| Tool Discovery | 3 | HIGH | 5 min |
| Chat Integration | 6 | HIGH | 15 min |
| Approval Workflow | 4 | HIGH | 10 min |
| Error Handling | 5 | MEDIUM | 15 min |
| Performance | 3 | MEDIUM | 10 min |
| Telemetry | 3 | LOW | 5 min |
| Configuration | 3 | LOW | 5 min |
| End-to-End | 3 | HIGH | 20 min |
| Security | 3 | MEDIUM | 10 min |
| **TOTAL** | **37** | - | **~2 hours** |

---

## 🐛 Common Issues & Fixes

### Issue: "Backend service unavailable"
**Fix:** Start backend: `python mock_backend_server.py`

### Issue: "GITHUB_TOKEN not found"
**Fix:** Set environment variable: `set GITHUB_TOKEN=your_token_here`

### Issue: ML tools missing
**Fix:** Enable ULTRA in config: `"IDE_AGENTS_ULTRA_ENABLED": "true"`

### Issue: Approval dialog not appearing
**Fix:** Remove tool from autoApprove list in mcp.json

### Issue: Slow response times
**Fix:** Check backend logs, verify network latency, review telemetry

### Issue: Server crashes on startup
**Fix:** Check Python version (3.11+), verify dependencies, review logs

---

## 📝 Test Result Recording

### Quick Pass/Fail Template
```
Date: [YYYY-MM-DD]
Tester: [Name]

✅ Server starts automatically
✅ Tools discovered (23+ with ULTRA)
✅ Emotion analysis works
✅ GitHub search works
✅ Approval workflow works
✅ Error handling graceful
✅ Performance < 500ms
✅ Telemetry recorded
✅ Clean shutdown

❌ [Any failures]

Issues: [List any problems]
```

---

## 🎓 Testing Tips

1. **Start Simple:** Test health check first
2. **Check Logs:** Telemetry is your friend
3. **Test Failures:** Intentionally break things to verify error handling
4. **Performance:** Use telemetry to identify slow operations
5. **Security:** Verify tokens never logged
6. **Real Usage:** Test actual developer workflows
7. **Document:** Record all issues with reproduction steps

---

## 📞 Support Resources

- **Full Test Guide:** `KIRO_IDE_INTEGRATION_TEST_GUIDE.md`
- **MCP Integration Guide:** `MCP_INTEGRATION_GUIDE.md`
- **Tool Usage Examples:** `TOOL_USAGE_EXAMPLES.md`
- **Deployment Guide:** `DEPLOYMENT_GUIDE.md`
- **Telemetry Logs:** `logs/mcp_tool_spans.jsonl`
- **Server Logs:** `logs/mcp_server_lifecycle.log`

---

## 🎯 Success Checklist

Before signing off on integration:

- [ ] All 37 tests executed
- [ ] Pass rate > 95%
- [ ] Performance requirements met
- [ ] Security validation passed
- [ ] Error handling verified
- [ ] Telemetry useful for debugging
- [ ] Documentation complete
- [ ] User feedback positive
- [ ] Production deployment approved

---

**End of Quick Reference**

