# /rank_top_bug_prs

Goal: Quickly surface top open PRs and issues related to bug fixes.

Tool: `ide_agents_github_rank_all`

Recommended Args:

```json
/ask ide_agents_github_rank_all {
  "query": "bug fix",
  "state": "open",
  "items_per_repo": 15,
  "top": 20,
  "since": "2025-10-01T00:00:00Z"
}
```

Tips:

- Adjust `query` (e.g., "security", "regression", "performance") for thematic triage.
- Combine `include` to narrow to core repositories.
- Use `IDE_AGENTS_ULTRA_MOCK=1` to experiment without a live ULTRA backend.
