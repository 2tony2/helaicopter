# Layered Repo Boundaries Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the new layered repo boundaries on one safe, representative slice by migrating the `plans` domain plus the shared frontend primitives it depends on.

**Architecture:** Pilot the new structure on `plans` instead of attempting a repo-wide move. On the frontend, introduce `src/shared`, `src/views`, and `src/features/plans` while keeping temporary compatibility shims at the old import paths for shared primitives. On the backend, introduce `helaicopter_api.contracts.plans` and `helaicopter_api.domain.plans`, keep `schema/plans.py` as a short compatibility wrapper for now, and move plan-specific summarization logic out of the application module.

**Tech Stack:** Next.js App Router, React 19, TypeScript 5, ESLint, node:test-compatible TypeScript files, FastAPI, Pydantic v2, pytest, uv.

---

## Scope Note

This plan intentionally does **not** reorganize every frontend and backend domain. It proves the target boundaries on:

- shared frontend primitives needed by `plans`
- the frontend `plans` pages and conversation-plan embed
- the backend `plans` API and its contract/domain split

Follow-up plans should migrate `conversations`, `analytics`, `databases`, and the remaining generic `src/components/*`, `src/hooks/*`, and `src/lib/*` surfaces after this slice is green.

## File Map

### Create

- `src/shared/ui/badge.tsx`
- `src/shared/ui/button.tsx`
- `src/shared/ui/card.tsx`
- `src/shared/ui/scroll-area.tsx`
- `src/shared/ui/skeleton.tsx`
- `src/shared/layout/breadcrumbs.tsx`
- `src/shared/layout/page-header.tsx`
- `src/views/plans/plans-index-view.tsx`
- `src/views/plans/plan-detail-view.tsx`
- `src/features/plans/components/plan-panel.tsx`
- `src/features/plans/components/plan-viewer.tsx`
- `src/features/plans/hooks/use-plans.ts`
- `docs/architecture/repo-layers.mdx`
- `python/helaicopter_api/contracts/__init__.py`
- `python/helaicopter_api/contracts/plans.py`
- `python/helaicopter_api/domain/__init__.py`
- `python/helaicopter_api/domain/plans.py`
- `tests/test_repo_boundaries.py`

### Modify

- `src/components/ui/badge.tsx`
- `src/components/ui/button.tsx`
- `src/components/ui/card.tsx`
- `src/components/ui/scroll-area.tsx`
- `src/components/ui/skeleton.tsx`
- `src/components/layout/breadcrumbs.tsx`
- `src/components/layout/page-header.tsx`
- `src/components/plans/plan-panel.tsx`
- `src/components/plans/plan-viewer.tsx`
- `src/hooks/use-plans.ts`
- `src/app/plans/page.tsx`
- `src/app/plans/[slug]/page.tsx`
- `src/components/conversation/conversation-viewer.tsx`
- `eslint.config.mjs`
- `python/helaicopter_api/router/plans.py`
- `python/helaicopter_api/application/plans.py`
- `python/helaicopter_api/schema/plans.py`
- `python/helaicopter_api/schema/__init__.py`
- `tests/test_api_plans.py`
- `tests/test_backend_type_system_rollout.py`

### Defer

- `src/lib/types.ts`
- `src/lib/client/*`
- non-`plans` feature folders under `src/components/*`
- non-`plans` backend schema modules under `python/helaicopter_api/schema/*`

Do not pull these into the first slice unless a blocker is proven by tests.

### Compatibility Decision

Use temporary deprecated re-export shims for:

- the moved shared frontend primitives under `src/components/ui/*` and `src/components/layout/*`
- the old `src/components/plans/*` paths
- the old `src/hooks/use-plans.ts` path
- the old `python/helaicopter_api/schema/plans.py` module

That keeps phase 1 small and reversible while making the new ownership boundaries real. Each shim must be explicit, one-line, and marked `@deprecated` so later slices remove them deliberately.

### Task 1: Add repo-boundary guardrail tests first

**Files:**
- Create: `tests/test_repo_boundaries.py`

