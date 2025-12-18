# MCP Server Deployment Guide

---
**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** 2025-11-14

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Production Deployment](#production-deployment)
3. [Configuration Examples](#configuration-examples)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Monitoring and Logging](#monitoring-and-logging)
6. [Security Best Practices](#security-best-practices)

---

## Development Environment Setup

### Prerequisites

Before setting up the MCP server integration, ensure you have:

- **Python 3.11+** installed
- **Kiro IDE** installed and configured
- **Git** for version control
- **Virtual environment** tool (venv or conda)
- **GitHub Personal Access Token** (for GitHub integration features)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd <project-directory>
```

### Step 2: Create Virtual Environment

```bash
# Using venv
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Start Backend Service

The MCP server requires the AI intelligence backend service running on port 8001:

```bash
# Start the backend service
python mock_backend_server.py
```

Verify the backend is running:

```bash
curl http://127.0.0.1:8001/health
```

Expected response:
```json
{"status": "ok", "version": "1.0.0"}
```

### Step 5: Configure MCP Server in Kiro IDE

Create the MCP configuration file at `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "http://127.0.0.1:8001",
        "IDE_AGENTS_REQUEST_TIMEOUT": "30.0",
        "IDE_AGENTS_ULTRA_ENABLED": "true",
        "IDE_AGENTS_ULTRA_MOCK": "false",
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "MCP_TOOL_SPANS_DIR": "./logs"
      },
      "disabled": false,
      "autoApprove": [
        "ide_agents_health",
        "ide_agents_ml_analyze_emotion",
        "ide_agents_ml_get_predictions",
        "ide_agents_ml_get_learning_insights",
        "ide_agents_ml_get_system_status",
        "ide_agents_github_repos",
        "ide_agents_github_rank_repos",
        "ide_agents_github_rank_all",
        "ide_agents_resource",
        "ide_agents_prompt",
        "ide_agents_catalog"
      ]
    }
  }
}
```

### Step 6: Set Environment Variables

Create a `.env` file in the project root:

```bash
# GitHub Integration
GITHUB_TOKEN=ghp_your_personal_access_token_here

# Backend Configuration
IDE_AGENTS_BACKEND_URL=http://127.0.0.1:8001
IDE_AGENTS_REQUEST_TIMEOUT=30.0

# ULTRA Mode Configuration
IDE_AGENTS_ULTRA_ENABLED=true
IDE_AGENTS_ULTRA_MOCK=false
IDE_AGENTS_ULTRA_LOCAL=false

# Telemetry
MCP_TOOL_SPANS_DIR=./logs
```

**Important:** Never commit `.env` files to version control. Add to `.gitignore`:

```bash
echo ".env" >> .gitignore
```

### Step 7: Test MCP Server Standalone

Before integrating with Kiro IDE, test the MCP server independently:

```bash
python -m ide_agents_mcp_server
```

The server should start and display:
```
MCP Server started successfully
Listening on stdio
ULTRA mode: enabled
```

Press `Ctrl+C` to stop the server.

### Step 8: Restart Kiro IDE

1. Close Kiro IDE completely
2. Reopen Kiro IDE
3. The MCP server should start automatically
4. Check the Kiro output panel for MCP connection status

### Step 9: Verify Integration

Test the integration by asking the Kiro chat agent:

```
Can you check the MCP server health?
```

Expected response should include server status and available tools.

---

## Production Deployment

### Architecture Considerations

For production deployments, consider the following architecture:

```
┌─────────────────┐
│   Kiro IDE      │
│   (Client)      │
└────────┬────────┘
         │ MCP Protocol
┌────────▼────────┐
│  MCP Server     │
│  (Local/Remote) │
└────────┬────────┘
         │ HTTPS/REST
┌────────▼────────┐
│  Backend API    │
│  (Production)   │
└─────────────────┘
```

### Production Backend Deployment

#### Option 1: Docker Deployment

Create `Dockerfile` for the backend service:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "mock_backend_server.py"]
```

Build and run:

```bash
docker build -t ide-agents-backend .
docker run -d -p 8001:8001 --name ide-agents-backend ide-agents-backend
```

#### Option 2: Cloud Deployment (AWS)

Deploy using AWS ECS or EC2:

1. **Create EC2 instance** (t3.medium or larger)
2. **Install dependencies** and configure security groups
3. **Set up systemd service** for auto-restart
4. **Configure HTTPS** with Let's Encrypt
5. **Set up CloudWatch** for monitoring

Example systemd service (`/etc/systemd/system/ide-agents-backend.service`):

```ini
[Unit]
Description=IDE Agents Backend Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/ide-agents
ExecStart=/opt/ide-agents/venv/bin/python mock_backend_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable ide-agents-backend
sudo systemctl start ide-agents-backend
sudo systemctl status ide-agents-backend
```

### Production MCP Configuration

Update `.kiro/settings/mcp.json` for production:

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "/opt/ide-agents/venv/bin/python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "https://api.yourcompany.com",
        "IDE_AGENTS_REQUEST_TIMEOUT": "60.0",
        "IDE_AGENTS_ULTRA_ENABLED": "true",
        "IDE_AGENTS_ULTRA_MOCK": "false",
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "MCP_TOOL_SPANS_DIR": "/var/log/ide-agents"
      },
      "disabled": false,
      "autoApprove": [
        "ide_agents_health",
        "ide_agents_ml_analyze_emotion",
        "ide_agents_ml_get_predictions",
        "ide_agents_ml_get_learning_insights",
        "ide_agents_ml_get_system_status",
        "ide_agents_github_repos",
        "ide_agents_github_rank_repos",
        "ide_agents_github_rank_all",
        "ide_agents_resource",
        "ide_agents_prompt",
        "ide_agents_catalog"
      ]
    }
  }
}
```

### Security Hardening for Production

1. **Use HTTPS only** for backend communication
2. **Implement API authentication** (JWT tokens, API keys)
3. **Enable rate limiting** at the API gateway level
4. **Use secrets management** (AWS Secrets Manager, HashiCorp Vault)
5. **Enable audit logging** for all API calls
6. **Implement IP whitelisting** if applicable
7. **Regular security updates** and dependency scanning

### Scaling Considerations

For high-traffic scenarios:

- **Load Balancing**: Use AWS ALB or NGINX
- **Horizontal Scaling**: Deploy multiple backend instances
- **Caching**: Implement Redis for frequently accessed data
- **Database**: Use managed PostgreSQL/MongoDB for persistence
- **CDN**: Use CloudFront for static resources
- **Auto-scaling**: Configure based on CPU/memory metrics

---

## Configuration Examples

### Example 1: Development Environment (Local)

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "http://127.0.0.1:8001",
        "IDE_AGENTS_REQUEST_TIMEOUT": "30.0",
        "IDE_AGENTS_ULTRA_ENABLED": "true",
        "IDE_AGENTS_ULTRA_MOCK": "false",
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "MCP_TOOL_SPANS_DIR": "./logs"
      },
      "disabled": false,
      "autoApprove": ["ide_agents_health", "ide_agents_ml_analyze_emotion"]
    }
  }
}
```

### Example 2: Testing Environment (Mock Mode)

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "http://127.0.0.1:8001",
        "IDE_AGENTS_REQUEST_TIMEOUT": "10.0",
        "IDE_AGENTS_ULTRA_ENABLED": "true",
        "IDE_AGENTS_ULTRA_MOCK": "true",
        "GITHUB_TOKEN": "mock_token",
        "MCP_TOOL_SPANS_DIR": "./test_logs"
      },
      "disabled": false,
      "autoApprove": ["*"]
    }
  }
}
```

