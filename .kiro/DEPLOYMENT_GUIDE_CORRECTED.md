# ✅ CORRECTED DEPLOYMENT GUIDE - Task 7.1

## Aura IA MCP to Production NAS Server

**Last Updated:** December 13, 2025  
**Target Server:** {{NAS_IP}} (NAS)  
**SSH User:** wolf  
**Correct Deployment Path:** `/volume2/docker/Herman/MCP_Server`  

---

## 📋 QUICK REFERENCE

| Item | Value |
|------|-------|
| **Production Server** | {{NAS_IP}} |
| **SSH User** | wolf |
| **Deployment Directory** | `/volume2/docker/Herman/MCP_Server` |
| **Local Source** | `F:\Kiro_Projects\LATEST_MCP` |
| **Docker Compose** | Yes, 11 services |
| **Services Port Range** | 9200-9208, 8001, 2700, 5002 |

---

## 🚀 STEP-BY-STEP DEPLOYMENT

### Phase 1: WINDOWS (Your Machine)

#### Step 1: Verify Local Code

```powershell
cd F:\Kiro_Projects\LATEST_MCP

# Verify key files exist
ls aura_ia_mcp/
ls src/
ls ops/
ls docker-compose.yml
ls requirements-base.txt
```

#### Step 2: Execute Deployment Script (PowerShell)

```powershell
# Navigate to project directory
cd F:\Kiro_Projects\LATEST_MCP

# Execute with dry-run first (recommended)
& scripts/deploy_to_production.ps1 -DryRun

# Then execute actual deployment
& scripts/deploy_to_production.ps1
```

**Script Parameters:**

```powershell
& scripts/deploy_to_production.ps1 `
  -ProductionServer "{{NAS_IP}}" `
  -ProductionUser "wolf" `
  -ProductionPath "/volume2/docker/Herman/MCP_Server" `
  -LocalProjectPath "F:\Kiro_Projects\LATEST_MCP"
```

**What the script does:**

- ✅ Creates backup of current deployment
- ✅ Transfers all code files via SCP
- ✅ Configures environment variables
- ✅ Builds Docker containers
- ✅ Starts all 11 services
- ✅ Verifies health endpoints
- ✅ Generates deployment report

---

### Phase 2: LINUX/UBUNTU (NAS Server)

#### Step 3: SSH to NAS Server

```bash
ssh {{YOUR_SSH_USER}}@{{NAS_IP}}
```

#### Step 4: Navigate to Deployment Directory

```bash
# Go to correct deployment location
cd /volume2/docker/Herman/MCP_Server

# Verify you're in the right place
pwd
# Output should be:
# /volume2/docker/Herman/MCP_Server
```

#### Step 5: Verify Files Transferred

```bash
# Check that files are present
ls -la

# Should see:
# - aura_ia_mcp/
# - src/
# - ops/
# - docker-compose.yml
# - requirements*.txt
# - .env
```

#### Step 6: Verify Docker Compose File

```bash
# Check docker-compose configuration
docker-compose config | head -20

# List services to be started
docker-compose config --services
```

#### Step 7: Create Backup (IMPORTANT)

```bash
# Before building, backup current state
sudo cp -r /volume2/docker/Herman/MCP_Server \
           /volume2/docker/Herman/MCP_Server_backup_$(date +%Y%m%d_%H%M%S)

# Verify backup created
ls -la /volume2/docker/Herman/ | grep backup
```

#### Step 8: Start Deployment

```bash
# Ensure you're in the right directory
cd /volume2/docker/Herman/MCP_Server

# Pull latest base images
sudo docker-compose pull

# Build containers (this takes 5-10 minutes)
sudo docker-compose build

# Start all services
sudo docker-compose up -d

# Watch the startup process
sudo docker-compose logs -f
```

#### Step 9: Verify Services Running

```bash
# Check all containers are running
sudo docker-compose ps

# Expected output: All 11 containers in "Up" state
# - aura-ia-mcp-server (port 9200)
# - aura-ia-ml-backend (port 9201)
# - aura-ia-rag (port 9202)
# - aura-ia-dashboard (port 9205)
# - aura-ia-role-engine (port 9206)
# - aura-ia-ollama (port 9207)
# - aura-ia-postgres (port 9208)
# - aura-ia-audio-service (port 8001)
# - aura-ia-vosk (port 2700)
# - aura-ia-coqui (port 5002)
# - (1 more service)
```

#### Step 10: Health Checks

```bash
# Test Gateway health
curl -s http://localhost:9200/healthz | jq .

# Test readiness
curl -s http://localhost:9200/readyz | jq .

# Test ML Backend
curl -s http://localhost:9201/health | jq .

# Test Role Engine
curl -s http://localhost:9206/health | jq .
```

#### Step 11: Access Dashboard

```bash
# From your browser on Windows:
# http://{{NAS_IP}}:9205

# Or from NAS terminal:
curl -s http://localhost:9205 | head -20
```

---

## 🛠️ MANUAL FILE TRANSFER (Alternative)

If the PowerShell script doesn't work, manually transfer files:

