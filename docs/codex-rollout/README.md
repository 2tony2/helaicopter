# Codex Rollout Tickets

These ticket prompts are designed for `scripts/run-codex-rollout.sh`.

The runner will:

- create a fresh `codex/...` branch from the repo default branch for each ticket
- invoke `codex exec` in full-access autonomous mode
- commit any remaining uncommitted changes
- push the branch
- open a GitHub PR
- merge the PR back to `main` or the detected default branch

Recommended usage:

```bash
scripts/run-codex-rollout.sh
```

Useful partial runs:

```bash
scripts/run-codex-rollout.sh --start-at 1 --end-at 1
scripts/run-codex-rollout.sh --start-at 4
scripts/run-codex-rollout.sh --dry-run
```

Notes:

- The runner expects a clean working tree before it starts.
- Each ticket prompt tells the downstream agent not to create branches or PRs because the runner owns that workflow.
- Logs and captured final messages are written under `var/codex-rollout/` during execution.
