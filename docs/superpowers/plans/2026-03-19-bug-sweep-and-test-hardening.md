# T010 Bug Sweep And Test Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identify and fix regressions from the platform API/orchestration refresh and harden brittle areas with targeted tests.

**Architecture:** Lean changes. Start from failing tests to find root causes, apply minimal, localized fixes, and add regression tests before code changes. Avoid refactors unless necessary to fix defects.

**Tech Stack:** Python (FastAPI/SQLAlchemy likely), Pytest; Node/TypeScript (frontend), ESLint.

---

### Task 1: Establish Baseline

**Files:**
- Read-only across repo

- [ ] Run: `PYTHONPATH=python /Users/tony/Code/helaicopter/.venv/bin/pytest -q`
- [ ] Run: `env npm_config_cache=.cache/npm npm run lint`
- [ ] Capture failures and errors

### Task 2: Triage Failures

- [ ] Group by root cause (code bug vs brittle test vs fixture/env)
- [ ] Pick highest-impact failures first

### Task 3: Add/Strengthen Tests (TDD)

- [ ] Write failing test reproducing each defect
- [ ] Verify RED: each test fails for the right reason

### Task 4: Fix Defects Minimally

- [ ] Apply smallest code change to pass failing test
- [ ] Prefer local fixes over refactors

### Task 5: Verify and Iterate

- [ ] Re-run full suite until green
- [ ] Run linter and fix any violations related to changes

### Task 6: Document Risks

- [ ] Note remaining flaky areas or tech debt for follow-up