- [ ] **Step 1: Write the failing repo-structure tests**
  Add **separate** test functions so later `-k` filtering is deterministic:
  - `test_repo_boundaries_shared_layer_paths`
  - `test_repo_boundaries_plans_feature_paths`
  - `test_repo_boundaries_plans_route_shells`
  - `test_repo_boundaries_architecture_note_and_lint`
  - `test_repo_boundaries_backend_plans_layers`

  Encode the intended phase-1 end state:
  - `test_repo_boundaries_shared_layer_paths` checks that `src/shared/ui/{badge,button,card,scroll-area,skeleton}.tsx` and `src/shared/layout/{breadcrumbs,page-header}.tsx` exist
  - `test_repo_boundaries_plans_feature_paths` checks that `src/features/plans/components/{plan-panel,plan-viewer}.tsx` and `src/features/plans/hooks/use-plans.ts` exist
  - `test_repo_boundaries_plans_route_shells` checks that `src/views/plans/plans-index-view.tsx` and `src/views/plans/plan-detail-view.tsx` exist and that the route files are thin
  - `test_repo_boundaries_architecture_note_and_lint` checks for the architecture note and lint guardrails
  - `test_repo_boundaries_backend_plans_layers` checks that `python/helaicopter_api/contracts/plans.py` and `python/helaicopter_api/domain/plans.py` exist
  - plan-specific legacy files are allowed only as deprecated re-export shims and must no longer contain the full implementation bodies

- [ ] **Step 2: Run the new guardrail test to verify it fails**
  Run: `uv run --group dev pytest -q tests/test_repo_boundaries.py`
  Expected: FAIL because the new directories and files do not exist yet.

- [ ] **Step 3: Commit the failing-test baseline**
  Run:
  ```bash
  git add tests/test_repo_boundaries.py
  git commit -m "test: add layered repo boundary guardrails"
  ```

### Task 2: Introduce `src/shared` for the plan slice dependencies

**Files:**
- Create: `src/shared/ui/badge.tsx`
- Create: `src/shared/ui/button.tsx`
- Create: `src/shared/ui/card.tsx`
- Create: `src/shared/ui/scroll-area.tsx`
- Create: `src/shared/ui/skeleton.tsx`
- Create: `src/shared/layout/breadcrumbs.tsx`
- Create: `src/shared/layout/page-header.tsx`
- Modify: `src/components/ui/badge.tsx`
- Modify: `src/components/ui/button.tsx`
- Modify: `src/components/ui/card.tsx`
- Modify: `src/components/ui/scroll-area.tsx`
- Modify: `src/components/ui/skeleton.tsx`
- Modify: `src/components/layout/breadcrumbs.tsx`
- Modify: `src/components/layout/page-header.tsx`

- [ ] **Step 1: Move the shared implementations**
  Copy the actual implementations into `src/shared/*` without changing behavior. Keep filenames stable where possible so diff noise stays low.

- [ ] **Step 2: Replace the old shared paths with short re-export shims**
  Each old file should become a thin wrapper like:
  ```ts
  export * from "@/shared/ui/badge";
  ```
  or
  ```ts
  export * from "@/shared/layout/breadcrumbs";
  ```
  Add a one-line `@deprecated` comment so later slices remove them deliberately.

- [ ] **Step 3: Keep scope tight**
  Do not migrate the entire `src/components/ui` directory in this slice. Only move the primitives the `plans` area already uses.

