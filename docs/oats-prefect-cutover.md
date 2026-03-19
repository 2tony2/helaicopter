# Oats Prefect Cutover Runbook

This runbook makes the Prefect control plane the primary orchestration surface for Oats while keeping the legacy local-runtime commands available for rollback and compatibility.

## 1. Start the local Prefect control plane

Preferred one-shot bootstrap:

```bash
bin/oats-prefect-up
```

Manual equivalent:

```bash
docker compose -f ops/prefect/docker-compose.yml up -d
docker compose -f ops/prefect/docker-compose.yml ps
curl http://127.0.0.1:4200/api/health
```

Expected state:

- `postgres`, `redis`, `prefect-server`, and `prefect-services` are up
- the health endpoint returns a successful response

## 2. Bootstrap the host worker with launchd

1. Copy `ops/launchd/com.helaicopter.prefect-worker.plist.template` to `~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist`.
2. Replace `{{REPO_ROOT}}`, `{{PREFECT_API_URL}}`, `{{WORK_POOL}}`, and `{{LOG_DIR}}`.
3. Ensure the work pool exists:

```bash
prefect work-pool create local-macos --type process
```

4. Load the worker:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist
launchctl kickstart -k gui/$(id -u)/com.helaicopter.prefect-worker
prefect worker ls --pool local-macos
```

Expected state:

- one online worker in `local-macos`
- worker logs streaming via the paths configured in `{{LOG_DIR}}`

## 3. Deploy the Oats run definition

Use the Prefect-first CLI path:

```bash
uv run oats prefect deploy examples/prefect_native_oats_orchestration_run.md
```

Expected state:

- the deployment is created or updated
- the deployment targets the `local-macos` work pool

## 4. Create a schedule and trigger a run

Create or update a schedule in Prefect after deployment if the run should execute automatically:

```bash
prefect deployment inspect "oats-compiled-run/helaicopter-run-prefect-native-oats-orchestration"
```

Then trigger a manual run:

```bash
uv run oats prefect run examples/prefect_native_oats_orchestration_run.md
uv run oats prefect status <flow-run-id>
```

Expected state:

- the run is visible in Prefect as a flow run
- flow-run artifacts are written under `.oats/prefect/flow-runs/<flow-run-id>/`

## 5. Validate Helaicopter orchestration UI

Open `/orchestration?tab=prefect`.

Expected UI state:

- the Prefect tab is the primary orchestration view
- the `Prefect UI` tab embeds the local Prefect web app from `http://127.0.0.1:4200`
- deployments, flow runs, workers, and work pools load from `/orchestration/prefect/*`
- repo-local Oats metadata links resolve into `.oats/prefect/flow-runs/...`
- the legacy Oats records card is present only as a compatibility surface for `.oats/runs` and `.oats/runtime`

## 6. Targeted verification commands

Run these checks after the cutover changes land:

```bash
uv run --group dev pytest -q tests/oats/test_prefect_deployments.py tests/oats/test_prefect_flows.py tests/test_api_prefect_orchestration.py
node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/prefect-normalize.test.ts
npm run lint
```

If `uv run` is blocked by a local environment issue, run the equivalent pytest command from the project virtualenv to isolate whether the problem is in `uv` or in the code under test.

## 7. Rollback

If the cutover needs to be reversed:

1. Stop launching new Prefect runs from the CLI and UI.
2. Unload the worker:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist
```

3. Stop the Prefect services:

```bash
docker compose -f ops/prefect/docker-compose.yml down
```

4. Use the legacy compatibility commands for local recovery only:

```bash
uv run oats run examples/sample_run.md
uv run oats status
uv run oats resume
```

Rollback is complete when the launchd worker is unloaded, the Compose stack is down, and no new Prefect flow runs are being created.
