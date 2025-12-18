# MCP Integration Troubleshooting

---
**Issue:** "Command 'MCP: Browse Servers' resulted in an error"  
**Status:** MCP server configured but not connecting to Kiro IDE

---

## Current Status

✅ **Backend:** Running on port 8001  
✅ **API Keys:** All 6 loaded correctly  
✅ **MCP Config:** Valid JSON in both user and workspace  
✅ **MCP Server Module:** Can be imported  
⚠️ **MCP Connection:** Not established with Kiro IDE  

## Possible Causes

1. **Kiro IDE version doesn't support MCP** - Feature might be in beta
2. **MCP server not auto-starting** - Needs manual launch
3. **Python path issue** - Kiro can't find Python
4. **Working directory issue** - Server needs to run from project root

---

## Solution 1: Manual MCP Server Launch (Recommended)

Instead of relying on auto-start, launch the MCP server manually:

### Step 1: Open a NEW PowerShell window

### Step 2: Navigate to project
```powershell
cd F:\Kiro_Projects\mcp_server
```

### Step 3: Start MCP server manually
```powershell
python -m ide_agents_mcp_server
```

### Step 4: Keep it running
- Don't close this window
- Server will listen on stdio
- Kiro IDE should detect it

### Step 5: Restart Kiro IDE
- Close Kiro IDE completely
- Reopen it
- It should connect to the running server

---

## Solution 2: Use Absolute Python Path

Update the MCP config to use absolute Python path:

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "C:\\Users\\herma\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["-m", "ide_agents_mcp_server"],
      "cwd": "F:\\Kiro_Projects\\mcp_server",
      ...
    }
  }
}
```

---

## Solution 3: Check Kiro IDE Version

The MCP feature might be:
- In beta/preview
- Requires specific Kiro IDE version
- Needs to be enabled in settings

### Check Kiro IDE Settings:
1. Open Settings (Ctrl+,)
2. Search for "MCP"
3. Look for any MCP-related settings
4. Enable if disabled

---

## Solution 4: Alternative - Use Tools Directly

Even if the "Browse Servers" UI doesn't work, the tools might still be available.

### Test in Kiro Chat:

**Test 1:**
```
What tools and capabilities do you have?
```

**Test 2:**
```
Can you analyze the emotion in this text: "I'm excited about this project!"
```

**Test 3:**
```
List my GitHub repositories
```

If these work, the MCP server IS connected, just the UI command is missing.

---

## Diagnostic Commands

### Check if MCP server process is running:
```powershell
Get-Process python | Where-Object {$_.CommandLine -like "*ide_agents_mcp_server*"}
```

### Check Python path:
```powershell
where.exe python
```

### Test MCP server standalone:
```powershell
cd F:\Kiro_Projects\mcp_server
python -m ide_agents_mcp_server
# Press Ctrl+C to stop
```

### Check Kiro IDE logs:
Look in Kiro IDE Output panel for MCP-related messages

---

## What to Try Next

1. **Try Solution 4 first** - Test if tools work in chat
2. **If not, try Solution 1** - Manual server launch
3. **If still not working, try Solution 2** - Absolute paths
4. **Check Kiro IDE version** - Might need update

---

## Expected Behavior When Working

When MCP is properly connected:

✅ Kiro agent can use MCP tools in responses  
✅ Tools appear in tool list (if UI available)  
✅ Agent responds to: "Check MCP server health"  
✅ Emotion analysis works  
✅ GitHub integration works  

---

## Alternative: Direct API Usage

If MCP integration doesn't work, you can still use the backend directly:

```python
import httpx

# Emotion analysis
response = httpx.post(
    "http://127.0.0.1:8001/ai/intelligence/mood/analyze",
    json={"text": "I'm excited!"}
)
print(response.json())
```

---

**Next Step:** Try the commands in Solution 4 in your Kiro chat and let me know what happens!

