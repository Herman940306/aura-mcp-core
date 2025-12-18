# /rank_github_all

Goal: Unified ranking over repositories plus recent issues & PRs.

Tool: `ide_agents_github_rank_all`

Arguments:

- `query` (required): semantic/keyword intent.
- `visibility` (optional): public|private repo filter.
- `limit` (optional): number of repos fetched (<=100).
- `state` (optional): open|closed issue/PR state (default open).
- `include` / `exclude` (optional arrays): repo name or full_name filters.
- `items_per_repo` (optional): issues/PRs pulled per repo (<=50, default 30).
- `page` (optional): pagination page for issues/PRs.
- `top` (optional): truncate final ranked list to N.

Example:

```json
/ask ide_agents_github_rank_all {
  "query": "bug detection",
  "visibility": "public",
  "state": "open",
  "limit": 40,
  "items_per_repo": 20,
  "top": 15
}
```

Scoring:

- ULTRA backend or mock (if enabled) produces semantic scores normalized to 0–10.
- Heuristic fallback blends stars/forks, recency, text match, and comment volume.

Environment:

- Ensure `GITHUB_TOKEN` available.
- Enable ULTRA: `IDE_AGENTS_ULTRA_ENABLED=1` (mock: `IDE_AGENTS_ULTRA_MOCK=1`).
