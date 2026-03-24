# Mobile Interface Masterplan

**Date**: 2026-03-24
**Status**: Approved

## Overview

Three-phase plan to make Helaicopter mobile-ready: clean up dead code, make the web app responsive across three viewports, and wrap it in a Capacitor shell for iPhone use over Tailscale.

## Phasing

- **Phase 0**: Remove all OpenCloud and Prefect references from the codebase
- **Phase 1**: Responsive viewports (mobile < 640px, iPad 768px+, laptop 1024px+)
- **Phase 2**: Capacitor iPhone app connecting via Tailscale

Phase 0 comes first so we don't build mobile views for features we're removing.

---

## Phase 0: OpenCloud + Prefect Removal

### Goal

Delete all OpenCloud and Prefect code, routes, types, UI, docs, and tests. The app supports three providers going forward: Claude Code, Codex, and OpenClaw.

### OpenCloud Removal (~31 files)

**Entire directories/files to delete:**
- `python/helaicopter_api/adapters/opencloud_sqlite/` (entire directory)
- `python/helaicopter_api/ports/opencloud_sqlite.py`

**Type system cleanup:**
- Remove `"opencloud"` from `FrontendProvider` union in `src/lib/types.ts`
- Remove `"opencloud"` from `ProviderIdentifier` in `python/helaicopter_semantics/models.py`
- Remove `"opencloud"` from `ProviderSelection` in `python/helaicopter_domain/vocab.py`
- Remove opencloud fields from analytics types in `src/lib/types.ts` (lines ~768, 834-845, 930-935)
- Remove from `src/lib/client/schemas/shared.ts`

**Backend application code:**
- `python/helaicopter_api/application/conversations.py`: Remove ~15 OpenCloud-specific functions (`_get_opencloud_live_conversation`, `_list_opencloud_live_summaries`, `_summarize_opencloud_session`, `_resolve_live_opencloud_conversation_identity`, `_opencloud_sessions`, `_opencloud_parts_by_message`, `_opencloud_user_texts`, `_first_opencloud_user_message`, `_opencloud_usage_for_message`, `_opencloud_project_path`, etc.) and all call sites
- `python/helaicopter_api/application/conversation_refs.py`: Remove `"opencloud"` from `_KNOWN_CONVERSATION_REF_PROVIDERS`
- `python/helaicopter_api/bootstrap/services.py`: Remove `opencloud_store` field, `FileOpenCloudStore` import/instantiation, `OpenCloudStore` import
- `python/helaicopter_api/server/config.py`: Remove `opencloud_dir` field, `opencloud_sqlite_path` property
- `python/helaicopter_db/utils.py`: Remove `"opencloud:"` prefix check

**Frontend components:**
- `src/components/ui/provider-filter.tsx`: Remove `{ value: "opencloud", label: "OpenCloud" }` option
- `src/components/conversation/conversation-viewer.tsx`: Remove `"OpenCloud"` display name branch
- `src/components/conversation/conversation-list.tsx`: Remove opencloud references
- `src/components/analytics/cost-breakdown-card.tsx`: Remove OpenCloud provider check
- `src/views/plans/plans-index-view.tsx`: Remove `"OpenCloud"` branch
- `src/features/plans/components/plan-panel.tsx`: Remove `"OpenCloud"` branch
- `src/lib/client/normalize.ts`: Remove opencloud normalization fields

**Documentation to delete:**
- `docs/superpowers/plans/2026-03-22-opencloud-opencode-provider.md`
- `docs/superpowers/specs/2026-03-22-opencloud-opencode-provider-design.md`
- Remove opencloud references from `docs/superpowers/specs/2026-03-22-openclaw-conversation-tabs-design.md`

**Tests to update/delete:**
- `src/app/conversations/[...segments]/page.test.ts`: Remove OpenCloud test cases
- `src/lib/client/normalize.test.ts`: Remove OpenCloud test data
- `tests/test_semantics.py`: Remove `test_explicit_opencloud_provider_field_takes_precedence`, `test_opencloud_project_path_prefix_identifies_opencloud`
- `tests/test_api_conversations.py`: Remove OpenCloud test data
- `tests/test_api_analytics.py`: Remove OpenCloud analytics tests
- `tests/test_backend_settings.py`: Remove OpenCloud settings tests

