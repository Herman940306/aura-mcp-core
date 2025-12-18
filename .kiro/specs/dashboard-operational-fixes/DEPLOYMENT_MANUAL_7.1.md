# TASK 7.1 - PRODUCTION DEPLOYMENT MANUAL

## Step-by-Step Instructions for {{NAS_IP}}

**Document Version**: 1.0  
**Date**: December 13, 2025  
**Target Server**: {{NAS_IP}} (NAS Server)  
**Deployment Method**: Manual SSH/SCP with PowerShell script  
**Estimated Time**: 1-2 hours

---

## 📋 PRE-DEPLOYMENT CHECKLIST

Before starting, ensure you have:

- [ ] Local copy of updated code (all 5 modified files)
- [ ] SSH access to {{NAS_IP}} (username: `wolf`)
- [ ] SCP capability (or file transfer method)
- [ ] All documentation files available
- [ ] Current system backup confirmed
- [ ] Estimated downtime window (30-60 minutes)

---

## 🚀 QUICK START (Automated)

### Option 1: Windows PowerShell (Recommended for Windows Users)

```powershell
cd f:\Kiro_Projects\LATEST_MCP

# Dry run first (no changes made)
& scripts/deploy_to_production.ps1 -DryRun

# If dry run looks good, execute deployment
& scripts/deploy_to_production.ps1
```

### Option 2: Bash Script (Linux/Mac)

```bash
cd ~/kiro/projects/latest-mcp
chmod +x scripts/deploy_to_production.sh
./scripts/deploy_to_production.sh
```

---

## 🛠️ MANUAL DEPLOYMENT (Step-by-Step)

Use this if you prefer manual control or the automated scripts don't work.

### Step 1: Connect to Production Server

```bash
ssh {{YOUR_SSH_USER}}@{{NAS_IP}}
```

Expected output:

```
{{YOUR_SSH_USER}}@{{NAS_IP}}'s password: ••••••••
Last login: [date] from [IP]
wolf@NAS:~$
```

### Step 2: Navigate to Project Directory

```bash
cd /volume2/docker/Herman/MCP_Server
pwd
```

Expected output:

```
/volume2/docker/Herman/MCP_Server
```

### Step 3: Create Backup

```bash
# Create timestamped backup directory
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
cp -r . ./backup_$BACKUP_DATE

# Verify backup created
ls -la | grep backup
```

Expected output:

```
drwxr-xr-x  backup_20251213_143022
```

### Step 4: Stop Current Services

```bash
# Stop all Docker services
docker-compose down

# Verify services stopped
docker ps
```

Expected output:

```
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
(empty)
```

### Step 5: Transfer Updated Files (From Local Machine)

Open a NEW terminal on your local machine:

```powershell
# Windows PowerShell
$SERVER = "{{NAS_IP}}"
$USER = "wolf"
$PATH = "/volume2/docker/Herman/MCP_Server"
$LOCAL = "f:\Kiro_Projects\LATEST_MCP"

# Transfer individual files
scp "$LOCAL\requirements-base.txt" "${USER}@${SERVER}:${PATH}/"
scp "$LOCAL\requirements.txt" "${USER}@${SERVER}:${PATH}/"
scp "$LOCAL\config\dashboard_config.yaml" "${USER}@${SERVER}:${PATH}/config/"
scp "$LOCAL\docker-compose.yml" "${USER}@${SERVER}:${PATH}/"
scp "$LOCAL\.env.example" "${USER}@${SERVER}:${PATH}/"

# Transfer test files
scp "$LOCAL\tests\test_task5_*.py" "${USER}@${SERVER}:${PATH}/tests/"
```

Or on Linux/Mac:

```bash
SERVER="{{NAS_IP}}"
USER="wolf"
PATH="/volume2/docker/Herman/MCP_Server"
LOCAL="~/kiro/projects/latest-mcp"

scp $LOCAL/requirements-base.txt $USER@$SERVER:$PATH/
scp $LOCAL/requirements.txt $USER@$SERVER:$PATH/
scp $LOCAL/config/dashboard_config.yaml $USER@$SERVER:$PATH/config/
scp $LOCAL/docker-compose.yml $USER@$SERVER:$PATH/
scp $LOCAL/.env.example $USER@$SERVER:$PATH/
scp $LOCAL/tests/test_task5_*.py $USER@$SERVER:$PATH/tests/
```

### Step 6: Configure Environment (Back on SSH Session)

Still on production server terminal:

```bash
# Create .env from template
cp .env.example .env

# Edit environment variables
nano .env
```

Key variables to set/verify:

```env
# Dashboard Configuration
FEATURE_REAL_TIME_UPDATES=true
FEATURE_WEBSOCKET_FALLBACK=true

# Monitoring Features
FEATURE_SYSTEM_MONITORING=true
FEATURE_DATABASE_MONITORING=true
ENABLE_GPU_MONITORING=true
ENABLE_TEMPERATURE_MONITORING=true

# WebSocket Settings
WEBSOCKET_RECONNECT_BACKOFF_MULTIPLIER=1.5
WEBSOCKET_MAX_ATTEMPTS=10
WEBSOCKET_MAX_DELAY_MS=30000

# Feature Flags
FEATURE_GOVERNANCE_PANEL=true
FEATURE_INTELLIGENCE_ARENA=true
FEATURE_OMNI_MONITOR=true
FEATURE_CHAT=true
FEATURE_AI_SYSTEM=true
```

