# Orchestration Next Phases Roadmap

> Strategic roadmap for the post-PR-37 work needed to turn the permanent-worker-loop foundation into a genuinely usable end-to-end system for real Claude and Codex workers.

## Goal

Define the next implementation phases after PR #37 so the system reaches a provider-complete local milestone:

- real Claude workers can authenticate, receive work, execute runs, and report results
- real Codex workers can authenticate, receive work, execute runs, and report results
- Helaicopter acts as a usable operator console rather than a passive dashboard
- the system passes meaningful end-to-end smoke scenarios across bootstrap, dispatch, execution, and recovery

## What PR #37 Already Established

PR #37 landed the permanent-worker-loop foundation:

- background resolver loop in the backend
- worker registry and worker state surfaces
- dispatch plumbing and queue visibility
- auth credential models and management surfaces
- graph-native runtime integration
- operator UI foundations for orchestration visibility
- Pi v1 as the initial long-lived worker shape

That is enough to prove the architecture direction. It is not yet enough to call the system genuinely usable end to end for real provider-backed workers.

## Milestone Definition

The target milestone is provider completeness, not just infrastructure completeness.

A provider-complete milestone means:

- both Claude and Codex can be exercised through real workers, not just mocked adapters
- an operator can bootstrap the system from a cold start without relying on hidden setup knowledge
- run state is materialized clearly enough that the operator can understand what happened during and after execution
- auth and provider failures are surfaced as actionable operator states
- a small set of real smoke scenarios can prove the system works end to end

## Recommended Phase Ordering

### Phase 1: Bootstrap and Operator Viability

**Tracks advanced:** bootstrap/operator flow, Pi worker usability, protocol refinement

**Goal:** Make the system operable from a clean local setup without tribal knowledge.

**Why first:** If the operator cannot reliably start the backend, register workers, understand readiness, and see why dispatch is blocked, every later phase stays hard to validate.

**Deliverables:**

- a canonical backend plus resolver plus Pi worker bootstrap flow
- deterministic worker registration and liveness behavior
- operator-visible readiness states for workers, auth, and dispatch eligibility
- clear UI states for idle, blocked, unhealthy, and active execution
- first-run documentation and recovery instructions

**Dependencies:** none beyond PR #37

**Exit criteria:**

- a fresh local checkout can reach one healthy Claude worker and one healthy Codex worker
- the operator can distinguish no work, no eligible worker, auth blocked, and active dispatch
- the operator can recover from common startup failures without reading internal code

**Key risks and questions:**

- how much bootstrap complexity still leaks from backend internals into operator flow
- whether Pi worker startup still assumes too much manual context
- whether current protocol fields are sufficient for explaining blocked dispatch

### Phase 2: Run Ingestion and Runtime Truth

**Tracks advanced:** run ingestion/materialization, protocol refinement, end-to-end smoke scenarios

**Goal:** Make run state durable, inspectable, and authoritative enough for real operation.

**Why second:** Provider-complete execution is much harder to validate if live state, attempts, mutations, and outputs are not materialized into a coherent operator-facing truth model.

**Deliverables:**

- explicit mapping from runtime events to persisted and operator-visible state
- authoritative views for runs, tasks, attempts, worker claims, and artifacts
- durable provenance for graph mutations and retry history
- reload and restart behavior that preserves operator understanding of run history
- backend and UI contracts that consistently surface live versus persisted state

**Dependencies:** Phase 1

**Exit criteria:**

- an operator can inspect a run from queueing through completion using stable runtime surfaces
- restart or refresh does not make the system state ambiguous
- smoke scenarios can assert on materialized runtime truth rather than implementation-specific internals

**Key risks and questions:**

- whether file-backed runtime state and SQLite-backed operator state have any unresolved authority overlap
- whether current event and attempt models are rich enough for postmortem inspection
- whether protocol simplification is needed before adding more provider-specific behavior

### Phase 3: Provider-Complete Real Execution

**Tracks advanced:** real auth/provider validation, Pi worker usability, protocol refinement

**Goal:** Make both Claude and Codex genuinely runnable through the real system with actionable auth and routing behavior.

**Why third:** Once operator flow and runtime truth are solid, the next constraint is no longer architecture but real provider execution and failure handling.

**Deliverables:**

- real credential validation and health reporting for Claude and Codex
- provider-aware dispatch gating based on capability and auth readiness
- clear handling for expired CLI sessions, invalid credentials, capability mismatch, and provider routing failures
- Pi worker ergonomics improvements required for repeated real-world operation
- operator-facing remediation guidance for auth and provider problems

**Dependencies:** Phases 1 and 2

**Exit criteria:**

- one real Claude-backed run can complete successfully
- one real Codex-backed run can complete successfully
- provider and auth failures are surfaced explicitly and do not fail silently
- Pi workers are usable enough for repeated local operation without bespoke manual patching

**Key risks and questions:**

- whether delegated local CLI auth is robust enough for both providers in repeated runs
- whether Claude and Codex need materially different worker capability modeling
- whether any provider mismatch logic belongs in dispatch rules versus worker registration metadata

### Phase 4: End-to-End Operational Confidence

**Tracks advanced:** end-to-end smoke scenarios, plus coverage across all previous tracks

**Goal:** Prove the full system is actually usable with realistic flows and recovery cases.

