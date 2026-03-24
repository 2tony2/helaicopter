# ty Cutover And CI Reliability Design

## Executive Summary

This change replaces `pyright` with Astral `ty` as the only required Python type checker in Helaicopter and hardens the repository's Python quality workflow around deterministic, diagnosable CI behavior. The target enforcement scope widens from the current narrow backend subset to all `python/**` sources, while `tests/**` remain outside required type checking for this migration.

The work is not just a tool swap. The repository currently has green `pytest` coverage but failing static-quality lanes caused by drift between the codebase and the configured quality tooling. A successful cutover therefore needs three coordinated outcomes:

- move all repository contracts, docs, tests, and CI steps from `pyright` to `ty`
- widen required type checking to all Python source files under `python/`
- fix the existing static-analysis blockers so the new required workflow is green locally and in CI

## Goals

- Make `ty` the only required Python type checker in local development and CI.
- Enforce required type checking over all `python/**` sources.
- Keep `ruff`, `pytest`, and `ty` as separate required CI lanes for clear failure diagnosis.
- Make the workflow more reliable by using deterministic `uv`-managed environments and explicit commands.
- Update repository guardrails so future changes cannot silently reintroduce `pyright` assumptions.

## Non-Goals

- Adding `tests/**` to required type checking in this migration.
- Expanding quality enforcement beyond the existing Python toolchain.
- Refactoring unrelated application behavior while fixing type-checking drift.
- Running a dual-tool transition period with both `pyright` and `ty`.

## Current State

### Tooling

- `pyproject.toml` currently declares `pyright` in the `dev` dependency group.
- `pyproject.toml` also contains a strict `[tool.pyright]` configuration with a narrow include list:
  - `python/helaicopter_api/server`
  - `python/helaicopter_api/schema`
  - `python/helaicopter_api/ports`
  - `python/oats/models.py`
- `.github/workflows/backend-quality.yml` currently runs separate `ruff`, `pytest`, and `pyright` jobs.

### Reproduced quality state

Local reproduction before the migration shows:

- `uv run --group dev pytest -q` passes.
- `uv run --group dev ruff check python tests` fails on unused imports and an undefined type name.
- `uv run --group dev pyright` fails on an unknown-type issue in the legacy orchestration port models.
- `uvx ty check` over the current backend subset fails on a different but manageable set of diagnostics, primarily FastAPI middleware typing and stale suppression comments.

This indicates the CI failures are currently driven by static-quality lanes rather than runtime test regressions.

## Design Decisions

### 1. Hard cutover to `ty`

The repository will not keep a temporary `pyright` lane. `pyright` will be removed from:

- dev dependencies
- repo guardrail tests
- baseline documentation
- CI workflow steps
- any repository messaging that still describes `pyright` as required

`ty` becomes the single source of truth for required Python type checking.

### 2. Required type-check scope is all `python/**`

The required `ty` scope for this migration is all source files under `python/`. This widens enforcement meaningfully without immediately pulling `tests/**` into the backlog. The repository will continue to rely on `pytest` for test correctness while leaving test type checking as future work.

### 3. CI keeps distinct quality lanes

The Python quality workflow remains split into separate jobs for:

- `ruff`
- `pytest`
- `ty`

This keeps failure diagnosis straightforward. A single combined job would reduce duplicate setup but would make the user's current "CI is failing" complaint harder to localize from GitHub output.

### 4. Reliability beats minimal diff

The workflow update will optimize for repeatable behavior and clear debugging, not merely the smallest textual change. That includes:

- explicit `uv sync --group dev`
- explicit tool invocations from the synced environment
- clear job naming around the three required lanes
- path triggers and guardrail tests aligned to the `ty` enforcement model

### 5. Fix current blockers as part of the migration

The repository cannot land a clean `ty` cutover by configuration changes alone. The migration includes the small code cleanup necessary to make the real commands pass. Expected classes of fixes are:

- remove unused imports reported by `ruff`
- restore or import missing names so source files are internally coherent
- tighten dataclass field typing where `pyright` and `ty` infer unknowns
- remove stale `type: ignore` comments
- adjust FastAPI middleware wiring so `ty` accepts the application setup

These fixes are in scope because they are direct blockers to the requested cutover.

## File And Contract Changes

### `pyproject.toml`

The project configuration will be updated to:

- replace `pyright` in `dependency-groups.dev` with `ty`
- remove the `[tool.pyright]` section
- add the equivalent `ty` configuration for Python 3.13 and repo-local source resolution
- preserve the existing `ruff` and `pytest` settings

The `ty` configuration must enforce all `python/**` sources while keeping import resolution consistent with the `python/` source root.

### `.github/workflows/backend-quality.yml`

The workflow will be updated to:

- replace the `pyright` job with a `ty` job
- keep `ruff` and `pytest` jobs separate
- run `uv sync --group dev` in each job before invoking the required tool
- update workflow path triggers and messaging so they refer to `ty` rather than `pyright`

### Repository guardrails

Tests and docs that currently encode the `pyright` rollout must be rewritten to encode the new contracts:

- `ty` is required
- required type-check scope is all `python/**`
- `pyright` is no longer part of the repository baseline

Any baseline JSON or documentation tied specifically to historical `pyright` rollout state should either be removed from the required contract or replaced with `ty`-based equivalents if the repository still needs a persistent baseline artifact.

## Verification Strategy

This migration will use test-first verification where practical for repo-contract behavior:

1. Update or add failing repo-config tests that assert the new `ty` contract and widened scope.
2. Run those tests to confirm the pre-change repository fails against the new expectations.
3. Implement the minimal config, workflow, and code changes to satisfy the new contract.
4. Run the real quality commands that CI depends on:
   - `uv run --group dev pytest -q`
   - `uv run --group dev ruff check python tests`
   - `uv run --group dev ty check python`

The migration is not complete until the real commands pass locally.

## Error Handling And Diagnostics

- If `ty` configuration cannot express the desired source-root behavior cleanly inside `pyproject.toml`, the implementation may introduce a dedicated `ty.toml` only if that is necessary and clearly improves reliability.
- If widening to all `python/**` reveals a large backlog outside the currently reproduced issues, the implementation should fix only the blockers required to achieve a green required lane, not opportunistically refactor unrelated modules.
- If the workflow still fails after local verification, the first investigation target should be environment or runner differences rather than additional speculative code changes.

## Risks And Mitigations

### Risk: `ty` and `pyright` disagree on some diagnostics

Mitigation: treat `ty` as authoritative after cutover and fix the code to satisfy `ty` directly instead of trying to preserve pyright-shaped suppressions.

### Risk: widening to all `python/**` uncovers unexpected backlog

Mitigation: verify the widened command early and keep the migration focused on the failures it actually reports.

### Risk: workflow changes reduce observability

Mitigation: keep the jobs separate and the commands explicit so failures remain localized to one lane.

## Success Criteria

The migration is successful when all of the following are true:

- `pyright` is removed from repository-required tooling and CI.
- `ty` is the only required type checker in docs, tests, config, and workflow.
- `uv run --group dev ty check python` passes locally.
- `uv run --group dev ruff check python tests` passes locally.
- `uv run --group dev pytest -q` passes locally.
- The repository guardrail tests reflect the `ty` contract and pass.

## Deferred Follow-Up

- Evaluate adding `tests/**` to required `ty` checking after the source-tree cutover is stable.
- Consider whether the repository still wants a persisted type-system baseline artifact once the tool transition is complete.
