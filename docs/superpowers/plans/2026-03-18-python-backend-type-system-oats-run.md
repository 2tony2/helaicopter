# Run: Python Backend Type-System Rollout

This run spec operationalizes `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md` as ten sequential OATS tasks. The master plan is the governing document for architecture, constraints, wave intent, acceptance, and deferred work.

## Tasks

### baseline_foundation
Title: Wave 0-1 Baseline Freeze And Tooling Foundation

Implement Wave 0 and Wave 1 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. Read that plan before editing and treat its target-state architecture, conflict register, decision ledger, dependency graph, acceptance matrix, and final recommendation as authoritative.

Preserve these global constraints from the plan while doing this task: keep Python `>=3.13`, `uv`, and `setuptools`; keep current runtime dependencies stable; do not introduce repo-wide strictness or wide pyright scope yet; do not add new family-local alias helpers; do not add new public raw `dict[str, Any]` payloads; keep `BaseModel` for durable or external boundaries and reserve `TypedDict + TypeAdapter` for transient internal payloads.

The goal of this task is to freeze the current backend contract behavior, record the starting pyright baseline, and establish the first non-blocking backend tooling lane. Work in the files the plan calls out first: `pyproject.toml`, any future CI workflow files, targeted architecture or guardrail tests under `tests/`, and supporting docs if needed. Add the backend dev dependency baseline (`pytest`, `pytest-cov`, `httpx`, `pyright`, `ruff`), commit `[tool.pyright]` in `pyproject.toml` with the narrow initial scope from the plan (`python/helaicopter_api/server`, `python/helaicopter_api/schema`, `python/helaicopter_api/ports`, and `python/oats/models.py`), commit `[tool.ruff]`, and create the non-blocking CI shape where `ruff` and `pytest` are required while pyright is advisory. Capture the initial pyright baseline in a durable repo-visible form and add guardrails so the rollout does not drift while later waves land.

Acceptance criteria:
- documented backend scope exists and the initial pyright baseline is captured
- no new family-local alias helpers are introduced
- no new public raw `dict[str, Any]` payloads are introduced
- the backend dev group includes `pytest`, `pytest-cov`, `httpx`, `pyright`, and `ruff`
- `[tool.pyright]` and `[tool.ruff]` are committed
- CI requires `ruff` and `pytest`
- pyright runs in advisory mode on the initial backend scope

### domain_catalog
Title: Wave 2 Shared Domain Type Catalog
Depends on: baseline_foundation

