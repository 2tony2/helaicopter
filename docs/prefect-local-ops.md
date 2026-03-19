# Prefect Local Ops

This runbook covers the local Prefect control plane and the host-managed macOS worker used for the first rollout.

## Environment expectations

- Start the local control plane with `docker compose -f ops/prefect/docker-compose.yml up -d`.
- Confirm the control plane is healthy with `docker compose -f ops/prefect/docker-compose.yml ps`.
- Point the worker at that API with `PREFECT_API_URL=http://127.0.0.1:4200/api` unless you intentionally changed the port or host.
- The worker defaults to `OATS_PREFECT_WORK_POOL=local-macos`; set a different value only if you also create the matching Prefect work pool.
- Install the Python environment that provides the `prefect` CLI before loading the worker service.
- Create the work pool once per machine with `prefect work-pool create local-macos --type process` if it does not already exist.

## launchd asset setup

Copy `ops/launchd/com.helaicopter.prefect-worker.plist.template` to a machine-local plist, replace:

- `{{REPO_ROOT}}` with the absolute path to this checkout
- `{{PREFECT_API_URL}}` with the local Prefect API URL
- `{{WORK_POOL}}` with the target work pool name
- `{{LOG_DIR}}` with a writable directory for worker logs

The committed template intentionally avoids machine-specific absolute paths.

## Load and unload

Load the worker after the Prefect server stack is healthy:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist
launchctl kickstart -k gui/$(id -u)/com.helaicopter.prefect-worker
```

Unload it when you want to stop the local worker cleanly:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.helaicopter.prefect-worker.plist
```

## Logs

The launchd plist writes worker output to:

- `{{LOG_DIR}}/stdout.log`
- `{{LOG_DIR}}/stderr.log`

Tail them while bootstrapping or debugging:

```bash
tail -f /path/to/logs/stdout.log /path/to/logs/stderr.log
```

## Wrapper behavior

`ops/scripts/prefect-worker.sh` is the service entrypoint. It:

- exports `PREFECT_API_URL`
- defaults `OATS_PREFECT_WORK_POOL` to `local-macos`
- runs `prefect worker start` under `caffeinate` so the machine is less likely to sleep through local execution windows

## Local validation

Use these checks before or after cutover work:

```bash
curl http://127.0.0.1:4200/api/health
prefect work-pool ls
prefect worker ls --pool local-macos
uv run oats prefect deploy examples/prefect_native_oats_orchestration_run.md
uv run oats prefect run examples/prefect_native_oats_orchestration_run.md
```

For the full cutover sequence, UI expectations, and rollback steps, use [`docs/oats-prefect-cutover.md`](/Users/tony/Code/helaicopter/docs/oats-prefect-cutover.md).