### Prefect Removal (~94 files)

**Entire directories/files to delete:**
- `python/oats/prefect/` (entire directory — client, compiler, flows, tasks, deployments, analytics, artifacts, ignore, models, settings, worktree)
- `python/helaicopter_api/adapters/prefect_http.py`
- `python/helaicopter_api/ports/prefect.py`
- `python/helaicopter_api/router/prefect_orchestration.py`
- `python/helaicopter_api/application/prefect_orchestration.py`
- `python/helaicopter_api/schema/prefect_orchestration.py`
- `src/components/orchestration/prefect-ui-embed.tsx`
- `src/lib/client/prefect-normalize.test.ts`
- `public/openapi/helaicopter-prefect-orchestration-api.json`
- All `tests/oats/test_prefect_*.py` files (8 files)

**Backend application code:**
- `python/helaicopter_api/application/orchestration.py`: Remove Prefect imports (`oats.prefect.analytics`), `_prefect_flow_runs_by_id`, `_prefect_attempts_by_task_id`, Prefect status normalization functions, `mode="prefect"` branches, `prefect_artifacts`/`prefect_attempt` handling
- `python/helaicopter_api/application/gateway.py`: Remove Prefect gateway definition
- `python/helaicopter_api/application/database.py`: Remove `prefectPostgres` check and database config
- `python/helaicopter_api/bootstrap/services.py`: Remove `PrefectHttpAdapter` import/instantiation, `PrefectOrchestrationPort` import, `prefect_client` field
- `python/helaicopter_api/server/config.py`: Remove `prefect_api_url`, `prefect_api_timeout_seconds` fields, `prefect` property
- `python/helaicopter_api/server/openapi_artifacts.py`: Remove Prefect OpenAPI artifact generation
- `python/helaicopter_api/router/router.py`: Remove `prefect_orchestration_router` import and `include_router`
- `python/helaicopter_db/orchestration_facts.py`: Remove `oats.prefect.analytics` import, Prefect artifact loading and fact building
- `python/helaicopter_db/status.py`: Remove `prefectPostgres` field, `_prefect_postgres_target` function, `prefectPostgres` configuration
- `python/helaicopter_domain/vocab.py`: Remove `"prefect_postgres"` from `DatabaseStatusKey`
- `python/oats/cli.py`: Remove Prefect imports, `prefect_app` Typer instance, all `@prefect_app` commands

**Frontend:**
- `src/components/orchestration/orchestration-hub.tsx`: Remove Prefect UI tab
- `src/components/databases/database-dashboard.tsx`: Remove `prefectPostgres` display section
- `src/app/orchestration/page.tsx`: Remove `prefectPath` search param handling
- `src/lib/routes.ts`: Remove `buildPrefectUiUrl`, `normalizePrefectUiPath` functions
- `src/lib/types.ts`: Remove `prefectPostgres` from `DatabaseStatusKey`, remove field from database types
- `src/lib/client/endpoints.ts`: Remove Prefect API endpoints
- `src/lib/client/schemas/runtime.ts`: Remove `"prefect-ui"` tab, `prefectPathSchema`
- `src/lib/client/schemas/database.ts`: Remove `"prefect_postgres"` key, `prefectPostgres` schema

**Documentation to delete:**
- `docs/prefect-local-ops.md`
- `docs/oats-prefect-cutover.md`
- `docs/orchestration/prefect.mdx`
- `docs/superpowers/plans/2026-03-18-prefect-native-oats-orchestration.md`
- `docs/superpowers/plans/2026-03-19-full-program-oats-prefect-pipeline.md`
- `docs/superpowers/specs/2026-03-18-prefect-native-oats-orchestration-design.md`
- `docs/superpowers/specs/2026-03-19-full-program-oats-prefect-overnight-run-design.md`
- `examples/prefect_native_oats_orchestration_run.md`
- Remove Prefect references from remaining docs (orchestration overview, guides, mint.json, other specs/plans)