### Example 3: Production Environment (Remote Backend)

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "/usr/bin/python3",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "https://api.production.com",
        "IDE_AGENTS_REQUEST_TIMEOUT": "60.0",
        "IDE_AGENTS_ULTRA_ENABLED": "true",
        "IDE_AGENTS_ULTRA_MOCK": "false",
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "MCP_TOOL_SPANS_DIR": "/var/log/mcp"
      },
      "disabled": false,
      "autoApprove": [
        "ide_agents_health",
        "ide_agents_ml_analyze_emotion",
        "ide_agents_ml_get_predictions",
        "ide_agents_github_repos"
      ]
    }
  }
}
```

### Example 4: Disabled MCP Server

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {},
      "disabled": true,
      "autoApprove": []
    }
  }
}
```

### Example 5: Minimal Configuration (Core Tools Only)

```json
{
  "mcpServers": {
    "ide-agents-mcp": {
      "command": "python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "http://127.0.0.1:8001",
        "IDE_AGENTS_ULTRA_ENABLED": "false",
        "MCP_TOOL_SPANS_DIR": "./logs"
      },
      "disabled": false,
      "autoApprove": ["ide_agents_health", "ide_agents_catalog"]
    }
  }
}
```

---

## Troubleshooting Guide

### Issue 1: MCP Server Won't Start