- [ ] **Step 4: Run lint and the guardrail test**
  Run:
  ```bash
  npm run lint
  uv run --group dev pytest -q tests/test_repo_boundaries.py -k shared_layer_paths
  ```
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add src/shared/ui/badge.tsx src/shared/ui/button.tsx src/shared/ui/card.tsx src/shared/ui/scroll-area.tsx src/shared/ui/skeleton.tsx src/shared/layout/breadcrumbs.tsx src/shared/layout/page-header.tsx src/components/ui/badge.tsx src/components/ui/button.tsx src/components/ui/card.tsx src/components/ui/scroll-area.tsx src/components/ui/skeleton.tsx src/components/layout/breadcrumbs.tsx src/components/layout/page-header.tsx tests/test_repo_boundaries.py
  git commit -m "refactor: introduce shared frontend primitives for plans slice"
  ```

### Task 3: Move `plans` feature code under `src/features/plans`

**Files:**
- Create: `src/features/plans/components/plan-panel.tsx`
- Create: `src/features/plans/components/plan-viewer.tsx`
- Create: `src/features/plans/hooks/use-plans.ts`
- Modify: `src/components/plans/plan-panel.tsx`
- Modify: `src/components/plans/plan-viewer.tsx`
- Modify: `src/hooks/use-plans.ts`
- Modify: `src/components/conversation/conversation-viewer.tsx`

- [ ] **Step 1: Expand the guardrail test for feature ownership**
  In `test_repo_boundaries_plans_feature_paths`, add checks that:
  - the real plan feature implementation lives under `src/features/plans/*`
  - `src/components/plans/plan-panel.tsx` and `src/components/plans/plan-viewer.tsx` are removed or replaced with explicit deprecated re-exports
  - `src/hooks/use-plans.ts` is removed or replaced with an explicit deprecated re-export

- [ ] **Step 2: Run the test to verify it fails**
  Run: `uv run --group dev pytest -q tests/test_repo_boundaries.py -k plans_feature_paths`
  Expected: FAIL because the plan feature still lives in the old folders.

- [ ] **Step 3: Move the implementation**
  Create the new feature-owned files:
  - `src/features/plans/components/plan-panel.tsx`
  - `src/features/plans/components/plan-viewer.tsx`
  - `src/features/plans/hooks/use-plans.ts`

  Update imports inside them to use `@/shared/*` rather than `@/components/*`.

- [ ] **Step 4: Update current consumers**
  Change:
  - `src/components/conversation/conversation-viewer.tsx` to import `PlanPanel` from `@/features/plans/components/plan-panel`
  - do not update the route files yet; that belongs to the `views` task

- [ ] **Step 5: Decide old-path behavior explicitly**
  Keep `src/components/plans/*.tsx` and `src/hooks/use-plans.ts` only as short deprecated re-export shims for this phase:
  ```ts
  export * from "@/features/plans/components/plan-panel";
  ```
  and
  ```ts
  export * from "@/features/plans/hooks/use-plans";
  ```
  This keeps the route-thinning task smaller while making the ownership shift real.

- [ ] **Step 6: Run verification**
  Run:
  ```bash
  npm run lint
  uv run --group dev pytest -q tests/test_repo_boundaries.py -k plans_feature_paths
  ```
  Expected: PASS

- [ ] **Step 7: Commit**
  Run:
  ```bash
  git add src/features/plans/components/plan-panel.tsx src/features/plans/components/plan-viewer.tsx src/features/plans/hooks/use-plans.ts src/components/plans/plan-panel.tsx src/components/plans/plan-viewer.tsx src/hooks/use-plans.ts src/components/conversation/conversation-viewer.tsx tests/test_repo_boundaries.py
  git commit -m "refactor: move plans feature code into feature layer"
  ```

### Task 4: Introduce `src/views/plans` and thin the route files

**Files:**
- Create: `src/views/plans/plans-index-view.tsx`
- Create: `src/views/plans/plan-detail-view.tsx`
- Modify: `src/app/plans/page.tsx`
- Modify: `src/app/plans/[slug]/page.tsx`
- Modify: `tests/test_repo_boundaries.py`

- [ ] **Step 1: Add route-thinning assertions first**
  Update `test_repo_boundaries_plans_route_shells` to inspect:
  - `src/app/plans/page.tsx`
  - `src/app/plans/[slug]/page.tsx`

  Assert that each route file imports from `@/views/plans/...` and does **not** import from `@/components/plans`, `@/features/plans/hooks/use-plans`, or the shared primitives directly other than what a tiny route shell needs.

- [ ] **Step 2: Run the test to verify it fails**
  Run: `uv run --group dev pytest -q tests/test_repo_boundaries.py -k plans_route_shells`
  Expected: FAIL because the route files still contain feature/composition logic.

- [ ] **Step 3: Extract page composition into `views`**
  Create:
  - `src/views/plans/plans-index-view.tsx`
  - `src/views/plans/plan-detail-view.tsx`

  Move the current page UI into those files. Keep route-only concerns in `src/app/plans/*`: params, entrypoint wiring, and rendering the view.

- [ ] **Step 4: Update route files to become thin shells**
  Target shapes:
  ```tsx
  export default function PlansPage() {
    return <PlansIndexView />;
  }
  ```
  and
  ```tsx
  export default function PlanDetailPage({ params }: { params: Promise<{ slug: string }> }) {
    return <PlanDetailView params={params} />;
  }
  ```

- [ ] **Step 5: Run verification**
  Run:
  ```bash
  npm run lint
  uv run --group dev pytest -q tests/test_repo_boundaries.py -k plans_route_shells
  ```
  Expected: PASS

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add src/views/plans/plans-index-view.tsx src/views/plans/plan-detail-view.tsx src/app/plans/page.tsx 'src/app/plans/[slug]/page.tsx' tests/test_repo_boundaries.py
  git commit -m "refactor: thin plans routes through views layer"
  ```

### Task 5: Add the architecture note and frontend lint guardrails

**Files:**
- Create: `docs/architecture/repo-layers.mdx`
- Modify: `eslint.config.mjs`
- Modify: `tests/test_repo_boundaries.py`

- [ ] **Step 1: Add failing assertions for documentation and lint rules**
  Extend `test_repo_boundaries_architecture_note_and_lint` to assert:
  - `docs/architecture/repo-layers.mdx` exists
  - the doc mentions `src/app`, `src/views`, `src/features`, `src/shared`, `router`, `application`, `domain`, `contracts`, `ports`, and `adapters`
  - `eslint.config.mjs` contains `no-restricted-imports` rules that block upward frontend layer imports for the new paths

- [ ] **Step 2: Run the test to verify it fails**
  Run: `uv run --group dev pytest -q tests/test_repo_boundaries.py -k architecture_note_and_lint`
  Expected: FAIL because the architecture note and lint restrictions do not exist yet.

- [ ] **Step 3: Write the architecture note**
  Document:
  - the allowed frontend layers and import directions
  - the allowed backend layers and import directions
  - the phase-1 decision to keep shared/frontend re-export shims temporary
  - the rule that `src/app/*` files stay thin and `router/*` files stay transport-only

- [ ] **Step 4: Add ESLint import restrictions**
  Use ESLint’s built-in `no-restricted-imports` configuration rather than pulling in a new plugin. Configure both:
  - `files` globs such as `src/views/**/*.ts?(x)`, `src/features/**/*.ts?(x)`, and `src/shared/**/*.ts?(x)`
  - alias-based restricted import patterns that match the repo’s actual imports, such as `@/app/*`, `@/views/*`, and `@/features/*`

  Encode at least these restrictions:
  - files under `src/views/**` cannot import from `@/app/*`
  - files under `src/features/**` cannot import from `@/views/*` or `@/app/*`
  - files under `src/shared/**` cannot import from `@/features/*`, `@/views/*`, or `@/app/*`

- [ ] **Step 5: Run verification**
  Run:
  ```bash
  npm run lint
  uv run --group dev pytest -q tests/test_repo_boundaries.py -k architecture_note_and_lint
  ```
  Expected: PASS

- [ ] **Step 6: Commit**
  Run:
  ```bash
  git add docs/architecture/repo-layers.mdx eslint.config.mjs tests/test_repo_boundaries.py
  git commit -m "docs: codify repo layer rules and lint guardrails"
  ```

### Task 6: Split backend `plans` into contracts and domain

**Files:**
- Create: `python/helaicopter_api/contracts/__init__.py`
- Create: `python/helaicopter_api/contracts/plans.py`
- Create: `python/helaicopter_api/domain/__init__.py`
- Create: `python/helaicopter_api/domain/plans.py`
- Modify: `python/helaicopter_api/router/plans.py`
- Modify: `python/helaicopter_api/application/plans.py`
- Modify: `python/helaicopter_api/schema/plans.py`
- Modify: `python/helaicopter_api/schema/__init__.py`
- Modify: `tests/test_api_plans.py`
- Modify: `tests/test_backend_type_system_rollout.py`
- Modify: `tests/test_repo_boundaries.py`

- [ ] **Step 1: Add failing backend assertions first**
  Update tests to require:
  - `PlanDetailResponse`, `PlanSummaryResponse`, and `PlanStepResponse` are defined in `helaicopter_api.contracts.plans`
  - `test_repo_boundaries_backend_plans_layers` is the named repo-boundary check for file-placement assertions
  - plan summarization and step-parsing helpers are imported from `helaicopter_api.domain.plans` rather than living inline in `application/plans.py`
  - `schema/plans.py` remains only as a compatibility re-export layer during phase 1
  - `tests/test_api_plans.py::TestPlansEndpoints::test_list_plans_summarizes_each_claude_plan_once` monkeypatches the moved summarization helper at its new module path
  - `tests/test_backend_type_system_rollout.py::test_wave_two_domain_catalog_exposes_nominal_ids_and_split_project_path_semantics` imports `PlanDetailResponse` from `helaicopter_api.contracts.plans`

- [ ] **Step 2: Run the targeted backend tests to verify they fail**
  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_plans.py::TestPlansEndpoints::test_list_plans_summarizes_each_claude_plan_once tests/test_backend_type_system_rollout.py::test_wave_two_domain_catalog_exposes_nominal_ids_and_split_project_path_semantics tests/test_repo_boundaries.py::test_repo_boundaries_backend_plans_layers
  ```
  Expected: FAIL because `contracts/` and `domain/` do not exist yet.

- [ ] **Step 3: Move the response models into `contracts/plans.py`**
  Copy the Pydantic models from `schema/plans.py` into `contracts/plans.py` without changing field names or defaults.

- [ ] **Step 4: Extract pure plan-domain helpers**
  Create `domain/plans.py` and move the content-derived helpers there, but keep the domain layer contract-free. Define small domain-owned shapes there, for example:
  - a `PlanSummaryParts` dataclass for title/preview/slug
  - a `PlanStepData` dataclass or `TypedDict` for step/status pairs

  Move the content-derived helpers there, including:
  - title/preview summarization
  - markdown/body splitting
  - plan-step extraction and normalization logic that does not require `BackendServices`

  Keep I/O and repository traversal in `application/plans.py`, and have `application/plans.py` map those domain-owned shapes into `PlanSummaryResponse`, `PlanDetailResponse`, and `PlanStepResponse`.

- [ ] **Step 5: Update application and router imports**
  Change `application/plans.py` and `router/plans.py` to import contracts from `helaicopter_api.contracts.plans` and domain helpers from `helaicopter_api.domain.plans`.

- [ ] **Step 6: Keep compatibility explicit**
  Convert `schema/plans.py` into a short compatibility shim:
  ```py
  from helaicopter_api.contracts.plans import PlanDetailResponse, PlanStepResponse, PlanSummaryResponse

  __all__ = ["PlanDetailResponse", "PlanStepResponse", "PlanSummaryResponse"]
  ```
  Update `schema/__init__.py` to re-export from the new source or the shim consistently.

- [ ] **Step 7: Run verification**
  Run:
  ```bash
  uv run --group dev pytest -q tests/test_api_plans.py tests/test_backend_type_system_rollout.py tests/test_repo_boundaries.py
  ```
  Expected: PASS

- [ ] **Step 8: Commit**
  Run:
  ```bash
  git add python/helaicopter_api/contracts/__init__.py python/helaicopter_api/contracts/plans.py python/helaicopter_api/domain/__init__.py python/helaicopter_api/domain/plans.py python/helaicopter_api/router/plans.py python/helaicopter_api/application/plans.py python/helaicopter_api/schema/plans.py python/helaicopter_api/schema/__init__.py tests/test_api_plans.py tests/test_backend_type_system_rollout.py tests/test_repo_boundaries.py
  git commit -m "refactor: split plans contracts and domain boundaries"
  ```

### Task 7: Run full phase-1 verification and remove accidental leaks

**Files:**
- Modify: any files touched above if verification exposes leaks

- [ ] **Step 1: Run the frontend checks**
  Run:
  ```bash
  npm run lint
  npm run build
  ```
  Expected: PASS

- [ ] **Step 2: Run the targeted Python checks**
  Run:
  ```bash
  uv run --group dev ruff check python tests
  uv run --group dev ty check python/helaicopter_api/contracts/plans.py python/helaicopter_api/domain/plans.py python/helaicopter_api/application/plans.py python/helaicopter_api/router/plans.py python/helaicopter_api/schema/plans.py --error-on-warning
  uv run --group dev pytest -q tests/test_repo_boundaries.py tests/test_api_plans.py tests/test_frontend_backend_split.py tests/test_backend_type_system_rollout.py
  ```
  Expected: PASS

- [ ] **Step 3: Fix only phase-1 regressions**
  If failures occur, fix import paths, stale shims, or boundary assertions. Do not widen scope into other domains unless a failing check proves it is required.

- [ ] **Step 4: Verify the final state manually**
  Confirm:
  - `src/app/plans/*` are thin route shells
  - `src/views/plans/*` owns page composition
  - `src/features/plans/*` owns plan-specific UI and data hooks
  - `src/shared/*` owns the shared primitives used by the slice
  - `router/plans.py` is transport-only
  - `application/plans.py` owns service coordination
  - `domain/plans.py` owns content semantics
  - `contracts/plans.py` owns response models

- [ ] **Step 5: Commit the final cleanup**
  Run:
  ```bash
  git add -A
  git commit -m "chore: verify layered repo boundaries phase 1"
  ```

## Handoff Notes

- Do not remove the temporary shared-primitive re-export shims in this phase. That is follow-up cleanup after at least one more domain migrates to `src/shared`.
- Do not migrate `src/lib/types.ts` into `src/entities` or `src/shared/types` during this slice unless a concrete test forces it.
- If the backend `plans` extraction exposes reusable domain helpers needed by `conversations`, note that in a follow-up issue or doc comment, but do not expand the migration.
