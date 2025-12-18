$NAS_USER = "Wolf"
$NAS_IP = "{{NAS_IP}}"
$REMOTE_PATH = "/volume2/docker/Herman/MCP_Server"

Write-Host "Deploying Critical Fixes for Phase 8 & 9..." -ForegroundColor Cyan

# 1. Update Configuration (Docker Compose for Ports)
Write-Host "Uploading docker-compose.yml (Port Fixes)..."
scp -O docker-compose.yml "${NAS_USER}@${NAS_IP}:${REMOTE_PATH}/docker-compose.yml"

# 2. Update Source Code (Ensure Latest Phase 9)
Write-Host "Uploading Source Code..."
scp -O ops/role_engine/are_service.py "${NAS_USER}@${NAS_IP}:${REMOTE_PATH}/ops/role_engine/are_service.py"
scp -O dashboard/index.html "${NAS_USER}@${NAS_IP}:${REMOTE_PATH}/dashboard/index.html"
scp -O dashboard/assets/app.js "${NAS_USER}@${NAS_IP}:${REMOTE_PATH}/dashboard/assets/app.js"

# 3. Apply Changes (Recreate Containers)
Write-Host "Recreating Containers (Applying Port Updates)..."
ssh -t "${NAS_USER}@${NAS_IP}" "cd ${REMOTE_PATH} && sudo /usr/local/bin/docker compose up -d --force-recreate aura-ia-ml aura-ia-role-engine aura-ia-dashboard"

Write-Host "Fixes Deployed!" -ForegroundColor Green
Write-Host "Please verify: 1. Debate Simulator (Port 9209), 2. Governance Tab."
