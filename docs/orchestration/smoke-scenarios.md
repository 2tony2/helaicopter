# Orchestration Smoke Scenarios

These are the high-signal Phase 4 acceptance scenarios for the permanent-worker-loop system.

## Release Gate

- Cold start to healthy system: backend, resolver, Claude worker, and Codex worker all appear healthy in `/operator/bootstrap`.
- Auth management wiring: `/orchestration#auth-management` shows `Reuse Claude CLI session` for Claude and `Reuse Codex CLI session` for Codex.
- Claude happy path: a Claude task dispatches, reports completion, and materializes runtime truth.
- Codex happy path: a Codex task dispatches, reports completion, and materializes runtime truth.
- Auth failure visibility: provider auth/session problems block dispatch with an explicit operator-visible reason.
- Worker interruption and recovery: a dead worker is surfaced cleanly and the task is recoverable on another eligible worker.
- Operator intervention visibility: pause, resume, retry, and reroute remain visible through orchestration state and graph mutations.

## What To Check When A Smoke Fails

- `operator/bootstrap`: confirms resolver status, worker presence, provider readiness, and first actionable next step.
- `dispatch/queue`: shows whether work is ready, deferred, or blocked by provider or worker state.
- `orchestration/runtime/{run_id}`: shows task attempts, dispatch events, graph mutations, and operator actions from runtime artifacts.
- `workers`: confirms whether a worker is idle, busy, dead, draining, or blocked by auth.

## Current Automation Boundary

- The Python smoke suite covers the cold-start, provider happy-path, and worker interruption slices.
- Auth-failure and operator-intervention flows are currently verified by the focused API/runtime tests rather than a single monolithic smoke harness.
- Local auth remains provider-specific during manual smoke verification:
  - Claude requires an authenticated local Claude CLI session on the same machine.
  - Codex requires an authenticated local Codex CLI session on the same machine.
- Phase 4 verification should currently run both the smoke tests and the focused operator/runtime assertions:
  `uv run pytest tests/test_end_to_end_smoke.py tests/test_api_operator_controls.py tests/test_api_dispatch.py tests/test_api_runtime_materialization.py tests/test_api_operator_bootstrap.py tests/test_api_orchestration.py tests/test_resolver_loop.py tests/test_permanent_loop_integration.py -q`

## Local Auth Smoke Checklist

When verifying the real auth paths locally:

- Start the app with `npm run dev`.
- Open `/orchestration#auth-management`.
- Confirm Claude offers `Reuse Claude CLI session`.
- Confirm Codex offers `Reuse Codex CLI session`.
- Click Claude connect and verify a credential appears when the local Claude CLI is already authenticated.
- Click Codex connect and verify a credential appears when the local Codex CLI is already authenticated.
