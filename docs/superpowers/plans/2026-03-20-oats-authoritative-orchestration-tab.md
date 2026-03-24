# OATS Authoritative Orchestration Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the orchestration tab read authoritative persisted OATS orchestration facts instead of legacy file-merged run artifacts, while improving status reconciliation with legacy orchestration.

**Architecture:** Replace the `/orchestration/oats` list builder with a SQLite fact-table reader over persisted orchestration runs and task attempts. Reconstruct the existing frontend run shape from those facts, filter known sample/example noise, and overlay legacy orchestration flow-run state when it sharpens active run status.

**Tech Stack:** FastAPI, SQLite/SQLAlchemy, existing OATS/legacy orchestration schemas, Next.js, SWR, pytest

---

### Task 1: Backend authoritative run-list test

**Files:**
- Modify: `tests/test_api_orchestration.py`

- [ ] Add a failing endpoint test proving `/orchestration/oats` reads persisted `fact_orchestration_runs` and `fact_orchestration_task_attempts`, excludes `sample_run.md`, and returns reconstructed task status.
- [ ] Run the focused test and confirm it fails for the current file-backed implementation.

### Task 2: Backend run-list cutover

**Files:**
- Modify: `python/helaicopter_api/application/orchestration.py`
- Modify: `python/helaicopter_api/router/orchestration.py`

- [ ] Implement a persisted-facts reader for the orchestration run list.
- [ ] Reconstruct run/task/DAG payloads from facts and filter sample/example noise.
- [ ] Overlay legacy orchestration flow-run state for matching persisted legacy orchestration runs.
- [ ] Run focused backend tests and confirm green.

### Task 3: Frontend contract verification

**Files:**
- Modify: `src/components/orchestration/overnight-oats-panel.tsx` only if the new source reveals contract assumptions
- Modify: `src/lib/client/normalize.test.ts` only if normalization expectations change

- [ ] Verify the existing panel works against the authoritative API shape.
- [ ] Tighten any tests or small UI assumptions exposed by the cutover.

### Task 4: End-to-end verification

**Files:**
- None required unless test fixes surface additional gaps

- [ ] Run orchestration API tests and any touched frontend tests.
- [ ] Hit the local endpoint or app path to confirm real runs are visible again and sample runs are gone.
