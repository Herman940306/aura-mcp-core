---
inclusion: always
---

# 🚨 CRITICAL SERVER SAFETY RULES

**Priority:** HIGHEST - These rules override all other considerations

## Production Server Protection

The NAS server at `{{NAS_IP}}` runs **mission-critical workloads**. Any action that could impact server health, data integrity, or service availability requires **100% confidence** before execution.

## Mandatory Requirements

### Before ANY Server Action:
1. **Verify the command/action is correct** - No guessing, no assumptions
2. **Understand the impact** - What services could be affected?
3. **Have a rollback plan** - How to undo if something goes wrong?
4. **Test locally first** - When possible, validate on local environment

### NEVER Do:
- ❌ Run destructive commands without explicit user confirmation
- ❌ Modify production configs without backup verification
- ❌ Restart critical services during uncertain conditions
- ❌ Execute commands you're not 100% confident about
- ❌ Make assumptions about server state - always verify first
- ❌ Chain multiple risky operations without checkpoints

### ALWAYS Do:
- ✅ Ask for clarification if uncertain about any step
- ✅ Provide the exact command for user review before execution
- ✅ Suggest dry-run or read-only verification first
- ✅ Document what was changed and how to revert
- ✅ Check service health after any modification
- ✅ Prefer non-destructive approaches

## Critical Services (Do Not Disrupt)

| Service | Impact if Down |
|---------|----------------|
| PostgreSQL (9208) | Data loss, all services fail |
| Ollama (9207) | AI/ML features unavailable |
| Gateway (9200) | All MCP tools unavailable |
| Home Assistant ({{HOME_ASSISTANT_IP}}) | Home automation offline |
| Plex/Sonarr/Radarr | Media services offline |

## When In Doubt

**STOP and ASK** - It's always better to ask for confirmation than to risk breaking production systems.

```
"I want to [action], but I'm not 100% certain this is safe. 
Should I proceed, or would you like to verify first?"
```

## Data Protection

- All data on the NAS is considered **irreplaceable**
- Database operations require extra caution
- File deletions must be explicitly confirmed
- Config changes should be backed up first