Implement Wave 2 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`, assuming the baseline/tooling wave already established the narrow type-checking and lint foundation. Re-read the master plan before editing so the domain package matches the intended type hierarchy instead of becoming an ad hoc alias dump.

The objective is to create the minimum shared backend domain package at `python/helaicopter_domain/` and use it to remove duplicated literals and ambiguous primitives across API, DB, and OATS code. Keep this wave intentionally minimal and high-value: centralize repeated provider/status/scope/runtime vocabularies, introduce nominal ID aliases for the important identifiers already reused across the codebase, and split `project_path` into explicit semantics for encoded project key, absolute filesystem path, and display path. Follow the plan's "meaning first" rule with semantic aliases above lower-level validation helpers, but do not over-model speculative concepts that are not yet reused. Update the highest-value consumers in `python/helaicopter_api/schema/*`, `python/helaicopter_api/ports/*`, `python/oats/models.py`, and selected `python/helaicopter_db` modules where the duplication is already real.

Acceptance criteria:
- repeated provider, status, scope, and runtime vocabularies are centralized
- nominal ID aliases exist for high-value identifiers
- `project_path` semantics are split into explicit types
- the new domain package is reused by API, DB, or OATS modules where the duplication previously existed

### internal_shapes
Title: Wave 3 Internal Shapes And Cached Adapters
Depends on: domain_catalog

Implement Wave 3 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. Read the master plan again before editing because this wave depends on the validation-boundary policy and performance guardrails being followed precisely.

Replace the highest-value raw internal dict seams with `TypedDict + TypeAdapter` at ingress, using cached or singleton-style adapters only. Start with the concrete targets named in the plan: `python/helaicopter_api/application/conversations.py`, `python/helaicopter_api/application/plans.py`, `python/helaicopter_api/application/database.py`, `python/helaicopter_db/export_types.py`, `python/helaicopter_db/status.py`, and selected OATS runtime helpers if they have the same transient anonymous-payload problem. Validate once at ingress and transform many times; do not construct adapters inside loops; do not introduce `BaseModel -> model_dump -> model_validate` churn on hot paths; and do not duplicate ownership of the same internal shape across multiple layers without a good reason. Reuse the domain aliases from the prior wave where they carry semantics.

Acceptance criteria:
- the first target payloads are typed at ingress with `TypedDict + TypeAdapter`
- adapters are cached or singleton-style rather than repeatedly constructed
- there is no per-loop adapter construction in the targeted code
- the initial pyright scope is materially cleaner than before this wave

### boundary_models
Title: Wave 4 Boundary Ownership And Public Payload Cleanup
Depends on: internal_shapes

Implement Wave 4 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. Re-read the master plan and keep its schema-boundary policy intact while you work.

Make boundary ownership explicit across the backend. `python/helaicopter_api/schema/` must remain HTTP-only request and response models; `python/helaicopter_api/ports/` must remain integration or store DTOs and protocols only; and `python/oats/models.py` must stay the durable local artifact contract instead of being pulled into transient internal parsing. Remove inappropriate public or cross-layer `dict` usage by replacing or wrapping opaque payloads with named models where the contract is externally visible or durable. Where conversation payloads are public and polymorphic, introduce discriminated unions if that is the correct fit. Preserve legacy snake_case conversation and analytics HTTP surfaces for now, because the plan explicitly defers that migration instead of blessing it permanently.

Acceptance criteria:
- `schema/` is HTTP-only and `ports/` is integration or store DTO only
- public opaque dict payloads are replaced or wrapped with explicit contracts
- conversation polymorphism uses discriminated unions where appropriate
- there is no new shared cross-layer "god model"

### function_contracts
Title: Wave 5 Strict Function Contracts On Service Boundaries
Depends on: boundary_models

Implement Wave 5 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. This wave should only happen after ingress typing and boundary cleanup are in place, so rely on the previous waves rather than trying to compensate for unfinished typing with permissive decorators.

Add strict `@validate_call(config=ConfigDict(strict=True), validate_return=True)` only to exported application or service boundaries that now have sufficiently typed inputs and outputs. Focus on `python/helaicopter_api/application/*.py`, selected orchestration service entry points, and any `python/oats/runner.py` entrypoints that the plan calls out as exported boundaries. Do not decorate routers, Typer commands, tiny helpers, hot loops, or `Any`-heavy parser utilities. If a candidate function is still too dynamic to benefit from a strict boundary contract, improve its typing first or skip it for now rather than applying a performative decorator.

Acceptance criteria:
- exported service functions use strict `validate_call(..., validate_return=True)` where inputs and outputs are typed enough to benefit
- routers, tiny helpers, parsers, and hot loops remain undecorated
- this wave does not broaden validation into `Any`-heavy code paths that still need ingress typing work

### settings_configuration
Title: Wave 6 Canonical Backend Settings Contract
Depends on: function_contracts

Implement Wave 6 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. Re-read the config strategy in the master plan first, because the important constraint here is order: settings cleanup happens after boundary and payload work, not before.

Converge backend runtime settings under one canonical `BaseSettings` tree rooted in `python/helaicopter_api/server/config.py`, keeping the `HELA_` prefix and keeping OATS repo config separate. Introduce nested settings sections only where they clarify ownership. Remove the implicit `Settings()` fallback from `python/helaicopter_api/bootstrap/services.py` in this wave, not earlier. Migrate `python/helaicopter_db/settings.py` plus the Alembic and DB tooling entry points onto the shared backend settings contract. Watch carefully for environment-loading regressions in refresh flows, local DB tooling, and migration entry points.

Acceptance criteria:
- one backend settings entry point exists for API and DB tooling
- nested settings sections are introduced where they improve clarity
- `build_services` no longer silently creates `Settings()`
- DB tooling reads from the shared backend settings contract
- OATS repo config remains separate from backend runtime settings

### serialization_alignment
Title: Wave 7 Serialization And Contract Alignment
Depends on: settings_configuration

Implement Wave 7 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. Re-read the alias and serialization strategy section before making changes, because this wave needs to standardize behavior without breaking the intentionally deferred legacy surfaces.

Centralize alias and casing behavior in shared HTTP schema utilities and remove the family-local `_to_camel` helpers from the schema families the plan names: database, evaluations, orchestration, and subscriptions. Keep internal Python naming in `snake_case` while making external `camelCase` behavior explicit at the HTTP boundary. Do not rely on blanket `populate_by_name=True`; alias acceptance and `extra` behavior should be explicit per request or query model. Add or update route/OpenAPI and casing-focused contract tests so accidental serialization drift is caught. Legacy conversation and analytics HTTP families remain deferred and should be documented as such rather than silently changed.

Acceptance criteria:
- family-local `_to_camel` helpers are removed from the targeted HTTP schema families
- shared HTTP base utilities centralize alias behavior
- alias acceptance and `extra` policy are explicit where they matter
- casing-focused contract tests and OpenAPI fragment assertions exist
- legacy snake_case families are explicitly documented as deferred

### performance_refinements
Title: Wave 8 Validation Overhead And Hot-Path Cleanup
Depends on: serialization_alignment

Implement Wave 8 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. This wave only makes sense after explicit validation boundaries exist, so keep the prior waves intact and optimize within that structure rather than bypassing it.

Audit the hot paths identified in the master plan and remove avoidable validation overhead. Prioritize `python/helaicopter_api/adapters/app_sqlite/store.py`, `python/helaicopter_api/application/conversations.py`, `python/helaicopter_api/application/plans.py`, `python/helaicopter_api/pure/analytics.py`, and `python/helaicopter_api/adapters/oats_artifacts/store.py`. Remove repeated adapter construction inside loops, reduce avoidable `model_dump` or `model_validate` churn, and introduce trusted fast paths only when an explicit earlier validation boundary exists and tests cover the assumption. Do not trade correctness for speed by smuggling unchecked payloads across boundaries.

Acceptance criteria:
- there is no repeated adapter creation in loops on the targeted hot paths
- avoidable `model_dump` and `model_validate` churn is reduced on hot paths
- any trusted fast paths are covered by tests and sit behind explicit validation boundaries

### legacy_cleanup
Title: Wave 9 Compatibility Debt Cleanup
Depends on: performance_refinements

Implement Wave 9 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. Re-read the deferred decisions and conflict register before editing so this wave removes only the temporary debt created by the rollout instead of reopening settled architecture choices.

Retire compatibility debt that remains after the new architecture is in place. Focus on the areas the plan names: legacy field migration zones in `python/oats/models.py`, `python/helaicopter_db/settings.py`, status or runtime naming surfaces, and deprecated helper paths. Remove or sharply minimize temporary shims, but keep the explicit architectural decisions intact: `python/oats/models.py` remains the durable artifact contract for this program, and the deferred legacy snake_case HTTP surfaces stay deferred unless a versioned migration is intentionally introduced. Do not add new compatibility shims without review.

Acceptance criteria:
- architectural debt items introduced during the rollout are removed or explicitly documented with end dates
- legacy naming shims are minimized
- no new compatibility shims are introduced without clear review justification

### ci_hardening
Title: Wave 10 Required Enforcement And Regression Guards
Depends on: legacy_cleanup

Implement Wave 10 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-18-python-backend-type-system-master-plan.md`. This is the enforcement wave that turns the earlier architecture work into a durable gate, so verify the current scoped backlog is actually green before you make pyright required.

Harden CI and architecture tests so the target state becomes enforceable rather than aspirational. Keep `ruff` and `pytest` required, and make pyright required for the agreed backend scope from the master plan only after that scope is green. Add or refine targeted architecture tests covering schema rejection, alias serialization behavior, and config parsing or rejection. Make sure the repo has a clear next-step schedule for later pyright expansion to tests and `python/helaicopter_db`, but do not expand the required scope yet if the agreed green base is not clean.

Acceptance criteria:
- `ruff` and `pytest` remain required in CI
- pyright is required for the agreed backend scope and that scope is green
- architecture tests cover schema rejection, alias serialization, and config parsing or rejection
- later pyright expansion to tests and `helaicopter_db` is explicitly scheduled from a green base

Validation override:
- npm run lint
- uv run --group dev pytest -q
- uv run --group dev pyright
