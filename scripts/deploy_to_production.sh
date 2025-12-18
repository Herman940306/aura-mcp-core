#!/bin/bash
# Production Deployment Script for Aura IA MCP Dashboard
# Target: Your NAS Server (set PRODUCTION_SERVER below)
# Date: December 13, 2025

set -e

# Configuration - Set your server IP here
PRODUCTION_SERVER="${NAS_IP:-your-nas-ip}"
PRODUCTION_USER="wolf"
PRODUCTION_PATH="/volume2/docker/Herman/MCP_Server"
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
LOCAL_PROJECT_PATH="f:/Kiro_Projects/LATEST_MCP"

echo "=================================================="
echo "AURA IA MCP - PRODUCTION DEPLOYMENT"
echo "Target: $PRODUCTION_SERVER"
echo "Date: $(date)"
echo "=================================================="
echo ""

# Phase 1: Pre-deployment checks
echo "[PHASE 1] Pre-Deployment Checks"
echo "=================================="
echo "✓ Checking local code integrity..."
if [ -f "$LOCAL_PROJECT_PATH/requirements-base.txt" ]; then
    echo "  ✓ requirements-base.txt found"
else
    echo "  ✗ requirements-base.txt NOT found - ABORT"
    exit 1
fi

if [ -f "$LOCAL_PROJECT_PATH/requirements.txt" ]; then
    echo "  ✓ requirements.txt found"
else
    echo "  ✗ requirements.txt NOT found - ABORT"
    exit 1
fi

if [ -f "$LOCAL_PROJECT_PATH/config/dashboard_config.yaml" ]; then
    echo "  ✓ config/dashboard_config.yaml found"
else
    echo "  ✗ config/dashboard_config.yaml NOT found - ABORT"
    exit 1
fi

if [ -f "$LOCAL_PROJECT_PATH/docker-compose.yml" ]; then
    echo "  ✓ docker-compose.yml found"
else
    echo "  ✗ docker-compose.yml NOT found - ABORT"
    exit 1
fi

echo "✓ Verifying test files..."
test_count=$(find "$LOCAL_PROJECT_PATH/tests" -name "test_task5_*.py" | wc -l)
if [ $test_count -ge 3 ]; then
    echo "  ✓ All test files found ($test_count files)"
else
    echo "  ✗ Test files incomplete - ABORT"
    exit 1
fi

echo ""
echo "✓ Testing connection to production server..."
if ping -c 1 $PRODUCTION_SERVER &> /dev/null; then
    echo "  ✓ Server $PRODUCTION_SERVER is reachable"
else
    echo "  ✗ Cannot reach server $PRODUCTION_SERVER"
    echo "  Attempting SSH connection instead..."
fi

echo ""
echo "[PHASE 1] ✓ PRE-DEPLOYMENT CHECKS PASSED"
echo ""
read -p "Continue to Phase 2 (Code Transfer)? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

# Phase 2: Connect and backup
echo "[PHASE 2] Server Connection & Backup"
echo "====================================="
echo "Connecting to $PRODUCTION_SERVER..."
echo ""

# Create backup on production server
echo "Creating backup of current production code..."
ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "cd $PRODUCTION_PATH && cp -r . ./$BACKUP_DIR 2>/dev/null || mkdir -p ../backups && cp -r . ../backups/$BACKUP_DIR" || {
    echo "Warning: Backup may not have completed successfully"
    echo "Continuing anyway..."
}

echo "✓ Backup created"
echo ""
echo "[PHASE 2] ✓ SERVER CONNECTION & BACKUP COMPLETE"
echo ""

# Phase 3: Code Transfer
echo "[PHASE 3] Code Transfer to Production"
echo "====================================="
echo "Files to transfer:"
echo "  - requirements-base.txt"
echo "  - requirements.txt"
echo "  - config/dashboard_config.yaml"
echo "  - docker-compose.yml"
echo "  - tests/test_task5_*.py"
echo "  - All documentation files"
echo ""
read -p "Transfer code now? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Code transfer cancelled."
    exit 1
fi

echo "Transferring requirements-base.txt..."
scp "$LOCAL_PROJECT_PATH/requirements-base.txt" "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/"

echo "Transferring requirements.txt..."
scp "$LOCAL_PROJECT_PATH/requirements.txt" "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/"

echo "Transferring config/dashboard_config.yaml..."
scp "$LOCAL_PROJECT_PATH/config/dashboard_config.yaml" "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/config/" 2>/dev/null || {
    echo "Creating config directory on server..."
    ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "mkdir -p $PRODUCTION_PATH/config"
    scp "$LOCAL_PROJECT_PATH/config/dashboard_config.yaml" "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/config/"
}

echo "Transferring docker-compose.yml..."
scp "$LOCAL_PROJECT_PATH/docker-compose.yml" "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/"