**Symptoms:**
- Kiro IDE shows "MCP server failed to start"
- No MCP tools available in chat agent

**Diagnosis:**

```bash
# Test Python interpreter
python --version

# Test module import
python -c "import ide_agents_mcp_server"

# Check dependencies
pip list | grep fastmcp
```

**Solutions:**

1. **Verify Python path in configuration:**
   ```bash
   which python  # On macOS/Linux
   where python  # On Windows
   ```
   Update `command` in `mcp.json` with the correct path.

2. **Install missing dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Check Kiro IDE logs:**
   - Open Kiro IDE Output panel
   - Look for MCP server error messages
   - Check for permission issues

### Issue 2: Backend Service Unavailable

**Symptoms:**
- MCP tools return "Backend service unavailable"
- Health check fails

**Diagnosis:**

```bash
# Test backend connectivity
curl http://127.0.0.1:8001/health

# Check if backend is running
netstat -an | grep 8001  # On Windows
lsof -i :8001            # On macOS/Linux

# Test with verbose output
curl -v http://127.0.0.1:8001/health
```

**Solutions:**

1. **Start the backend service:**
   ```bash
   python mock_backend_server.py
   ```

2. **Check firewall settings:**
   - Ensure port 8001 is not blocked
   - Add firewall exception if needed

3. **Verify backend URL in configuration:**
   - Check `IDE_AGENTS_BACKEND_URL` in `mcp.json`
   - Ensure it matches the actual backend address

4. **Use mock mode for testing:**
   ```json
   "IDE_AGENTS_ULTRA_MOCK": "true"
   ```

### Issue 3: GitHub Integration Fails

**Symptoms:**
- GitHub tools return authentication errors
- "Invalid GitHub token" messages

**Diagnosis:**

```bash
# Test GitHub token
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user

# Check token scopes
curl -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/rate_limit
```

**Solutions:**

1. **Generate new GitHub token:**
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Create token with `repo` and `read:user` scopes
   - Update `.env` file with new token

2. **Verify token is loaded:**
   ```bash
   echo $GITHUB_TOKEN  # Should show your token
   ```

3. **Check token expiration:**
   - Tokens may expire after 90 days
   - Regenerate if expired

4. **Test without GitHub features:**
   - Remove GitHub tools from `autoApprove` list
   - Use other MCP features while troubleshooting

### Issue 4: Tools Not Appearing in Kiro IDE

**Symptoms:**
- MCP server starts but tools are not available
- Chat agent doesn't recognize MCP commands

**Diagnosis:**

```bash
# Test tool discovery
python -c "
from ide_agents_mcp_server import mcp
print([tool.name for tool in mcp.list_tools()])
"
```

**Solutions:**

1. **Enable ULTRA mode:**
   ```json
   "IDE_AGENTS_ULTRA_ENABLED": "true"
   ```

2. **Restart Kiro IDE completely:**
   - Close all windows
   - Reopen and wait for MCP server to initialize

3. **Check plugin loading:**
   - Review MCP server logs for plugin errors
   - Ensure all plugin dependencies are installed

4. **Verify configuration syntax:**
   - Validate `mcp.json` with a JSON validator
   - Check for trailing commas or syntax errors

### Issue 5: Rate Limiting Errors

**Symptoms:**
- "Rate limit exceeded" messages
- Tools become temporarily unavailable

**Diagnosis:**

Check telemetry logs:

