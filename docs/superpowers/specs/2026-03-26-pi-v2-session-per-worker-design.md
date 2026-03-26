# Pi V2 Session-Per-Worker Design

**Date:** 2026-03-26  
**Status:** Draft  
**Builds on:** `docs/superpowers/specs/2026-03-26-pi-v2-persistent-session-roadmap-design.md`  
**Context:** Focused follow-on design for persistent worker-local provider sessions

## Goal

Upgrade Pi from a supervisor that spawns a fresh provider subprocess per task into a worker that owns a persistent provider session and reuses it across tasks, while preserving the current resolver loop, worker registry, runtime materialization, and operator-facing control surfaces.

The target is not a new orchestration architecture. The target is a new execution backend behind the existing worker boundary.

## Design Summary

Pi v2 uses a **session-per-worker** model:

- each registered Pi worker owns at most one active provider session
- the worker reuses that session across multiple task envelopes
- the control plane continues to dispatch work to workers, not directly to provider sessions
- session lifecycle and health become explicit worker-local state and operator-visible metadata

This keeps the current mental model intact:

- resolver loop chooses a worker
- worker executes a task
- runtime truth is materialized centrally

What changes is how the worker executes the task.

## Why Session-Per-Worker

This design is the smallest meaningful upgrade from Pi v1.

It preserves:

- current worker registry identity
- current dispatch affinity model
- current task envelope flow
- current result reporting contract
- current operator console structure

It adds:

- warm provider session reuse
- explicit worker session lifecycle
- session reset and recycle semantics
- finer-grained interruption semantics

It avoids:

- run-scoped session leasing complexity
- pooled-session coordination
- rewriting the control plane around session ownership

## State Model

Pi v2 introduces worker-local session state with one new invariant:

**A worker may be healthy while its provider session is unhealthy.**

That means worker health and session health must be modeled separately.

### Worker state

Existing worker lifecycle remains:

- `idle`
- `busy`
- `draining`
- `dead`
- `auth_expired`

### Session state

New worker-local provider session state:

- `absent`
- `starting`
- `ready`
- `degraded`
- `stale`
- `failed`
- `resetting`

### Combined meaning

- `worker=idle`, `session=ready`: best case, reusable warm worker
- `worker=idle`, `session=absent`: worker is alive but must create a session before useful execution
- `worker=idle`, `session=failed`: worker exists but should not receive work until reset
- `worker=busy`, `session=degraded`: active task may still finish, but operator should expect reset afterward

## Session Lifecycle

### Creation

Session creation happens lazily on first task assignment or eagerly during worker startup depending on provider behavior.

Recommended initial rule:

- start worker with `session=absent`
- create session on first claimed task
- optionally add eager warm-up later if operator experience proves it worthwhile

### Reuse

The same session is reused across tasks assigned to the worker until one of these occurs:

- operator requests reset
- provider auth/session becomes invalid
- session exceeds configured reuse age or task count budget
- provider backend reports unrecoverable session failure

### Reset

Reset discards the current provider session and returns the worker to `session=absent` or `session=starting`.

Reset must be explicit and visible in the operator model, not a hidden side effect.

### Death

If the Pi process dies, the session is assumed lost. We do not attempt detached session reattachment in the first Pi v2 wave.

That keeps failure semantics simple:

- worker dies
- session dies with it
- task is interrupted
- control plane recovers through retry or reroute

## Context Boundary

Persistent sessions introduce context bleed risk, so Pi v2 needs a clear boundary.

### Allowed to persist

- provider-local auth/session bootstrap
- repository warm state inside the worker session
- execution continuity for related tasks

### Not allowed to persist implicitly

- hidden cross-run business logic assumptions
- unbounded conversational carryover
- stale task-specific instructions that silently affect later tasks

### Required guardrail

Each task execution must still be framed by the explicit task envelope and attack plan, even if the provider session is warm. Session reuse may improve efficiency, but it cannot replace the authoritative task handoff contract.

## Worker/Session Protocol Additions

Pi v2 should extend the current contract conservatively.

### Worker registration / detail additions

- `sessionStatus`
- `sessionProvider`
- `sessionStartedAt`
- `sessionLastUsedAt`
- `sessionFailureReason`
- `sessionResetAvailable`

### Heartbeat additions

- `sessionStatus`
- `sessionHealthy`
- `activeProviderSessionId` or opaque provider-local session token if useful

### Result reporting additions

- `sessionStatusAfterTask`
- `sessionReused`
- `sessionResetRequired`

### Operator action additions

- `reset_worker_session`
- optionally `warm_worker_session`

## Execution Flow

### Pi v1 today

1. pull task
2. spawn provider subprocess
3. wait for completion
4. report result
5. discard provider process

### Pi v2

1. pull task
2. ensure provider session exists and is healthy
3. bind task execution to existing session
4. stream heartbeats with both worker and session health
5. report result with session reuse metadata
6. retain or reset session based on policy

## Failure and Recovery Semantics

Pi v2 should make failure more specific, not more magical.

### Failure classes

- worker process failure
- session bootstrap failure
- session corruption or invalidation
- task execution failure
- auth failure

### Recovery rules

- worker process failure: existing Phase 4 interruption behavior remains; retry or reroute
- session bootstrap failure: worker remains alive but session becomes `failed`; operator can reset or reroute work
- session corruption: mark session failed, block reuse, expose reset action
- auth failure: keep current provider readiness/auth surfaces as authority

### What Pi v2 does not promise initially

- resuming an in-flight provider conversation after worker death
- migrating a live session between workers
- pooled-session failover

## Operator Surfaces

The operator console should show session state as part of worker usability, not as hidden backend detail.

### Worker dashboard additions

- session status badge
- session age / last-used timestamp
- explicit reset control
- distinction between worker unhealthy and session unhealthy

### Queue/dispatch implications

- deferred reason may become `session_reset_required`
- interrupted work remains retryable, but session-local failures can recommend reset on the same worker before reroute

### Runtime truth additions

- operator actions should include session resets
- materialized task attempts may include whether the session was reused

## Migration Plan

Recommended migration steps:

1. add session state to worker schemas and registry projections
2. introduce worker-local session manager abstraction in Pi
3. keep the existing task/report loop, but route execution through the session manager
4. add operator-visible session reset controls
5. extend runtime materialization with session reuse/reset metadata

This keeps the migration incremental and reversible.

## Risks

### Risk: hidden context contamination

Mitigation:

- keep attack-plan framing mandatory
- add reset controls
- add reuse budgets and stale-session policy

### Risk: provider asymmetry

Mitigation:

- use one shared worker/session abstraction
- allow provider-specific session managers beneath it

### Risk: operator confusion

Mitigation:

- keep worker state and session state separate in the UI
- never collapse session failure into generic worker death

## Non-Goals

This design does not include:

- session pools
- cross-worker session migration
- run-scoped leased sessions
- cloud-hosted worker/session infrastructure

## Recommendation

If the team pursues Pi v2, this should be the starting implementation target:

**persistent worker-local provider sessions with explicit session state, reset controls, and conservative protocol extensions layered on top of the existing permanent-worker-loop architecture**

That keeps Pi v2 ambitious enough to matter, but narrow enough not to destabilize the system that Phases 1 through 4 just made usable.
