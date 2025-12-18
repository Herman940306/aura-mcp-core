$NAS_USER = "Wolf"
$NAS_IP = "{{NAS_IP}}"
$REMOTE_PATH = "/volume2/docker/Herman/MCP_Server"

Write-Host "Deploying Phase 9.0 (Governance UI) to NAS..." -ForegroundColor Cyan

# 1. Dashboard Files
Write-Host "Uploading Dashboard..."
scp -O dashboard/index.html "${NAS_USER}@${NAS_IP}:${REMOTE_PATH}/dashboard/index.html"
scp -O dashboard/assets/app.js "${NAS_USER}@${NAS_IP}:${REMOTE_PATH}/dashboard/assets/app.js"

# 2. Role Engine Backend
Write-Host "Uploading Role Engine Service..."
scp -O ops/role_engine/are_service.py "${NAS_USER}@${NAS_IP}:${REMOTE_PATH}/ops/role_engine/are_service.py"

# 3. Restart Services
Write-Host "Restarting Services..."
ssh -t "${NAS_USER}@${NAS_IP}" "cd ${REMOTE_PATH} && sudo /usr/local/bin/docker compose restart aura-ia-role-engine aura-ia-dashboard"

Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "Verify at http://${NAS_IP}:9205"