```bash
tail -f logs/mcp_tool_spans.jsonl | grep rate_limit
```

**Solutions:**

1. **Wait for rate limit window (250ms):**
   - Rate limiting is automatic
   - Tools will become available after cooldown

2. **Reduce tool invocation frequency:**
   - Batch operations when possible
   - Avoid rapid successive calls

3. **Adjust rate limit settings (advanced):**
   - Modify `RATE_LIMIT_INTERVAL` in server code
   - Only for development/testing environments

### Issue 6: Telemetry Not Recording

**Symptoms:**
- No telemetry data in `logs/mcp_tool_spans.jsonl`
- Monitoring data unavailable

**Diagnosis:**

```bash
# Check if logs directory exists
ls -la logs/

# Check file permissions
ls -la logs/mcp_tool_spans.jsonl

# Test write permissions
touch logs/test_write.txt
```

**Solutions:**

1. **Create logs directory:**
   ```bash
   mkdir -p logs
   chmod 755 logs
   ```

2. **Verify MCP_TOOL_SPANS_DIR:**
   ```json
   "MCP_TOOL_SPANS_DIR": "./logs"
   ```

3. **Check disk space:**
   ```bash
   df -h  # Ensure sufficient disk space
   ```

4. **Review file permissions:**
   ```bash
   chmod 644 logs/mcp_tool_spans.jsonl
   ```

### Issue 7: Performance Issues

**Symptoms:**
- Slow tool responses
- High latency
- Timeouts

**Diagnosis:**

Analyze telemetry data:

```bash
# Check average response times
cat logs/mcp_tool_spans.jsonl | jq '.duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'

# Find slowest tools
cat logs/mcp_tool_spans.jsonl | jq -r '[.tool_name, .duration_ms] | @tsv' | sort -k2 -rn | head -10
```

**Solutions:**

1. **Increase timeout:**
   ```json
   "IDE_AGENTS_REQUEST_TIMEOUT": "60.0"
   ```

2. **Check backend performance:**
   - Monitor backend CPU/memory usage
   - Scale backend resources if needed

3. **Enable caching:**
   - Implement Redis for frequently accessed data
   - Cache GitHub repository data

4. **Optimize network:**
   - Use local backend when possible
   - Reduce network latency with CDN

### Issue 8: Approval Workflow Not Working

**Symptoms:**
- Commands execute without approval prompts
- Approval prompts don't appear

**Diagnosis:**

Check autoApprove configuration:

```bash
cat .kiro/settings/mcp.json | jq '.mcpServers["ide-agents-mcp"].autoApprove'
```

**Solutions:**

1. **Remove tool from autoApprove list:**
   ```json
   "autoApprove": [
     "ide_agents_health"
     // Remove "ide_agents_command" to require approval
   ]
   ```

2. **Test approval workflow:**
   - Use `ide_agents_command` with method "run"
   - Should prompt for approval

3. **Check Kiro IDE approval UI:**
   - Ensure approval prompts are not hidden
   - Check notification settings

---

## Monitoring and Logging

### Telemetry Data Structure

Telemetry spans are written to `logs/mcp_tool_spans.jsonl` in JSON Lines format:

```json
{
  "timestamp_ms": 1699999999000,
  "tool_name": "ide_agents_ml_get_predictions",
  "method": "GET /ai/intelligence/predictions/default_user",
  "duration_ms": 145,
  "success": true,
  "error_code": null,
  "extra": {
    "user_id": "default_user",
    "mode": "backend"
  }
}
```

### Analyzing Telemetry Data

#### Tool Usage Statistics

```bash
# Count tool invocations
cat logs/mcp_tool_spans.jsonl | jq -r '.tool_name' | sort | uniq -c | sort -rn

# Success rate by tool
cat logs/mcp_tool_spans.jsonl | jq -r '[.tool_name, .success] | @tsv' | \
  awk '{tools[$1]++; if($2=="true") success[$1]++} END {for(t in tools) print t, success[t]/tools[t]*100"%"}'
```

#### Performance Metrics

