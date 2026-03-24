# Run: Mobile Interface Masterplan

## Tasks

### p0_opencloud_backend
Title: Phase 0 — Remove OpenCloud from Python backend
Agent: codex
Model: gpt-5.4

Remove all OpenCloud references from the Python backend: type system, adapter/port modules, bootstrap, config, conversations application logic, and related Python tests.

Covers plan tasks 1–4 from `docs/superpowers/plans/2026-03-24-phase0-opencloud-prefect-removal.md`.

Acceptance criteria:
- `"opencloud"` removed from ProviderIdentifier, ProviderName, ProviderSelection, conversation_refs
- `python/helaicopter_api/adapters/opencloud_sqlite/` directory deleted
- `python/helaicopter_api/ports/opencloud_sqlite.py` deleted
- OpenCloud removed from bootstrap/services.py, server/config.py
- All ~15 OpenCloud functions removed from conversations.py
- `python -m pytest tests/test_semantics.py tests/test_api_conversations.py tests/test_backend_settings.py tests/test_api_bootstrap.py` passes

Validation override:
- uv run --group dev pytest -q tests/test_semantics.py tests/test_api_conversations.py tests/test_backend_settings.py tests/test_api_bootstrap.py

### p0_prefect_backend
Title: Phase 0 — Remove Prefect from Python backend
Agent: codex
Model: gpt-5.4

Delete all Prefect Python modules and remove Prefect from backend wiring and application logic. Delete oats/prefect/ directory, Prefect adapter/port/router/application/schema modules, and all Prefect test files. Remove Prefect from bootstrap, config, router, openapi_artifacts, orchestration.py, gateway.py, database.py, status.py, orchestration_facts.py, vocab.py, and oats/cli.py. Remove prefect dependency from pyproject.toml.

Covers plan tasks 8–10 from `docs/superpowers/plans/2026-03-24-phase0-opencloud-prefect-removal.md`.

Acceptance criteria:
- `python/oats/prefect/` directory deleted
- All Prefect API modules deleted (adapter, port, router, application, schema)
- All `tests/oats/test_prefect_*.py` and `tests/test_api_prefect_orchestration.py` deleted
- Prefect removed from bootstrap/services.py, config.py, router.py, openapi_artifacts.py
- Prefect removed from orchestration.py, gateway.py, database.py, status.py, orchestration_facts.py, vocab.py, cli.py
- `prefect` dependency removed from pyproject.toml
- `python -c "from helaicopter_api.server.main import create_app; print('OK')"` succeeds
- `python -m pytest tests/test_api_orchestration.py tests/test_orchestration_analytics.py tests/test_api_database.py tests/test_api_bootstrap.py` passes

Validation override:
- uv run --group dev pytest -q tests/test_api_orchestration.py tests/test_orchestration_analytics.py tests/test_api_database.py tests/test_api_bootstrap.py

### p0_opencloud_frontend
Title: Phase 0 — Remove OpenCloud from TypeScript frontend
Depends on: p0_opencloud_backend
Agent: claude
Model: claude-opus-4-6

Remove all OpenCloud references from the TypeScript frontend: types, schemas, normalize logic, UI components (provider-filter, conversation-viewer, conversation-list, cost-breakdown-card, plans views), and frontend tests.

Covers plan tasks 5–6 from `docs/superpowers/plans/2026-03-24-phase0-opencloud-prefect-removal.md`.

Acceptance criteria:
- `"opencloud"` removed from FrontendProvider type, providers array, ProviderBreakdown
- All `opencloud*` fields removed from analytics types and DailyUsage
- OpenCloud removed from normalize.ts field mappings
- OpenCloud option removed from provider-filter.tsx
- OpenCloud branches removed from conversation-viewer, conversation-list, cost-breakdown-card, plans views
- OpenCloud test cases removed from page.test.ts, normalize.test.ts, shared.test.ts
- `npx tsc --noEmit` passes
- `npm run build` succeeds

Validation override:
- npx tsc --noEmit
- npm run build

