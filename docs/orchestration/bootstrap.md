# Orchestration Bootstrap

Use this flow to bring the permanent-worker-loop control plane to a healthy local state.

## Cold Start

1. Install dependencies:

```bash
npm install
uv sync --group dev
```

2. Start Helaicopter:

```bash
npm run dev
```

3. Confirm the backend is alive:

```bash
curl http://127.0.0.1:30000/health
curl http://127.0.0.1:30000/operator/bootstrap
```

## Start Workers

Start one Claude worker:

```bash
uv run oats pi start \
  --provider claude \
  --model claude-sonnet-4-6 \
  --control-plane http://127.0.0.1:30000
```

Start one Codex worker:

```bash
uv run oats pi start \
  --provider codex \
  --model o3-pro \
  --control-plane http://127.0.0.1:30000
```

On successful registration, the worker should stay running and the orchestration hub should show:

- Bootstrap Checklist
- Worker Dashboard
- Auth Management
- Queue Monitor

## Expected Healthy State

`GET /operator/bootstrap` should report:

- `overallStatus: "ready"`
- `hasClaudeWorker: true`
- `hasCodexWorker: true`

If the status remains blocked, use the `blockingReasons` array and the worker dashboard readiness messages to decide what to fix next.
