# Remove Repo-Local Orchestration Design

**Date:** 2026-03-30
**Status:** Approved

## Executive Summary

Helaicopter should stop acting as a repo-local orchestration control plane. The app will no longer package, serve, inspect, or control OATS runs, dispatch queues, or worker lifecycle state. This removal includes the backend APIs, frontend pages and components, packaged Python runtime, and the docs/scripts that advertise orchestration as a product feature.

The rest of the product remains intact: conversations, DAG inspection, plans, databases, prompts, analytics unrelated to orchestration, pricing, and schema tooling stay in place.

## Scope

Remove these surfaces entirely:

- `python/oats/` and the `oats` CLI packaging/script
- OATS run artifact adapters, orchestration ports, orchestration application services, and orchestration schemas
- Dispatch queue and worker control-plane backends
- The `/orchestration` frontend page and all orchestration, dispatch, and worker UI components
- Frontend client types, endpoints, normalizers, and mutations that only exist for orchestration/dispatch/workers
- Tests that only cover orchestration, dispatch, workers, and the packaged OATS runtime
- README and related docs that describe orchestration as part of Helaicopter

Keep these surfaces:

- Conversation and conversation DAG inspection
- Database inspection and refresh paths
- Evaluation prompts and evaluation APIs
- General gateway/runtime metadata that is still accurate after removal

## Approaches Considered

### 1. Hide the UI but keep the backend and runtime

This is the smallest code diff, but it leaves dead product surface, maintenance burden, runtime coupling, and unsupported control-plane APIs behind. It does not match the request to remove orchestration from the repo.

### 2. Remove only OATS pages and routes, keep dispatch/workers

This removes the most visible orchestration page, but it leaves the permanent worker loop, dispatch queue, and backend control plane in place. Because those systems exist to operate the orchestration runtime, this still leaves orchestration handling in the repo under another name.

### 3. Remove the entire orchestration control plane

This removes OATS runtime packaging, backend orchestration/dispatch/workers, frontend orchestration/dispatch/workers, and supporting docs/tests. It is the cleanest boundary and best matches the intent that Helaicopter should not handle orchestration here.

**Recommendation:** Approach 3.

## Target Architecture

After this change, Helaicopter is a read/write app for local conversation, plan, prompt, analytics, and database surfaces only. It no longer exposes orchestration runtime state or worker control APIs. The backend router tree and frontend navigation should reflect that smaller scope explicitly.

## Removal Plan

### Backend

- Stop registering orchestration, dispatch, and workers routers.
- Remove orchestration-related application modules, schemas, adapters, and ports.
- Remove resolver-loop and worker-registry startup wiring from server lifespan and service bootstrap.
- Remove any backend documentation/openapi artifacts that publish orchestration routes.
- Update config and settings only where orchestration-specific fields become unused.

### Frontend

- Remove the `/orchestration` route.
- Remove orchestration, dispatch, and worker components.
- Remove client endpoints, hooks, mutations, schemas, and types that are only used by those surfaces.
- Update shared runtime tab helpers and navigation tests so the product no longer references orchestration.

### Packaging and Repo Layout

- Remove the `oats` script from `package.json`.
- Remove the packaged `python/oats/` implementation from the repo.
- Remove examples or repo docs that exist only to support OATS orchestration.

### Tests and Verification

- Delete tests that only validate removed orchestration/dispatch/worker behavior.
- Add or update regression tests for the remaining navigation/runtime helpers where orchestration entries disappear.
- Verify the repo with focused backend tests, frontend tests, linting, and a production build.

## Risks and Mitigations

- Removing router registrations without removing all imports can leave startup failures.
  Mitigation: remove from router composition first, then clean unused modules and imports.
- Shared frontend type files may still reference orchestration unions.
  Mitigation: search type names and route helpers after each deletion wave.
- README and OpenAPI artifacts can drift from the actual product surface.
  Mitigation: update docs and generated artifacts in the same branch.

## Success Criteria

- No backend route, schema, service, or startup path for OATS orchestration, dispatch, or workers remains.
- No frontend route, nav link, client hook, or UI component for orchestration, dispatch, or workers remains.
- The packaged `python/oats/` runtime is gone from the repo and no script references it.
- Verification commands succeed on the remaining product surface.