### p0_prefect_frontend
Title: Phase 0 — Remove Prefect from TypeScript frontend
Depends on: p0_prefect_backend
Agent: claude
Model: claude-opus-4-6

Remove all Prefect references from TypeScript frontend: types, routes, endpoints, schemas (runtime, database), normalize logic, UI components (orchestration-hub, prefect-ui-embed, database-dashboard, orchestration page), and frontend tests. Delete prefect OpenAPI artifact.

Covers plan tasks 11–12 from `docs/superpowers/plans/2026-03-24-phase0-opencloud-prefect-removal.md`.

Acceptance criteria:
- `"prefect-ui"` removed from orchestrationTabs, prefectPathSchema and parsePrefectPath deleted
- `"prefect_postgres"` removed from database schema
- All orchestrationPrefect* endpoint functions deleted
- Prefect functions removed from routes.ts (buildPrefectUiUrl, normalizePrefectUiPath, PREFECT_UI_URL)
- prefectPath removed from orchestration page and hub props
- `src/components/orchestration/prefect-ui-embed.tsx` deleted
- `src/lib/client/prefect-normalize.test.ts` deleted
- `public/openapi/helaicopter-prefect-orchestration-api.json` deleted
- Prefect test cases removed from routes.test.ts, normalize.test.ts, mutations.test.ts, tabs.test.ts
- `npx tsc --noEmit` passes
- `npm run build` succeeds

Validation override:
- npx tsc --noEmit
- npm run build

### p0_docs_cleanup
Title: Phase 0 — Delete OpenCloud and Prefect documentation
Depends on: p0_opencloud_frontend, p0_prefect_frontend
Agent: codex
Model: gpt-5.4

Delete all OpenCloud and Prefect documentation files. Clean remaining docs of stale references. Delete related examples.

Covers plan tasks 7 and 13 from `docs/superpowers/plans/2026-03-24-phase0-opencloud-prefect-removal.md`.

Acceptance criteria:
- OpenCloud spec and plan docs deleted
- Prefect docs deleted (prefect-local-ops.md, oats-prefect-cutover.md, orchestration/prefect.mdx, related specs/plans)
- `examples/prefect_native_oats_orchestration_run.md` deleted
- Remaining docs cleaned of stale opencloud/prefect references (mint.json, orchestration guides, other specs)
- `grep -ri "opencloud\|prefect" docs/ examples/ --include="*.md" --include="*.mdx"` returns no matches (excluding this run spec and the mobile masterplan spec)

Validation override:
- grep -ri "opencloud\|prefect" docs/ examples/ --include="*.md" --include="*.mdx" | grep -v mobile_interface_masterplan | grep -v mobile-interface-masterplan | grep -v phase0-opencloud-prefect-removal | wc -l

### p0_verification
Title: Phase 0 — Regenerate OpenAPI and final verification
Depends on: p0_docs_cleanup
Agent: codex
Model: gpt-5.4

Regenerate OpenAPI artifacts, run full grep verification for stray references, run full test suite, build, and lint. Verify FastAPI starts cleanly.

Covers plan task 14 from `docs/superpowers/plans/2026-03-24-phase0-opencloud-prefect-removal.md`.

Acceptance criteria:
- OpenAPI artifacts regenerated via `npm run api:openapi`
- No stray opencloud or prefect references in python/, src/, tests/ source files
- Full Python test suite passes
- `npm run build` succeeds
- `npm run lint` passes
- FastAPI starts without import errors

Validation override:
- uv run --group dev pytest -q
- npm run build
- npm run lint

### p1_layout_core
Title: Phase 1 — Responsive layout core (viewport, sidebar provider, header, drawer)
Depends on: p0_verification
Agent: claude
Model: claude-opus-4-6

Build the responsive layout infrastructure: add viewport metadata, create SidebarProvider context, MobileHeader with hamburger, SidebarDrawer overlay, restructure root layout, and add safe-area CSS. The sidebar should be hidden behind a hamburger drawer on mobile/iPad (< 1024px) and visible as a static sidebar on laptop (>= 1024px).

Covers plan tasks 1–6 from `docs/superpowers/plans/2026-03-24-phase1-responsive-viewports.md`.