```bash
# Average response time by tool
cat logs/mcp_tool_spans.jsonl | jq -r '[.tool_name, .duration_ms] | @tsv' | \
  awk '{sum[$1]+=$2; count[$1]++} END {for(t in sum) print t, sum[t]/count[t]"ms"}'

# 95th percentile latency
cat logs/mcp_tool_spans.jsonl | jq '.duration_ms' | sort -n | \
  awk '{a[NR]=$1} END {print a[int(NR*0.95)]}'
```

#### Error Analysis

```bash
# Error rate over time
cat logs/mcp_tool_spans.jsonl | jq -r '[.timestamp_ms, .success] | @tsv' | \
  awk '{hour=int($1/3600000); if($2=="false") errors[hour]++; total[hour]++} \
       END {for(h in total) print h, errors[h]/total[h]*100"%"}'

# Most common errors
cat logs/mcp_tool_spans.jsonl | jq -r 'select(.success==false) | .error_code' | \
  sort | uniq -c | sort -rn
```

### Log Rotation

Implement log rotation to prevent disk space issues:

**Linux/macOS (logrotate):**

Create `/etc/logrotate.d/mcp-telemetry`:

```
/path/to/logs/mcp_tool_spans.jsonl {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 user group
    postrotate
        # Optional: restart MCP server
    endscript
}
```

**Windows (PowerShell script):**

```powershell
# rotate-logs.ps1
$logFile = "logs\mcp_tool_spans.jsonl"
$maxSize = 100MB

if ((Get-Item $logFile).Length -gt $maxSize) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Move-Item $logFile "$logFile.$timestamp"
    Compress-Archive "$logFile.$timestamp" "$logFile.$timestamp.zip"
    Remove-Item "$logFile.$timestamp"
}
```

### Monitoring Best Practices

1. **Set up alerts for:**
   - Error rate > 5%
   - Average latency > 1000ms
   - Backend service downtime
   - Rate limit violations

2. **Track key metrics:**
   - Tool invocation count
   - Success/failure rates
   - Response time percentiles (p50, p95, p99)
   - Backend service health

3. **Regular reviews:**
   - Weekly telemetry analysis
   - Monthly performance optimization
   - Quarterly capacity planning

4. **Dashboard creation:**
   - Use Grafana or similar for visualization
   - Create real-time monitoring dashboards
   - Set up automated reports

### Integration with External Monitoring

#### Prometheus Integration

Export telemetry metrics to Prometheus:

```python
# metrics_exporter.py
from prometheus_client import Counter, Histogram, start_http_server
import json
import time

# Define metrics
tool_invocations = Counter('mcp_tool_invocations_total', 'Total tool invocations', ['tool_name', 'success'])
tool_duration = Histogram('mcp_tool_duration_seconds', 'Tool execution duration', ['tool_name'])

def process_telemetry_line(line):
    data = json.loads(line)
    tool_invocations.labels(
        tool_name=data['tool_name'],
        success=str(data['success'])
    ).inc()
    tool_duration.labels(tool_name=data['tool_name']).observe(data['duration_ms'] / 1000)

# Start metrics server
start_http_server(9090)

# Tail telemetry file
with open('logs/mcp_tool_spans.jsonl', 'r') as f:
    f.seek(0, 2)  # Go to end
    while True:
        line = f.readline()
        if line:
            process_telemetry_line(line)
        else:
            time.sleep(0.1)
```

#### CloudWatch Integration (AWS)

```python
# cloudwatch_exporter.py
import boto3
import json
from datetime import datetime

cloudwatch = boto3.client('cloudwatch')

def send_to_cloudwatch(span):
    cloudwatch.put_metric_data(
        Namespace='MCP/Tools',
        MetricData=[
            {
                'MetricName': 'ToolInvocations',
                'Dimensions': [
                    {'Name': 'ToolName', 'Value': span['tool_name']},
                    {'Name': 'Success', 'Value': str(span['success'])}
                ],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.fromtimestamp(span['timestamp_ms'] / 1000)
            },
            {
                'MetricName': 'ToolDuration',
                'Dimensions': [{'Name': 'ToolName', 'Value': span['tool_name']}],
                'Value': span['duration_ms'],
                'Unit': 'Milliseconds',
                'Timestamp': datetime.fromtimestamp(span['timestamp_ms'] / 1000)
            }
        ]
    )
```

