# Pi V2 Persistent-Session Roadmap Design

**Date:** 2026-03-26  
**Status:** Draft  
**Builds on:** `docs/superpowers/specs/2026-03-26-permanent-worker-loop-architecture-design.md`, `docs/superpowers/specs/2026-03-26-orchestration-next-phases-roadmap.md`  
**Context:** Phase 5 of the orchestration roadmap

## Executive Summary

Pi v1 is now good enough to support a provider-complete local orchestration system: real Claude and Codex workers can register, authenticate, pick up work, report runtime truth, surface operator actions, and recover from common failures. That means Pi v2 should not be treated as hidden critical-path work.

Pi v2 exists to solve the next layer of problems: execution continuity, session reuse, startup overhead, operator ergonomics, and richer recovery semantics. The core question is no longer "can Helaicopter orchestrate real workers?" but "when is the supervisor-style Pi v1 model too costly or fragile compared to a persistent-session worker?"

This document sets the boundary:

- Pi v1 is the shippable system for the current milestone.
- Pi v2 is a deliberate follow-on architecture wave.
- Persistent sessions should only move back onto the critical path if Pi v1 proves insufficient for correctness or reliability, not merely because Pi v2 is more elegant.

## What Pi V1 Now Proves

Pi v1 currently means:

- a long-lived worker process registers with the control plane
- the worker pulls a task envelope from the resolver loop
- each task is executed by spawning a fresh provider subprocess or CLI invocation
- results, attempts, dispatch history, graph mutations, and operator actions are materialized into operator-facing runtime truth
- interruption, auth blockage, retry, reroute, and pause/resume are visible enough for local operation

After Phases 1 through 4, Pi v1 is no longer just scaffolding. It supports the provider-complete acceptance bar:

- cold start to healthy system
- Claude happy-path execution
- Codex happy-path execution
- auth failure visibility
- worker interruption and recovery
- operator intervention visibility

That matters because it changes the burden of proof. Pi v2 does not need to justify the architecture direction; it needs to justify the migration cost.

## Pi V1 Ceiling

These are the accepted tradeoffs for Pi v1.

### Acceptable for v1

- Fresh subprocess per task. This is slower than persistent sessions but keeps state isolation simple.
- Repeated provider startup cost. Claude and Codex CLIs may need to re-bootstrap auth/session state per task.
- Limited continuity across tasks. Context has to be reconstructed from the task envelope and runtime artifacts rather than preserved in-memory by the worker.
- Recovery via re-dispatch, not session repair. If a worker dies, the system retries or reroutes the task rather than attempting to resume an in-flight provider session.
- Local-single-operator optimization. Pi v1 is tuned for one developer running a small number of workers, not for a large fleet or shared pool.

### Not acceptable even for v1

- Silent loss of task state
- unclear authority between control-plane and worker state
- hidden auth/session prerequisites
- inability to understand why work is blocked
- inability to recover from worker interruption with a clear operator path

The difference is important: Pi v1 may be less ergonomic than a persistent-session system, but it still has to be trustworthy.

## Why Pi V2 Exists

Pi v2 should be driven by observed pain, not by architectural aspiration alone.

### Problem 1: Repeated startup overhead

Pi v1 pays provider startup cost on every task. That cost may be acceptable for short local runs, but it becomes more painful when:

- tasks are very small and frequent
- operators run many retries or reroutes
- provider CLIs do expensive session or auth initialization

### Problem 2: Weak continuity across related tasks

Pi v1 reconstructs task context each time from artifacts and attack plans. That is reliable, but it loses advantages a persistent worker might provide:

- conversational continuity
- warm repository context
- fewer repeated setup prompts
- better throughput on multi-step work assigned to the same worker

### Problem 3: Limited recovery semantics

Pi v1 handles interruption well enough at the scheduler level, but only coarsely:

- kill and retry
- reroute to another worker
- surface operator guidance

What it cannot do well is repair or resume a partially live provider session.

### Problem 4: Operator friction

Persistent sessions could make Pi feel more like a durable tool and less like a supervisor shell:

- better mental model of "this worker has an active Claude/Codex session"
- clearer reuse of provider-local auth/session state
- less repeated setup burden

### Problem 5: Provider-specific execution mismatches

Claude and Codex may diverge over time in how much they benefit from session persistence, local state reuse, or warm caches. Pi v2 may be where those differences need to become explicit instead of hidden behind a single subprocess-launch model.

## What Should Force Pi V2 Back Onto The Critical Path

Persistent sessions should move earlier only if one of these becomes true:

1. Pi v1 cannot satisfy correctness requirements.
   Example: provider subprocess churn causes state loss or makes completion reporting unreliable.

2. Pi v1 cannot satisfy reliability requirements.
   Example: repeated auth/session bootstrap fails often enough that end-to-end runs are not dependable.

3. Pi v1 blocks essential operator workflows.
   Example: recovery or reroute becomes too slow or too opaque for real local usage.

4. Pi v1 creates provider asymmetry that breaks the provider-complete goal.
   Example: Codex is usable only with warm persistent sessions while Claude remains fine without them.

