# Targeted Zod Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Zod as an incremental runtime-validation layer on the TypeScript frontend boundary without changing the backend’s Pydantic-based validation model.

**Architecture:** Introduce small schema modules under `src/lib/client/schemas/`, add schema-aware fetch helpers, then migrate a few high-value endpoint families from permissive `unknown` normalization to explicit parsing plus view-model mapping. Keep large conversation payload migration separate until the helper pattern is proven on smaller surfaces.

**Tech Stack:** Next.js App Router, React 19, TypeScript 5, SWR, Node test runner, FastAPI/OpenAPI backend contracts, Zod.

---

### Task 1: Add Zod and establish frontend schema conventions

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`
- Create: `src/lib/client/schemas/shared.ts`
- Create: `src/lib/client/schemas/shared.test.ts`

- [x] **Step 1: Add the direct dependency**
  Run: `npm install zod`
  Expected: `package.json` and `package-lock.json` record a direct `zod` dependency rather than relying on the transitive dev-only copy.

- [x] **Step 2: Create shared schema helpers**
  Add `src/lib/client/schemas/shared.ts` with focused primitives:
  - `nonEmptyTrimmedString`
  - `optionalTrimmedString`
  - `isoDateString`
  - `urlString`
  - enum helpers for provider/tab-style values where appropriate
  Keep this file small and reusable.

- [x] **Step 3: Write the helper tests first**
  Add `src/lib/client/schemas/shared.test.ts` covering:
  - trimming behavior
  - empty-string rejection for required strings
  - optional-string normalization to `undefined` or `null` where intended
  - invalid URL/date rejection for helpers that promise those constraints

- [x] **Step 4: Run the targeted tests**
  Run: `node --test src/lib/client/schemas/shared.test.ts`
  Expected: PASS

- [x] **Step 5: Commit**
  Run:
  ```bash
  git add package.json package-lock.json src/lib/client/schemas/shared.ts src/lib/client/schemas/shared.test.ts
  git commit -m "feat: add shared frontend zod schema helpers"
  ```

### Task 2: Add a schema-aware fetch boundary

**Files:**
- Modify: `src/lib/client/fetcher.ts`
- Create: `src/lib/client/fetcher.test.ts`

- [x] **Step 1: Write failing tests for schema-aware fetch behavior**
  Cover:
  - valid JSON parsed through a schema returns typed data
  - invalid JSON shape throws a descriptive validation error
  - non-OK responses still surface backend error messages
  - legacy no-schema call-sites continue working during migration

- [x] **Step 2: Add a schema-aware API**
  Extend `requestJson` with a Zod-aware path, for example:
  ```ts
  requestJson(url, init, schema)
  requestJson(url, init, parseFn)
  ```
  or add a parallel helper such as `requestJsonWithSchema`.
  Choose the shape that minimizes churn at existing call-sites.

- [x] **Step 3: Keep the boundary explicit**
  Ensure schema parsing happens immediately after `res.json()` and before any view-model normalization. Do not hide validation inside downstream component logic.

- [x] **Step 4: Surface useful validation failures**
  Format thrown validation errors so they are actionable in tests and visible in local debugging. Avoid dumping unreadable raw Zod internals if a concise summary is possible.

- [x] **Step 5: Explicitly defer plan hooks**
  Leave `src/hooks/use-plans.ts` on the legacy fetch path for this rollout unless one of the selected small payload families requires it. Record that defer in a code comment or rollout note so the omission is deliberate rather than accidental.

- [x] **Step 6: Run the targeted fetcher tests**
  Run: `node --test src/lib/client/fetcher.test.ts`
  Expected: PASS

- [x] **Step 7: Commit**
  Run:
  ```bash
  git add src/lib/client/fetcher.ts src/lib/client/fetcher.test.ts
  git commit -m "feat: add schema-aware client fetch helpers"
  ```

### Task 3: Validate client env and route/query inputs

**Files:**
- Create: `src/lib/client/schemas/runtime.ts`
- Modify: `src/lib/client/endpoints.ts`
- Modify: `src/lib/routes.ts`
- Modify: `src/lib/client/normalize.test.ts`
- Modify: `src/lib/routes.test.ts`

- [x] **Step 1: Write failing route/env tests**
  Add tests for:
  - invalid `NEXT_PUBLIC_API_BASE_URL`
  - valid absolute base URL normalization
  - invalid `legacy-orchestrationPath` rejection or safe fallback
  - unsupported tab values resolving predictably
  Put base-URL coverage in `src/lib/client/normalize.test.ts` alongside the existing endpoint/base-URL assertions, and keep route-state coverage in `src/lib/routes.test.ts`.

- [x] **Step 2: Implement runtime/env schema parsing**
  In `src/lib/client/schemas/runtime.ts`, define schemas for:
  - API base URL
  - legacy orchestration path
  - conversation detail tabs
  - orchestration tabs

- [x] **Step 3: Update endpoint and route helpers**
  Refactor `src/lib/client/endpoints.ts` and `src/lib/routes.ts` to consume those schemas rather than open-coded string trimming and cast-based narrowing.

- [x] **Step 4: Preserve current UX where deliberate**
  Keep the existing default-tab behavior and local-dev origin inference unless a test proves the behavior is unsafe or inconsistent with the design.

- [x] **Step 5: Run route/env tests**
  Run: `node --test src/lib/routes.test.ts`
  Expected: PASS

- [x] **Step 6: Commit**
  Run:
  ```bash
  git add src/lib/client/schemas/runtime.ts src/lib/client/endpoints.ts src/lib/routes.ts src/lib/client/normalize.test.ts src/lib/routes.test.ts
  git commit -m "feat: validate client runtime and route inputs"
  ```

### Task 4: Migrate small, high-value payloads first

**Files:**
- Create: `src/lib/client/schemas/evaluations.ts`
- Create: `src/lib/client/schemas/subscriptions.ts`
- Create: `src/lib/client/schemas/database.ts`
- Modify: `src/lib/client/mutations.ts`
- Modify: `src/hooks/use-conversations.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`

- [x] **Step 1: Write failing tests for raw payload parsing**
  Cover these families independently:
  - evaluation prompts
  - conversation evaluations
  - subscription settings
  - database status
  Include at least one invalid-payload case per family that currently would have fallen back silently.

- [x] **Step 2: Define raw schemas**
  Add Zod schemas for the backend payload shapes those families actually return today. Where the backend still emits multiple accepted shapes, model them explicitly with unions or transforms.

- [x] **Step 3: Refactor normalization into mapping**
  Update the relevant `normalize*` functions so they accept validated input and remain responsible only for:
  - camel/snake compatibility where still required
  - UI-facing derived fields
  - compatibility-preserving output structure
  Remove raw `unknown` coercion from the migrated branches.

- [x] **Step 4: Update hooks and mutations**
  Switch the affected `useSWR` hooks and mutation helpers to call the schema-aware fetch boundary with the new schemas before mapping.

- [x] **Step 5: Validate outgoing mutation payloads**
  Reuse the same module family to validate outgoing evaluation prompt writes, conversation evaluation creation, and subscription setting updates before `fetch`.

- [x] **Step 6: Run targeted tests**
  Run:
  ```bash
  node --test src/lib/client/normalize.test.ts
  node --test src/lib/client/mutations.test.ts
  ```
  Expected: PASS

- [x] **Step 7: Commit**
  Run:
  ```bash
  git add src/lib/client/schemas/evaluations.ts src/lib/client/schemas/subscriptions.ts src/lib/client/schemas/database.ts src/lib/client/mutations.ts src/hooks/use-conversations.ts src/lib/client/normalize.ts src/lib/client/normalize.test.ts
  git commit -m "feat: validate high-value frontend payloads with zod"
  ```

### Task 5: Apply shared schemas to evaluation UI forms

**Files:**
- Modify: `src/components/evaluations/prompt-manager.tsx`
- Modify: `src/components/conversation/evaluation-dialog.tsx`
- Modify: `src/lib/client/schemas/evaluations.ts`
- Create: `src/lib/client/schemas/evaluations-form.test.ts`

- [x] **Step 1: Write failing tests for form-state parsing helpers**
  Cover:
  - trimmed prompt name and prompt text
  - blank required field rejection
  - guided-subset selection instruction requirement
  - prompt-id versus custom-prompt rules

- [x] **Step 2: Extract reusable parsing helpers**
  Put schema-backed helpers in `src/lib/client/schemas/evaluations.ts` for:
  - prompt write input
  - conversation evaluation create input
  Keep component code focused on UI state and error presentation.

- [x] **Step 3: Update the forms to use shared validation**
  Replace duplicated trim/required checks and `as EvaluationScope`-style assumptions where practical. Keep component behavior stable from a user perspective.

- [x] **Step 4: Run targeted tests**
  Run:
  ```bash
  node --test src/lib/client/schemas/evaluations-form.test.ts
  node --test src/lib/client/mutations.test.ts
  ```
  Expected: PASS

- [x] **Step 5: Commit**
  Run:
  ```bash
  git add src/components/evaluations/prompt-manager.tsx src/components/conversation/evaluation-dialog.tsx src/lib/client/schemas/evaluations.ts src/lib/client/schemas/evaluations-form.test.ts
  git commit -m "feat: share zod-backed validation across evaluation forms"
  ```

### Task 6: Migrate one conversation-family read path

**Files:**
- Create: `src/lib/client/schemas/conversations.ts`
- Modify: `src/hooks/use-conversations.ts`
- Modify: `src/lib/client/normalize.ts`
- Modify: `src/lib/client/normalize.test.ts`
- Test: `src/lib/client/normalize.test.ts`

- [x] **Step 1: Choose the smallest conversation-family surface**
  Start with `ConversationSummary[]`, not full conversation detail. Only fall back to `ConversationDagSummary[]` if the summaries route exposes an unresolved compatibility issue. The task is to prove the pattern on a medium-complexity payload without destabilizing the largest response shape.

- [x] **Step 2: Write failing schema tests**
  Include:
  - valid summary payload acceptance
  - invalid enum/string/number fields rejection
  - explicit handling for any still-supported legacy field aliases

- [x] **Step 3: Implement the raw schema and hook integration**
  Add raw payload schemas and wire the relevant hook to parse through Zod before normalization.

- [x] **Step 4: Reduce `unknown` handling in the migrated path**
  Remove the migrated path’s dependence on generic helpers like `asRecord` and `numberOr` wherever the raw schema already guarantees shape.

- [x] **Step 5: Run targeted tests**
  Run: `node --test src/lib/client/normalize.test.ts`
  Expected: PASS

- [x] **Step 6: Commit**
  Run:
  ```bash
  git add src/lib/client/schemas/conversations.ts src/hooks/use-conversations.ts src/lib/client/normalize.ts src/lib/client/normalize.test.ts
  git commit -m "feat: validate conversation summary payloads with zod"
  ```

### Task 7: Verify, document, and decide next migration slice

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-03-20-targeted-zod-adoption-design.md`
- Modify: `docs/superpowers/plans/2026-03-20-targeted-zod-adoption.md`

