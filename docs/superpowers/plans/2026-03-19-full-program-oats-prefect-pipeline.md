# Full Program OATS Prefect Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full-program Prefect-backed OATS run spec for the authoritative-analytics program, validate that OATS can load and plan it, and attempt to start execution.

**Architecture:** Reuse the existing markdown-first OATS model and Prefect runtime instead of inventing a new pipeline layer. The implementation adds one new run spec, extends loader-level test coverage to pin its structure, and validates both `oats plan` and the Prefect execution entrypoint from the isolated worktree.

**Tech Stack:** Python 3.13, OATS markdown run specs, Prefect-backed OATS CLI, pytest.

---

## File Structure Map

### Existing files to modify

- `tests/oats/test_run_definition_loader.py`

### New files to create

- `examples/full_program_authoritative_analytics_overnight_run.md`

## Task 1: Add Loader Coverage For The New Overnight Run Spec

**Files:**
- Modify: `tests/oats/test_run_definition_loader.py`
- Test: `tests/oats/test_run_definition_loader.py`

- [ ] **Step 1: Write the failing test**

Add a new test that loads `examples/full_program_authoritative_analytics_overnight_run.md` and asserts:
- the title matches the new run
- the task ids cover the phased full-program groups
- key dependencies enforce semantic foundation before later phases
- task validation overrides are preserved for at least one task

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --group dev pytest -q tests/oats/test_run_definition_loader.py -k full_program`
Expected: FAIL because the new markdown run spec does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Keep the test focused on run-definition loading semantics only. Do not change parser or loader code unless the new spec reveals a real incompatibility.

- [ ] **Step 4: Run test to verify it still fails for the expected reason**

Run: `uv run --group dev pytest -q tests/oats/test_run_definition_loader.py -k full_program`
Expected: FAIL with missing-file or load failure tied to the absent run spec.

- [ ] **Step 5: Commit**

```bash
git add tests/oats/test_run_definition_loader.py
git commit -m "test: add loader coverage for full-program oats run"
```

## Task 2: Author The Full-Program Prefect OATS Run Spec

**Files:**
- Create: `examples/full_program_authoritative_analytics_overnight_run.md`
- Modify: `tests/oats/test_run_definition_loader.py`
- Test: `tests/oats/test_run_definition_loader.py`

- [ ] **Step 1: Write the run spec**

Create `examples/full_program_authoritative_analytics_overnight_run.md` with bounded phased tasks for:
- semantic foundation
- Python-native ingestion
- operational store migration
- warehouse authority cutover
- orchestration analytics
- frontend simplification
- near-real-time polish and final cutover

Use explicit dependencies, acceptance criteria, notes, and validation overrides modeled after `examples/prefect_native_oats_orchestration_run.md`.

- [ ] **Step 2: Run the focused loader test**

Run: `uv run --group dev pytest -q tests/oats/test_run_definition_loader.py -k full_program`
Expected: PASS

- [ ] **Step 3: Run the whole loader test file**

Run: `uv run --group dev pytest -q tests/oats/test_run_definition_loader.py`
Expected: PASS

- [ ] **Step 4: Verify OATS can plan the new run**

Run: `uv run oats plan examples/full_program_authoritative_analytics_overnight_run.md`
Expected: a valid task DAG with the new phased tasks and no parser/loader errors.

- [ ] **Step 5: Commit**

```bash
git add examples/full_program_authoritative_analytics_overnight_run.md tests/oats/test_run_definition_loader.py
git commit -m "feat: add full-program authoritative analytics oats run"
```

## Task 3: Attempt Prefect-Backed Execution

**Files:**
- Modify: `examples/full_program_authoritative_analytics_overnight_run.md` (only if execution reveals fixable run-spec issues)

- [ ] **Step 1: Deploy the run through the Prefect entrypoint**

Run: `uv run oats prefect deploy examples/full_program_authoritative_analytics_overnight_run.md`
Expected: deployment is created or updated successfully.

- [ ] **Step 2: Start execution**

Run: `uv run oats prefect run examples/full_program_authoritative_analytics_overnight_run.md`
Expected: a Prefect flow run is created successfully.

- [ ] **Step 3: Capture outcome**

If execution succeeds:
- record the run identifier and immediate status from CLI output

If execution fails:
- preserve the exact failure
- fix only run-spec issues revealed by the failure
- do not start changing Prefect runtime code in this task unless the failure proves the current runtime cannot accept a valid markdown run spec

- [ ] **Step 4: Re-run targeted validation if the spec changed**

Run: `uv run --group dev pytest -q tests/oats/test_run_definition_loader.py`
Run: `uv run oats plan examples/full_program_authoritative_analytics_overnight_run.md`
Expected: PASS before retrying execution.

- [ ] **Step 5: Commit**

```bash
git add examples/full_program_authoritative_analytics_overnight_run.md
git commit -m "chore: finalize full-program oats pipeline execution"
```