```bash
# From Windows PowerShell:
scp -r F:\Kiro_Projects\LATEST_MCP\aura_ia_mcp `
       {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/

scp -r F:\Kiro_Projects\LATEST_MCP\src `
       {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/

scp -r F:\Kiro_Projects\LATEST_MCP\ops `
       {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/

scp F:\Kiro_Projects\LATEST_MCP\docker-compose.yml `
    {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/

scp F:\Kiro_Projects\LATEST_MCP\requirements-base.txt `
    {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/

scp F:\Kiro_Projects\LATEST_MCP\requirements.txt `
    {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/

scp F:\Kiro_Projects\LATEST_MCP\.env `
    {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/
```

---

## ⚡ QUICK COMMANDS SUMMARY

```bash
# SSH to server
ssh {{YOUR_SSH_USER}}@{{NAS_IP}}

# Navigate to deployment dir
cd /volume2/docker/Herman/MCP_Server

# Check status
sudo docker-compose ps

# View logs
sudo docker-compose logs -f

# Restart specific service
sudo docker-compose restart aura-ia-gateway

# Restart all services
sudo docker-compose down && sudo docker-compose up -d

# Stop all services
sudo docker-compose down

# Clean volumes (WARNING: deletes data)
sudo docker-compose down -v

# Check service logs
sudo docker-compose logs aura-ia-ml-backend

# Monitor resources
watch -n 1 'sudo docker-compose ps'
```

---

## 🔍 SERVICE PORTS

| Service | Port | URL |
|---------|------|-----|
| Gateway (MCP) | 9200 | <http://{{NAS_IP}}:9200> |
| ML Backend | 9201 | <http://{{NAS_IP}}:9201> |
| RAG/Qdrant | 9202 | <http://{{NAS_IP}}:9202> |
| Dashboard | 9205 | <http://{{NAS_IP}}:9205> |
| Role Engine | 9206 | <http://{{NAS_IP}}:9206> |
| Ollama | 9207 | <http://{{NAS_IP}}:9207> |
| PostgreSQL | 9208 | localhost:9208 (internal) |
| Audio Service | 8001 | <http://{{NAS_IP}}:8001> |
| Vosk STT | 2700 | <http://{{NAS_IP}}:2700> |
| Coqui TTS | 5002 | <http://{{NAS_IP}}:5002> |

---

## ✅ VERIFICATION CHECKLIST

- [ ] All files transferred to `/volume2/docker/Herman/MCP_Server`
- [ ] Docker-compose.yml validates with no errors
- [ ] Backup created: `/volume2/docker/Herman/MCP_Server_backup_YYYYMMDD_HHMMSS`
- [ ] All 11 containers running: `docker-compose ps`
- [ ] Gateway health: `curl -s http://localhost:9200/healthz`
- [ ] Dashboard accessible: <http://{{NAS_IP}}:9205>
- [ ] ML Backend responding: `curl -s http://localhost:9201/health`
- [ ] Role Engine active: `curl -s http://localhost:9206/health`
- [ ] No error logs: `docker-compose logs --tail=50 | grep -i error`
- [ ] Database connected: Models loading in dashboard

---

## 🔄 ROLLBACK PROCEDURE

If something goes wrong:

```bash
cd /volume2/docker/Herman

# Stop current deployment
sudo docker-compose down

# Restore from backup
sudo rm -rf MCP_Server
sudo mv MCP_Server_backup_YYYYMMDD_HHMMSS MCP_Server

# Restart
cd MCP_Server
sudo docker-compose up -d
```

---

## 📞 TROUBLESHOOTING

### Services not starting?

```bash
# Check logs
sudo docker-compose logs --tail=100

# Check specific service
sudo docker-compose logs aura-ia-gateway

# Rebuild
sudo docker-compose build --no-cache
sudo docker-compose up -d
```

### Port already in use?

```bash
# Find what's using port
sudo lsof -i :9200

# Kill process
sudo kill -9 <PID>

# Or change port in docker-compose.yml
```

### Database connection issues?

```bash
# Check PostgreSQL
sudo docker-compose logs aura-ia-postgres

# Test database
sudo docker-compose exec aura-ia-postgres psql -U Admin -d aura_db -c "SELECT 1"
```

### Dashboard not loading?

```bash
# Check dashboard logs
sudo docker-compose logs aura-ia-dashboard

# Test endpoint directly
curl -s http://localhost:9205/api/health | jq .
```

---

## 📊 MONITORING

### Check System Resources

```bash
# Watch containers
watch -n 2 'sudo docker-compose ps'

# Check disk usage
df -h /volume2

# Check memory
free -h
```

### View Real-Time Logs

```bash
# All services
sudo docker-compose logs -f

# Specific service
sudo docker-compose logs -f aura-ia-ml-backend

# Last 100 lines
sudo docker-compose logs --tail=100
```

---

## 🎯 DEPLOYMENT COMPLETE

Once all services are running and health checks pass:

1. ✅ **Access Dashboard:** <http://{{NAS_IP}}:9205>
2. ✅ **Test Chat:** Click "MCP Concierge" tab
3. ✅ **Monitor System:** Check "Omni-Monitor" tab for live metrics
4. ✅ **View Intelligence:** Check "Intelligence" tab for model stats
5. ✅ **Manage Security:** Check "Governance" tab for role/policy

---

## 📝 NOTES

- **Deployment Path is Critical:** `/volume2/docker/Herman/MCP_Server` (NOT `/mnt/storage/...`)
- **SSH User:** Always use `wolf` user
- **Server:** Always target `{{NAS_IP}}`
- **Backup:** Always create backup before deployment
- **Docker Compose:** Uses native `docker-compose` or `docker compose` command
- **Persistence:** PostgreSQL data persists in Docker volumes

---

**Document Generated:** December 13, 2025  
**Version:** 2.0.0 (Corrected Path Edition)  
**Status:** ✅ PRODUCTION READY