To edit with nano:

- Edit the values
- Press `Ctrl+O` to save
- Press Enter to confirm
- Press `Ctrl+X` to exit

### Step 7: Verify Configuration

```bash
# Check .env file created
cat .env | head -20

# Verify key files present
ls -la requirements*.txt
ls -la config/dashboard_config.yaml
ls -la docker-compose.yml
```

### Step 8: Build Docker Images

```bash
# Pull latest base images first (optional but recommended)
docker pull python:3.11-slim

# Build Docker containers with new dependencies
docker-compose build

# This may take 3-10 minutes depending on bandwidth
```

Monitor the build output for any errors. It should show:

```
Building backend
...
[main ...] Successfully built abcdef123456
[gateway ...] Successfully built xyz789uvw
...
Successfully tagged [image names]
```

### Step 9: Start Services

```bash
# Start all services
docker-compose up -d

# Check service startup
docker-compose logs -f
```

Wait for logs to stabilize. Look for:

```
gateway_1       | INFO: Started server
ml-backend_1    | INFO: Server started
role-engine_1   | INFO: Service ready
```

Press `Ctrl+C` to stop viewing logs (services continue running).

### Step 10: Wait for Initialization

```bash
# Wait 30 seconds for services to fully initialize
sleep 30

# Check service status
docker-compose ps
```

Expected output:

```
NAME                COMMAND                  STATUS              PORTS
gateway             "python -m uvicorn..." Up (healthy)       0.0.0.0:9200->9200/tcp
ml-backend          "python -m uvicorn..." Up (healthy)       0.0.0.0:9201->9201/tcp
role-engine         "uvicorn ops.role..." Up (healthy)       0.0.0.0:9206->9206/tcp
dashboard           "http-server -p..."    Up (healthy)       0.0.0.0:9205->9205/tcp
```

---

## ✅ VERIFICATION TESTS

### Test 1: Service Health Check

```bash
curl http://localhost:9200/healthz
```

Expected response:

```json
{
  "status": "healthy",
  "timestamp": "2025-12-13T14:30:22Z",
  "services": {
    "gateway": "healthy",
    "ml-backend": "healthy",
    "role-engine": "healthy"
  }
}
```

### Test 2: Readiness Check

```bash
curl http://localhost:9200/readyz
```

Expected response:

```json
{
  "ready": true,
  "checks": [...]
}
```

### Test 3: WebSocket Connection Test

```bash
# Install wscat if not available
npm install -g wscat

# Test WebSocket endpoint
wscat -c ws://localhost:9200/ws/models
```

Expected output:

```
Connected (press CTRL+C to quit)
> {"type": "subscribe", "channel": "models"}
< {"type": "update", "data": {...}}
```

Press `Ctrl+C` to exit.

### Test 4: Dashboard Access

From your local machine, open browser and navigate to:

```
http://{{NAS_IP}}:9205/
```

Verify:

- [ ] Page loads without errors
- [ ] All 5 panels visible (AI System, Governance, Intelligence Arena, Omni Monitor, Chat)
- [ ] No red error messages
- [ ] Real-time data updating

### Test 5: API Endpoints

```bash
# Test system metrics endpoint
curl http://localhost:9200/api/system/metrics

# Test governance endpoint
curl http://localhost:9200/api/governance/roles

# Test model status endpoint
curl http://localhost:9200/api/models/status

# Test database health endpoint
curl http://localhost:9200/api/database/health
```

Each should return valid JSON with status 200.

---

## 🐛 TROUBLESHOOTING

### Issue 1: Services Won't Start

**Symptom**: `docker-compose ps` shows services as `Exited`

**Solution**:

```bash
# View error logs
docker-compose logs

# Rebuild without cache
docker-compose build --no-cache

# Start with verbose output
docker-compose up
```

**Common causes**:

- Missing dependencies in requirements file
- Port already in use (change docker-compose port mappings)
- Insufficient disk space
- Memory issues (check `docker stats`)

### Issue 2: WebSocket Connection Fails

**Symptom**: Cannot connect to `ws://{{NAS_IP}}:9200/ws/models`

**Solution**:

```bash
# Check if port is open
netstat -an | grep 9200

# Check firewall
sudo ufw status
sudo ufw allow 9200

# Check Docker network
docker network ls
docker network inspect mcp_network
```

### Issue 3: Dashboard Doesn't Update

**Symptom**: Dashboard loads but shows old data

**Solution**:

```bash
# Check WebSocket logs
docker-compose logs gateway | grep websocket

# Verify real-time feature is enabled
cat .env | grep FEATURE_REAL_TIME_UPDATES

# Restart gateway service
docker-compose restart gateway
```

