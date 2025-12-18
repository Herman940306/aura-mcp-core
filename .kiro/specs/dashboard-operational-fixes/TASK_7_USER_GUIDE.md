# 👥 TASK 7.3 - USER GUIDE & ADMINISTRATION

**Status**: USER GUIDE COMPLETE  
**Version**: 1.0  
**Date**: December 13, 2025

---

## 🎯 Quick Start Guide

### Accessing the Dashboard

1. **Open your browser** to: `http://{{NAS_IP}}:9205/`
2. **Dashboard loads** with real-time data streaming
3. **Features automatically enable** when services are ready
4. **Real-time updates** appear automatically in each panel

### Connection Status

- **Green icon**: Connected and receiving real-time updates
- **Yellow icon**: Attempting to reconnect
- **Red icon**: Disconnected (data will cache when reconnected)

---

## 📊 Dashboard Panels Overview

### 1. AI System Panel

**What it shows**:

- All currently loaded AI models
- Model memory usage (RAM)
- Inference speed (tokens/second)
- Active user sessions per model
- Model load/unload status

**How to use**:

```
1. Click "AI System" tab
2. View loaded models in the list
3. Check memory usage per model
4. Monitor active sessions
5. Click "Load Model" to load additional models (if available)
```

**Real-time Updates**:

- Model status updates every 3 seconds
- Inference performance updates every 500ms
- Session count updates in real-time

**Example Metrics**:

```
Model: Llama 3
├─ Status: Loaded ✅
├─ Memory: 4.0 GB / 8.0 GB (50%)
├─ Inference: 45.2 tokens/sec
└─ Sessions: 3 active
```

---

### 2. Governance Panel

**What it shows**:

- Role hierarchy visualization
- User role assignments
- Capabilities per role
- Trust levels
- Audit log of role changes

**How to use**:

```
1. Click "Governance" tab
2. View role hierarchy tree
3. Expand role to see members
4. Check role capabilities
5. Browse audit logs below
```

**Role Hierarchy Example**:

```
Administrator (1.0 trust) [2 members]
├─ Developer (0.8 trust) [15 members]
│  └─ Developer Junior (0.6 trust) [8 members]
└─ Reviewer (0.7 trust) [5 members]
   └─ Developer (0.8 trust) [15 members]
```

**Audit Log**:

- Timestamp of each role change
- Who made the change
- What role was affected
- Success/failure status

**Real-time Updates**:

- Role changes appear immediately
- Audit logs update as events occur
- New members visible in tree

---

### 3. Intelligence Arena

**What it shows**:

- Model vs Model debate matchups
- Win rates per model
- Historical debate statistics
- Model rankings
- Recent debate outcomes

**How to use**:

```
1. Click "Intelligence Arena" tab
2. View models ranked by win rate
3. Click model for detailed stats
4. View recent debates and outcomes
5. Compare model performance
```

**Model Ranking Display**:

```
Rank | Model        | Debates | Win Rate | Avg Score
-----|--------------|---------|----------|----------
  1  | Llama 3      |   145   |  62.1%   |   8.5/10
  2  | Mistral      |   132   |  58.3%   |   8.2/10
  3  | GPT-4        |   128   |  71.9%   |   9.1/10
```

**Real-time Updates**:

- Win rates update after each debate
- New debates appear immediately
- Rankings recalculate in real-time

---

### 4. Omni Monitor

**What it shows**:

- CPU usage percentage and frequency
- Memory usage (used/total)
- Disk space (used/total)
- Network statistics (sent/received)
- GPU metrics (if GPU available)
- System temperature

**How to use**:

```
1. Click "Omni Monitor" tab
2. View system metrics updating in real-time
3. Watch for alerts (red = high)
4. Check thresholds: CPU 80%, RAM 85%, Disk 90%
5. Monitor GPU memory if GPU available
```

**System Metrics Display**:

