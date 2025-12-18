# Aura IA Phase 8.0 Deployment Script
# Run this script in PowerShell. You will be prompted for the NAS password multiple times.

Write-Host "🚀 Deploying Phase 8.0 (Dashboard V3) to NAS..." -ForegroundColor Cyan

# 1. Dashboard Frontend
Write-Host "dumping index.html..." -ForegroundColor Yellow
scp -O F:\Kiro_Projects\LATEST_MCP\dashboard\index.html {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/dashboard/

Write-Host "dumping app.js..." -ForegroundColor Yellow
scp -O F:\Kiro_Projects\LATEST_MCP\dashboard\assets\app.js {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/dashboard/assets/

# 2. Backend Logic (and Dependencies)
Write-Host "dumping real_backend_server.py..." -ForegroundColor Yellow
scp -O F:\Kiro_Projects\LATEST_MCP\src\mcp_server\real_backend_server.py {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/src/mcp_server/

Write-Host "dumping requirements-backend.txt..." -ForegroundColor Yellow
scp -O F:\Kiro_Projects\LATEST_MCP\requirements-backend.txt {{YOUR_SSH_USER}}@{{NAS_IP}}:/volume2/docker/Herman/MCP_Server/

# 3. Rebuild & Restart Services
Write-Host "🔄 Rebuilding Remote Services (to install psutil)..." -ForegroundColor Magenta
Write-Host "Attempting build & restart via SSH..."
ssh -t {{YOUR_SSH_USER}}@{{NAS_IP}} "cd /volume2/docker/Herman/MCP_Server && sudo /usr/local/bin/docker compose up -d --build aura-ia-ml aura-ia-dashboard"

Write-Host "✅ Deployment Complete! Check http://{{NAS_IP}}:9205" -ForegroundColor Green
