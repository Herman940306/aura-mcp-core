# MCP Tool Usage Examples for Kiro Chat Agent

---
**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** 2025-11-14

---

## Overview

This document provides comprehensive examples of how to use MCP tools through the Kiro chat agent. Each example includes:
- Example user prompts
- Expected tool invocations
- Expected responses
- Error handling scenarios
- Best practices

---

## Table of Contents

1. [Emotion Analysis Examples](#emotion-analysis-examples)
2. [Prediction Examples](#prediction-examples)
3. [Learning Insights Examples](#learning-insights-examples)
4. [GitHub Search Examples](#github-search-examples)
5. [Command Execution Examples](#command-execution-examples)
6. [Error Handling Scenarios](#error-handling-scenarios)

---

## Emotion Analysis Examples

### Example 1: Basic Emotion Detection

**User Prompt:**
```
Analyze the emotion in: "I'm really excited about this new feature!"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_analyze_emotion",
  "arguments": {
    "text": "I'm really excited about this new feature!"
  }
}
```

**Expected Response:**
```json
{
  "text": "I'm really excited about this new feature!",
  "mood": "excited",
  "confidence": 0.94
}
```


**Chat Agent Response:**
```
I can see you're excited! The emotion analysis shows a 94% confidence that you're feeling excited about this new feature. How can I help you build it?
```

**Requirements Covered:** 3.2

---

### Example 2: Frustration Detection

**User Prompt:**
```
Analyze the emotion in: "This bug has been driving me crazy for hours"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_analyze_emotion",
  "arguments": {
    "text": "This bug has been driving me crazy for hours"
  }
}
```

**Expected Response:**
```json
{
  "text": "This bug has been driving me crazy for hours",
  "mood": "frustrated",
  "confidence": 0.91
}
```

**Chat Agent Response:**
```
I understand this is frustrating. Let me help you debug this systematically. Can you describe what the bug is doing?
```

**Requirements Covered:** 3.2

---

### Example 3: Neutral Sentiment

**User Prompt:**
```
Analyze the emotion in: "The function returns a list of objects"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_analyze_emotion",
  "arguments": {
    "text": "The function returns a list of objects"
  }
}
```

**Expected Response:**
```json
{
  "text": "The function returns a list of objects",
  "mood": "neutral",
  "confidence": 0.88
}
```

**Chat Agent Response:**
```
Got it. That's a neutral technical statement. Would you like me to help you work with that function?
```

**Requirements Covered:** 3.2

---

## Prediction Examples

### Example 1: Get AI Predictions for Routines

**User Prompt:**
```
Show me AI predictions for my routines
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_predictions",
  "arguments": {
    "user_id": "default_user"
  }
}
```

**Expected Response:**
```json
{
  "predictions": [
    {
      "action": "run_tests",
      "confidence": 0.92,
      "context": "After code changes in src/",
      "reasoning": "You typically run tests after modifying source files"
    },
    {
      "action": "commit_changes",
      "confidence": 0.85,
      "context": "Multiple files modified",
      "reasoning": "You usually commit after completing a feature"
    },
    {
      "action": "update_documentation",
      "confidence": 0.78,
      "context": "New API endpoints added",
      "reasoning": "You document new APIs before pushing"
    }
  ],
  "user_id": "default_user",
  "timestamp": "2025-11-14T10:30:00Z"
}
```

**Chat Agent Response:**
```
Based on your workflow patterns, I predict you'll want to:

1. **Run tests** (92% confidence) - You typically test after modifying source files
2. **Commit changes** (85% confidence) - Multiple files have been modified
3. **Update documentation** (78% confidence) - New API endpoints were added

Would you like me to help with any of these?
```

**Requirements Covered:** 3.3

---

### Example 2: Predictions for Specific User

**User Prompt:**
```
What are the AI predictions for user "john_dev"?
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_predictions",
  "arguments": {
    "user_id": "john_dev"
  }
}
```

**Expected Response:**
```json
{
  "predictions": [
    {
      "action": "refactor_code",
      "confidence": 0.88,
      "context": "Code complexity threshold exceeded",
      "reasoning": "You refactor when cyclomatic complexity > 10"
    },
    {
      "action": "write_unit_tests",
      "confidence": 0.82,
      "context": "New functions added without tests",
      "reasoning": "You maintain 80%+ test coverage"
    }
  ],
  "user_id": "john_dev",
  "timestamp": "2025-11-14T10:30:00Z"
}
```

**Chat Agent Response:**
```
For user john_dev, I predict:

1. **Refactor code** (88% confidence) - Code complexity has exceeded your threshold
2. **Write unit tests** (82% confidence) - New functions need test coverage

These predictions are based on john_dev's established patterns.
```

**Requirements Covered:** 3.3

---

### Example 3: Empty Predictions

**User Prompt:**
```
Show me predictions for my workflow
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_predictions",
  "arguments": {
    "user_id": "default_user"
  }
}
```

**Expected Response:**
```json
{
  "predictions": [],
  "user_id": "default_user",
  "timestamp": "2025-11-14T10:30:00Z",
  "message": "Not enough data to generate predictions yet"
}
```

**Chat Agent Response:**
```
I don't have enough data to make predictions yet. As you work, I'll learn your patterns and start suggesting actions. Keep coding, and I'll get smarter!
```

**Requirements Covered:** 3.3

---

## Learning Insights Examples

### Example 1: Get Learning Insights

**User Prompt:**
```
What has the AI learned about me?
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_learning_insights",
  "arguments": {
    "user_id": "default_user"
  }
}
```

**Expected Response:**
```json
{
  "insights": [
    "Prefers testing before committing (95% of sessions)",
    "Most active during morning hours (8-11 AM)",
    "Frequently works on React components",
    "Uses TypeScript for new projects",
    "Commits every 30-45 minutes on average"
  ],
  "patterns": {
    "commit_frequency": "every 30 minutes",
    "test_coverage_preference": "high",
    "preferred_languages": ["TypeScript", "Python"],
    "work_hours": "8:00-17:00",
    "break_pattern": "15 min break every 2 hours"
  },
  "statistics": {
    "total_sessions": 127,
    "total_commits": 543,
    "average_session_duration": "3.5 hours",
    "test_pass_rate": 0.94
  },
  "user_id": "default_user"
}
```

**Chat Agent Response:**
```
Here's what I've learned about your development patterns:

**Key Insights:**
- You prefer testing before committing (95% of the time)
- You're most productive in the morning (8-11 AM)
- You frequently work on React components
- You use TypeScript for new projects
- You commit every 30-45 minutes

**Work Patterns:**
- Commit frequency: Every 30 minutes
- Test coverage: High priority
- Preferred languages: TypeScript, Python
- Work hours: 8:00-17:00
- Break pattern: 15 min every 2 hours

**Statistics:**
- Total sessions: 127
- Total commits: 543
- Average session: 3.5 hours
- Test pass rate: 94%

I use these insights to provide better suggestions tailored to your workflow!
```

**Requirements Covered:** 3.4

---

### Example 2: Insights for New User

**User Prompt:**
```
What insights do you have about my coding style?
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_learning_insights",
  "arguments": {
    "user_id": "default_user"
  }
}
```

**Expected Response:**
```json
{
  "insights": [
    "New user - still learning patterns"
  ],
  "patterns": {},
  "statistics": {
    "total_sessions": 3,
    "total_commits": 5,
    "average_session_duration": "1.2 hours"
  },
  "user_id": "default_user",
  "message": "Not enough data yet. Keep working and I'll learn your patterns!"
}
```

**Chat Agent Response:**
```
You're a new user, so I'm still learning your patterns. I've observed:
- 3 sessions so far
- 5 commits
- Average session: 1.2 hours

Keep coding, and I'll start recognizing your workflow patterns and preferences!
```

**Requirements Covered:** 3.4

---

### Example 3: Detailed Workflow Analysis

**User Prompt:**
```
Analyze my development workflow patterns
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_learning_insights",
  "arguments": {
    "user_id": "default_user"
  }
}
```

**Expected Response:**
```json
{
  "insights": [
    "Strong TDD practitioner - writes tests first 87% of the time",
    "Prefers small, atomic commits with clear messages",
    "Refactors code immediately when complexity increases",
    "Takes regular breaks to maintain focus",
    "Reviews own code before committing"
  ],
  "patterns": {
    "development_approach": "test_driven",
    "commit_style": "atomic",
    "refactoring_trigger": "complexity_threshold",
    "code_review": "self_review_before_commit"
  },
  "recommendations": [
    "Consider pair programming for complex features",
    "Your test coverage is excellent - maintain this standard",
    "Your commit messages are clear and descriptive"
  ],
  "user_id": "default_user"
}
```

**Chat Agent Response:**
```
Your workflow analysis shows excellent development practices:

**Strengths:**
- Strong TDD practitioner (87% test-first approach)
- Atomic commits with clear messages
- Proactive refactoring when complexity increases
- Regular breaks for sustained focus
- Self-review before committing

**Recommendations:**
- Consider pair programming for complex features
- Maintain your excellent test coverage
- Keep up the clear commit messages

You're following industry best practices!
```

**Requirements Covered:** 3.4

---

## GitHub Search Examples

### Example 1: Find Repositories by Topic

**User Prompt:**
```
Find my repositories related to machine learning
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_github_rank_repos",
  "arguments": {
    "query": "machine learning",
    "visibility": "all",
    "limit": 10
  }
}
```

**Expected Response:**
```json
{
  "ranking": [
    {
      "repo": {
        "name": "ml-prediction-engine",
        "full_name": "user/ml-prediction-engine",
        "description": "Machine learning prediction engine with RLHF",
        "stargazers_count": 45,
        "language": "Python",
        "html_url": "https://github.com/user/ml-prediction-engine",
        "updated_at": "2025-11-10T14:30:00Z"
      },
      "score": 0.95,
      "reason": "Contains ML models, training scripts, and prediction APIs"
    },
    {
      "repo": {
        "name": "ai-assistant",
        "full_name": "user/ai-assistant",
        "description": "AI-powered home automation assistant",
        "stargazers_count": 32,
        "language": "Python",
        "html_url": "https://github.com/user/ai-assistant",
        "updated_at": "2025-11-08T09:15:00Z"
      },
      "score": 0.87,
      "reason": "Uses machine learning for automation predictions"
    },
    {
      "repo": {
        "name": "data-analysis-toolkit",
        "full_name": "user/data-analysis-toolkit",
        "description": "Data analysis and visualization tools",
        "stargazers_count": 18,
        "language": "Python",
        "html_url": "https://github.com/user/data-analysis-toolkit",
        "updated_at": "2025-10-25T16:45:00Z"
      },
      "score": 0.72,
      "reason": "Includes ML-based data analysis features"
    }
  ],
  "query": "machine learning",
  "total_repos_searched": 47
}
```

**Chat Agent Response:**
```
I found 3 repositories related to machine learning:

1. **ml-prediction-engine** (95% match) ⭐ 45
   - Machine learning prediction engine with RLHF
   - Contains ML models, training scripts, and prediction APIs
   - https://github.com/user/ml-prediction-engine

2. **ai-assistant** (87% match) ⭐ 32
   - AI-powered home automation assistant
   - Uses machine learning for automation predictions
   - https://github.com/user/ai-assistant

3. **data-analysis-toolkit** (72% match) ⭐ 18
   - Data analysis and visualization tools
   - Includes ML-based data analysis features
   - https://github.com/user/data-analysis-toolkit

Would you like me to open any of these repositories?
```

**Requirements Covered:** 5.1, 5.2, 5.3

---

### Example 2: Search for Authentication Projects

**User Prompt:**
```
Find my repositories related to authentication and security
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_github_rank_repos",
  "arguments": {
    "query": "authentication security",
    "visibility": "all",
    "limit": 5
  }
}
```

**Expected Response:**
```json
{
  "ranking": [
    {
      "repo": {
        "name": "oauth2-service",
        "full_name": "user/oauth2-service",
        "description": "OAuth2 authentication service with JWT",
        "stargazers_count": 67,
        "language": "TypeScript",
        "html_url": "https://github.com/user/oauth2-service"
      },
      "score": 0.98,
      "reason": "Primary authentication service with OAuth2 and JWT implementation"
    },
    {
      "repo": {
        "name": "api-gateway",
        "full_name": "user/api-gateway",
        "description": "API gateway with authentication middleware",
        "stargazers_count": 54,
        "language": "Node.js",
        "html_url": "https://github.com/user/api-gateway"
      },
      "score": 0.89,
      "reason": "Implements authentication middleware and security policies"
    }
  ],
  "query": "authentication security",
  "total_repos_searched": 47
}
```

**Chat Agent Response:**
```
Found 2 repositories matching "authentication security":

1. **oauth2-service** (98% match) ⭐ 67
   - OAuth2 authentication service with JWT
   - Primary authentication service with OAuth2 and JWT implementation
   - Language: TypeScript
   - https://github.com/user/oauth2-service

2. **api-gateway** (89% match) ⭐ 54
   - API gateway with authentication middleware
   - Implements authentication middleware and security policies
   - Language: Node.js
   - https://github.com/user/api-gateway

These are your most relevant authentication projects.
```

**Requirements Covered:** 5.1, 5.2, 5.3

---

### Example 3: Find Issues Across Repositories

**User Prompt:**
```
Find critical bugs in my repositories
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_github_rank_all",
  "arguments": {
    "query": "critical bug",
    "state": "open",
    "limit": 10
  }
}
```

**Expected Response:**
```json
{
  "ranking": [
    {
      "type": "issue",
      "repo": "user/ml-prediction-engine",
      "title": "Critical: Memory leak in prediction service",
      "number": 42,
      "score": 0.96,
      "labels": ["bug", "critical", "production"],
      "created_at": "2025-11-12T08:30:00Z",
      "url": "https://github.com/user/ml-prediction-engine/issues/42",
      "reason": "Critical production bug affecting memory usage"
    },
    {
      "type": "issue",
      "repo": "user/oauth2-service",
      "title": "Security: Token validation bypass vulnerability",
      "number": 28,
      "score": 0.94,
      "labels": ["security", "critical"],
      "created_at": "2025-11-11T14:20:00Z",
      "url": "https://github.com/user/oauth2-service/issues/28",
      "reason": "Critical security vulnerability in token validation"
    },
    {
      "type": "issue",
      "repo": "user/api-gateway",
      "title": "Bug: Rate limiting not working correctly",
      "number": 15,
      "score": 0.85,
      "labels": ["bug", "high-priority"],
      "created_at": "2025-11-10T10:15:00Z",
      "url": "https://github.com/user/api-gateway/issues/15",
      "reason": "High priority bug affecting rate limiting"
    }
  ],
  "query": "critical bug",
  "total_items_searched": 156
}
```

**Chat Agent Response:**
```
Found 3 critical bugs across your repositories:

🔴 **CRITICAL** - ml-prediction-engine #42
   Memory leak in prediction service
   Labels: bug, critical, production
   Created: Nov 12, 2025
   https://github.com/user/ml-prediction-engine/issues/42

🔴 **CRITICAL** - oauth2-service #28
   Security: Token validation bypass vulnerability
   Labels: security, critical
   Created: Nov 11, 2025
   https://github.com/user/oauth2-service/issues/28

🟠 **HIGH** - api-gateway #15
   Bug: Rate limiting not working correctly
   Labels: bug, high-priority
   Created: Nov 10, 2025
   https://github.com/user/api-gateway/issues/15

These require immediate attention. Would you like me to help prioritize or create a fix plan?
```

**Requirements Covered:** 5.1, 5.2, 5.3

---

### Example 4: Filter by Repository Visibility

**User Prompt:**
```
Show me only my private repositories related to backend
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_github_rank_repos",
  "arguments": {
    "query": "backend",
    "visibility": "private",
    "limit": 10
  }
}
```

**Expected Response:**
```json
{
  "ranking": [
    {
      "repo": {
        "name": "internal-api",
        "full_name": "user/internal-api",
        "description": "Internal backend API service",
        "private": true,
        "language": "Python",
        "html_url": "https://github.com/user/internal-api"
      },
      "score": 0.91,
      "reason": "Backend API service with FastAPI"
    }
  ],
  "query": "backend",
  "total_repos_searched": 12
}
```

**Chat Agent Response:**
```
Found 1 private repository related to backend:

🔒 **internal-api** (91% match)
   - Internal backend API service
   - Backend API service with FastAPI
   - Language: Python
   - https://github.com/user/internal-api

This is your only private backend repository.
```

**Requirements Covered:** 5.1, 5.2, 5.3

---

## Command Execution Examples

### Example 1: Explain Command Before Running

**User Prompt:**
```
What does "npm install" do?
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_command",
  "arguments": {
    "method": "explain",
    "command": "npm install"
  }
}
```

**Expected Response:**
```json
{
  "command": "npm install",
  "explanation": "Installs all dependencies listed in package.json into the node_modules directory. This command reads package.json and package-lock.json to determine which packages to install and their versions.",
  "category": "package_management",
  "risk_level": "low",
  "side_effects": [
    "Creates or updates node_modules directory",
    "Creates or updates package-lock.json",
    "Downloads packages from npm registry"
  ]
}
```

**Chat Agent Response:**
```
The command "npm install" does the following:

**Purpose:** Installs all dependencies listed in package.json into the node_modules directory.

**How it works:** Reads package.json and package-lock.json to determine which packages to install and their versions.

**Side effects:**
- Creates or updates node_modules directory
- Creates or updates package-lock.json
- Downloads packages from npm registry

**Risk level:** Low

Would you like me to run this command?
```

**Requirements Covered:** 7.1, 7.2

---

### Example 2: Dry Run Command Simulation

**User Prompt:**
```
Simulate running "git commit -m 'Add new feature'"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_command",
  "arguments": {
    "method": "dry_run",
    "command": "git commit -m 'Add new feature'"
  }
}
```

**Expected Response:**
```json
{
  "command": "git commit -m 'Add new feature'",
  "simulation_result": {
    "would_execute": true,
    "estimated_changes": [
      "Create new commit with message 'Add new feature'",
      "Update HEAD to point to new commit",
      "Update current branch reference"
    ],
    "files_affected": [
      "src/feature.ts",
      "src/feature.test.ts",
      "README.md"
    ],
    "warnings": [
      "3 files staged for commit"
    ]
  },
  "safe_to_run": true
}
```

**Chat Agent Response:**
```
Simulation of "git commit -m 'Add new feature'":

**Would execute:** Yes

**Estimated changes:**
- Create new commit with message 'Add new feature'
- Update HEAD to point to new commit
- Update current branch reference

**Files affected:**
- src/feature.ts
- src/feature.test.ts
- README.md

**Warnings:**
- 3 files staged for commit

**Safe to run:** Yes

Would you like me to execute this command for real?
```

**Requirements Covered:** 7.1, 7.2

---

### Example 3: Run Command with Approval

**User Prompt:**
```
Run "npm test"
```

**Tool Invocation (First Attempt):**
```json
{
  "tool": "ide_agents_command",
  "arguments": {
    "method": "run",
    "command": "npm test"
  }
}
```

**Expected Response (Approval Required):**
```json
{
  "approval_required": true,
  "action_id": "cmd:npm test:1699999999",
  "command": "npm test",
  "message": "This command will execute tests. Approve to continue.",
  "risk_assessment": {
    "risk_level": "low",
    "reason": "Test execution is generally safe"
  }
}
```

**Chat Agent Response:**
```
⚠️ Approval Required

Command: npm test

This command will execute tests.

Risk level: Low (Test execution is generally safe)

Do you approve this command?
[Approve] [Deny]
```

**User Action:** Clicks "Approve"

**Tool Invocation (After Approval):**
```json
{
  "tool": "ide_agents_command",
  "arguments": {
    "method": "run",
    "command": "npm test",
    "action_id": "cmd:npm test:1699999999"
  }
}
```

**Expected Response (After Approval):**
```json
{
  "success": true,
  "command": "npm test",
  "output": "PASS  src/feature.test.ts\n  Feature Tests\n    ✓ should create feature (15ms)\n    ✓ should update feature (12ms)\n    ✓ should delete feature (8ms)\n\nTest Suites: 1 passed, 1 total\nTests:       3 passed, 3 total\nTime:        2.456s",
  "exit_code": 0,
  "duration_ms": 2456
}
```

**Chat Agent Response:**
```
✅ Command executed successfully!

**Output:**
```
PASS  src/feature.test.ts
  Feature Tests
    ✓ should create feature (15ms)
    ✓ should update feature (12ms)
    ✓ should delete feature (8ms)

Test Suites: 1 passed, 1 total
Tests:       3 passed, 3 total
Time:        2.456s
```

All tests passed! 🎉
```

**Requirements Covered:** 7.1, 7.2, 3.5

---

### Example 4: Run Dangerous Command with Approval

**User Prompt:**
```
Run "rm -rf node_modules"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_command",
  "arguments": {
    "method": "run",
    "command": "rm -rf node_modules"
  }
}
```

**Expected Response (Approval Required):**
```json
{
  "approval_required": true,
  "action_id": "cmd:rm -rf node_modules:1699999999",
  "command": "rm -rf node_modules",
  "message": "⚠️ WARNING: This command will permanently delete the node_modules directory. This action cannot be undone.",
  "risk_assessment": {
    "risk_level": "medium",
    "reason": "Deletes files permanently",
    "affected_paths": ["node_modules/"],
    "recovery_options": ["Run 'npm install' to restore"]
  }
}
```

**Chat Agent Response:**
```
⚠️ HIGH RISK COMMAND - APPROVAL REQUIRED

Command: rm -rf node_modules

**WARNING:** This command will permanently delete the node_modules directory. This action cannot be undone.

**Risk level:** Medium
**Reason:** Deletes files permanently
**Affected paths:** node_modules/
**Recovery:** Run 'npm install' to restore

Are you sure you want to proceed?
[Approve] [Deny]
```

**User Action:** Clicks "Approve"

**Expected Response (After Approval):**
```json
{
  "success": true,
  "command": "rm -rf node_modules",
  "output": "",
  "exit_code": 0,
  "duration_ms": 1234,
  "message": "Directory node_modules has been deleted"
}
```

**Chat Agent Response:**
```
✅ Command executed successfully!

Directory node_modules has been deleted.

You can restore it by running: npm install
```

**Requirements Covered:** 7.1, 7.2

---

### Example 5: Command Execution Denied

**User Prompt:**
```
Run "sudo rm -rf /"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_command",
  "arguments": {
    "method": "run",
    "command": "sudo rm -rf /"
  }
}
```

**Expected Response (Approval Required):**
```json
{
  "approval_required": true,
  "action_id": "cmd:sudo rm -rf /:1699999999",
  "command": "sudo rm -rf /",
  "message": "🚨 CRITICAL WARNING: This command will delete your entire system. This is EXTREMELY DANGEROUS and will destroy all data.",
  "risk_assessment": {
    "risk_level": "critical",
    "reason": "System-wide deletion - will destroy operating system",
    "recommendation": "DO NOT APPROVE THIS COMMAND"
  }
}
```

**Chat Agent Response:**
```
🚨 CRITICAL DANGER - DO NOT APPROVE

Command: sudo rm -rf /

**CRITICAL WARNING:** This command will delete your entire system. This is EXTREMELY DANGEROUS and will destroy all data.

**Risk level:** CRITICAL
**Impact:** System-wide deletion - will destroy operating system

**RECOMMENDATION: DO NOT APPROVE THIS COMMAND**

This appears to be a mistake. Did you mean something else?
[Deny] [Explain what I meant]
```

**User Action:** Clicks "Deny"

**Chat Agent Response:**
```
✅ Command denied for your safety.

That command would have deleted your entire system. If you need to delete something specific, please let me know what you're trying to accomplish, and I'll help you with the correct command.
```

**Requirements Covered:** 7.1, 7.2

---

## Error Handling Scenarios

### Error 1: Backend Service Unavailable

**User Prompt:**
```
Analyze the emotion in: "I'm happy"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_analyze_emotion",
  "arguments": {
    "text": "I'm happy"
  }
}
```

**Expected Error Response:**
```json
{
  "error": "Backend service unavailable",
  "error_code": "BACKEND_UNAVAILABLE",
  "message": "Could not connect to AI backend service at http://127.0.0.1:8001",
  "details": "Connection refused. Please ensure the backend service is running.",
  "recovery_steps": [
    "Start the backend service: python mock_backend_server.py",
    "Verify service is running: curl http://127.0.0.1:8001/health",
    "Check firewall settings"
  ]
}
```

**Chat Agent Response:**
```
❌ Error: Backend service unavailable

I couldn't connect to the AI backend service at http://127.0.0.1:8001

**Recovery steps:**
1. Start the backend service: `python mock_backend_server.py`
2. Verify service is running: `curl http://127.0.0.1:8001/health`
3. Check firewall settings

Once the backend is running, try your request again.
```

**Requirements Covered:** 3.2, Error Handling

---

### Error 2: ULTRA Mode Not Enabled

**User Prompt:**
```
Show me AI predictions
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_predictions",
  "arguments": {
    "user_id": "default_user"
  }
}
```

**Expected Error Response:**
```json
{
  "error": "ULTRA mode not enabled",
  "error_code": "ULTRA_DISABLED",
  "message": "ML intelligence tools require ULTRA mode to be enabled",
  "details": "Set IDE_AGENTS_ULTRA_ENABLED=true in your MCP configuration",
  "recovery_steps": [
    "Open .kiro/settings/mcp.json",
    "Set 'IDE_AGENTS_ULTRA_ENABLED': 'true' in the env section",
    "Restart Kiro IDE"
  ]
}
```

**Chat Agent Response:**
```
❌ Error: ULTRA mode not enabled

ML intelligence tools require ULTRA mode to be enabled.

**To enable ULTRA mode:**
1. Open `.kiro/settings/mcp.json`
2. Set `"IDE_AGENTS_ULTRA_ENABLED": "true"` in the env section
3. Restart Kiro IDE

After enabling ULTRA mode, you'll have access to all ML intelligence features.
```

**Requirements Covered:** 3.3, Error Handling

---

### Error 3: GitHub Token Missing

**User Prompt:**
```
Find my repositories
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_github_repos",
  "arguments": {
    "visibility": "all",
    "limit": 10
  }
}
```

**Expected Error Response:**
```json
{
  "error": "GitHub token not found",
  "error_code": "GITHUB_TOKEN_MISSING",
  "message": "GITHUB_TOKEN environment variable is not set",
  "details": "GitHub integration requires a personal access token",
  "recovery_steps": [
    "Create a GitHub Personal Access Token at https://github.com/settings/tokens",
    "Set the token in your environment: export GITHUB_TOKEN='your_token'",
    "Or add it to .kiro/settings/mcp.json env section",
    "Restart Kiro IDE"
  ]
}
```


**Chat Agent Response:**
```
❌ Error: GitHub token not found

GitHub integration requires a personal access token.

**Setup steps:**
1. Create a token at https://github.com/settings/tokens
2. Required scopes: `repo`, `read:org`
3. Set the token:
   - Environment: `export GITHUB_TOKEN='your_token'`
   - Or add to `.kiro/settings/mcp.json` env section
4. Restart Kiro IDE

Once configured, you'll be able to search and rank your GitHub repositories.
```

**Requirements Covered:** 5.1, Error Handling

---

### Error 4: Invalid Command Syntax

**User Prompt:**
```
Run "git commit"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_command",
  "arguments": {
    "method": "run",
    "command": "git commit"
  }
}
```

**Expected Error Response:**
```json
{
  "error": "Command execution failed",
  "error_code": "COMMAND_FAILED",
  "command": "git commit",
  "exit_code": 1,
  "output": "error: pathspec '' did not match any file(s) known to git\nnothing to commit (use 'git add' to track)",
  "suggestion": "Did you mean: git commit -m 'your message'?",
  "help": "Git commit requires a message. Use -m flag to provide one."
}
```

**Chat Agent Response:**
```
❌ Command failed

Command: git commit
Exit code: 1

**Error output:**
```
error: pathspec '' did not match any file(s) known to git
nothing to commit (use 'git add' to track)
```

**Suggestion:** Did you mean: `git commit -m 'your message'`?

**Help:** Git commit requires a message. Use -m flag to provide one.

Would you like me to help you create a proper commit command?
```

**Requirements Covered:** 7.1, 7.2, Error Handling

---

### Error 5: Rate Limit Exceeded

**User Prompt:**
```
Analyze emotion in: "text1"
Analyze emotion in: "text2"
Analyze emotion in: "text3"
[... many rapid requests ...]
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_analyze_emotion",
  "arguments": {
    "text": "text50"
  }
}
```

**Expected Error Response:**
```json
{
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please wait before trying again.",
  "details": "Rate limit: 1 request per 250ms",
  "retry_after_ms": 250,
  "requests_made": 50,
  "time_window": "10 seconds"
}
```

**Chat Agent Response:**
```
⏱️ Rate limit exceeded

You've made 50 requests in 10 seconds. Please slow down.

**Rate limit:** 1 request per 250ms

I'll automatically retry in 250ms...

[Request succeeds after waiting]

✅ Analysis complete: "text50" - mood: neutral, confidence: 0.85
```

**Requirements Covered:** Error Handling

---

### Error 6: Invalid Tool Arguments

**User Prompt:**
```
Get predictions for user 12345
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_ml_get_predictions",
  "arguments": {
    "user_id": 12345
  }
}
```

**Expected Error Response:**
```json
{
  "error": "Invalid arguments",
  "error_code": "VALIDATION_ERROR",
  "message": "Argument 'user_id' must be a string, got number",
  "details": {
    "parameter": "user_id",
    "expected_type": "string",
    "received_type": "number",
    "received_value": 12345
  },
  "suggestion": "Use: user_id='12345' (as string)"
}
```

**Chat Agent Response:**
```
❌ Invalid arguments

The parameter 'user_id' must be a string, but I received a number.

**Expected:** string
**Received:** number (12345)

**Suggestion:** Use `user_id='12345'` (as string)

Let me correct that and try again...

[Retries with correct type]
```

**Requirements Covered:** Error Handling

---

### Error 7: Network Timeout

**User Prompt:**
```
Rank my repositories by relevance to "complex query"
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_github_rank_repos",
  "arguments": {
    "query": "complex query",
    "limit": 100
  }
}
```

**Expected Error Response:**
```json
{
  "error": "Request timeout",
  "error_code": "TIMEOUT",
  "message": "Request to backend service timed out after 30 seconds",
  "details": "The backend service took too long to respond",
  "recovery_steps": [
    "Try reducing the limit parameter",
    "Check backend service performance",
    "Increase timeout: Set IDE_AGENTS_REQUEST_TIMEOUT=60.0"
  ]
}
```

**Chat Agent Response:**
```
⏱️ Request timeout