### Issue 4: Performance Issues

**Symptom**: Dashboard slow or unresponsive

**Solution**:

```bash
# Check system resources
docker stats

# Check database connections
docker-compose exec ml-backend psql -h db -U postgres -c "SELECT count(*) as connections FROM pg_stat_activity;"

# Optimize monitoring intervals (edit .env)
SYSTEM_MONITOR_INTERVAL_MS=5000  # Increase from 1000
```

### Issue 5: Out of Disk Space

**Symptom**: Docker containers fail with "no space left"

**Solution**:

```bash
# Check disk usage
df -h

# Clean up Docker (be careful!)
docker system prune -a --volumes

# Remove old backups
cd /volume2/docker/Herman/MCP_Server
rm -rf backup_* (keep recent ones!)
```

---

## 🔄 ROLLBACK PROCEDURE

If deployment fails or issues arise, rollback to previous version:

### Quick Rollback

```bash
# Stop current services
docker-compose down

# Remove current code and replace with backup
cd /volume2/docker/Herman/MCP_Server
rm -rf current_code
mv backup_YYYYMMDD_HHMMSS current_code

# Restart with previous version
docker-compose up -d
```

### Full System Rollback

```bash
# Stop and clean up Docker
docker-compose down
docker system prune -a --volumes

# Restore entire directory from backup
cd /mnt/storage/kiro/projects
rm -rf latest-mcp
cp -r backups/backup_YYYYMMDD_HHMMSS latest-mcp

# Rebuild and restart
cd latest-mcp
docker-compose build
docker-compose up -d
```

---

## 📊 MONITORING DEPLOYMENT

### Real-time Monitoring

```bash
# Watch services
docker-compose ps -a

# View live logs (all services)
docker-compose logs -f

# View logs for specific service
docker-compose logs -f gateway
docker-compose logs -f ml-backend

# Monitor resource usage
docker stats

# Check for errors in last N lines
docker-compose logs --tail=100 | grep -i error
```

### Log Files

```bash
# View system logs
tail -f /var/log/syslog

# View Docker daemon logs
journalctl -u docker -f

# Check application logs inside container
docker-compose exec gateway tail -f /app/logs/app.log
```

---

## 🎉 SUCCESSFUL DEPLOYMENT CHECKLIST

When deployment completes, verify:

- [ ] All 7 services running (`docker-compose ps`)
- [ ] Health endpoint responds (200 status)
- [ ] Readiness endpoint responds (200 status)
- [ ] WebSocket `/ws/models` accessible
- [ ] WebSocket `/ws/system` accessible
- [ ] WebSocket `/ws/governance` accessible
- [ ] WebSocket `/ws/database` accessible
- [ ] Dashboard loads (<http://{{NAS_IP}}:9205/>)
- [ ] AI System panel visible
- [ ] Governance panel visible
- [ ] Intelligence Arena panel visible
- [ ] Omni Monitor panel visible with real data
- [ ] Chat panel functional
- [ ] Real-time updates visible (check browser console)
- [ ] No error messages in dashboard
- [ ] System metrics displaying correctly
- [ ] CPU usage < 80%
- [ ] RAM usage < 75%
- [ ] Disk usage < 85%
- [ ] All API endpoints responding

---

## 📝 POST-DEPLOYMENT

### Create Deployment Report

```bash
# Document deployment
cat > deployment_report.txt << 'EOF'
DEPLOYMENT REPORT
=================
Date: $(date)
Server: {{NAS_IP}}
Status: SUCCESS / NEEDS ATTENTION / FAILED

Services Started: $(docker-compose ps -q | wc -l)
Health Status: $(curl -s http://localhost:9200/healthz | jq .status)
Disk Usage: $(df -h /mnt/storage | tail -1 | awk '{print $5}')
Memory Usage: $(free -h | grep Mem | awk '{print $3 "/" $2}')

Notes:
[Add any observations here]
EOF
```

### Enable Auto-restart

```bash
# Enable automatic service restart on server reboot
crontab -e

# Add this line to restart on boot:
@reboot cd /volume2/docker/Herman/MCP_Server && docker-compose up -d
```

### Set Up Monitoring Alerts

```bash
# Check services periodically
*/5 * * * * cd /volume2/docker/Herman/MCP_Server && docker-compose ps | grep -q "Exit" && docker-compose up -d
```

---

## 📞 SUPPORT

If issues arise:

1. **Check TASK_7_DEPLOYMENT_CHECKLIST.md** - Official deployment guide
2. **Check TASK_7_API_DOCUMENTATION.md** - API reference
3. **Check TASK_7_USER_GUIDE.md** - Troubleshooting section
4. **View logs**: `docker-compose logs -f`
5. **Check health**: `curl http://{{NAS_IP}}:9200/healthz`

---

**Deployment Manual Version**: 1.0  
**Last Updated**: December 13, 2025  
**Status**: Production Ready  
**Approval**: [Pending Deployment]

Ready to deploy? Start with "Quick Start" section above or follow "Manual Deployment" for step-by-step control.