```
CPU Usage:        45% ▬▬▬░░░░░░░░
Memory:           62% ▬▬▬▬▬▬░░░░░
Disk:             45% ▬▬▬░░░░░░░░
Network: 125 MB/s (sent) ↑ 245 MB/s (received) ↓
GPU:              75% ▬▬▬▬▬▬▬░░░░
Temperature:      45°C ✅
```

**Alert Conditions**:

- CPU > 85% = 🔴 Red alert
- Memory > 90% = 🔴 Red alert
- Disk > 95% = 🔴 Red alert

**Real-time Updates**:

- Metrics update every second
- Graphs show 5-minute history
- Alerts trigger on threshold breach

---

### 5. Chat System

**What it shows**:

- Chat input and message history
- Message timestamps and status
- Response latency
- Queue position when busy
- Current model being used

**How to use**:

```
1. Click "Chat" tab or use main chat input
2. Type your message
3. Press Enter or click Send
4. Wait for response (typically < 100ms)
5. Response appears with timestamp
```

**Chat Modes**:

```
Standard Mode:   Generic responses, balanced quality
Expert Mode:     Optimized for technical questions
Creative Mode:   More creative and diverse responses
```

**Response Display**:

```
User: What is machine learning?
└─ 34ms response
   Model: Llama 3
   Response: "Machine learning is..."
```

**Queue Status**:

```
Your position: 3
Estimated wait: 15 seconds
Model: Llama 3 (45 tokens/sec)
```

**Real-time Updates**:

- Message status updates immediately
- Typing indicators show in real-time
- Response latency visible
- Queue position updates

---

## 🔧 Configuration Guide

### Enabling/Disabling Features

**Edit .env file**:

```bash
nano /app/aura_ia_mcp/.env

# WebSocket features
FEATURE_REAL_TIME_UPDATES=true          # Enable/disable real-time updates
FEATURE_WEBSOCKET_FALLBACK=true         # Enable/disable polling fallback

# Monitoring features
FEATURE_SYSTEM_MONITORING=true          # Enable/disable system metrics
FEATURE_DATABASE_MONITORING=true        # Enable/disable database monitoring
ENABLE_GPU_MONITORING=false             # Enable/disable GPU monitoring
ENABLE_TEMPERATURE_MONITORING=false     # Enable/disable temperature

# Panel features
FEATURE_GOVERNANCE_PANEL=true
FEATURE_AI_SYSTEM_PANEL=true
FEATURE_INTELLIGENCE_ARENA=true
FEATURE_OMNI_MONITOR=true
FEATURE_CHAT_OPTIMIZATION=true
```

**Apply Changes**:

```bash
docker compose down
docker compose up -d
```

---

### Setting Update Intervals

**Edit config/dashboard_config.yaml**:

```yaml
updates:
  # Interval in milliseconds
  system_metrics: 1000      # 1 second
  gpu_metrics: 2000         # 2 seconds
  database_metrics: 5000    # 5 seconds
  model_status: 3000        # 3 seconds
  chat_status: 500          # 500 milliseconds
```

**Recommended Settings**:

- **High Performance**: Shorter intervals (500ms)
- **Balanced**: Default intervals (1-5s)
- **Low Bandwidth**: Longer intervals (10-30s)

---

### Monitoring Thresholds

**Edit config/dashboard_config.yaml**:

```yaml
monitoring:
  thresholds:
    cpu_percent: 80         # Alert at 80% CPU
    memory_percent: 85      # Alert at 85% RAM
    disk_percent: 90        # Alert at 90% Disk
    gpu_percent: 80         # Alert at 80% GPU
    temperature_c: 85       # Alert at 85°C
```

---

## 🚨 Troubleshooting

### Dashboard Won't Load

**Symptom**: Page shows blank or "Connection failed"

**Solutions**:

1. Check browser console (F12) for errors
2. Verify service is running: `docker compose ps`
3. Test endpoint: `curl http://{{NAS_IP}}:9200/healthz`
4. Check firewall: Allow port 9200, 9201

**Recovery**:

```bash
docker compose logs -f aura-ia-gateway
docker compose restart aura-ia-gateway
```

### Real-time Updates Not Working