Acceptance criteria:
- Viewport metadata exported with `width: "device-width"`, `initialScale: 1`, `viewportFit: "cover"`
- `src/components/layout/sidebar-provider.tsx` created with open/toggle/close state
- `src/components/layout/mobile-header.tsx` created with hamburger button (44px tap target) and safe-area-inset-top
- `src/components/layout/sidebar-drawer.tsx` created with backdrop, slide-in animation, close-on-nav
- Root layout restructured: desktop sidebar in `hidden lg:block`, MobileHeader in `lg:hidden`, main padding `p-4 sm:p-6 lg:p-8`
- Safe-area CSS utilities and `overscroll-behavior: none` added to globals.css
- `npm run build` succeeds
- At 390px width: hamburger visible, sidebar hidden, drawer opens/closes
- At 1440px width: sidebar always visible, no hamburger

Validation override:
- npx tsc --noEmit
- npm run build

### p1_page_responsive
Title: Phase 1 — Make all pages responsive across viewports
Depends on: p1_layout_core
Agent: claude
Model: claude-opus-4-6

Audit and fix all page content for responsive behavior across mobile (< 640px), iPad (768px+), and laptop (1024px+). Analytics grids, conversation list/viewer, orchestration, plans, databases, pricing, docs, and schema pages must all work at all three viewport widths.

Covers plan tasks 7–10 from `docs/superpowers/plans/2026-03-24-phase1-responsive-viewports.md`.

Acceptance criteria:
- Analytics: stats grid stacks on mobile, charts full-width on mobile, filters wrap
- Conversations: cards single-column on mobile, filters stack vertically, search full-width
- All tables wrapped in `overflow-x-auto` for mobile horizontal scroll
- No horizontal page overflow at 390px on any page
- All interactive elements have minimum 44px tap targets
- `npm run build` succeeds
- `npm run lint` passes

Validation override:
- npm run build
- npm run lint

### p2_capacitor_setup
Title: Phase 2 — Capacitor iOS project setup and native plugins
Depends on: p1_page_responsive
Agent: claude
Model: claude-opus-4-6

Install Capacitor dependencies, initialize the iOS project, configure native plugins (status-bar, splash-screen, haptics, app lifecycle), create the Capacitor init bridge, add npm scripts, and configure the Tailscale server URL.

Covers plan tasks 1–4 from `docs/superpowers/plans/2026-03-24-phase2-capacitor-iphone-app.md`.

Acceptance criteria:
- `@capacitor/core`, `@capacitor/cli`, `@capacitor/status-bar`, `@capacitor/splash-screen`, `@capacitor/haptics`, `@capacitor/app` installed
- `capacitor.config.ts` created with app ID, Tailscale server URL, and plugin config
- `ios/` directory created via `npx cap add ios`
- `src/lib/capacitor.ts` created with initCapacitor() (status bar, app lifecycle)
- `src/components/layout/capacitor-init.tsx` created and wired into root layout
- npm scripts added: `cap:sync`, `cap:open`, `cap:run`
- `.gitignore` updated for iOS build artifacts
- `npx cap sync ios` succeeds
- `npm run build` succeeds

Validation override:
- npx tsc --noEmit
- npm run build

### p2_haptics_polish
Title: Phase 2 — Haptic feedback and final native polish
Depends on: p2_capacitor_setup
Agent: claude
Model: claude-opus-4-6

Add optional haptic feedback on nav taps when running in native Capacitor context. Verify the complete native experience works on iPhone over Tailscale.

Covers plan tasks 5–6 from `docs/superpowers/plans/2026-03-24-phase2-capacitor-iphone-app.md`.

Acceptance criteria:
- Nav link clicks trigger light haptic feedback on native platform only
- Haptics gracefully no-op in browser context
- `npm run build` succeeds

Notes:
- Task 5 (build and test on iPhone) requires manual Xcode/device testing that the agent cannot perform — focus on getting the code right and leave physical device testing to the human

Validation override:
- npx tsc --noEmit
- npm run build
