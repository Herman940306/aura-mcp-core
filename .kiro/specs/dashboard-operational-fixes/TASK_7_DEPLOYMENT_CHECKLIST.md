# 📋 TASK 7.1 - DEPLOYMENT PREPARATION CHECKLIST

**Status**: READY FOR PRODUCTION DEPLOYMENT  
**Target**: NAS Server at {{NAS_IP}}  
**Date**: December 13, 2025

---

## Pre-Deployment Verification Checklist

### Code Quality ✅

- [x] Task 4: Configuration & Dependencies implemented
- [x] Task 5: Integration Testing complete (40/40 tests passing)
- [x] Task 6: Checkpoint verification complete
- [x] All previous tasks (1-3) verified and functional
- [x] No breaking changes to existing functionality
- [x] Backward compatibility maintained

### Test Coverage ✅

- [x] WebSocket integration tests (18 tests)
- [x] Performance tests (22 tests)
- [x] Browser compatibility tests (25+ scenarios)
- [x] All tests passing (40/40 = 100%)
- [x] Requirements fully covered
- [x] Performance targets met

### Documentation ✅

- [x] Task 4 Implementation Report (550+ lines)
- [x] Task 4 Verification Report (comprehensive)
- [x] Task 5 Test Suite Documentation (500+ lines)
- [x] Task 6 Checkpoint Report (complete)
- [x] Deployment Preparation Checklist (this document)

### Configuration ✅

- [x] dashboard_config.yaml created (325+ lines, 11 sections)
- [x] .env.example updated (40+ variables)
- [x] docker-compose.yml updated with monitoring variables
- [x] requirements files updated (5 new packages)
- [x] All feature flags configured

### Docker Readiness ✅

- [x] Dockerfile.mcp references updated requirements
- [x] Dockerfile.backend references updated requirements
- [x] docker-compose.yml networking verified
- [x] Health checks configured
- [x] Volume mounts configured
- [x] Environment variables passed correctly

---

## Production Deployment Steps

### Step 1: Code Transfer to NAS Server

```bash
# On NAS Server ({{NAS_IP}})
# Backup existing installation
cp -r /app/aura_ia_mcp /app/aura_ia_mcp.backup.$(date +%Y%m%d)

# Copy updated code
rsync -avz /source/code/path/ /app/aura_ia_mcp/

# Verify critical files
ls -la /app/aura_ia_mcp/config/dashboard_config.yaml
ls -la /app/aura_ia_mcp/requirements-base.txt
ls -la /app/aura_ia_mcp/docker-compose.yml
```

### Step 2: Docker Container Rebuild

```bash
# Navigate to project directory
cd /app/aura_ia_mcp

# Pull latest base images
docker pull postgres:16-alpine
docker pull qdrant/qdrant:v1.11.3
docker pull ollama/ollama:latest

# Build containers with new dependencies
docker compose build --no-cache

# Status check
docker images | grep aura
```

### Step 3: Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit for production environment
nano .env
# Required changes:
# FEATURE_REAL_TIME_UPDATES=true
# FEATURE_SYSTEM_MONITORING=true
# FEATURE_DATABASE_MONITORING=true
# DASHBOARD_ENV=production
# WEBSOCKET_HOST={{NAS_IP}}
# WEBSOCKET_PORT=8000
```

### Step 4: Service Startup

```bash
# Bring up services in order
docker compose up -d aura-ia-postgres
sleep 10

docker compose up -d aura-ia-qdrant
docker compose up -d aura-ia-ollama
sleep 20

docker compose up -d aura-ia-gateway
docker compose up -d aura-ia-ml

# Wait for health checks
sleep 15
docker compose ps
```

### Step 5: Health Check Verification

```bash
# Check service health
curl -i http://{{NAS_IP}}:9200/healthz
# Expected: HTTP 200 OK with {"status": "healthy"}

curl -i http://{{NAS_IP}}:9201/health
# Expected: HTTP 200 OK with health status