- [x] **Step 1: Run the full targeted verification set**
  Run:
  ```bash
  npm run lint
  node --test src/lib/client/normalize.test.ts
  node --test src/lib/client/mutations.test.ts
  node --test src/lib/client/legacy-orchestration-normalize.test.ts
  node --test src/lib/routes.test.ts
  node --test src/lib/client/fetcher.test.ts
  node --test src/lib/client/schemas/shared.test.ts
  node --test src/lib/client/schemas/evaluations-form.test.ts
  ```
  Expected: PASS

  Result: PASS after aligning `src/lib/client/legacy-orchestration-normalize.test.ts` with the repo’s dynamic-import test harness pattern used by the other direct `node --test` files.

- [x] **Step 2: Update developer docs**
  Add a short note to `README.md` or an equivalent frontend-dev section describing:
  - Zod’s role on the frontend
  - the parse-then-map pattern
  - the fact that backend contracts still live in FastAPI/Pydantic

- [x] **Step 3: Record rollout status**
  Update the design and plan docs with the completed migration slice and explicitly call out the next deferred target, likely full conversation detail or export-script validation.

- [x] **Step 4: Commit**
  Run:
  ```bash
  git add README.md docs/superpowers/specs/2026-03-20-targeted-zod-adoption-design.md docs/superpowers/plans/2026-03-20-targeted-zod-adoption.md
  git commit -m "docs: record targeted zod adoption rollout"
  ```

## Completed Rollout Summary

- Task 1 commit: `ee6ad4a`
- Task 2 commit: `1fd4892`
- Task 3 commit: `8d7a8b1`
- Task 4 commit: `374338b`
- Task 5 commit: `4f6c4f1`
- Task 6 commit: `aae9d4c`

## Next Deferred Slice

The next recommended migration target is full conversation detail. It is now the most valuable remaining read path that still relies heavily on permissive `unknown` normalization, and the smaller-summary migration established the parse-then-map pattern without forcing the much larger detail payload into this rollout.