**Tests to delete/update:**
- `tests/test_api_prefect_orchestration.py` (entire file)
- `tests/test_api_bootstrap.py`: Remove Prefect references
- `tests/test_api_database.py`: Remove Prefect references
- `tests/test_api_orchestration.py`: Remove Prefect references
- `tests/test_orchestration_analytics.py`: Remove Prefect references
- `src/lib/routes.test.ts`: Remove Prefect route tests
- `src/lib/client/normalize.test.ts`: Remove Prefect test data
- `src/lib/client/mutations.test.ts`: Remove Prefect database status tests
- `src/lib/client/schemas/shared.test.ts`: Remove Prefect schema tests
- `src/components/orchestration/tabs.test.ts`: Remove Prefect tab test

**Config/dependencies:**
- `pyproject.toml`: Remove Prefect dependency
- Regenerate OpenAPI artifacts after removal (`npm run api:openapi`)

### Verification

- All existing tests pass (minus deleted ones) after removal
- `npm run build` succeeds
- `npm run lint` passes
- FastAPI starts without errors
- OpenAPI artifacts regenerated cleanly
- No remaining references to "opencloud" or "prefect" in source code (grep verification)

---

## Phase 1: Responsive Viewports

### Goal

Make the web app fully responsive across three viewports using standard Tailwind breakpoints: mobile (< 640px), iPad (md: 768px+), laptop (lg: 1024px+).

### Breakpoints

| Viewport | Tailwind prefix | Width | Sidebar behavior |
|----------|----------------|-------|-----------------|
| Mobile | base (default) | < 640px | Hidden, hamburger overlay |
| iPad | `md:` | 768px+ | Hidden, hamburger overlay |
| Laptop | `lg:` | 1024px+ | Always visible, w-64 |

### New Components

**`SidebarProvider`** (React context):
- State: `open: boolean`
- Methods: `toggle()`, `close()`
- Minimal — just controls drawer visibility
- Location: `src/components/layout/sidebar-provider.tsx`

**`MobileHeader`**:
- Sticky top bar, visible only below `lg` breakpoint (`lg:hidden`)
- Contains: hamburger icon button (triggers sidebar drawer) + "Helaicopter" title
- Styling: `sticky top-0 z-40 border-b bg-background/95 backdrop-blur`
- Location: `src/components/layout/mobile-header.tsx`

**`SidebarDrawer`**:
- Wraps `AppSidebar` in a slide-over overlay for mobile/iPad
- Fixed positioning with backdrop (`fixed inset-0 z-50`)
- Sidebar slides in from the left
- Tap backdrop or any nav item → closes drawer (calls `close()`)
- Can use Radix Dialog internally or simple portal + animation
- Location: `src/components/layout/sidebar-drawer.tsx`

### Root Layout Changes

Current:
```tsx
<div className="flex min-h-screen">
  <AppSidebar />
  <main className="flex-1 p-8 overflow-auto">{children}</main>
</div>
```

New:
```tsx
<SidebarProvider>
  <div className="flex min-h-screen">
    {/* Desktop sidebar */}
    <div className="hidden lg:block">
      <AppSidebar />
    </div>

    {/* Mobile/iPad drawer overlay */}
    <SidebarDrawer />

    <div className="flex-1 flex flex-col min-w-0">
      {/* Mobile/iPad header */}
      <MobileHeader className="lg:hidden" />

      <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
        {children}
      </main>
    </div>
  </div>
</SidebarProvider>
```

### AppSidebar Changes

- No structural changes to the sidebar component itself
- Add `onClick` handler to nav links that calls `close()` from SidebarProvider (for drawer usage)
- The same component renders in both desktop (static) and mobile (drawer) contexts

### Page Content Responsive Patterns

