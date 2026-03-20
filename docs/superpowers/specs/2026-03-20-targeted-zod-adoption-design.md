# Targeted Zod Adoption Design

## Executive Summary

This change introduces Zod as a narrowly scoped runtime-validation layer for the TypeScript frontend in Helaicopter. The goal is to harden the client boundary where backend JSON, form payloads, query strings, and client environment values are currently accepted through TypeScript-only types and permissive normalization logic. The backend will continue to use FastAPI and Pydantic as its runtime-validation system.

The work is intentionally incremental. Helaicopter already has a large compatibility layer in `src/lib/client/normalize.ts` that accepts both legacy and current response shapes while deriving UI-facing models. Replacing that file wholesale would create unnecessary risk. The design therefore introduces Zod at the raw boundary first, then migrates high-value endpoints one slice at a time.

## Goals

- Add a direct `zod` dependency to the frontend toolchain.
- Validate raw frontend API responses before they reach UI-facing model code.
- Validate mutation payloads, selected form state, query-string state, and client env inputs on the TypeScript side.
- Reduce silent fallback behavior where malformed payloads currently degrade into empty UI state.
- Preserve the current backend validation architecture based on FastAPI, Pydantic, and generated OpenAPI artifacts.

## Non-Goals

- Replacing Pydantic or adding Zod to Python code.
- Converting every TypeScript interface in one pass.
- Eliminating all normalization and view-model mapping logic from `src/lib/client/normalize.ts`.
- Solving end-to-end schema sharing between Python and TypeScript in this iteration.
- Rewriting stable backend request-body/query validation that is already enforced by FastAPI schemas.

## Current State

### Frontend boundary behavior

- `src/lib/client/fetcher.ts` reads JSON and returns `body as T` unless a custom normalizer is supplied.
- `src/lib/client/normalize.ts` is a large compatibility shim that:
  - accepts `unknown`
  - converts non-objects to `{}` and non-arrays to `[]`
  - coerces strings, numbers, and booleans with default fallbacks
  - mixes raw validation, compatibility handling, and UI-facing transformations
- Components and mutations perform some local validation, but the rules are distributed and incomplete.

### Backend boundary behavior

- FastAPI request models, query models, and settings are already validated with Pydantic.
- The repo already publishes OpenAPI artifacts for backend contracts.
- Some backend provider/file-ingestion surfaces could use stricter validation, but they should remain Pydantic-based.

## Design Decisions

### 1. Use Zod only on the TypeScript side

Zod becomes a frontend/runtime helper, not a new cross-language schema authority. Python validation remains in Pydantic. This keeps each runtime on its native validation stack and avoids forcing a JavaScript library into backend code paths.

### 2. Parse raw data first, then normalize to view models

The new boundary pattern is:

1. fetch JSON
2. parse it with a Zod schema for the raw payload contract
3. map the validated result into the existing UI-facing model shape

This preserves useful derived fields and presentation-focused mapping while removing today’s permissive `unknown` coercion at the network edge.

### 3. Migrate high-value surfaces before large conversation schemas

The first rollout targets smaller, higher-signal boundaries:

- client env and route/query parsing
- evaluation prompt payloads
- conversation evaluation payloads
- subscription settings
- database status

Large conversation payloads are in scope, but only after the helper pattern and tests are established. That reduces churn in the most complex contract surface.

### 4. Keep compatibility explicit during migration

Some frontend code still tolerates multiple payload shapes during the FastAPI transition. Zod should not hide that complexity. If a surface must accept both legacy and current shapes, the schema should express that explicitly through unions or preprocess/transform steps rather than silent fallback defaults.

### 5. Prefer fail-loud behavior at the boundary

Malformed backend payloads should surface as explicit client errors, test failures, or logged diagnostics instead of empty tables, missing evaluations, or zeroed counters. This change optimizes for correctness and debuggability over permissive rendering.

## File And Boundary Changes

### New frontend schema layer

Add focused schema modules under `src/lib/client/schemas/` for:

- shared primitives and helpers
- environment/config parsing
- route/query parsing where needed
- evaluation prompt shapes
- conversation evaluation shapes
- subscription settings
- database status
- selected conversation/conversation-summary payloads after the initial rollout

### Fetch and normalization updates

- `src/lib/client/fetcher.ts` gains a schema-aware API that parses JSON before returning it.
- Existing normalizers become mapping functions over validated input instead of ad hoc validators.
- `src/hooks/use-conversations.ts` and `src/hooks/use-plans.ts` switch call-sites to the schema-aware fetch helpers.

### Form and mutation updates

- `src/lib/client/mutations.ts` validates outgoing payloads before sending them.
- `src/components/evaluations/prompt-manager.tsx` and `src/components/conversation/evaluation-dialog.tsx` reuse shared schemas or schema-derived helper functions instead of duplicating trim/required-field logic.

### Route/env updates

- `src/lib/client/endpoints.ts` validates `NEXT_PUBLIC_API_BASE_URL`.
- `src/lib/routes.ts` validates or constrains `prefectPath`, tab values, and related query state using explicit schemas or schema-driven allowlists.

## Testing Strategy

- Add unit tests for raw Zod schemas and schema-aware fetch helpers.
- Preserve existing normalization tests where view-model transformations still matter.
- Add targeted tests for invalid payload rejection, not just valid payload acceptance.
- Keep migration steps small enough that existing node-based frontend tests remain easy to run locally.

## Risks And Mitigations

### Risk: schema duplication drifts from backend contracts

Mitigation: keep the rollout narrow, prefer the OpenAPI artifact as the backend source of truth, and avoid translating every backend schema at once.

### Risk: over-migrating `normalize.ts`

Mitigation: split boundary parsing from view-model mapping first. Do not require one mega-refactor.

### Risk: mixed legacy/current payload shapes create verbose schemas

Mitigation: prioritize endpoints with already-stable shapes first, and use explicit unions only where compatibility is still required.

### Risk: rollout breaks existing UI paths

Mitigation: migrate endpoint families one at a time with targeted tests and preserve existing UI-facing model contracts unless a separate UI refactor is justified.

## Success Criteria

- `zod` is a direct dependency in the frontend workspace.
- At least the initial high-value frontend boundaries are validated with Zod before reaching UI-facing code.
- Invalid payloads on migrated surfaces fail explicitly in tests instead of silently defaulting.
- Backend Pydantic validation remains unchanged as the authoritative Python-side mechanism.
- `src/lib/client/normalize.ts` has less responsibility for raw `unknown` validation on migrated endpoints.

## Rollout Status

Completed in this rollout:

- shared frontend schema helpers in `src/lib/client/schemas/shared.ts`
- schema-aware fetch helpers in `src/lib/client/fetcher.ts`
- validated client env and route/query parsing in `src/lib/client/endpoints.ts` and `src/lib/routes.ts`
- validated evaluation prompt, conversation evaluation, subscription, and database-status payloads
- shared evaluation-form parsing helpers reused by `prompt-manager.tsx` and `evaluation-dialog.tsx`
- validated `ConversationSummary[]` reads before normalization in `useConversations`

Still deferred after this rollout:

- full conversation detail payload validation
- `ConversationDagSummary[]` migration
- export-script validation and any OpenAPI-driven schema generation follow-up

## Deferred Follow-Up

- Evaluate whether frontend schema generation from OpenAPI is worth pursuing after the targeted rollout proves out.
- Consider stricter Pydantic parsing for selected backend provider/file-ingestion surfaces in a separate Python-focused effort.
- The next frontend migration slice should be full conversation detail, because it is the largest remaining read path still relying on permissive `unknown` normalization.
