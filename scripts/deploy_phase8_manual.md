## 1. Copy Frontend (Dashboard)
```powershell
# Copy index.html (Note: -O flag forces legacy SCP protocol for Synology compatibility)
scp -O F:\Kiro_Projects\LATEST_MCP\dashboard\index.html {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/dashboard/

# Copy app.js
scp -O F:\Kiro_Projects\LATEST_MCP\dashboard\assets\app.js {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/dashboard/assets/
```

## 2. Copy Backend (Brain)
```powershell
# Copy real_backend_server.py
scp -O F:\Kiro_Projects\LATEST_MCP\src\mcp_server\real_backend_server.py {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/src/mcp_server/
```

## 3. Restart Server (SSH)
Login to the NAS to apply backend changes:
```bash
ssh {{YOUR_SSH_USER}}@{{NAS_IP}}
sudo -i
cd /volume2/docker/Herman/MCP_Server

# Restart the backend & dashboard services
docker compose restart aura-ia-ml aura-ia-dashboard
```
