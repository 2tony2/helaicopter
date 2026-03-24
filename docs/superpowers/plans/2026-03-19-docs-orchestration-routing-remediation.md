# Docs, Orchestration, And Routing Remediation

## Goal

Fix the post-merge regressions where:

- docs content exists but is not accessible from the app
- `/docs` does not exist in the Next.js app
- database status is incomplete and stale for some resources
- `/orchestration` still exposes the older legacy orchestration-first tab model
- conversation URLs do not deep-link to a unique per-message UUID

## Findings

- The app has no `src/app/docs` route even though Mintlify-style docs exist under `docs/`.
- The sidebar does not link to docs.
- The backend database status payload types include `frontendCache` and `legacy-orchestrationPostgres`, but `build_status_payload()` only emits `sqlite` and `duckdb`.
- The frontend database hook refreshes every five minutes, which is too slow for a live status surface.
- Orchestration routing still defaults to `legacy-orchestration`, and the hub still labels the primary tab `legacy orchestration`.
- Conversation messages already have stable IDs from the backend, but the route model only carries tab/plan/subagent state.

## Plan

1. Add an app-native docs surface.
   - Create a `/docs` landing page and a catch-all docs route.
   - Render repo docs files from `docs/` directly inside the app.
   - Add a sidebar link to `/docs`.

2. Repair database status completeness and sync behavior.
   - Emit `frontendCache` and `legacy-orchestrationPostgres` from the backend status payload.
   - Align frontend types and normalization with all four resources.
   - Tighten polling cadence for the dashboard.

3. Align the orchestration page with the requested UX.
   - Rename the primary tab from `legacy orchestration` to `Orchestration`.
   - Make orchestration the default tab.
   - Remove redundant legacy orchestration health chrome from the main tab while keeping the embedded legacy orchestration UI tab.

4. Add stable per-message deep links.
   - Extend conversation route helpers with a `message` parameter.
   - Persist selected message state in URLs.
   - Scroll/select by message ID on load.

5. Verify with focused tests.
   - Route tests for docs/orchestration/message deep links.
   - Frontend normalization tests for database status.
   - Backend database status tests.
