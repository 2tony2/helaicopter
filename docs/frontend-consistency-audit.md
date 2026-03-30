# Frontend Consistency Audit (2026-03-19)

Scope: Next.js app under `src/app/*` and shared UI primitives under `src/components/ui/*` and layout under `src/components/layout/*`.

## Key Findings

- Page headers repeated inline with inconsistent spacing (`space-y-6` vs `space-y-8`) and mixed title/description markup.
- Schema page (`src/app/schema/page.tsx`) used its own `<main>` wrapper, gradient background, and ad‑hoc rounded cards inconsistent with the rest of the app shell.
- Breadcrumb patterns duplicated with slightly different styles across detail views (plan details and conversation details).
- Layout width constraints were ad‑hoc (`max-w-4xl` etc.) rather than a shared primitive; most pages were full-width while some constrained content locally.
- Tabs, cards, and buttons were already standardized via `src/components/ui/*` and generally consistent; no changes needed.
- Sidebar navigation patterns were consistent enough; no structural change required.

## Goals

- Introduce light-weight layout primitives to standardize page headers, breadcrumbs, and optional width constraints.
- Normalize page-level vertical rhythm to `space-y-8`.
- Make Schema page follow the same shell and card patterns as the rest of the app.

## Implemented Changes (Summary)

- Added `Container`, `PageHeader`, and `Breadcrumbs` primitives under `src/components/layout/`.
- Refactored pages to use the primitives and normalized spacing:
  - `src/app/page.tsx` (Analytics) → `PageHeader` + consistent actions area.
  - `src/app/conversations/page.tsx` → `PageHeader` and `space-y-8`.
  - `src/app/plans/page.tsx` → `PageHeader` and `space-y-8`.
  - `src/app/prompts/page.tsx` → `PageHeader` and `space-y-8`.
  - `src/app/plans/[slug]/page.tsx` and `src/app/conversations/[projectPath]/[sessionId]/page.tsx` → standardized `Breadcrumbs`.
  - `src/app/schema/page.tsx` → replaced custom `<main>`+gradient with `PageHeader` + `Container` + `Card`.

## Rationale

- `PageHeader` unifies title/description typography and aligns optional action controls for a predictable top area across all pages.
- `Breadcrumbs` removes duplicated nav markup and ensures consistent iconography/spacing.
- `Container` provides an opt‑in max‑width constraint for content that benefits from readable measure without changing the global shell.
- Normalized `space-y-8` delivers consistent vertical rhythm page‑to‑page.

## Next Opportunities (non-blocking)

- Pull repeated analytics grid gap sizes into a small `Grid` utility or presets.
- Introduce a dedicated `Page` wrapper that composes `Container` + `PageHeader` for even less repetition.
- Add storybook or visual tests for `layout` primitives.
- Consider a design tokens file for spacing scale aliases if needs evolve beyond Tailwind defaults.