**Symptom**: Dashboard data not updating, shows "Connecting..."

**Solutions**:

1. Check WebSocket connection: Browser DevTools → Network → WS
2. Verify WebSocket is enabled: `grep FEATURE_REAL_TIME_UPDATES .env`
3. Check firewall allows WebSocket port 8000
4. Restart services: `docker compose restart`

**Test WebSocket**:

```bash
wscat -c ws://{{NAS_IP}}:9200/ws/models
# Should show: {"type": "model_status", ...}
```

### High Memory Usage

**Symptom**: Dashboard becomes slow, system unresponsive

**Solutions**:

1. Reduce update frequency in config
2. Disable GPU monitoring if not needed
3. Reduce history window size
4. Clear browser cache

**Check Memory**:

```bash
docker stats aura-ia-gateway
# Look for MEMORY column
```

### Slow Chat Responses

**Symptom**: Chat responses take > 500ms

**Solutions**:

1. Check system CPU usage: `curl http://{{NAS_IP}}:9200/api/system/metrics`
2. Check model is loaded: Click "AI System" panel
3. Reduce concurrent users
4. Load faster model if available

**Optimize**:

```bash
# Check queue
curl http://localhost:9200/api/queue/status

# Check model performance
curl http://localhost:9200/api/models/status
```

### GPU Not Showing Metrics

**Symptom**: GPU section shows "N/A" or "unavailable"

**Solutions**:

1. Set `ENABLE_GPU_MONITORING=false` if no GPU
2. Install NVIDIA drivers if GPU available
3. Verify GPUtil installation
4. Check system has compatible GPU

**Check GPU**:

```bash
python -c "
try:
    import GPUtil
    gpus = GPUtil.getGPUs()
    for gpu in gpus:
        print(f'GPU {gpu.id}: {gpu.name}')
except Exception as e:
    print(f'GPU error: {e}')
"
```

---

## 📈 Performance Tips

### For Better Dashboard Performance

1. **Reduce Update Frequency**
   - Set intervals to 2000-5000ms instead of 500ms
   - Reduces network traffic and CPU usage

2. **Disable Unused Features**
   - Disable GPU monitoring if not needed
   - Disable temperature monitoring if unavailable
   - Disable database monitoring if not needed

3. **Optimize Browser**
   - Close other tabs
   - Clear browser cache
   - Update browser to latest version
   - Use hardware acceleration

4. **Upgrade Server Resources**
   - Increase Docker memory limit
   - Increase number of CPU cores
   - Ensure sufficient disk space
   - Use SSD for database

---

## 🔒 Security Best Practices

### Dashboard Access

1. **Firewall Rules**

   ```bash
   # Allow only trusted IPs
   ufw allow from 192.168.1.0/24 to any port 9205
   ```

2. **HTTPS Setup**

   ```bash
   # Configure SSL certificates
   # Update dashboard config with wss:// instead of ws://
   ```

3. **Authentication**
   - Implement API key authentication
   - Use GITHUB_TOKEN for authorization
   - Log all access attempts

### Data Protection

1. **Backup Strategy**

   ```bash
   # Backup PostgreSQL
   docker exec aura-ia-postgres pg_dump > backup.sql
   ```

2. **Audit Logging**
   - All role changes logged
   - Access events tracked
   - Errors recorded

3. **Data Privacy**
   - Mask sensitive data in logs
   - Encrypt data in transit (HTTPS/WSS)
   - Implement data retention policies

---

## 📱 Mobile Usage

### Accessing Dashboard on Mobile

1. Open browser on mobile device
2. Navigate to: `http://{{NAS_IP}}:9205/`
3. Dashboard auto-detects mobile layout
4. Touch controls work for interactions

### Mobile Features

- ✅ Responsive design (375px - 1920px)
- ✅ Touch-friendly buttons
- ✅ Landscape and portrait support
- ✅ Mobile-optimized charts
- ✅ Efficient network usage

### Mobile Optimization

