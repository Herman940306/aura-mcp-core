# MCP Server Integration Guide for Kiro IDE

---
**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** 2025-11-14

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Available Tools](#available-tools)
6. [Usage Examples](#usage-examples)
7. [Environment Variables](#environment-variables)
8. [Security Best Practices](#security-best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Features](#advanced-features)

---

## Overview

The IDE Agents MCP (Model Context Protocol) server integrates advanced AI intelligence capabilities into Kiro IDE, enabling the chat agent to:

- **Analyze emotions** in user text for sentiment-aware responses
- **Generate predictions** for automation and workflow optimization
- **Rank GitHub repositories** semantically for intelligent search
- **Execute commands** with approval workflows for safety
- **Access resources** like project graphs, knowledge bases, and build logs
- **Leverage ULTRA mode** for autonomous development with RLHF and confidence calibration

This guide walks you through setup, configuration, and usage of all MCP tools.

---

## Prerequisites

### Required Software

- **Python 3.11+** installed and accessible in PATH
- **Kiro IDE** (latest version)
- **Git** for version control
- **Backend AI Service** running on `http://127.0.0.1:8001`

### Optional Requirements

- **GitHub Personal Access Token** for GitHub integration tools
- **Virtual Environment** (recommended for isolation)

### System Requirements

- **OS**: Windows, macOS, or Linux
- **RAM**: Minimum 4GB (8GB+ recommended for ULTRA mode)
- **Disk Space**: 500MB for MCP server and dependencies
- **Network**: Local backend service on port 8001

---

## Installation & Setup

### Step 1: Install Python Dependencies

Navigate to your project directory and install required packages:

```bash
pip install -r requirements.txt
```

Key dependencies include:
- `fastmcp` - MCP server framework
- `httpx` - Async HTTP client for backend communication
- `pydantic` - Data validation and settings management

### Step 2: Start Backend AI Service

The MCP server requires a backend AI intelligence service running locally:

```bash
python mock_backend_server.py
```

Verify the service is running:

```bash
curl http://127.0.0.1:8001/health
```

Expected response: `{"status": "ok"}`

### Step 3: Configure Kiro IDE

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

### Step 4: Restart Kiro IDE

After creating the configuration file:

1. Close Kiro IDE completely
2. Reopen Kiro IDE
3. The MCP server will start automatically
4. Check the MCP Server view in Kiro to verify connection

### Step 5: Verify Installation

Test the MCP server connection by asking the Kiro chat agent:

```
Can you check the MCP server health?
```

The agent should invoke `ide_agents_health` and return server status.

---

## Configuration

### Configuration File Structure

The `.kiro/settings/mcp.json` file controls MCP server behavior:

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Python interpreter path (use virtual env if available) |
| `args` | array | Module path to MCP server entry point |
| `env` | object | Environment variables for server configuration |
| `disabled` | boolean | Set to `true` to disable server without removing config |
| `autoApprove` | array | List of tools that don't require user approval |

### Environment Variables Reference

See [Environment Variables](#environment-variables) section for detailed configuration options.

### Auto-Approval Configuration

Tools in the `autoApprove` list execute without user confirmation. Recommended safe tools:

- **Health & Status**: `ide_agents_health`, `ide_agents_ml_get_system_status`
- **Read-Only ML**: `ide_agents_ml_analyze_emotion`, `ide_agents_ml_get_predictions`, `ide_agents_ml_get_learning_insights`
- **GitHub Read**: `ide_agents_github_repos`, `ide_agents_github_rank_repos`, `ide_agents_github_rank_all`
- **Resources**: `ide_agents_resource`, `ide_agents_prompt`, `ide_agents_catalog`

**Warning**: Never auto-approve `ide_agents_command` with method "run" as it executes system commands.

---

## Available Tools

The MCP server exposes tools organized by category. Availability depends on configuration and ULTRA mode.

### Core Tools (Always Available)

#### 1. Health Check

**Tool**: `ide_agents_health`

**Description**: Check MCP server and backend service health status

**Parameters**: None

**Returns**: Server status, backend connectivity, ULTRA mode state

**Example**:
```
Agent: Check MCP server health
Response: {
  "status": "healthy",
  "backend_url": "http://127.0.0.1:8001",
  "ultra_enabled": true,
  "plugins_loaded": ["ml_intelligence", "calibration_service", "prediction_ranker_rlhf"]
}
```

#### 2. Entity Catalog

**Tool**: `ide_agents_catalog`

**Description**: List available entities or fetch documentation

**Parameters**:
- `method` (required): "list_entities" or "get_doc"
- `entity_name` (optional): Entity name for documentation

**Returns**: Entity mappings or documentation content

**Example**:
```
Agent: List all available entities
Tool: ide_agents_catalog(method="list_entities")
Response: {
  "entities": {
    "git": ["commit", "push", "pull", "status"],
    "npm": ["install", "run", "test"],
    "docker": ["build", "run", "ps"]
  }
}
```

#### 3. Resource Access

**Tool**: `ide_agents_resource`

**Description**: Access project resources like repo graph, knowledge base, build logs

**Parameters**:
- `method` (required): "list" or "get"
- `name` (optional): Resource name ("repo.graph", "kb.snippet", "build.logs")

**Returns**: Resource list or content

**Available Resources**:
- `repo.graph` - Project structure and dependency graph (JSON)
- `kb.snippet` - Knowledge base snippets and documentation
- `build.logs` - Recent build and compilation logs

**Example**:
```
Agent: Show me the project structure
Tool: ide_agents_resource(method="get", name="repo.graph")
Response: {
  "files": [...],
  "dependencies": {...},
  "structure": {...}
}
```

#### 4. Prompt Templates

**Tool**: `ide_agents_prompt`

**Description**: Access predefined prompt templates for common tasks

**Parameters**:
- `method` (required): "list" or "get"
- `name` (optional): Prompt template name

**Available Templates**:
- `/diff_review` - Code review for git diffs
- `/test_failures` - Analyze test failure patterns
- `/hotfix_plan` - Generate hotfix implementation plan
- `/rank_github_repos` - Rank repositories by relevance
- `/rank_github_all` - Rank issues and PRs across repos
- `/rank_top_bug_prs` - Identify critical bug PRs

**Example**:
```
Agent: Get the diff review prompt template
Tool: ide_agents_prompt(method="get", name="/diff_review")
Response: "Analyze the following git diff and provide..."
```

#### 5. Command Execution

**Tool**: `ide_agents_command`

**Description**: Execute, simulate, or explain system commands with approval workflow

**Parameters**:
- `method` (required): "run", "dry_run", or "explain"
- `command` (required): Command string to execute
- `action_id` (optional): Approval action ID for "run" method

**Methods**:
- `dry_run` - Simulate command without execution (safe, no approval needed)
- `explain` - Get explanation of what command does (safe, no approval needed)
- `run` - Execute command (requires approval unless pre-approved)

**Example**:
```
Agent: Explain what "git status" does
Tool: ide_agents_command(method="explain", command="git status")
Response: "Shows the working tree status, including staged, unstaged, and untracked files"

Agent: Run "npm install"
Tool: ide_agents_command(method="run", command="npm install")
[Approval prompt appears]
User: Approve
Response: {
  "success": true,
  "output": "added 245 packages in 12s"
}
```

**Security Note**: Always use `dry_run` or `explain` first to understand command impact before using `run`.

---

### ML Intelligence Tools (ULTRA Mode Required)

These tools require `IDE_AGENTS_ULTRA_ENABLED=true` in configuration.

#### 6. Emotion Analysis

**Tool**: `ide_agents_ml_analyze_emotion`

**Description**: Analyze sentiment and emotion in text for context-aware responses

**Parameters**:
- `text` (required): Text to analyze

**Returns**: Detected mood, confidence score

**Example**:
```
Agent: Analyze emotion in "I'm frustrated with this bug"
Tool: ide_agents_ml_analyze_emotion(text="I'm frustrated with this bug")
Response: {
  "text": "I'm frustrated with this bug",
  "mood": "frustrated",
  "confidence": 0.89
}
```

**Use Cases**:
- Adjust agent tone based on user sentiment
- Detect frustration to offer proactive help
- Track emotional patterns during development sessions

#### 7. Predictive Suggestions

**Tool**: `ide_agents_ml_get_predictions`

**Description**: Get personalized predictions for automation and workflow optimization

**Parameters**:
- `user_id` (optional): User identifier (defaults to "default_user")

**Returns**: List of predicted actions with confidence scores

**Example**:
```
Agent: What predictions do you have for me?
Tool: ide_agents_ml_get_predictions(user_id="default_user")
Response: {
  "predictions": [
    {
      "action": "run_tests",
      "confidence": 0.92,
      "context": "After code changes in src/"
    },
    {
      "action": "commit_changes",
      "confidence": 0.85,
      "context": "Multiple files modified"
    }
  ]
}
```

#### 8. Learning Insights

**Tool**: `ide_agents_ml_get_learning_insights`

**Description**: Understand user patterns and learned behaviors

**Parameters**:
- `user_id` (optional): User identifier (defaults to "default_user")

**Returns**: Insights about user habits, preferences, and patterns

**Example**:
```
Agent: What have you learned about my workflow?
Tool: ide_agents_ml_get_learning_insights(user_id="default_user")
Response: {
  "insights": [
    "Prefers testing before committing (95% of sessions)",
    "Most active during morning hours (8-11 AM)",
    "Frequently works on React components"
  ],
  "patterns": {
    "commit_frequency": "every 30 minutes",
    "test_coverage_preference": "high"
  }
}
```

#### 9. Reasoning Analysis

**Tool**: `ide_agents_ml_analyze_reasoning`

**Description**: Validate understanding of complex commands and multi-step tasks

**Parameters**:
- `command` (required): Command or task description to analyze

**Returns**: Reasoning breakdown, confidence, potential issues

**Example**:
```
Agent: Analyze "Deploy to production after running all tests"
Tool: ide_agents_ml_analyze_reasoning(command="Deploy to production after running all tests")
Response: {
  "steps": [
    "Run test suite",
    "Verify all tests pass",
    "Build production bundle",
    "Deploy to production environment"
  ],
  "confidence": 0.94,
  "warnings": ["No rollback plan specified"]
}
```

#### 10. Personality Profile

**Tool**: `ide_agents_ml_get_personality_profile`

**Description**: Get current AI personality configuration

**Parameters**: None

**Returns**: Personality traits, communication style, adaptation settings

**Example**:
```
Agent: Show my personality profile
Tool: ide_agents_ml_get_personality_profile()
Response: {
  "traits": {
    "formality": 0.6,
    "verbosity": 0.4,
    "proactivity": 0.8
  },
  "communication_style": "professional_friendly"
}
```

#### 11. System Status

**Tool**: `ide_agents_ml_get_system_status`

**Description**: Get status of all ML engines and services

**Parameters**: None

**Returns**: Health status of emotion, prediction, reasoning, personality, and learning engines

**Example**:
```
Agent: Check ML system status
Tool: ide_agents_ml_get_system_status()
Response: {
  "emotion_engine": "healthy",
  "prediction_engine": "healthy",
  "reasoning_engine": "healthy",
  "personality_engine": "healthy",
  "learning_engine": "healthy",
  "ultra_mode": true
}
```

---

### ULTRA Advanced Tools (ULTRA Mode Required)

Advanced autonomous features for confidence calibration and RLHF-based ranking.

#### 12. Confidence Calibration

**Tool**: `ide_agents_ml_calibrate_confidence`

**Description**: Calibrate raw prediction scores to accurate probabilities using Platt scaling

**Parameters**:
- `raw_scores` (required): Array of raw prediction scores
- `features` (optional): Feature data for calibration

**Returns**: Calibrated probabilities with confidence intervals

**Example**:
```
Agent: Calibrate these prediction scores: [0.7, 0.85, 0.6]
Tool: ide_agents_ml_calibrate_confidence(raw_scores=[0.7, 0.85, 0.6])
Response: {
  "calibrated_probabilities": [0.65, 0.82, 0.55],
  "confidence_intervals": [[0.60, 0.70], [0.78, 0.86], [0.50, 0.60]]
}
```

#### 13. RLHF Prediction Ranking

**Tool**: `ide_agents_ml_rank_predictions_rlhf`

**Description**: Rank predictions using reinforcement learning from human feedback

**Parameters**:
- `predictions` (required): Array of prediction candidates
- `context` (optional): Context for ranking

**Returns**: Ranked predictions with expected reward scores

**Example**:
```
Agent: Rank these suggestions by expected value
Tool: ide_agents_ml_rank_predictions_rlhf(predictions=[...])
Response: {
  "ranked_predictions": [
    {"action": "run_tests", "reward": 0.92},
    {"action": "commit", "reward": 0.78},
    {"action": "push", "reward": 0.65}
  ]
}
```

#### 14. Record Prediction Outcome

**Tool**: `ide_agents_ml_record_prediction_outcome`

**Description**: Record user feedback on predictions for continuous learning

**Parameters**:
- `prediction_id` (required): Prediction identifier
- `outcome` (required): "accepted", "rejected", or "modified"
- `feedback` (optional): Additional feedback text

**Returns**: Confirmation of recorded outcome

**Example**:
```
Agent: Record that user accepted prediction "run_tests"
Tool: ide_agents_ml_record_prediction_outcome(
  prediction_id="pred_123",
  outcome="accepted"
)
Response: {
  "recorded": true,
  "prediction_id": "pred_123",
  "outcome": "accepted"
}
```

#### 15. Calibration Metrics

**Tool**: `ide_agents_ml_get_calibration_metrics`

**Description**: Get calibration performance metrics (Brier score, ROC AUC)

**Parameters**: None

**Returns**: Calibration quality metrics

**Example**:
```
Agent: Show calibration metrics
Tool: ide_agents_ml_get_calibration_metrics()
Response: {
  "brier_score": 0.12,
  "roc_auc": 0.89,
  "calibration_error": 0.05
}
```

#### 16. RLHF Metrics

**Tool**: `ide_agents_ml_get_rlhf_metrics`

**Description**: Get RLHF performance metrics (acceptance rate, average reward)

**Parameters**: None

**Returns**: RLHF learning metrics

**Example**:
```
Agent: Show RLHF metrics
Tool: ide_agents_ml_get_rlhf_metrics()
Response: {
  "acceptance_rate": 0.78,
  "average_reward": 0.85,
  "total_feedback_samples": 1247
}
```

---

### GitHub Integration Tools

GitHub tools require `GITHUB_TOKEN` environment variable.

#### 17. List Repositories

**Tool**: `ide_agents_github_repos`

**Description**: List GitHub repositories with filtering options

**Parameters**:
- `visibility` (optional): "all", "public", or "private" (default: "all")
- `limit` (optional): Maximum number of repos to return (default: 30)
- `include` (optional): Comma-separated keywords to include
- `exclude` (optional): Comma-separated keywords to exclude

**Returns**: List of repositories with metadata

**Example**:
```
Agent: List my public repositories
Tool: ide_agents_github_repos(visibility="public", limit=10)
Response: {
  "repositories": [
    {
      "name": "ai-assistant",
      "full_name": "user/ai-assistant",
      "description": "ML-powered home automation",
      "stargazers_count": 42,
      "language": "Python",
      "html_url": "https://github.com/user/ai-assistant"
    }
  ]
}
```

#### 18. Rank Repositories

**Tool**: `ide_agents_github_rank_repos`

**Description**: Semantically rank repositories by relevance to a query

**Parameters**:
- `query` (required): Search query or description
- `visibility` (optional): Filter by visibility
- `limit` (optional): Maximum results

**Returns**: Ranked repositories with relevance scores

**Example**:
```
Agent: Find my repositories related to machine learning
Tool: ide_agents_github_rank_repos(query="machine learning", limit=5)
Response: {
  "ranking": [
    {
      "repo": {...},
      "score": 0.92,
      "reason": "Contains ML models and training scripts"
    }
  ]
}
```

**Note**: Uses semantic ranking in ULTRA mode, falls back to keyword matching otherwise.

#### 19. Rank All Issues and PRs

**Tool**: `ide_agents_github_rank_all`

**Description**: Rank issues and pull requests across all repositories

**Parameters**:
- `query` (required): Search query
- `state` (optional): "open", "closed", or "all" (default: "open")
- `since` (optional): ISO date string for filtering recent items
- `limit` (optional): Maximum results

**Returns**: Ranked issues and PRs with relevance scores

**Example**:
```
Agent: Find critical bugs in my repositories
Tool: ide_agents_github_rank_all(
  query="critical bug",
  state="open",
  limit=10
)
Response: {
  "ranking": [
    {
      "type": "issue",
      "repo": "user/project",
      "title": "Critical: Memory leak in production",
      "score": 0.95,
      "url": "https://github.com/user/project/issues/42"
    }
  ]
}
```

---

## Usage Examples

### Example 1: Emotion-Aware Assistance

**Scenario**: User expresses frustration, agent adapts response tone

```
User: "This bug is driving me crazy!"

Agent internally:
1. Calls ide_agents_ml_analyze_emotion(text="This bug is driving me crazy!")
2. Receives: {"mood": "frustrated", "confidence": 0.91}
3. Adjusts response tone to be more supportive

Agent: "I understand this is frustrating. Let me help you debug this systematically..."
```

### Example 2: Predictive Workflow Automation

**Scenario**: Agent predicts next action based on user patterns

```
User: "I just finished implementing the login feature"

Agent internally:
1. Calls ide_agents_ml_get_predictions(user_id="default_user")
2. Receives: [
     {"action": "run_tests", "confidence": 0.94},
     {"action": "commit_changes", "confidence": 0.87}
   ]
3. Proactively suggests next steps

Agent: "Great! Based on your workflow, you typically run tests next. Would you like me to run the test suite?"
```

### Example 3: Intelligent GitHub Search

**Scenario**: Find relevant repositories for a new feature

```
User: "I need to reference my authentication implementation"

Agent internally:
1. Calls ide_agents_github_rank_repos(query="authentication implementation")
2. Receives ranked list with scores
3. Presents top results

Agent: "I found these relevant repositories:
1. user/auth-service (score: 0.92) - OAuth2 implementation
2. user/api-gateway (score: 0.78) - JWT authentication
Would you like me to open any of these?"
```

### Example 4: Safe Command Execution

**Scenario**: Execute command with approval workflow

```
User: "Install the new dependencies"

Agent internally:
1. Calls ide_agents_command(method="explain", command="npm install")
2. Reviews explanation
3. Calls ide_agents_command(method="run", command="npm install")
4. Approval prompt appears

[User approves]

Agent: "Installing dependencies... Done! Added 15 packages in 8s."
```

### Example 5: Learning from Feedback

**Scenario**: Improve predictions based on user acceptance

```
Agent: "I predict you'll want to commit these changes"
User: "Yes, do it"

Agent internally:
1. Executes commit
2. Calls ide_agents_ml_record_prediction_outcome(
     prediction_id="pred_456",
     outcome="accepted"
   )
3. System learns this pattern for future predictions

[Future sessions will have higher confidence for similar predictions]
```

---

## Environment Variables

Configure MCP server behavior through environment variables in `.kiro/settings/mcp.json`:

### Core Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IDE_AGENTS_BACKEND_URL` | string | `http://127.0.0.1:8001` | Backend AI service URL |
| `IDE_AGENTS_REQUEST_TIMEOUT` | float | `30.0` | HTTP request timeout in seconds |
| `IDE_AGENTS_ULTRA_ENABLED` | boolean | `false` | Enable ULTRA mode with ML tools |
| `IDE_AGENTS_ULTRA_MOCK` | boolean | `false` | Use mock responses for testing |
| `IDE_AGENTS_ULTRA_LOCAL` | boolean | `false` | Use local ML models instead of backend |

### GitHub Integration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `GITHUB_TOKEN` | string | - | GitHub Personal Access Token (required for GitHub tools) |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | string | - | Alternative name for GitHub token |

### Telemetry & Logging

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MCP_TOOL_SPANS_DIR` | string | `./logs` | Directory for telemetry span logs |
| `FASTMCP_LOG_LEVEL` | string | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Advanced Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IDE_AGENTS_RATE_LIMIT_MS` | integer | `250` | Minimum milliseconds between tool calls |
| `IDE_AGENTS_MAX_RETRIES` | integer | `3` | Maximum retry attempts for failed requests |
| `IDE_AGENTS_CACHE_TTL` | integer | `300` | Cache time-to-live in seconds |

### Environment Variable Examples

**Development Setup**:
```json
{
  "env": {
    "IDE_AGENTS_BACKEND_URL": "http://127.0.0.1:8001",
    "IDE_AGENTS_ULTRA_ENABLED": "true",
    "IDE_AGENTS_ULTRA_MOCK": "false",
    "GITHUB_TOKEN": "${GITHUB_TOKEN}",
    "FASTMCP_LOG_LEVEL": "DEBUG"
  }
}
```

**Testing Setup** (with mocks):
```json
{
  "env": {
    "IDE_AGENTS_BACKEND_URL": "http://127.0.0.1:8001",
    "IDE_AGENTS_ULTRA_ENABLED": "true",
    "IDE_AGENTS_ULTRA_MOCK": "true",
    "FASTMCP_LOG_LEVEL": "DEBUG"
  }
}
```

**Production Setup**:
```json
{
  "env": {
    "IDE_AGENTS_BACKEND_URL": "https://ai-backend.company.com",
    "IDE_AGENTS_ULTRA_ENABLED": "true",
    "GITHUB_TOKEN": "${GITHUB_TOKEN}",
    "FASTMCP_LOG_LEVEL": "WARNING",
    "IDE_AGENTS_REQUEST_TIMEOUT": "60.0"
  }
}
```

---

## Security Best Practices

### 1. Token Management

**DO**:
- Store tokens in environment variables, never in configuration files
- Use `${GITHUB_TOKEN}` syntax to reference environment variables
- Rotate tokens regularly (every 90 days recommended)
- Use fine-grained personal access tokens with minimal scopes
- Store tokens in secure credential managers (e.g., 1Password, LastPass)

**DON'T**:
- Hardcode tokens in `.kiro/settings/mcp.json`
- Commit tokens to version control
- Share tokens across multiple users
- Use tokens with excessive permissions

**GitHub Token Scopes** (minimum required):
- `repo` - Access repositories
- `read:org` - Read organization data (if using org repos)

### 2. Approval Workflow

**Critical Operations Requiring Approval**:
- Command execution (`ide_agents_command` with method "run")
- File system modifications
- Network requests to external services
- Database operations

**Safe Auto-Approve Operations**:
- Health checks
- Read-only ML analysis (emotion, predictions, insights)
- GitHub repository listing and ranking
- Resource and prompt template access
- Catalog queries

**Best Practices**:
- Review approval prompts carefully before accepting
- Use `dry_run` or `explain` methods first to understand command impact
- Customize `autoApprove` list based on your trust level
- Monitor telemetry logs for unexpected tool invocations

### 3. Rate Limiting

**Purpose**: Prevent accidental DoS attacks on backend service

**Configuration**:
- Default: 250ms minimum between tool calls
- Adjust via `IDE_AGENTS_RATE_LIMIT_MS` environment variable
- Applies per-tool, not globally

**Monitoring**:
- Check telemetry logs for rate limit events
- Increase timeout if legitimate use cases are being throttled

### 4. Network Security

**Backend Service**:
- Run on localhost (`127.0.0.1`) for development
- Use HTTPS for production deployments
- Implement authentication for remote backends
- Use VPN or private networks for sensitive environments

**Firewall Rules**:
- Allow outbound connections to GitHub API (`api.github.com`)
- Allow localhost connections to backend service (port 8001)
- Block unnecessary inbound connections

### 5. Data Privacy

**Telemetry**:
- Telemetry logs contain tool names, methods, and timing data
- Sensitive data (tokens, passwords) are never logged
- Review `logs/mcp_tool_spans.jsonl` periodically
- Implement log rotation to prevent disk space issues

**User Data**:
- ML predictions and insights are stored locally
- No data is sent to external services without explicit consent
- User patterns remain on local backend service

### 6. Sandboxing

**MCP Server Isolation**:
- Runs in separate process from Kiro IDE
- Limited file system access (only resources directory)
- No direct shell access (commands go through approval)

**Resource Access**:
- Only predefined resources are accessible (repo.graph, kb.snippet, build.logs)
- Path traversal attacks are prevented
- File access is read-only

### 7. Dependency Security

**Regular Updates**:
```bash
pip install --upgrade fastmcp httpx pydantic
```

**Vulnerability Scanning**:
```bash
pip install safety
safety check
```

**Audit Dependencies**:
```bash
pip list --outdated
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: MCP Server Won't Start

**Symptoms**:
- Kiro IDE shows "MCP server disconnected"
- No tools available in chat agent
- Error in Kiro output panel

**Solutions**:

1. **Check Python Installation**:
   ```bash
   python --version
   # Should be 3.11 or higher
   ```

2. **Verify Dependencies**:
   ```bash
   pip list | grep fastmcp
   pip list | grep httpx
   # If missing, run: pip install -r requirements.txt
   ```

3. **Check Configuration Syntax**:
   - Open `.kiro/settings/mcp.json`
   - Validate JSON syntax (use online JSON validator)
   - Ensure all required fields are present

4. **Review Logs**:
   - Open Kiro IDE output panel
   - Look for MCP server startup errors
   - Check for Python import errors

5. **Test Manual Start**:
   ```bash
   python -m ide_agents_mcp_server
   # Should start without errors
   ```

#### Issue 2: Backend Service Unavailable

**Symptoms**:
- Tools return "Backend service unavailable" errors
- Health check fails
- Timeout errors in logs

**Solutions**:

1. **Verify Backend is Running**:
   ```bash
   curl http://127.0.0.1:8001/health
   # Expected: {"status": "ok"}
   ```

2. **Start Backend Service**:
   ```bash
   python mock_backend_server.py
   # Or your actual backend service
   ```

3. **Check Port Availability**:
   ```bash
   # Windows
   netstat -ano | findstr :8001
   
   # Linux/Mac
   lsof -i :8001
   ```

4. **Verify Backend URL**:
   - Check `IDE_AGENTS_BACKEND_URL` in configuration
   - Ensure it matches where backend is running
   - Try `http://localhost:8001` if `127.0.0.1` doesn't work

5. **Check Firewall**:
   - Ensure localhost connections are allowed
   - Temporarily disable firewall to test

#### Issue 3: GitHub Tools Not Working

**Symptoms**:
- GitHub tools return authentication errors
- "GITHUB_TOKEN not found" errors
- Rate limit errors

**Solutions**:

1. **Verify Token is Set**:
   ```bash
   # Windows
   echo %GITHUB_TOKEN%
   
   # Linux/Mac
   echo $GITHUB_TOKEN
   ```

2. **Test Token Validity**:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
   # Should return your GitHub user info
   ```

3. **Check Token Scopes**:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Verify token has `repo` scope
   - Regenerate token if needed

4. **Set Token in Environment**:
   ```bash
   # Windows (PowerShell)
   $env:GITHUB_TOKEN="your_token_here"
   
   # Linux/Mac
   export GITHUB_TOKEN="your_token_here"
   ```

5. **Check Rate Limits**:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/rate_limit
   # Shows remaining API calls
   ```

#### Issue 4: ULTRA Mode Tools Missing

**Symptoms**:
- ML tools not available
- Only basic tools appear
- "ULTRA mode disabled" in health check

**Solutions**:

1. **Enable ULTRA Mode**:
   - Open `.kiro/settings/mcp.json`
   - Set `"IDE_AGENTS_ULTRA_ENABLED": "true"`
   - Restart Kiro IDE

2. **Verify Plugin Loading**:
   - Check MCP server logs for plugin load messages
   - Look for "Loaded plugin: ml_intelligence" messages

3. **Check Backend ULTRA Support**:
   ```bash
   curl http://127.0.0.1:8001/ai/intelligence/status
   # Should return ML engine statuses
   ```

4. **Test with Mock Mode**:
   - Set `"IDE_AGENTS_ULTRA_MOCK": "true"` temporarily
   - Restart and test if tools appear
   - If working, issue is with backend connection

#### Issue 5: Approval Prompts Not Appearing

**Symptoms**:
- Commands execute without approval
- No approval dialog shown
- Security concern

**Solutions**:

1. **Check Auto-Approve List**:
   - Open `.kiro/settings/mcp.json`
   - Review `autoApprove` array
   - Remove tools that should require approval

2. **Verify Tool Name**:
   - Ensure tool name matches exactly
   - Case-sensitive: `ide_agents_command` not `IDE_AGENTS_COMMAND`

3. **Test Approval Workflow**:
   ```
   Agent: Run "echo test"
   # Should show approval prompt
   ```

4. **Check Kiro IDE Settings**:
   - Look for MCP approval settings in Kiro preferences
   - Ensure approval prompts are enabled globally

#### Issue 6: Slow Tool Response Times

**Symptoms**:
- Tools take > 5 seconds to respond
- Timeout errors
- Poor user experience

**Solutions**:

1. **Check Backend Performance**:
   ```bash
   curl -w "@curl-format.txt" http://127.0.0.1:8001/health
   # Measure response time
   ```

2. **Increase Timeout**:
   - Set `"IDE_AGENTS_REQUEST_TIMEOUT": "60.0"` in config
   - Restart Kiro IDE

3. **Enable Caching**:
   - Set `"IDE_AGENTS_CACHE_TTL": "300"` for 5-minute cache
   - Reduces repeated backend calls

4. **Optimize Backend**:
   - Check backend logs for slow queries
   - Add database indexes if needed
   - Scale backend resources (CPU, RAM)

5. **Use Local Mode**:
   - Set `"IDE_AGENTS_ULTRA_LOCAL": "true"`
   - Uses local ML models instead of backend (faster but less accurate)

#### Issue 7: Telemetry Logs Growing Too Large

**Symptoms**:
- `logs/mcp_tool_spans.jsonl` file is very large
- Disk space issues
- Slow log file access

**Solutions**:

1. **Implement Log Rotation**:
   ```bash
   # Linux/Mac
   logrotate /path/to/logrotate.conf
   
   # Windows - use PowerShell script
   Get-ChildItem logs/*.jsonl | Where-Object {$_.Length -gt 10MB} | Remove-Item
   ```

2. **Archive Old Logs**:
   ```bash
   # Compress logs older than 7 days
   find logs -name "*.jsonl" -mtime +7 -exec gzip {} \;
   ```

3. **Reduce Logging**:
   - Set `"FASTMCP_LOG_LEVEL": "WARNING"` to log only errors
   - Reduces telemetry verbosity

4. **Clean Up Manually**:
   ```bash
   # Backup and clear logs
   cp logs/mcp_tool_spans.jsonl logs/mcp_tool_spans.backup.jsonl
   echo "" > logs/mcp_tool_spans.jsonl
   ```

#### Issue 8: Tools Return Unexpected Results

**Symptoms**:
- Tool responses don't match expectations
- Data format issues
- Incorrect predictions

**Solutions**:

1. **Verify Input Parameters**:
   - Check tool documentation for required parameters
   - Validate parameter types (string, number, boolean)
   - Use correct parameter names

2. **Check Backend Version**:
   - Ensure backend service is up to date
   - Verify API compatibility with MCP server

3. **Test with Mock Mode**:
   - Enable `"IDE_AGENTS_ULTRA_MOCK": "true"`
   - Compare mock responses with actual responses
   - Identifies backend vs. MCP server issues

4. **Review Telemetry**:
   - Check `logs/mcp_tool_spans.jsonl` for error details
   - Look for error codes and messages
   - Identify patterns in failures

5. **Enable Debug Logging**:
   - Set `"FASTMCP_LOG_LEVEL": "DEBUG"`
   - Review detailed logs in Kiro output panel
   - Look for request/response details

### Getting Help

If you encounter issues not covered here:

1. **Check Documentation**:
   - Review requirements.md for system requirements
   - Review design.md for architecture details
   - Check this guide's examples section

2. **Review Logs**:
   - Kiro IDE output panel (MCP server logs)
   - Backend service logs
   - Telemetry logs (`logs/mcp_tool_spans.jsonl`)

3. **Test Components Individually**:
   - Test backend service standalone
   - Test MCP server standalone
   - Test Kiro IDE without MCP

4. **Community Support**:
   - Check GitHub issues for similar problems
   - Post detailed issue with logs and configuration
   - Include steps to reproduce

5. **Debug Mode**:
   ```json
   {
     "env": {
       "FASTMCP_LOG_LEVEL": "DEBUG",
       "IDE_AGENTS_ULTRA_MOCK": "true"
     }
   }
   ```
   - Restart Kiro IDE
   - Reproduce issue
   - Collect logs for analysis

---

## Advanced Features

### Custom Tool Development

You can extend the MCP server with custom tools:

1. **Create Tool Handler**:
   ```python
   @mcp.tool()
   async def my_custom_tool(param1: str, param2: int) -> dict:
       """Tool description for Kiro chat agent"""
       # Your implementation
       return {"result": "success"}
   ```

2. **Register Tool**:
   - Add handler to `ide_agents_mcp_server.py`
   - Restart MCP server
   - Tool appears in Kiro IDE automatically

3. **Add to Auto-Approve** (if safe):
   - Update `.kiro/settings/mcp.json`
   - Add tool name to `autoApprove` array

### Plugin Development

Create custom ML plugins for specialized functionality:

1. **Plugin Structure**:
   ```python
   # plugins/my_plugin.py
   
   class MyPlugin:
       def __init__(self, backend_url: str):
           self.backend_url = backend_url
       
       async def my_feature(self, input_data: dict) -> dict:
           # Implementation
           return {"output": "result"}
   ```

2. **Register Plugin**:
   ```python
   # In ide_agents_mcp_server.py
   from plugins.my_plugin import MyPlugin
   
   if ultra_enabled:
       my_plugin = MyPlugin(backend_url)
       # Register plugin tools
   ```

3. **Add Tool Handlers**:
   ```python
   @mcp.tool()
   async def ide_agents_my_feature(input_data: dict) -> dict:
       return await my_plugin.my_feature(input_data)
   ```

### Telemetry Analysis

Analyze tool usage patterns from telemetry logs:

```python
import json

# Load telemetry data
with open('logs/mcp_tool_spans.jsonl', 'r') as f:
    spans = [json.loads(line) for line in f]

# Analyze tool usage
tool_counts = {}
for span in spans:
    tool = span['tool_name']
    tool_counts[tool] = tool_counts.get(tool, 0) + 1

# Find slowest tools
slow_tools = sorted(spans, key=lambda x: x['duration_ms'], reverse=True)[:10]

# Calculate success rate
total = len(spans)
successful = sum(1 for s in spans if s['success'])
success_rate = successful / total * 100

print(f"Success Rate: {success_rate:.2f}%")
print(f"Most Used Tools: {tool_counts}")
```

### Performance Optimization

**Connection Pooling**:
```python
# Configure httpx client with connection pooling
import httpx

client = httpx.AsyncClient(
    timeout=30.0,
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
)
```

**Caching Strategy**:
```python
from functools import lru_cache
import time

@lru_cache(maxsize=100)
def cached_tool_schema(tool_name: str):
    # Cache tool schemas to avoid repeated lookups
    return get_tool_schema(tool_name)
```

**Async Batch Operations**:
```python
import asyncio

# Execute multiple tools in parallel
results = await asyncio.gather(
    tool1(),
    tool2(),
    tool3()
)
```

### Integration with CI/CD

Use MCP tools in automated workflows:

```yaml
# .github/workflows/mcp-analysis.yml
name: MCP Analysis

on: [push]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Start Backend Service
        run: python mock_backend_server.py &
      
      - name: Run MCP Health Check
        run: |
          python -c "
          import asyncio
          from ide_agents_mcp_server import health_check
          result = asyncio.run(health_check())
          print(result)
          "
      
      - name: Analyze Telemetry
        run: python scripts/analyze_telemetry.py
```

### Multi-User Configuration

Support multiple developers with different configurations:

```json
{
  "mcpServers": {
    "ide-agents-mcp-dev": {
      "command": "python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "http://127.0.0.1:8001",
        "IDE_AGENTS_ULTRA_ENABLED": "true",
        "GITHUB_TOKEN": "${GITHUB_TOKEN_DEV}"
      }
    },
    "ide-agents-mcp-prod": {
      "command": "python",
      "args": ["-m", "ide_agents_mcp_server"],
      "env": {
        "IDE_AGENTS_BACKEND_URL": "https://prod-backend.company.com",
        "IDE_AGENTS_ULTRA_ENABLED": "false",
        "GITHUB_TOKEN": "${GITHUB_TOKEN_PROD}"
      },
      "disabled": true
    }
  }
}
```

Switch between configurations by toggling the `disabled` flag.

---

## Appendix

### Tool Reference Quick Guide

| Tool | Category | Approval | ULTRA | Description |
|------|----------|----------|-------|-------------|
| `ide_agents_health` | Core | No | No | Server health check |
| `ide_agents_catalog` | Core | No | No | Entity catalog access |
| `ide_agents_resource` | Core | No | No | Project resource access |
| `ide_agents_prompt` | Core | No | No | Prompt template access |
| `ide_agents_command` | Core | Yes* | No | Command execution |
| `ide_agents_ml_analyze_emotion` | ML | No | Yes | Emotion detection |
| `ide_agents_ml_get_predictions` | ML | No | Yes | Predictive suggestions |
| `ide_agents_ml_get_learning_insights` | ML | No | Yes | Learning patterns |
| `ide_agents_ml_analyze_reasoning` | ML | No | Yes | Reasoning validation |
| `ide_agents_ml_get_personality_profile` | ML | No | Yes | Personality config |
| `ide_agents_ml_get_system_status` | ML | No | Yes | ML system status |
| `ide_agents_ml_calibrate_confidence` | ULTRA | No | Yes | Confidence calibration |
| `ide_agents_ml_rank_predictions_rlhf` | ULTRA | No | Yes | RLHF ranking |
| `ide_agents_ml_record_prediction_outcome` | ULTRA | No | Yes | Record feedback |
| `ide_agents_ml_get_calibration_metrics` | ULTRA | No | Yes | Calibration metrics |
| `ide_agents_ml_get_rlhf_metrics` | ULTRA | No | Yes | RLHF metrics |
| `ide_agents_github_repos` | GitHub | No | No | List repositories |
| `ide_agents_github_rank_repos` | GitHub | No | No | Rank repositories |
| `ide_agents_github_rank_all` | GitHub | No | No | Rank issues/PRs |

*Only "run" method requires approval; "dry_run" and "explain" are safe.

### Glossary

- **MCP**: Model Context Protocol - Standard for AI tool integration
- **ULTRA Mode**: Advanced autonomous features with ML intelligence
- **RLHF**: Reinforcement Learning from Human Feedback
- **Platt Scaling**: Calibration method for probability estimates
- **Telemetry Span**: Performance tracking record for tool invocation
- **Approval Queue**: Gating mechanism for potentially dangerous operations
- **Rate Limiting**: Throttling to prevent excessive API calls
- **Backend Service**: AI intelligence service providing ML capabilities

---

## Conclusion

The MCP server integration brings powerful AI capabilities to Kiro IDE, enabling:

- **Emotion-aware assistance** that adapts to user sentiment
- **Predictive automation** that learns from user patterns
- **Intelligent GitHub search** with semantic ranking
- **Safe command execution** with approval workflows
- **Continuous learning** through RLHF feedback

Follow this guide to set up, configure, and leverage these capabilities in your development workflow.

For questions or issues, refer to the [Troubleshooting](#troubleshooting) section or review the requirements and design documents.

---

**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** 2025-11-14

---

## Author

**Herman Swanepoel** - *Project Creator*