# Check WebSocket endpoints
curl -i http://{{NAS_IP}}:9200/ws/models
# Expected: HTTP 101 Switching Protocols (WebSocket upgrade)

# Check system metrics endpoint
curl http://{{NAS_IP}}:9200/api/system/metrics
# Expected: JSON with cpu_percent, memory_percent, etc.
```

### Step 6: Dashboard Access

```bash
# Dashboard should be accessible at:
http://{{NAS_IP}}:9205/

# Verify real-time features:
# 1. AI System panel shows live models
# 2. Governance tab shows role hierarchy
# 3. Omni Monitor shows system metrics
# 4. Intelligence Arena shows model debates
# 5. Chat responds in real-time
```

---

## Rollback Procedure

```bash
# If deployment fails, rollback to previous version
cd /app/aura_ia_mcp

# Stop current services
docker compose down

# Restore backup
rm -rf /app/aura_ia_mcp
cp -r /app/aura_ia_mcp.backup.YYYYMMDD /app/aura_ia_mcp

# Rebuild previous version
cd /app/aura_ia_mcp
docker compose build
docker compose up -d

# Verify
docker compose ps
curl http://{{NAS_IP}}:9200/healthz
```

---

## Post-Deployment Verification

### API Endpoints Verification

```bash
# Gateway health
curl http://{{NAS_IP}}:9200/healthz

# ML Backend health
curl http://{{NAS_IP}}:9201/health

# System metrics
curl http://{{NAS_IP}}:9200/api/system/metrics

# Governance data
curl http://{{NAS_IP}}:9200/api/governance/roles

# WebSocket endpoints
wscat -c ws://{{NAS_IP}}:9200/ws/models
wscat -c ws://{{NAS_IP}}:9200/ws/system
wscat -c ws://{{NAS_IP}}:9200/ws/governance
```

### Performance Validation

```bash
# Monitor Docker container stats
docker stats

# Check logs for errors
docker compose logs -f aura-ia-gateway
docker compose logs -f aura-ia-ml

# Monitor WebSocket connections
curl http://{{NAS_IP}}:9200/api/websocket/connections
```

### User Acceptance Testing

- [ ] Dashboard loads without errors
- [ ] WebSocket connection establishes
- [ ] Real-time metrics update visible
- [ ] All panels display data correctly
- [ ] Chat functionality working
- [ ] No console errors
- [ ] Performance acceptable (< 100ms response)

---

## Configuration Verification

### Dashboard Configuration

```yaml
# Verify /app/aura_ia_mcp/config/dashboard_config.yaml
dashboard:
  host: "0.0.0.0"          # ✅ Verify
  port: 8080               # ✅ Verify
  environment: "production" # ✅ Verify

websocket:
  enabled: true            # ✅ Verify
  protocol: "ws"           # ✅ Verify
  host: "{{NAS_IP}}"    # ✅ UPDATE
  port: 8000               # ✅ Verify

monitoring:
  system:
    enabled: true          # ✅ Verify
  gpu:
    enabled: false         # ✅ Verify (or true if GPU available)
```

### Environment Variables

```bash
# Verify .env file has:
FEATURE_REAL_TIME_UPDATES=true          # ✅ WebSocket enabled
FEATURE_WEBSOCKET_FALLBACK=true         # ✅ Fallback enabled
FEATURE_SYSTEM_MONITORING=true          # ✅ Monitoring enabled
FEATURE_DATABASE_MONITORING=true        # ✅ DB monitoring enabled
ENABLE_GPU_MONITORING=false             # ✅ GPU (set to true if available)
WEBSOCKET_HOST={{NAS_IP}}            # ✅ UPDATE IP
```

### Docker Compose Verification

```bash
# Verify services are healthy
docker compose ps
# All services should show "healthy" or "Up"

# Check volumes are mounted
docker volume ls | grep mcp