---

## Security Best Practices

### 1. Token Management

**Never hardcode tokens:**

```json
// ❌ BAD
"GITHUB_TOKEN": "ghp_abc123..."

// ✅ GOOD
"GITHUB_TOKEN": "${GITHUB_TOKEN}"
```

**Use environment variables or secrets management:**

```bash
# Development
export GITHUB_TOKEN=ghp_your_token

# Production (AWS Secrets Manager)
aws secretsmanager get-secret-value --secret-id github-token --query SecretString --output text
```

### 2. Network Security

**Use HTTPS for production:**

```json
"IDE_AGENTS_BACKEND_URL": "https://api.yourcompany.com"
```

**Implement certificate pinning:**

```python
# In backend client
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.load_verify_locations('/path/to/ca-bundle.crt')
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)
```

### 3. Input Validation

**Always validate tool arguments:**

```python
def validate_github_query(query: str) -> bool:
    # Prevent injection attacks
    if len(query) > 1000:
        raise ValueError("Query too long")
    if any(char in query for char in ['<', '>', ';', '&', '|']):
        raise ValueError("Invalid characters in query")
    return True
```

### 4. Rate Limiting

**Implement multiple layers:**

1. **Client-side:** 250ms between requests
2. **Server-side:** 100 requests per minute per user
3. **API Gateway:** 1000 requests per minute per IP

### 5. Audit Logging

**Log all security-relevant events:**

```python
import logging

security_logger = logging.getLogger('security')
security_logger.info(f"Tool invocation: {tool_name} by {user_id} at {timestamp}")
security_logger.warning(f"Approval denied: {action_id} by {user_id}")
security_logger.error(f"Authentication failed: {error_details}")
```

### 6. Least Privilege Principle

**Configure minimal permissions:**

```json
"autoApprove": [
  // Only approve read-only operations
  "ide_agents_health",
  "ide_agents_ml_analyze_emotion",
  "ide_agents_github_repos"
  // Never auto-approve: ide_agents_command with method "run"
]
```

### 7. Regular Security Updates

**Maintain dependencies:**

```bash
# Check for vulnerabilities
pip audit

# Update dependencies
pip install --upgrade -r requirements.txt

# Review security advisories
pip list --outdated
```

### 8. Secrets Rotation

**Rotate tokens regularly:**

1. Generate new GitHub token every 90 days
2. Update `.env` file or secrets manager
3. Restart MCP server to load new token
4. Revoke old token after verification

---

## Kiro IDE Integration Testing

### Prerequisites Verification

Before starting integration testing, run the verification script:

```bash
python verify_integration_readiness.py
```

This script checks:
- Python version (3.11+)
- Required dependencies
- MCP configuration validity
- Backend service availability
- File system setup
- MCP server module functionality

Expected output:
```
✓ Python Version: PASS
✓ Dependencies: PASS
✓ MCP Configuration: PASS
✓ Backend Service: PASS
✓ Telemetry Directory: PASS
✓ MCP Server Module: PASS

Results: 6/6 checks passed
✓ Environment is ready for integration testing!
```

### Integration Testing Guide

Follow the comprehensive testing guide:

**[Kiro IDE Integration Test Guide](KIRO_IDE_INTEGRATION_TEST_GUIDE.md)**

This guide includes:
- 10 test suites with 37 individual tests
- Server lifecycle integration tests
- Tool discovery and registration tests
- Chat agent integration tests
- Approval workflow tests
- Error handling tests
- Performance validation tests
- Telemetry and debugging tests
- Configuration management tests
- End-to-end workflow tests
- Security validation tests

### Quick Reference

For rapid testing, use the quick reference card:

**[Integration Test Quick Reference](INTEGRATION_TEST_QUICK_REFERENCE.md)**

This includes:
- 5-minute quick start guide
- Essential test commands
- Critical success criteria
- Quick diagnostics
- Common issues and fixes
- Test coverage matrix

### Test Execution Workflow

1. **Verify Prerequisites:**
   ```bash
   python verify_integration_readiness.py
   ```

