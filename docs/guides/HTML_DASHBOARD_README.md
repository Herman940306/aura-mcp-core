`# KIRO_MCP HTML Dashboard - GODMODE

**Project Creator:** Herman Swanepoel  
**Version:** 1.0  
**Last Updated:** 2025-11-15

---

## 🚀 Quick Start

### Option 1: One-Click Launch (Recommended)

```bash
launch_dashboard.bat
```

This will:
1. Start the dashboard API server
2. Open the HTML dashboard in your browser
3. Auto-refresh every 5 seconds

### Option 2: Manual Launch

```bash
# Terminal 1: Start the API server
python mcp_dashboard_server.py

# Terminal 2 or Browser: Open the dashboard
start mcp_monitor_dashboard.html
```

---

## 🎨 Features

### ⚙️ ULTRA Intelligence Controls

Toggle switches for real-time control of AI features:

- **🧠 ULTRA Mode** - Enable/disable advanced ML intelligence
- **🎯 Semantic Ranking** - Use ULTRA semantic ranking for GitHub
- **🔮 Predictions** - AI predictions and suggestions
- **😊 Emotion Detection** - Analyze emotional tone
- **🎓 Learning Analytics** - Track user patterns (coming soon)
- **🎭 Adaptive Personality** - Dynamic AI personality (coming soon)

### 📊 Real-Time Monitoring

- **🚀 MCP Server Status** - Health and response time
- **🧠 AI Intelligence System** - Active engines count
- **💻 System Resources** - CPU, Memory, Disk usage (coming soon)
- **📈 Telemetry Statistics** - Tool usage analytics (coming soon)

### 🎯 Theme Colors

- Primary Background: `#1a1a2e`
- Secondary Background: `#16213e`
- Tertiary Background: `#0f3460`
- Accent Cyan: `#00d4ff`
- Accent Bright: `#00ffff`
- Success: `#00ff00`
- Warning: `#ffaa00`
- Danger: `#ff0044`

---

## 📁 Files

### Core Files

- `mcp_monitor_dashboard.html` - Main HTML dashboard
- `mcp_dashboard_server.py` - Flask API backend
- `launch_dashboard.bat` - One-click launcher

### Setup Files

- `setup_mcp_monitor.bat` - Complete setup script
- `create_html_dashboard_shortcut.ps1` - Desktop shortcut creator
- `HTML_DASHBOARD_README.md` - This file

---

## 🔧 API Endpoints

The dashboard server provides these REST API endpoints:

### Health & Status

```
GET /api/health
GET /api/mcp/status
GET /api/ai/status
```

### System Monitoring

```
GET /api/system/resources
GET /api/telemetry/stats
```

### Settings Management

```
GET /api/settings
POST /api/settings
```

---

## ⚙️ Configuration

### Environment Variables

The dashboard reads from `.env` file:

```env
IDE_AGENTS_BACKEND_URL=http://127.0.0.1:8001
IDE_AGENTS_ULTRA_ENABLED=true
IDE_AGENTS_SEMANTIC_RANKING=true
IDE_AGENTS_PREDICTIONS=true
IDE_AGENTS_EMOTION_DETECTION=true
IDE_AGENTS_LEARNING_ANALYTICS=true
IDE_AGENTS_ADAPTIVE_PERSONALITY=false
```

### Ports

- **Dashboard API:** `http://localhost:5000`
- **MCP Backend:** `http://localhost:8001`

---

## 🎮 Usage

### Toggle ULTRA Features

1. Open the dashboard
2. Use the toggle switches in the "ULTRA CONTROLS" section
3. Click "💾 APPLY SETTINGS"
4. Settings are saved to `.env` file

### Monitor Status

The dashboard auto-refreshes every 5 seconds showing:
- MCP server online/offline status
- Response times
- Active AI engines
- System resources

### Apply Settings