**Analytics page**:
- Stats cards grid: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6`
- Charts: full width on mobile, side-by-side on laptop
- Date range / provider filters: stack vertically on mobile

**Conversations page**:
- Conversation cards: single column on mobile, grid on larger screens
- Filter bar: collapse filters into a dropdown or stack vertically on mobile
- Search input: full width on mobile

**Orchestration page**:
- Tab content adapts to available width
- Tables: horizontal scroll on mobile if needed

**General patterns**:
- All `PageHeader` instances: title and actions already use `flex-wrap`, will stack naturally
- Tables wider than viewport: `overflow-x-auto` wrapper
- Padding: `p-4 sm:p-6 lg:p-8` (reduce from fixed `p-8`)

### Touch-Friendly Adjustments

- Minimum 44px tap targets for interactive elements on mobile
- Nav items already `py-2` with adequate height
- Filter buttons and dropdowns: verify minimum height
- No hover-only interactions — all hover states should also work on tap

---

## Phase 2: Capacitor iPhone App

### Goal

Wrap the responsive Helaicopter web app in a Capacitor native shell for personal iPhone use, connecting to the Mac's FastAPI server over Tailscale.

### Architecture

```
iPhone (Capacitor WebView)
    │
    │  HTTP over Tailscale VPN
    │
    ▼
Mac (FastAPI :30000 + Next.js)
    │
    ├── ~/.claude/ (Claude Code data)
    ├── ~/.codex/ (Codex data)
    └── ~/.openclaw/ (OpenClaw data)
```

The Capacitor app loads the full Next.js app from the Tailscale URL. No static export — the WebView points directly at the running server. This is the simplest approach since FastAPI must be running on the Mac anyway.

### Setup

**Capacitor initialization:**
- `npx cap init helaicopter com.helaicopter.app --web-dir=out` at project root
- `npx cap add ios` creates `ios/` directory with Xcode project
- Configure `capacitor.config.ts` with Tailscale server URL

**`capacitor.config.ts`:**
```typescript
import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.helaicopter.app',
  appName: 'Helaicopter',
  server: {
    url: 'http://<tailscale-hostname>:3000',  // Next.js over Tailscale
    cleartext: true,  // Allow HTTP (Tailscale is already encrypted)
  },
  ios: {
    contentInset: 'automatic',
  },
};

export default config;
```

### Native Plugins

Minimal set for a tasteful native feel:

| Plugin | Purpose |
|--------|---------|
| `@capacitor/status-bar` | Match status bar to app theme (dark/light) |
| `@capacitor/splash-screen` | Brief branded splash on launch |
| `@capacitor/haptics` | Light haptic on nav taps (optional) |
| `@capacitor/app` | Lifecycle events — refresh data on foreground |

### CSS Adjustments for iOS

**Safe area insets** — prevent content from hiding behind notch/home indicator:
```css
/* Applied to MobileHeader */
padding-top: env(safe-area-inset-top);

/* Applied to main content bottom */
padding-bottom: env(safe-area-inset-bottom);
```

**Viewport meta tag** in root layout `<head>`:
```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

**WebView scroll behavior:**
- Smooth momentum scrolling (default in modern WebKit)
- Disable pull-to-refresh bounce on non-scrollable areas via `overscroll-behavior: none`

### Build & Deploy Workflow

1. Start FastAPI + Next.js on Mac: `npm run dev`
2. Ensure Tailscale is connected on both Mac and iPhone
3. `npx cap sync ios` (syncs plugin configs)
4. Open `ios/App/App.xcworkspace` in Xcode
5. Select your iPhone as target, hit Run
6. For subsequent web changes: just reload in the app (web is served live from Mac)

### What We're NOT Doing

- No App Store distribution — sideload via Xcode or TestFlight
- No offline support or service worker
- No push notifications
- No static export — WebView loads from live server
- No native navigation replacement — web hamburger menu works in WebView

---

## Out of Scope

- React Native rewrite
- Cloud deployment or data sync
- Multi-user support
- App Store submission
- Offline-first architecture
- Additional native iOS features beyond the listed plugins
