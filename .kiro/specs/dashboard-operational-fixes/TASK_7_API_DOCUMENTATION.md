# 📚 TASK 7.2 - API DOCUMENTATION UPDATE

**Status**: DOCUMENTATION COMPLETE  
**Date**: December 13, 2025  
**Scope**: New WebSocket endpoints, monitoring capabilities, configuration options

---

## New WebSocket Endpoints

### Endpoint: /ws/models

**Purpose**: Real-time model status and statistics  
**Protocol**: WebSocket (ws:// or wss://)  
**Connection URL**: `ws://localhost:9200/ws/models`

**Message Format (Incoming)**:

```json
{
  "type": "model_status",
  "timestamp": 1702500000,
  "data": {
    "model_id": "ollama:llama3",
    "model_name": "Llama 3",
    "status": "loaded",
    "memory_usage_mb": 4096,
    "memory_total_mb": 8192,
    "inference_time_ms": 2500,
    "tokens_per_second": 45.2,
    "active_sessions": 3
  }
}
```

**Message Format (Status Updates)**:

```json
{
  "type": "model_loaded",
  "model_id": "ollama:llama3",
  "timestamp": 1702500000
}

{
  "type": "model_unloaded",
  "model_id": "ollama:llama3",
  "timestamp": 1702500000
}
```

**Connection Parameters**:

- `reconnect_attempts`: 10 (maximum retries)
- `reconnect_delay_ms`: 1000-30000 (exponential backoff)
- `ping_interval_ms`: 30000 (keep-alive)
- `pong_timeout_ms`: 10000 (response timeout)

**Error Handling**:

```json
{
  "type": "error",
  "code": "CONNECTION_TIMEOUT",
  "message": "Failed to connect to model service",
  "timestamp": 1702500000
}
```

---

### Endpoint: /ws/system

**Purpose**: Real-time system metrics (CPU, RAM, disk, network, GPU)  
**Protocol**: WebSocket (ws:// or wss://)  
**Connection URL**: `ws://localhost:9200/ws/system`

**Message Format**:

```json
{
  "type": "system_metrics",
  "timestamp": 1702500000,
  "data": {
    "cpu": {
      "percent": 45.2,
      "cores": 8,
      "frequency_mhz": 2400
    },
    "memory": {
      "percent": 62.3,
      "used_mb": 4096,
      "total_mb": 6553.6,
      "available_mb": 2457.6
    },
    "disk": {
      "percent": 45.2,
      "used_gb": 450,
      "total_gb": 1000,
      "read_speed_mbs": 125.5,
      "write_speed_mbs": 98.2
    },
    "network": {
      "bytes_sent": 1000000,
      "bytes_recv": 2000000,
      "packets_sent": 5000,
      "packets_recv": 10000,
      "errors_in": 0,
      "errors_out": 0
    },
    "gpu": {
      "available": true,
      "gpu_id": 0,
      "name": "NVIDIA GeForce RTX 3080",
      "percent": 75.5,
      "memory_used_mb": 4096,
      "memory_total_mb": 10240,
      "temperature_c": 62
    },
    "temperature": {
      "cpu_c": 45.5,
      "gpu_c": 62.0
    }
  }
}
```

**Update Intervals**:

- System metrics: 1000ms (1 second)
- GPU metrics: 2000ms (2 seconds) - if enabled
- Temperature: 3000ms (3 seconds) - if available

---

### Endpoint: /ws/governance

**Purpose**: Real-time governance role hierarchy and audit events  
**Protocol**: WebSocket (ws:// or wss://)  
**Connection URL**: `ws://localhost:9200/ws/governance`

**Message Format - Role Hierarchy**:

```json
{
  "type": "role_hierarchy",
  "timestamp": 1702500000,
  "data": {
    "roles": [
      {
        "role_id": "admin",
        "role_name": "Administrator",
        "description": "Full system access",
        "parent_role": null,
        "capabilities": ["execute", "read", "write", "delete", "manage"],
        "trust_level": 1.0,
        "member_count": 2
      },
      {
        "role_id": "developer",
        "role_name": "Developer",
        "description": "Code execution and debugging",
        "parent_role": "user",
        "capabilities": ["execute", "read", "write", "debug"],
        "trust_level": 0.8,
        "member_count": 15
      }
    ]
  }
}
```

**Message Format - Audit Events**:

```json
{
  "type": "audit_event",
  "timestamp": 1702500000,
  "data": {
    "event_id": "evt_12345",
    "event_type": "role_assignment",
    "actor_id": "user_123",
    "target_id": "user_456",
    "action": "assigned role",
    "role": "developer",
    "status": "success",
    "details": "User added to developer role"
  }
}
```

---

### Endpoint: /ws/database

**Purpose**: Real-time database performance and health metrics  
**Protocol**: WebSocket (ws:// or wss://)  
**Connection URL**: `ws://localhost:9200/ws/database`

**Message Format**:

```json
{
  "type": "database_metrics",
  "timestamp": 1702500000,
  "data": {
    "connection": {
      "active_connections": 8,
      "idle_connections": 2,
      "max_connections": 100,
      "connection_pool_utilization": 0.10
    },
    "performance": {
      "active_queries": 3,
      "avg_query_time_ms": 45.2,
      "slow_queries_count": 2,
      "slow_query_threshold_ms": 1000,
      "query_cache_hit_rate": 0.92
    },
    "storage": {
      "database_size_gb": 5.2,
      "indexes_size_gb": 1.8,
      "tables": [
        {
          "table_name": "chat_messages",
          "size_mb": 512,
          "row_count": 1000000,
          "last_vacuum": "2025-12-13T12:00:00Z"
        }
      ]
    },
    "health": {
      "status": "healthy",
      "replication_lag_ms": 0,
      "backup_status": "completed",
      "last_backup": "2025-12-13T11:00:00Z"
    }
  }
}
```

**Update Intervals**:

- Database metrics: 5000ms (5 seconds)
- Slow queries: 10000ms (10 seconds)
- Storage stats: 60000ms (1 minute)

---

## REST API Endpoints (Enhanced)

### GET /api/system/metrics

**Purpose**: Get current system metrics (REST alternative to WebSocket)  
**Method**: GET  
**URL**: `http://localhost:9200/api/system/metrics`

**Response**:

```json
{
  "cpu_percent": 45.2,
  "memory_percent": 62.3,
  "disk_percent": 45.2,
  "network": {
    "bytes_sent": 1000000,
    "bytes_recv": 2000000
  },
  "timestamp": 1702500000
}
```

**Status Codes**:

- `200 OK` - Metrics retrieved
- `503 Service Unavailable` - Monitoring disabled

---

### GET /api/governance/roles

**Purpose**: Get governance role hierarchy  
**Method**: GET  
**URL**: `http://localhost:9200/api/governance/roles`

**Response**:

```json
{
  "roles": [
    {
      "role_id": "admin",
      "role_name": "Administrator",
      "capabilities": ["execute", "read", "write", "delete", "manage"],
      "member_count": 2
    }
  ]
}
```

**Query Parameters**:

- `include_members`: true/false - Include role members
- `include_permissions`: true/false - Include detailed permissions

---

### GET /api/governance/audit-logs

**Purpose**: Get audit log entries  
**Method**: GET  
**URL**: `http://localhost:9200/api/governance/audit-logs`

**Query Parameters**:

- `limit`: Number of entries (default: 100, max: 1000)
- `offset`: Pagination offset (default: 0)
- `event_type`: Filter by type (optional)
- `actor_id`: Filter by actor (optional)
- `since`: ISO 8601 timestamp (optional)

**Response**:

```json
{
  "audit_logs": [
    {
      "event_id": "evt_12345",
      "event_type": "role_assignment",
      "actor_id": "user_123",
      "timestamp": "2025-12-13T12:00:00Z",
      "status": "success"
    }
  ],
  "total": 1500,
  "limit": 100,
  "offset": 0
}
```

---

### GET /api/models/status

**Purpose**: Get all loaded models and their status  
**Method**: GET  
**URL**: `http://localhost:9200/api/models/status`

**Response**:

```json
{
  "models": [
    {
      "model_id": "ollama:llama3",
      "model_name": "Llama 3",
      "status": "loaded",
      "memory_usage_mb": 4096,
      "inference_time_ms": 2500,
      "active_sessions": 3
    }
  ]
}
```

---

### GET /api/database/health

**Purpose**: Get database health status  
**Method**: GET  
**URL**: `http://localhost:9200/api/database/health`

**Response**:

```json
{
  "status": "healthy",
  "active_connections": 8,
  "connection_pool_utilization": 0.10,
  "avg_query_time_ms": 45.2,
  "replication_lag_ms": 0,
  "backup_status": "completed"
}
```

---

### GET /api/websocket/connections

**Purpose**: Get WebSocket connection statistics  
**Method**: GET  
**URL**: `http://localhost:9200/api/websocket/connections`

**Response**:

```json
{
  "total_connections": 12,
  "active_connections": 10,
  "failed_connections": 0,
  "reconnections": 2,
  "endpoints": {
    "/ws/models": 3,
    "/ws/system": 4,
    "/ws/governance": 2,
    "/ws/database": 2
  }
}
```

---

## Configuration Reference

### Environment Variables

#### WebSocket Configuration

```env
WEBSOCKET_HOST=localhost           # WebSocket server host
WEBSOCKET_PORT=8000                # WebSocket server port
WEBSOCKET_PROTOCOL=ws              # ws or wss
FEATURE_WEBSOCKET_FALLBACK=true    # Enable HTTP polling fallback
```

#### Monitoring Features

```env
FEATURE_SYSTEM_MONITORING=true     # Enable system metrics monitoring
FEATURE_DATABASE_MONITORING=true   # Enable database monitoring
ENABLE_GPU_MONITORING=false        # Enable GPU monitoring (requires GPUtil)
ENABLE_TEMPERATURE_MONITORING=false # Enable temperature monitoring
```

#### Real-time Updates

```env
FEATURE_REAL_TIME_UPDATES=true     # Enable real-time WebSocket updates
WEBSOCKET_MESSAGE_BUFFER_SIZE=1000 # Max messages when offline
WEBSOCKET_RECONNECT_ATTEMPTS=10    # Max reconnection attempts
WEBSOCKET_RECONNECT_DELAY_MS=1000  # Initial reconnection delay
```

#### Panel Features

```env
FEATURE_GOVERNANCE_PANEL=true      # Enable governance panel
FEATURE_AI_SYSTEM_PANEL=true       # Enable AI system panel
FEATURE_INTELLIGENCE_ARENA=true    # Enable intelligence arena
FEATURE_OMNI_MONITOR=true          # Enable omni monitor
FEATURE_CHAT_OPTIMIZATION=true     # Enable chat optimization
```

---

## Performance Tuning Guide

### For High-Load Environments

```yaml
# In config/dashboard_config.yaml
websocket:
  reconnect:
    backoff_multiplier: 2.0    # Faster backoff for stable networks
    max_attempts: 5            # Fewer retries for reliability
    max_delay_ms: 10000        # Cap at 10s instead of 30s

monitoring:
  system:
    sample_interval_ms: 2000   # Less frequent sampling
  gpu:
    sample_interval_ms: 5000   # Less frequent GPU sampling
  database:
    sample_interval_ms: 10000  # Less frequent DB sampling
```

### For Low-Latency Requirements

```yaml
websocket:
  reconnect:
    backoff_multiplier: 1.2    # More gradual backoff
    max_attempts: 15           # More retries
    max_delay_ms: 60000        # Up to 60s for very persistent connection

updates:
  system_metrics: 500          # Faster updates
  model_status: 500
  chat_status: 250
```

---

## Error Handling Guide

### Common WebSocket Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| CONNECTION_TIMEOUT | Network connectivity issue | Check firewall, verify endpoint URL |
| CONNECTION_REFUSED | Service not running | Start aura-ia-gateway service |
| AUTHENTICATION_FAILED | Invalid credentials | Check GITHUB_TOKEN in environment |
| PAYLOAD_TOO_LARGE | Message > 1MB | Reduce batch size or increase limit |
| RATE_LIMITED | Too many requests | Implement request throttling |

### Recovery Strategies

1. **Automatic Reconnection**: Handled by client (exponential backoff)
2. **Message Buffering**: Up to 1000 messages when offline
3. **Fallback Mechanism**: HTTP polling when WebSocket unavailable
4. **Health Checks**: Periodic health endpoint pings

---

## Security Considerations

### WebSocket Security

- Use `wss://` (WebSocket Secure) in production
- Implement CORS validation
- Require authentication for sensitive endpoints
- Rate limit WebSocket connections
- Validate message payloads

### API Security

- Use HTTPS in production
- Implement API key authentication
- Add request signing
- Monitor for unusual patterns
- Log all security events

### Data Privacy

- Encrypt sensitive data in transit
- Mask sensitive values in logs
- Implement data retention policies
- Audit database access

---

## Monitoring & Alerting

### Key Metrics to Monitor

```
- WebSocket connection count
- Average message latency
- Failed connection attempts
- System metric collection success rate
- Database query performance
- GPU memory usage
```

### Alert Thresholds

| Alert | Threshold | Action |
|-------|-----------|--------|
| High CPU | > 85% | Investigate load |
| High Memory | > 90% | Check memory leaks |
| DB Connections | > 95% pool | Increase pool size |
| WS Failures | > 5/min | Restart services |
| Response Time | > 500ms | Optimize queries |

---

## Troubleshooting Guide

### WebSocket Connection Issues

```bash
# Test WebSocket endpoint
wscat -c ws://localhost:9200/ws/models

# Check service logs
docker logs aura-ia-gateway

# Verify firewall
iptables -L | grep 8000

# Check network connectivity
ping aura-ia-gateway
```

### Performance Issues

```bash
# Monitor Docker stats
docker stats aura-ia-gateway

# Check database connections
curl http://localhost:9200/api/database/health

# Check system metrics
curl http://localhost:9200/api/system/metrics
```

### Monitoring Not Working

```bash
# Verify feature is enabled
grep FEATURE_SYSTEM_MONITORING .env

# Check psutil installation
python -c "import psutil; print(psutil.cpu_percent())"

# Verify GPU if enabled
python -c "import GPUtil; print(GPUtil.getGPUs())"
```

---

## Release Notes

### Version 1.0 - December 13, 2025

**New Features**:

- WebSocket support for real-time updates
- System monitoring with psutil
- Database performance tracking
- GPU monitoring (optional)
- Governance audit log streaming
- Model status real-time updates

**Requirements**:

- Docker Compose
- Python 3.11+
- psutil >= 5.9.0
- GPUtil >= 1.4.0 (optional)

**Breaking Changes**:

- None (backward compatible)

**Known Limitations**:

- GPU monitoring requires NVIDIA drivers
- Temperature monitoring platform-dependent
- Max 1000 buffered messages when offline

---

## Sign-Off

**Documentation**: ✅ COMPLETE  
**API Coverage**: ✅ ALL NEW ENDPOINTS DOCUMENTED  
**Configuration Guide**: ✅ COMPREHENSIVE  
**Troubleshooting**: ✅ INCLUDED  

**Status**: ✅ **READY FOR DEPLOYMENT**