The backend service took too long to respond (>30 seconds).

**Suggestions:**
1. Try with fewer results: Reduce the limit parameter
2. Check backend service performance
3. Increase timeout in config: `IDE_AGENTS_REQUEST_TIMEOUT=60.0`

Would you like me to retry with a smaller limit (e.g., 20 repositories)?
```

**Requirements Covered:** Error Handling

---

### Error 8: GitHub API Rate Limit

**User Prompt:**
```
Find all issues across my repositories
```

**Tool Invocation:**
```json
{
  "tool": "ide_agents_github_rank_all",
  "arguments": {
    "query": "all issues",
    "state": "all",
    "limit": 1000
  }
}
```

**Expected Error Response:**
```json
{
  "error": "GitHub API rate limit exceeded",
  "error_code": "GITHUB_RATE_LIMIT",
  "message": "GitHub API rate limit exceeded. Limit resets at 2025-11-14T11:00:00Z",
  "details": {
    "limit": 5000,
    "remaining": 0,
    "reset_at": "2025-11-14T11:00:00Z",
    "reset_in_minutes": 45
  },
  "recovery_steps": [
    "Wait 45 minutes for rate limit reset",
    "Use a different GitHub token",
    "Reduce the number of requests"
  ]
}
```

**Chat Agent Response:**
```
⏱️ GitHub API rate limit exceeded