**Why fourth:** End-to-end confidence should validate a real system, not substitute for unfinished design. By this point the core operator, runtime, and provider pieces should exist.

**Deliverables:**

- a compact acceptance suite of real end-to-end smoke scenarios
- happy-path scenarios for Claude and Codex
- failure and recovery scenarios for auth expiry, worker loss, retry, reroute, pause, and resume
- operator-control scenarios that exercise manual intervention paths
- a release-style definition of "usable end to end"

**Dependencies:** Phases 1 through 3

**Exit criteria:**

- the core smoke scenarios pass consistently for both providers
- operator interventions can be exercised during real runs
- the team can judge readiness based on acceptance evidence rather than architectural intuition

**Key risks and questions:**

- how much of the smoke suite can be automated versus manually supervised
- which scenarios are truly critical path versus desirable but non-blocking
- whether provider-specific flakiness needs separate quarantine handling

### Phase 5: Pi v2 and Persistent-Session Roadmap

**Tracks advanced:** Pi v2 / persistent-session roadmap

**Goal:** Separate what is necessary for a usable Pi v1 system from what belongs in the next architecture wave.

**Why fifth:** Pi v2 should be informed by the operational pain discovered in real provider-complete usage, not guessed too early and allowed to disrupt the critical path.

**Deliverables:**

- explicit Pi v1 limits and accepted tradeoffs
- a problem statement for Pi v2
- a persistent-session roadmap with clear motivations and migration seams
- a deferred backlog separated from the provider-complete milestone

**Dependencies:** operational evidence from Phases 1 through 4

**Exit criteria:**

- the team can clearly say what is intentionally deferred from v1
- the v2 roadmap is concrete enough to guide later design
- no v2-only work remains accidentally embedded in the v1 critical path

**Key risks and questions:**

- whether current Pi v1 subprocess spawning imposes unacceptable latency or fragility
- whether persistent sessions are needed for correctness, ergonomics, or both
- whether protocol changes required for v2 should be designed now or deferred until evidence accumulates

## Cross-Cutting Guidance

### Provider completeness beats polish

The roadmap should prioritize getting both Claude and Codex working reliably through the same operator-facing system before broader UX or platform expansion work.

### Protocol refinement should be justified

Protocol changes should happen only when they unblock:

- operator understanding
- materialized runtime truth
- provider-aware dispatch
- real smoke coverage

Avoid refinement that is merely aesthetic or speculative.

### Pi v2 stays off the critical path unless evidence forces it on

Pi v1 should be treated as the default path to a usable system. Pi v2 should only move earlier if analysis shows Pi v1 cannot realistically support the provider-complete milestone.

## Minimal Acceptance Scenarios

The roadmap should define at least these acceptance scenarios:

1. Cold start to healthy system
   Backend starts, resolver loop runs, Claude and Codex workers register, operator UI shows healthy state.

2. Claude happy-path run
   A real Claude-capable worker accepts a task, completes it, and the run is materialized clearly in Helaicopter.

3. Codex happy-path run
   A real Codex-capable worker accepts a task, completes it, and the run is materialized clearly in Helaicopter.

4. Auth failure visibility
   An expired or invalid provider auth state prevents dispatch and produces a clear operator-visible remediation path.

5. Worker interruption and recovery
   A worker disappears mid-run, the system reflects the interruption, and retry or reroute behavior is understandable and testable.

6. Operator intervention
   The operator pauses, resumes, retries, or reroutes a run and the resulting state is visible and durable.

## Critical Path Summary

The likely critical path is:

1. make bootstrap and operator flow deterministic
2. make runtime state materialized and authoritative
3. make Claude and Codex real auth plus dispatch behavior trustworthy
4. prove end-to-end usability with smoke scenarios
5. use the resulting evidence to define Pi v2 cleanly

## Prompt for the Next LLM Session

```text
Given PR #37, what are the next implementation phases required to turn the permanent-worker-loop foundation into a genuinely usable end-to-end system for real Claude/Codex workers?

Treat PR #37 as foundational infrastructure already landed, not as the finished product. I want a strategic roadmap, not code changes.

Primary milestone:
A provider-complete local system where real Claude and Codex workers can authenticate, pick up work, execute runs, report status into Helaicopter, and pass meaningful end-to-end smoke scenarios through the full operator flow.

Please organize the answer as implementation phases rather than just a flat gap list. For each phase, include:
- goal
- why it comes in this order
- which of the roadmap tracks it advances
- concrete deliverables
- dependencies on prior phases
- exit criteria / what must be true before moving on
- key risks or unresolved design questions

Please reason explicitly across these tracks:
- bootstrap/operator flow
- run ingestion/materialization
- real auth/provider validation
- Pi worker usability
- end-to-end smoke scenarios
- protocol refinement
- Pi v2 / persistent-session roadmap

Additional guidance:
- Optimize for reaching provider completeness for both Claude and Codex before broader polish.
- Distinguish clearly between what is required for a genuinely usable Pi v1 system and what should be deferred to Pi v2.
- Call out where protocol refinement is actually necessary versus nice-to-have cleanup.
- Include the minimal acceptance/smoke scenarios that would prove the system is end-to-end usable.
- Assume Helaicopter is the operator console and PR #37 already introduced the basic resolver loop, worker registry, auth surfaces, dispatch plumbing, and operator UI foundation.
- End with a recommended phase ordering and a short critical-path summary.
```