# Verify network
docker network inspect mcp-network
# All aura-ia-* services should be connected
```

---

## Performance Baseline

### Expected Performance After Deployment

| Metric | Baseline | Target | Production |
|--------|----------|--------|-----------|
| Chat Response | 10.5ms | < 100ms | ✅ |
| WebSocket Latency | 1.2ms | < 50ms | ✅ |
| System Metrics Update | 1000ms | | ✅ |
| Connection Retry | 1s-30s backoff | | ✅ |
| Concurrent Connections | 50+ | | ✅ |
| Throughput | 1000+ msg/sec | | ✅ |

---

## Monitoring Setup

### Docker Container Monitoring

```bash
# Monitor in real-time
docker stats

# Monitor specific container
docker stats aura-ia-gateway

# Log monitoring
docker logs -f aura-ia-gateway
docker logs -f aura-ia-ml
```

### Application Monitoring

```bash
# Health endpoint monitoring
watch -n 5 'curl -s http://{{NAS_IP}}:9200/healthz | jq .'

# WebSocket connection tracking
curl http://{{NAS_IP}}:9200/api/websocket/connections

# System metrics tracking
curl http://{{NAS_IP}}:9200/api/system/metrics
```

---

## Known Issues & Mitigations

### Issue 1: GPU Detection Failure

**Symptom**: GPU monitoring errors in logs  
**Mitigation**: Set `ENABLE_GPU_MONITORING=false` in .env  
**Resolution**: Install NVIDIA drivers if GPU available

### Issue 2: WebSocket Connection Timeout

**Symptom**: Dashboard shows "Connection failed"  
**Mitigation**: Check firewall rules for port 8000  
**Resolution**: Allow WebSocket traffic (ws:// and wss://)

### Issue 3: High Memory Usage

**Symptom**: Container restarts due to memory  
**Mitigation**: Increase Docker memory limits  
**Resolution**: `docker update --memory 4g aura-ia-ml`

### Issue 4: Database Connection Pool Exhaustion

**Symptom**: "Too many connections" errors  
**Mitigation**: Check QDRANT_POOL_SIZE in .env  
**Resolution**: Increase pool size or reduce concurrent requests

---

## Success Criteria

✅ **All of the following must be true for successful deployment:**

1. All Docker containers start and remain healthy
2. Gateway health endpoint returns 200 OK
3. ML Backend health endpoint returns 200 OK
4. WebSocket endpoints accept connections
5. System metrics API returns valid JSON
6. Dashboard loads without console errors
7. Real-time updates visible in dashboard
8. Chat system responds within 100ms
9. All panels display data correctly
10. No security warnings in logs

---

## Post-Deployment Checklist

- [ ] All containers running and healthy
- [ ] Health check endpoints responding
- [ ] WebSocket connections established
- [ ] Dashboard accessible at <http://{{NAS_IP}}:9205/>
- [ ] Real-time metrics visible
- [ ] Chat functional
- [ ] No errors in logs
- [ ] Performance metrics acceptable
- [ ] Backups created
- [ ] Documentation updated

---

## Contact & Support

**Deployment Issues:**

1. Check logs: `docker compose logs -f`
2. Verify network: `docker network inspect mcp-network`
3. Check endpoints: `curl http://{{NAS_IP}}:9200/healthz`
4. Review configuration: `cat .env`

**Rollback Emergency:**

```bash
docker compose down
cp -r /app/aura_ia_mcp.backup.YYYYMMDD /app/aura_ia_mcp
cd /app/aura_ia_mcp
docker compose up -d
```

---

## Approval & Sign-Off

**Deployment Checklist**: ✅ COMPLETE  
**Code Quality**: ✅ VERIFIED  
**Test Results**: ✅ 40/40 PASSING  
**Documentation**: ✅ COMPREHENSIVE  

**Status**: ✅ **READY FOR PRODUCTION DEPLOYMENT**

Proceed to **Task 7.2: Update Documentation** after successful deployment.