If the problem is merely speed or elegance, that is not enough by itself to move Pi v2 ahead of the deferred roadmap.

## Architecture Options For Pi V2

There are three realistic shapes.

### Option A: Session-per-worker

Each registered Pi worker owns one persistent provider session at a time. Tasks dispatched to that worker reuse that session until the worker is recycled.

**Pros**

- closest to today’s worker-registry model
- easiest migration path from Pi v1
- preserves current control-plane assumptions
- gives strong session continuity for related tasks assigned to the same worker

**Cons**

- worker replacement may still discard useful context
- one worker may become "special" due to sticky session state
- session reset rules become an important operator concern

**Assessment**

This is the recommended first Pi v2 shape because it upgrades continuity without forcing a redesign of the worker registry or resolver loop.

### Option B: Session-per-run

Persistent provider sessions are scoped to a run rather than to a worker. Workers attach to run sessions as needed.

**Pros**

- aligns well with run-level continuity
- reduces accidental cross-run context bleed

**Cons**

- much more complicated attachment model
- weaker fit for the current worker registry
- raises harder ownership questions around session leasing and recovery

**Assessment**

This is attractive conceptually, but it is probably too large a jump for the first Pi v2 wave.

### Option C: Session pool with task handoff

Persistent provider sessions live in a shared pool and can be assigned or reassigned across tasks and workers.

**Pros**

- potentially best utilization
- most flexible routing and reuse

**Cons**

- highest complexity by far
- creates new state authority and coordination problems
- difficult to keep operator-facing behavior understandable

**Assessment**

This should be considered future-looking research, not the first Pi v2 milestone.

## Recommended Pi V2 Direction

Recommend **session-per-worker** as the first Pi v2 step.

The migration logic is straightforward:

- keep the permanent resolver loop
- keep the worker registry and provider-readiness model
- keep the materialized runtime truth model
- replace "spawn a fresh provider subprocess per task" with "bind tasks to a persistent worker-local provider session"

That lets Pi v2 improve continuity and performance without destabilizing the existing control plane.

## Required Design Questions For Pi V2

These should be answered before implementation starts.

### 1. Session lifecycle

- When is a persistent session created?
- When is it rotated or destroyed?
- What makes a session unhealthy?

### 2. Context boundary

- What state is allowed to persist across tasks?
- How do we prevent unwanted cross-task or cross-run contamination?

### 3. Worker/session identity

- Is the session identity operator-visible?
- Does a worker always have exactly one active session per provider?

### 4. Recovery model

- Can interrupted work resume on the same session?
- If a worker process dies, is the session recoverable or lost?

### 5. Provider asymmetry

- Should Claude and Codex share the same persistent-session abstraction?
- Where do provider-specific lifecycle rules live?

### 6. Protocol impact

- Which fields must be added to execution envelopes, result reporting, and worker status?
- Which current protocol fields remain valid unchanged?

## Expected Protocol Changes

Pi v2 should be conservative about protocol churn, but some changes are likely.

### Likely additions

- persistent `sessionId` or `providerSessionId` on worker/runtime surfaces
- explicit worker session health state
- session reset / recycle operator action
- richer interruption distinction:
  session lost vs worker lost vs task failed

### Likely to remain stable

- run/task identity
- provider-aware dispatch gating
- task attempt materialization
- operator action projection
- queue/deferred reason model

The goal is to evolve the execution layer without invalidating the Phase 1 through 4 operator surfaces.

## Migration Seams

The current architecture already has good seams for Pi v2.

### Stable seams we should preserve

- `worker_registry` remains the control-plane authority for worker presence and lifecycle
- runtime materialization remains the operator-facing truth layer
- execution envelopes remain the task handoff contract
- dispatch monitor remains the explanation layer for blocked or deferred work

### Where Pi v2 should plug in

- Pi worker execution backend
- worker-local provider/session manager
- richer worker heartbeat/status reporting

That means Pi v2 should mostly replace internals behind the existing worker boundary, not rewrite the resolver loop from scratch.

## Deferred Backlog

These items belong to the Pi v2 backlog, not the current provider-complete milestone.

- persistent provider sessions
- session recycling policies
- session reset and repair controls
- provider-specific warm-session optimization
- richer session-aware routing heuristics
- session pool experiments
- metrics comparing subprocess-per-task vs persistent-session throughput and failure rate

## Decision Summary

- Pi v1 is the completed and acceptable architecture for the current milestone.
- Pi v2 is justified by continuity, ergonomics, and throughput, not by missing correctness in the shipped system unless evidence later proves otherwise.
- The recommended first Pi v2 shape is **session-per-worker**.
- Pi v2 should reuse the existing worker registry, resolver loop, and runtime materialization model rather than replacing them.
- No Pi v2 work should be treated as hidden critical-path implementation for the current local provider-complete system.

## Next Step

When the team is ready to pursue Pi v2, the next artifact should be a focused implementation-oriented spec for:

`persistent worker-local provider sessions with explicit lifecycle, health, and reset semantics`

That future spec should include:

- worker/session state machine
- protocol deltas
- migration steps from Pi v1
- operator controls
- failure and recovery semantics
