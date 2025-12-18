# ⚡ DEPLOYMENT QUICK REFERENCE CARD

## 📍 CORRECT PATHS & CONFIGURATION

```
Server:      {{NAS_IP}} (NAS)
User:        wolf
Path:        /volume2/docker/Herman/MCP_Server  ✅
Local:       F:\Kiro_Projects\LATEST_MCP
```

---

## 🔴 WRONG PATH (DO NOT USE)

```
❌ /mnt/storage/kiro/projects/latest-mcp
```

---

## ⚡ ONE-LINE DEPLOYMENT

### From Windows PowerShell

```powershell
cd f:\Kiro_Projects\LATEST_MCP && & scripts/deploy_to_production.ps1
```

---

## 📋 STEP-BY-STEP QUICK GUIDE

### 1️⃣ Windows Machine

```powershell
# Navigate to project
cd f:\Kiro_Projects\LATEST_MCP

# Execute deployment script
& scripts/deploy_to_production.ps1

# Script will:
# ✓ Create NAS backup
# ✓ Transfer code files
# ✓ Build Docker containers
# ✓ Start 11 services
# ✓ Verify health endpoints
```

### 2️⃣ NAS Server (After script completes)

```bash
# SSH to NAS
ssh {{YOUR_SSH_USER}}@{{NAS_IP}}

# Verify services
cd /volume2/docker/Herman/MCP_Server
sudo docker-compose ps

# Check status
curl http://localhost:9200/healthz
curl http://localhost:9205  # Dashboard
```

---

## 🔌 SERVICE PORTS

| Service | Port | Check |
|---------|------|-------|
| Gateway | 9200 | curl <http://localhost:9200/healthz> |
| ML Backend | 9201 | curl <http://localhost:9201/health> |
| Dashboard | 9205 | <http://{{NAS_IP}}:9205> |
| Role Engine | 9206 | curl <http://localhost:9206/health> |
| Ollama | 9207 | curl <http://localhost:9207/api/tags> |
| PostgreSQL | 9208 | docker-compose exec postgres... |
| Audio | 8001 | curl <http://localhost:8001> |

---

## 🔄 ESSENTIAL COMMANDS (On NAS)

```bash
# Navigate
cd /volume2/docker/Herman/MCP_Server

# Status
sudo docker-compose ps

# Logs
sudo docker-compose logs -f

# Restart
sudo docker-compose down && sudo docker-compose up -d

# Stop
sudo docker-compose down

# Restart specific service
sudo docker-compose restart aura-ia-gateway
```

---

## ✅ VERIFICATION CHECKLIST

- [ ] File transfer complete (check file sizes on NAS)
- [ ] All 11 containers running: `docker-compose ps`
- [ ] Gateway health: `curl http://localhost:9200/healthz`
- [ ] Dashboard loads: <http://{{NAS_IP}}:9205>
- [ ] No error logs: `docker-compose logs | grep -i error`

---

## 🆘 QUICK TROUBLESHOOTING

| Issue | Command |
|-------|---------|
| Services not starting | `docker-compose logs --tail=100` |
| Port already in use | `sudo lsof -i :9200` |
| No database connection | `docker-compose logs aura-ia-postgres` |
| Dashboard blank | `curl http://localhost:9205/api/health` |
| Need rollback | `sudo cp -r MCP_Server_backup_* MCP_Server` |

---

## 📱 DASHBOARD ACCESS

Once deployed:

```
http://{{NAS_IP}}:9205

Available Tabs:
- Cockpit (System overview)
- Omni-Monitor (Real-time metrics)
- Intelligence (Model arena, debates)
- Governance (Role hierarchy, audit logs)
```

---

## 🔐 CORRECT CREDENTIALS

| Item | Value |
|------|-------|
| Server IP | {{NAS_IP}} |
| SSH User | wolf |
| Auth | SSH key (no password) |
| DB User | Admin |
| DB Auth | Trust (internal) |

---

## 📍 KEY FILES

| File | Purpose |
|------|---------|
| `deploy_to_production.ps1` | Main deployment script (CORRECTED) |
| `.kiro/DEPLOYMENT_GUIDE_CORRECTED.md` | Full deployment guide |
| `.kiro/steering/aura-ia-server-reference.md` | Server reference |
| `docker-compose.yml` | Service configuration |
| `.env` | Environment variables |

---

## ⚠️ CRITICAL REMINDER

```
CORRECT:   /volume2/docker/Herman/MCP_Server
WRONG:     /mnt/storage/kiro/projects/latest-mcp

All scripts and docs have been corrected.
Use /volume2/docker/Herman/MCP_Server
```

---

**Last Updated:** December 13, 2025  
**Status:** ✅ READY FOR DEPLOYMENT