2. **Start Backend Service:**
   ```bash
   python mock_backend_server.py
   ```

3. **Launch Kiro IDE:**
   - Open Kiro IDE
   - Wait for MCP server to connect (< 10 seconds)
   - Verify connection in MCP Server view

4. **Run Test Suites:**
   - Follow test procedures in the Integration Test Guide
   - Record results using the provided template
   - Document any issues or failures

5. **Analyze Results:**
   - Review telemetry data in `logs/mcp_tool_spans.jsonl`
   - Check performance metrics
   - Verify all requirements met

6. **Generate Report:**
   - Complete the test results template
   - Calculate pass rate
   - Document recommendations

### Performance Requirements

Verify these critical performance metrics:

| Metric | Requirement | How to Verify |
|--------|-------------|---------------|
| Server Startup | < 10 seconds | Time from IDE launch to "Connected" |
| Backend Latency | < 500ms | Check telemetry duration_ms |
| Tool Discovery | < 5 seconds | Time to list all tools |
| Memory Usage | < 200MB | Task Manager / Resource Monitor |
| CPU Usage (Idle) | < 5% | Task Manager / Resource Monitor |

### Critical Test Scenarios

**Must-Pass Tests:**

1. ✅ Server auto-starts with Kiro IDE
2. ✅ All tools discovered (23+ with ULTRA enabled)
3. ✅ Emotion analysis returns valid results
4. ✅ GitHub search works with valid token
5. ✅ Approval workflow prompts for commands
6. ✅ Error handling provides user-friendly messages
7. ✅ Backend unavailable handled gracefully
8. ✅ Telemetry records all invocations
9. ✅ Performance meets < 500ms requirement
10. ✅ Server shuts down cleanly with IDE

### Integration Testing Checklist

Before signing off on production deployment:

- [ ] All 37 integration tests executed
- [ ] Pass rate > 95%
- [ ] Performance requirements met
- [ ] Security validation passed
- [ ] Error handling verified
- [ ] Telemetry useful for debugging
- [ ] Documentation complete
- [ ] User feedback positive
- [ ] Production configuration reviewed
- [ ] Deployment plan approved

### Troubleshooting Integration Issues

**Server Won't Connect:**
1. Check backend service running
2. Verify MCP configuration syntax
3. Review Kiro IDE output panel
4. Test server standalone: `python -m ide_agents_mcp_server`

**Tools Not Working:**
1. Verify ULTRA mode enabled
2. Check GitHub token set
3. Test backend endpoints
4. Review telemetry for errors

**Performance Issues:**
1. Analyze telemetry duration_ms
2. Check backend response times
3. Monitor resource usage
4. Optimize slow operations

**For detailed troubleshooting, see the [Troubleshooting Guide](#troubleshooting-guide) above.**

---

## Additional Resources

### Documentation

- [MCP Integration Guide](MCP_INTEGRATION_GUIDE.md)
- [ML Integration Guide](ML_INTEGRATION_GUIDE.md)
- [Tool Usage Examples](TOOL_USAGE_EXAMPLES.md)
- [ULTRA Features Guide](ULTRA_FEATURES_GUIDE.md)
- [Kiro IDE Integration Test Guide](KIRO_IDE_INTEGRATION_TEST_GUIDE.md)
- [Integration Test Quick Reference](INTEGRATION_TEST_QUICK_REFERENCE.md)

### Testing

- [Integration Tests](test_integration_full.py)
- [Performance Benchmarks](test_performance_benchmarks.py)
- [Security Tests](test_security_hardening.py)
- [Integration Readiness Verification](verify_integration_readiness.py)

### Support

For issues or questions:

1. Check the [Troubleshooting Guide](#troubleshooting-guide)
2. Review telemetry logs for error details
3. Consult the [MCP Integration Guide](MCP_INTEGRATION_GUIDE.md)
4. Run the verification script: `python verify_integration_readiness.py`
5. Follow the [Kiro IDE Integration Test Guide](KIRO_IDE_INTEGRATION_TEST_GUIDE.md)
6. Open an issue on the project repository

---

**End of Deployment Guide**

---

**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** 2025-11-14