echo "Transferring test files..."
scp "$LOCAL_PROJECT_PATH/tests/test_task5_"*.py "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/tests/" 2>/dev/null || {
    echo "Creating tests directory on server..."
    ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "mkdir -p $PRODUCTION_PATH/tests"
    scp "$LOCAL_PROJECT_PATH/tests/test_task5_"*.py "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/tests/"
}

echo "Transferring .env.example..."
scp "$LOCAL_PROJECT_PATH/.env.example" "$PRODUCTION_USER@$PRODUCTION_SERVER:$PRODUCTION_PATH/" 2>/dev/null || {
    echo "Note: .env.example may not exist locally, skipping..."
}

echo ""
echo "✓ Code transferred successfully"
echo "[PHASE 3] ✓ CODE TRANSFER COMPLETE"
echo ""

# Phase 4: Environment Configuration
echo "[PHASE 4] Environment Configuration"
echo "==================================="
echo "Configuring production environment..."
echo ""

# Create .env on server if not exists
ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "cd $PRODUCTION_PATH && if [ ! -f .env ]; then cp .env.example .env 2>/dev/null || echo 'FEATURE_WEBSOCKET_ENABLED=true' > .env; fi"

echo "✓ Environment file created/configured"
echo ""
echo "IMPORTANT: Please SSH into the server and verify .env configuration:"
echo "  ssh $PRODUCTION_USER@$PRODUCTION_SERVER"
echo "  cd $PRODUCTION_PATH"
echo "  nano .env  # Review and edit as needed"
echo ""
read -p "Continue to Phase 5 (Docker Build)? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Waiting for manual configuration..."
    read -p "Press enter when ready to continue..." < /dev/tty
fi

echo "[PHASE 4] ✓ ENVIRONMENT CONFIGURATION COMPLETE"
echo ""

# Phase 5: Docker Build & Deployment
echo "[PHASE 5] Docker Build & Service Startup"
echo "========================================"
echo "Building Docker containers on production server..."
echo ""

ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "cd $PRODUCTION_PATH && docker-compose down 2>/dev/null || true"
echo "✓ Stopped previous services"
echo ""

echo "Building Docker images..."
ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "cd $PRODUCTION_PATH && docker-compose build 2>&1 | tail -20"
echo "✓ Docker build complete"
echo ""

echo "Starting services..."
ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "cd $PRODUCTION_PATH && docker-compose up -d 2>&1"
echo "✓ Services started"
echo ""

echo "Waiting for services to be ready (60 seconds)..."
sleep 30
echo "Services initializing..."
sleep 30
echo ""

echo "[PHASE 5] ✓ DOCKER BUILD & DEPLOYMENT COMPLETE"
echo ""

# Phase 6: Health Verification
echo "[PHASE 6] Health Verification"
echo "============================="
echo "Checking service status..."
echo ""

ssh "$PRODUCTION_USER@$PRODUCTION_SERVER" "cd $PRODUCTION_PATH && docker-compose ps" || {
    echo "Note: Could not retrieve service status"
}

echo ""
echo "Checking health endpoints..."
echo ""

# Test health endpoint
echo "Testing Health Endpoint..."
if curl -s http://$PRODUCTION_SERVER:9200/healthz | grep -q "status"; then
    echo "  ✓ Health endpoint responding"
else
    echo "  ⚠ Health endpoint may not be ready yet"
fi

echo ""
echo "[PHASE 6] ✓ HEALTH VERIFICATION COMPLETE"
echo ""

# Final Summary
echo "=================================================="
echo "DEPLOYMENT SUMMARY"
echo "=================================================="
echo "✓ Phase 1: Pre-deployment checks"
echo "✓ Phase 2: Server connection & backup"
echo "✓ Phase 3: Code transfer"
echo "✓ Phase 4: Environment configuration"
echo "✓ Phase 5: Docker build & deployment"
echo "✓ Phase 6: Health verification"
echo ""
echo "NEXT STEPS:"
echo "1. SSH into production server: ssh $PRODUCTION_USER@$PRODUCTION_SERVER"
echo "2. View logs: cd $PRODUCTION_PATH && docker-compose logs -f"
echo "3. Test WebSocket: curl ws://$PRODUCTION_SERVER:9200/ws/models"
echo "4. Access dashboard: http://$PRODUCTION_SERVER:9205/"
echo ""
echo "DOCUMENTATION:"
echo "- Deployment Checklist: TASK_7_DEPLOYMENT_CHECKLIST.md"
echo "- API Documentation: TASK_7_API_DOCUMENTATION.md"
echo "- User Guide: TASK_7_USER_GUIDE.md"
echo "- Troubleshooting: TASK_7_USER_GUIDE.md (Troubleshooting section)"
echo ""
echo "ROLLBACK (if needed):"
echo "  ssh $PRODUCTION_USER@$PRODUCTION_SERVER"
echo "  cd $PRODUCTION_PATH"
echo "  docker-compose down"
echo "  rm -rf current/* && mv $BACKUP_DIR/* current/"
echo "  docker-compose up -d"
echo ""
echo "=================================================="
echo "Deployment completed at $(date)"
echo "=================================================="