You've used all 5000 requests for this hour.

**Rate limit resets in:** 45 minutes (at 11:00 AM)

**Options:**
1. Wait for rate limit reset
2. Use a different GitHub token
3. Reduce the scope of your search

I'll automatically retry when the limit resets, or you can try a more specific query now.
```

**Requirements Covered:** 5.1, Error Handling

---

## Best Practices

### For Emotion Analysis
1. **Use natural language**: Provide complete sentences for better accuracy
2. **Context matters**: Include context when analyzing technical vs. personal statements
3. **Combine with actions**: Use emotion detection to adapt agent responses
4. **Monitor confidence**: Low confidence (<0.7) may indicate ambiguous text

### For Predictions
1. **Build history first**: Predictions improve with more usage data
2. **Provide feedback**: Accept or reject predictions to improve accuracy
3. **Check confidence**: Higher confidence (>0.85) indicates reliable predictions
4. **Review context**: Understand why predictions are made

### For Learning Insights
1. **Regular reviews**: Check insights weekly to understand patterns
2. **Privacy aware**: Insights are local and never shared externally
3. **Use for optimization**: Adjust workflow based on learned patterns
4. **Track progress**: Monitor statistics over time

### For GitHub Search
1. **Be specific**: Use detailed queries for better ranking
2. **Filter appropriately**: Use visibility and state filters to narrow results
3. **Check scores**: Higher scores (>0.85) indicate strong matches
4. **Semantic queries**: ULTRA mode enables natural language search

### For Command Execution
1. **Always explain first**: Use "explain" method before "run"
2. **Test with dry_run**: Simulate commands to understand impact
3. **Review approval prompts**: Read carefully before approving
4. **Start safe**: Begin with read-only commands
5. **Check exit codes**: 0 = success, non-zero = error

---

## Quick Reference

### Common User Prompts

| User Intent | Example Prompt | Tool Used |
|-------------|----------------|-----------|
| Emotion check | "How do I sound?" | `ide_agents_ml_analyze_emotion` |
| Get suggestions | "What should I do next?" | `ide_agents_ml_get_predictions` |
| Learn patterns | "What are my coding habits?" | `ide_agents_ml_get_learning_insights` |
| Find repos | "Find my React projects" | `ide_agents_github_rank_repos` |
| Find issues | "Show critical bugs" | `ide_agents_github_rank_all` |
| Explain command | "What does X do?" | `ide_agents_command` (explain) |
| Test command | "Simulate running X" | `ide_agents_command` (dry_run) |
| Run command | "Execute X" | `ide_agents_command` (run) |

### Response Time Expectations

| Tool Category | Expected Response Time |
|---------------|------------------------|
| Health check | < 100ms |
| Emotion analysis | < 500ms |
| Predictions | < 1s |
| Learning insights | < 1s |
| GitHub repos (10) | < 2s |
| GitHub ranking | < 3s |
| Command explain | < 200ms |
| Command dry_run | < 500ms |
| Command run | Varies by command |

### Error Code Reference

| Error Code | Meaning | Common Cause |
|------------|---------|--------------|
| `BACKEND_UNAVAILABLE` | Backend service not responding | Service not started |
| `ULTRA_DISABLED` | ULTRA mode not enabled | Config setting missing |
| `GITHUB_TOKEN_MISSING` | No GitHub token found | Token not configured |
| `GITHUB_RATE_LIMIT` | GitHub API limit exceeded | Too many requests |
| `RATE_LIMIT_EXCEEDED` | MCP rate limit hit | Too many rapid requests |
| `TIMEOUT` | Request took too long | Backend overloaded |
| `VALIDATION_ERROR` | Invalid arguments | Wrong parameter type |
| `COMMAND_FAILED` | Command execution failed | Invalid command syntax |
| `APPROVAL_DENIED` | User denied approval | User rejected command |

---

## Conclusion

This document provides comprehensive examples for using MCP tools through the Kiro chat agent. Each tool is designed to enhance your development workflow with AI-powered intelligence.

**Key Takeaways:**
- Always start with safe operations (explain, dry_run)
- Review approval prompts carefully
- Monitor error messages for troubleshooting
- Build usage history for better predictions
- Use semantic queries for GitHub search

For more information, see:
- [MCP Integration Guide](MCP_INTEGRATION_GUIDE.md) - Complete setup and configuration
- [Requirements Document](.kiro/specs/mcp-kiro-integration/requirements.md) - Detailed requirements
- [Design Document](.kiro/specs/mcp-kiro-integration/design.md) - Architecture and design

---

**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** 2025-11-14

---

## Author

**Herman Swanepoel** - *Project Creator*
