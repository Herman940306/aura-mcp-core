# KIRO_MCP Monitor Dashboard

**Project Creator:** Herman Swanepoel  
**Version:** 1.0  
**Last Updated:** 2025-11-15

---

## Overview

The KIRO_MCP Monitor Dashboard provides real-time monitoring and diagnostics for your MCP (Model Context Protocol) server and AI intelligence backend.

## Features

- 🚀 **MCP Server Status** - Real-time health monitoring
- 🧠 **AI Intelligence System** - Backend service connectivity
- 📊 **Telemetry Statistics** - Tool invocation analytics
- 💻 **System Resources** - CPU, Memory, and Disk usage
- 🔄 **Auto-Refresh** - Updates every 5 seconds
- 🎨 **Color-Coded Status** - Easy visual identification

## Quick Start

### Option 1: Desktop Shortcut (Recommended)

1. Run `setup_mcp_monitor.bat`
2. Double-click "KIRO_MCP Monitor" on your desktop

### Option 2: Batch File

1. Double-click `launch_mcp_monitor.bat`

### Option 3: Command Line

```bash
python mcp_monitor_dashboard.py
```

## Installation

### Automatic Setup

Run the setup script to install everything automatically:

```bash
setup_mcp_monitor.bat
```

This will:
1. Check Python installation
2. Install required packages (requests, psutil, Pillow)
3. Create the monitor icon
4. Create a desktop shortcut

### Manual Setup

If you prefer manual installation:

```bash
# Install dependencies
pip install requests psutil Pillow

# Create icon
python create_icon.py

# Create desktop shortcut
powershell -ExecutionPolicy Bypass -File create_desktop_shortcut.ps1

# Launch monitor
python mcp_monitor_dashboard.py
```

## Requirements

- Python 3.7 or higher
- Required packages:
  - `requests` - HTTP client for backend communication
  - `psutil` - System resource monitoring
  - `Pillow` - Icon creation (optional)

## Configuration

The monitor reads configuration from environment variables:

- `IDE_AGENTS_BACKEND_URL` - Backend service URL (default: `http://127.0.0.1:8001`)

You can set these in your `.env` file or system environment.

## Dashboard Sections

### 🚀 MCP Server Status

Shows the health and connectivity of your MCP server:
- ✅ **ONLINE** - Server is running and responsive
- ❌ **OFFLINE** - Server is not reachable
- ⏱️ **TIMEOUT** - Server is slow to respond
- Response time in milliseconds

### 🧠 AI Intelligence System

Monitors the backend AI service:
- Emotion detection engine
- Predictive engine
- Reasoning engine
- Personality engine
- Learning analytics

### 📊 Telemetry Statistics

Analyzes tool invocation data:
- Total invocations
- Success/failure counts
- Success rate percentage
- Average response duration
- Top 5 most-used tools

### 💻 System Resources

Real-time system metrics:
- CPU usage (%)
- Memory usage (%)
- Disk usage (%)

Color coding:
- 🟢 **Green** - Normal (< 50% CPU, < 70% Memory, < 80% Disk)
- 🟡 **Yellow** - Warning (50-80% CPU, 70-85% Memory, 80-90% Disk)
- 🔴 **Red** - Critical (> 80% CPU, > 85% Memory, > 90% Disk)

## Keyboard Shortcuts

- `Ctrl+C` - Exit the monitor

## Troubleshooting

### Monitor shows "OFFLINE"

1. Check if the backend service is running:
   ```bash
   curl http://127.0.0.1:8001/health
   ```

2. Verify the backend URL in your configuration

3. Check firewall settings

### No telemetry data

1. Ensure `logs/mcp_tool_spans.jsonl` exists
2. Verify MCP server is configured to write telemetry
3. Check file permissions

### Python not found

1. Install Python from https://www.python.org/
2. Add Python to your system PATH
3. Restart your terminal/command prompt

### Desktop shortcut not working

1. Right-click the shortcut → Properties
2. Verify "Target" points to Python executable
3. Verify "Start in" points to the correct directory
4. Try running `launch_mcp_monitor.bat` instead

## Files

- `mcp_monitor_dashboard.py` - Main dashboard script
- `launch_mcp_monitor.bat` - Quick launch batch file
- `setup_mcp_monitor.bat` - Automated setup script
- `create_desktop_shortcut.ps1` - PowerShell script for shortcut creation
- `create_icon.py` - Icon generator script
- `mcp_monitor_icon.ico` - Monitor icon file
- `MCP_MONITOR_README.md` - This file

## Advanced Usage

### Custom Refresh Interval

Edit `mcp_monitor_dashboard.py` and change:

```python
REFRESH_INTERVAL = 5  # seconds
```

### Custom Backend URL

Set environment variable before launching:

```bash
set IDE_AGENTS_BACKEND_URL=http://your-backend:8001
python mcp_monitor_dashboard.py
```

### Telemetry File Location

Edit `mcp_monitor_dashboard.py` and change:

```python
TELEMETRY_FILE = Path("logs/mcp_tool_spans.jsonl")
```

## Integration with KIRO_MCP

The monitor is designed to work seamlessly with the KIRO_MCP server:

1. Monitors the backend service on port 8001
2. Reads telemetry from `logs/mcp_tool_spans.jsonl`
3. Checks ULTRA intelligence features
4. Displays real-time tool usage statistics

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review `MCP_INTEGRATION_GUIDE.md`
3. Check `MCP_TROUBLESHOOTING.md`
4. Review backend service logs

## License

Part of the KIRO_MCP project by Herman Swanepoel.

---

**Enjoy monitoring your KIRO_MCP server! 🚀**
