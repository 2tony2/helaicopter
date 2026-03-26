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

## Configure Local Auth

The orchestration Auth Management UI now uses the real local provider flows:

- Claude: `Reuse Claude CLI session` only works when the same machine already has a valid Claude CLI login. Run `claude auth login` locally first if `~/.claude/credentials.json` or `claude auth status` is missing.
- Codex: `OAuth redirect` only works when the backend has a configured local OAuth client. Set `HELA_CODEX_OAUTH_CLIENT_ID` and, if you are not using the defaults, the matching authorize URL, token URL, and local callback URI env vars before starting `npm run dev`.
- Codex callback: the default local callback is `http://127.0.0.1:31506/auth/credentials/oauth/callback`, so your OAuth client must allow that redirect URI.

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

## Auth Management Quick Check

After the app is running, open `/orchestration#auth-management` on the local frontend URL and confirm:

- Claude shows `Reuse Claude CLI session`.
- Codex shows `OAuth redirect`.
- Claude connect creates or refreshes a local CLI credential when Claude CLI auth already exists on that machine.
- Codex OAuth starts a browser redirect without a `Failed to fetch` client-side error when the OAuth client env vars are configured.