```
Low Bandwidth Mode:
1. Go to Settings (if available)
2. Enable "Low Bandwidth"
3. Update intervals increase to 5-10s
4. Disable GPU/temperature monitoring
5. Smaller chart history window
```

---

## 🎓 Common Use Cases

### Monitoring AI Model Performance

```
1. Open "Intelligence Arena" tab
2. Observe model win rates
3. Check recent debate outcomes
4. Identify best performing model
5. Load that model in "AI System" panel
```

### Tracking System Health

```
1. Open "Omni Monitor" tab
2. Watch CPU, memory, disk metrics
3. Look for alert conditions (red)
4. If alerts appear, reduce load
5. Check logs if issue persists
```

### Managing User Access

```
1. Open "Governance" tab
2. View role hierarchy
3. Check member assignments
4. Review audit log for changes
5. Verify security compliance
```

### Debugging Chat Issues

```
1. Open "Chat" tab
2. Send test message
3. Check response latency
4. Verify model in use
5. Check "AI System" panel for model status
```

---

## 📞 Support Resources

### Getting Help

| Issue | Resource |
|-------|----------|
| Dashboard won't load | See "Troubleshooting" section |
| WebSocket connection | Check browser console (F12) |
| Performance issues | Monitor system metrics |
| Feature not working | Check feature flag in .env |
| Data not updating | Verify services running |

### Useful Commands

```bash
# Check all services running
docker compose ps

# View logs
docker compose logs -f aura-ia-gateway
docker compose logs -f aura-ia-ml

# Restart services
docker compose restart

# Restart specific service
docker compose restart aura-ia-gateway

# View health status
curl http://{{NAS_IP}}:9200/healthz

# Check system metrics
curl http://{{NAS_IP}}:9200/api/system/metrics
```

### Contact Information

For issues not covered in this guide:

1. Check logs: `docker compose logs | grep error`
2. Review configuration: `cat .env`
3. Verify services: `docker compose ps`
4. Restart if needed: `docker compose restart`

---

## 🔄 Regular Maintenance

### Daily Tasks

- Monitor dashboard for alerts
- Check system performance
- Review chat response times

### Weekly Tasks

- Review audit logs
- Check database size
- Monitor error rates

### Monthly Tasks

- Backup database
- Review and rotate logs
- Update models if needed
- Check Docker image versions

### Quarterly Tasks

- Security audit
- Performance optimization
- Update system packages
- Review resource allocation

---

## 📚 Additional Resources

### Configuration Files

- Main config: `/app/aura_ia_mcp/config/dashboard_config.yaml`
- Environment: `/app/aura_ia_mcp/.env`
- Docker: `/app/aura_ia_mcp/docker-compose.yml`

### Documentation

- API Documentation: See TASK_7_API_DOCUMENTATION.md
- Deployment Guide: See TASK_7_DEPLOYMENT_CHECKLIST.md
- Technical Specs: See AURA_IA_MCP_PRD.md

### Logs

- Gateway logs: `docker compose logs aura-ia-gateway`
- ML Backend logs: `docker compose logs aura-ia-ml`
- All services: `docker compose logs`

---

## ✅ Verification Checklist

**First Time Setup**:

- [ ] Dashboard loads without errors
- [ ] Connection status shows green
- [ ] Real-time metrics updating
- [ ] Chat responds to messages
- [ ] AI System panel shows models
- [ ] Governance panel shows roles
- [ ] Omni Monitor shows system stats
- [ ] Intelligence Arena shows debates

**Regular Verification**:

- [ ] All panels updating in real-time
- [ ] No console errors
- [ ] Response times acceptable
- [ ] No memory leaks
- [ ] Backup completed
- [ ] Logs reviewed for errors

---

## 📋 Sign-Off

**User Guide**: ✅ COMPLETE  
**Administrator Guide**: ✅ INCLUDED  
**Troubleshooting**: ✅ COMPREHENSIVE  
**Use Cases**: ✅ DOCUMENTED  

**Status**: ✅ **READY FOR USER DEPLOYMENT**

All features documented with step-by-step instructions for users and administrators.
