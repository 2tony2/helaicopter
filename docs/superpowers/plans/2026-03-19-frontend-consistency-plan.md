# T006 Frontend Consistency Audit & Cleanup — Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Standardize page headers, breadcrumbs, and optional width constraints; normalize page spacing; refactor out duplicated markup.

**Architecture:** Add tiny layout primitives (`Container`, `PageHeader`, `Breadcrumbs`), then refactor pages to consume them with minimal churn. Preserve existing UI primitives (cards, tabs, buttons).

**Tech Stack:** Next.js App Router, React/TypeScript, Tailwind v4, shadcn/ui-derived components.

---

### Task 1: Add `Container`

**Files:**
- Create: `src/components/layout/container.tsx`

- [x] Implement `Container` with `size` variants (md, lg, xl, 2xl, full) and optional padding.

### Task 2: Add `PageHeader`

**Files:**
- Create: `src/components/layout/page-header.tsx`

- [x] Title + optional description + optional actions, flex layout, shared typography.

### Task 3: Add `Breadcrumbs`

**Files:**
- Create: `src/components/layout/breadcrumbs.tsx`

- [x] Render items with chevrons; link when `href` provided; last item styled as current.

### Task 4: Refactor Analytics page

**Files:**
- Modify: `src/app/page.tsx`

- [x] Replace inline header with `PageHeader`; keep actions (date range, provider) in the actions slot; normalize outer spacing to `space-y-8`.

### Task 5: Refactor Conversations index

**Files:**
- Modify: `src/app/conversations/page.tsx`

- [x] Use `PageHeader`; normalize spacing.

### Task 6: Refactor Plans index

**Files:**
- Modify: `src/app/plans/page.tsx`

- [x] Use `PageHeader`; normalize spacing.

### Task 7: Refactor Prompts page

**Files:**
- Modify: `src/app/prompts/page.tsx`

- [x] Use `PageHeader`; normalize spacing and keep long description constrained.

### Task 8: Refactor Orchestration hub

**Files:**
- Modify: `src/components/orchestration/orchestration-hub.tsx`

- [x] Use `PageHeader`; normalize spacing.

### Task 9: Standardize breadcrumbs in details views

**Files:**
- Modify: `src/app/plans/[slug]/page.tsx`
- Modify: `src/app/conversations/[projectPath]/[sessionId]/page.tsx`

- [x] Replace ad‑hoc nav with `Breadcrumbs`.

### Task 10: Align Schema page with global shell

**Files:**
- Modify: `src/app/schema/page.tsx`

- [x] Replace nested `<main>`/gradient with `PageHeader`; use `Container` and `Card` to render artifact links; keep regenerate block as a `Card`.

### Task 11: Lint + tests

- [x] Run `npm run lint` (should pass)
- [x] Run targeted node tests provided by task (should pass)