Settings are applied in real-time:
1. Toggle switches update immediately in UI
2. Click "APPLY SETTINGS" to persist to `.env`
3. Backend services pick up changes automatically

---

## 🔍 Troubleshooting

### Dashboard shows "OFFLINE"

**Problem:** MCP server not running

**Solution:**
```bash
# Check if backend is running
curl http://127.0.0.1:8001/health

# Start backend if needed
python main.py  # or your backend start command
```

### Dashboard won't load

**Problem:** API server not running

**Solution:**
```bash
# Start the dashboard server
python mcp_dashboard_server.py

# Or use the launcher
launch_dashboard.bat
```

### Toggle switches don't work

**Problem:** API server not responding

**Solution:**
1. Check console for errors
2. Verify API server is running on port 5000
3. Check browser console (F12) for errors

### Settings not persisting

**Problem:** `.env` file permissions or missing

**Solution:**
```bash
# Create .env file if missing
echo IDE_AGENTS_BACKEND_URL=http://127.0.0.1:8001 > .env

# Check file permissions
icacls .env
```

---

## 🚀 Advanced Usage

### Custom Backend URL

Edit `mcp_dashboard_server.py`:

```python
BACKEND_URL = os.getenv("IDE_AGENTS_BACKEND_URL", "http://your-backend:8001")
```

### Custom Dashboard Port

Edit `mcp_dashboard_server.py`:

```python
app.run(host='0.0.0.0', port=5000, debug=False)  # Change port here
```

Then update `mcp_monitor_dashboard.html`:

```javascript
const API_URL = 'http://localhost:5000/api';  // Update port here
```

### Add Custom Metrics

1. Add endpoint in `mcp_dashboard_server.py`:

```python
@app.route('/api/custom/metric', methods=['GET'])
def custom_metric():
    return jsonify({"value": 42})
```

2. Add UI in `mcp_monitor_dashboard.html`:

```html
<div class="metric">
    <div class="metric-label">Custom Metric</div>
    <div class="metric-value" id="custom-metric">--</div>
</div>
```

3. Add JavaScript to fetch:

```javascript
async function updateCustomMetric() {
    const response = await fetch(`${API_URL}/custom/metric`);
    const data = await response.json();
    document.getElementById('custom-metric').textContent = data.value;
}
```

---

## 📦 Dependencies

### Python Packages

```bash
pip install flask flask-cors psutil requests
```

### Browser Requirements

- Modern browser with JavaScript enabled
- Support for CSS Grid and Flexbox
- Fetch API support

---

## 🎯 Roadmap

### Coming Soon

- [ ] Real-time telemetry charts
- [ ] Tool usage heatmap
- [ ] Performance metrics graphs
- [ ] Alert notifications
- [ ] Dark/Light theme toggle
- [ ] Export settings to JSON
- [ ] Import settings from JSON
- [ ] Multi-language support

### Future Enhancements

- [ ] WebSocket for real-time updates
- [ ] Historical data visualization
- [ ] Predictive analytics dashboard
- [ ] Custom widget system
- [ ] Mobile-responsive design
- [ ] PWA support

---

## 🤝 Integration

### With KIRO_MCP Server

The dashboard integrates seamlessly with KIRO_MCP:

1. Monitors backend health
2. Controls ULTRA features
3. Displays telemetry data
4. Manages settings

### With Other Tools

- **Prometheus:** Export metrics endpoint (coming soon)
- **Grafana:** Dashboard templates (coming soon)
- **Slack:** Alert notifications (coming soon)

---

## 📝 License

Part of the KIRO_MCP project by Herman Swanepoel.

---

## 🎉 Enjoy Your Dashboard!

**Double-click "KIRO_MCP Dashboard" on your desktop to get started!**

For support, check:
- `MCP_INTEGRATION_GUIDE.md`
- `MCP_TROUBLESHOOTING.md`
- Backend service logs

---

**Project Creator:** Herman Swanepoel  
**Version:** 1.0  
**Last Updated:** 2025-11-15
