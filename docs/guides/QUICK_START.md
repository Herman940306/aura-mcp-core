# Kiro IDE + MCP Server - Quick Start Guide

---
**Project Creator:** Herman Swanepoel  
**Last Updated:** 2025-11-14

---

## 🎯 You Are Here

✅ MCP server configured  
✅ Models configured (15+ models)  
✅ GitHub token set  
✅ Backend service ready  
⏳ **Setting environment variables** ← YOU'RE DOING THIS NOW  

---

## 📝 Exact Variable Names to Set

In Windows Environment Variables (`Win + R` → `sysdm.cpl` → Advanced → Environment Variables):

| Variable Name | Your Key | Required? |
|---------------|----------|-----------|
| `OPENAI_API_KEY` | openAI key | ✅ YES |
| `GITHUB_TOKEN` | GitHub Kiro MCP token | ✅ YES |
| `ANTHROPIC_API_KEY` | Anthropic key | ⭕ Optional |
| `DEEPSEEK_API_KEY` | DeepSeek Key | ⭕ Optional |
| `GOOGLE_API_KEY` | Google Gemini Key | ⭕ Optional |
| `GROQ_API_KEY` | Groq key | ⭕ Optional |

**GitHub Token Value:**
```
your_github_personal_access_token_here
```

---

## 🚀 After Setting Variables

### 1. Close ALL PowerShell windows

### 2. Open NEW PowerShell

### 3. Verify Keys
```powershell
cd F:\Kiro_Projects\mcp_server
python verify_api_keys.py
```

### 4. Start Backend (Keep Running)
```powershell
python mock_backend_server.py
```

### 5. Launch Kiro IDE
- MCP server auto-starts
- Wait 10 seconds for connection

### 6. Test in Kiro Agent
```
Check MCP server health
```

```
Analyze the emotion in: I'm excited!
```

```
List my GitHub repositories
```

---

## ✅ Success Indicators

- ✅ Verification script shows all keys valid
- ✅ Backend shows: "Server running on port 8001"
- ✅ Kiro IDE: MCP Server view shows "Connected"
- ✅ Model selector shows 15+ models
- ✅ Agent responds to MCP commands

---

## 📚 Full Documentation

- **SETUP_COMPLETE_SUMMARY.md** - Complete setup status
- **ENVIRONMENT_VARIABLES_REFERENCE.md** - Variable names
- **KIRO_API_KEYS_SETUP.md** - How to get API keys

---

## 🆘 Quick Troubleshooting

**Keys not found?**
→ Restart PowerShell after setting variables

**Backend not running?**
→ `python mock_backend_server.py`

**MCP not connecting?**
→ Check backend is running, restart Kiro IDE

---

**That's it! Set those variables and you're ready to go! 🎉**

