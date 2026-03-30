# FastMCP External Agent Surface Design

## Executive Summary

Helaicopter already exposes a rich FastAPI backend for local analytics, conversation reads, orchestration inspection, and evaluation workflows. This change adds a companion MCP surface so external agents can consume that backend through an LLM-friendly protocol instead of scraping HTTP routes manually.

The MCP surface should be mounted inside the existing FastAPI application and generated from the backend's OpenAPI contract using FastMCP's FastAPI integration. We will not expose the entire backend blindly. Instead, we will publish a curated, analysis-oriented surface that gives agents broad read access to data and limited write access only where it directly supports evaluation workflows.

## Goals

- Expose Helaicopter's backend data through a first-class MCP endpoint mounted on the existing FastAPI app.
- Make the MCP surface usable by external agents for analysis, exploration, and evaluation runs.
- Reuse the current FastAPI routers and Pydantic schemas so the MCP contract stays aligned with the canonical backend.
- Keep sensitive or operationally dangerous mutations out of the MCP surface.
- Preserve the current HTTP API and OpenAPI behavior for the frontend and local tooling.

## Non-Goals

- Replacing the existing FastAPI HTTP API.
- Designing a bespoke hand-written MCP tool for every backend action in this phase.
- Exposing auth credential management, worker control, or destructive maintenance operations to external agents.
- Adding remote multi-user security, tenancy, or internet-facing deployment concerns.

## Current Context

The backend already has domain-grouped routers for:

- analytics
- conversations and conversation DAGs
- history, plans, projects, tasks
- orchestration inspection
- evaluation prompts and conversation evaluations
- operational control surfaces such as auth credentials, worker control, and database refresh

FastMCP's current documentation supports two relevant patterns:

1. Generate an MCP server directly from a FastAPI app with `FastMCP.from_fastapi(...)`.
2. Mount the resulting ASGI app into the existing FastAPI process.

FastMCP also warns that raw API conversion is a good bootstrap path but less effective than a curated MCP surface. That argues for a constrained route map rather than publishing every route automatically.

## Product Decision

### Publish a curated MCP mirror, not a full backend mirror

The MCP server should expose:

- read-heavy GET endpoints needed for analysis and inspection
- conversation evaluation creation, because "run analyses and evals" requires an action surface

The MCP server should not expose:

- auth credential CRUD or OAuth callbacks
- worker registration, draining, or task result reporting
- database refresh triggers
- orchestration mutation endpoints such as pause, reroute, retry, cancel, or insert task
- subscription-setting writes

This keeps the MCP surface useful without turning it into a remote admin channel.

## Target Architecture

### 1. Base FastAPI app stays the source of truth

The existing FastAPI application remains the canonical backend. Routers, schemas, middleware, and startup state all continue to live under `python/helaicopter_api/`.

### 2. New MCP builder module

Add a backend-owned module responsible for:

- creating a FastMCP server from the FastAPI app
- defining route maps that allowlist safe routes
- tagging the generated MCP components for discoverability
- exposing a mounted ASGI app at a stable path such as `/mcp`

### 3. Mounted MCP endpoint

The MCP ASGI app is mounted into the existing FastAPI application. That gives one local server process with:

- standard HTTP API routes for the frontend
- MCP transport for external agent clients

### 4. Curated route mapping

FastMCP route maps should follow these rules:

- safe GET collection endpoints become MCP resources
- safe GET detail endpoints with path parameters become MCP resource templates
- evaluation-creation POST endpoints become MCP tools
- all unmatched or explicitly sensitive routes are excluded

This produces a resource-oriented read surface that better matches how agents explore data.

## Route Scope

### Included read surfaces

- `/analytics`
- `/conversations`
- `/conversations/by-ref/{conversation_ref}`
- `/conversations/{project_path}/{session_id}`
- `/conversations/{project_path}/{session_id}/dag`
- `/conversations/{project_path}/{session_id}/subagents/{agent_id}`
- `/conversation-dags`
- `/history`
- `/plans`
- `/plans/{slug}`
- `/projects`
- `/tasks/{session_id}`
- `/orchestration/oats`
- `/orchestration/oats/facts`
- `/orchestration/oats/{run_id}`
- `/dispatch/queue`
- `/dispatch/history`
- `/evaluation-prompts`
- conversation evaluation listing endpoint
- `/gateway/direction`
- `/subscription-settings`
- health and readiness metadata that helps clients reason about availability

### Included write surfaces

- `POST /conversations/{project_path}/{session_id}/evaluations`

This is the single allowed mutation because it directly supports external evaluation workflows.

### Excluded surfaces

- `/auth/**`
- `/workers/**`
- `POST /databases/refresh`
- orchestration mutation POST routes
- evaluation prompt create/update/delete
- subscription-setting patch

## Lifespan And Startup

The current FastAPI app already owns startup and shutdown via a custom lifespan that builds shared services and starts the resolver loop. The mounted MCP app must coexist with that lifecycle.

The implementation should use a small composition layer so:

- Helaicopter startup still initializes backend services exactly once
- the mounted MCP app receives any startup/shutdown behavior FastMCP requires

If FastMCP's mounted app does not require explicit lifecycle coordination for this configuration, the composition should remain minimal. The important rule is to avoid duplicate backend startup work.

## Dependencies

This feature adds a FastMCP dependency to the Python backend. While verifying the repo, the current backend test suite also failed at import time because `cryptography` is required by the auth application layer but missing from `pyproject.toml`. That dependency gap must be corrected in this branch so backend verification can run at all.

## Testing Strategy

### Backend contract tests

Add tests that verify:

- the FastAPI app mounts an MCP endpoint
- the mounted MCP transport responds on its configured path
- safe read routes appear in the generated MCP surface
- explicitly excluded operational routes do not appear

### Regression coverage

Keep or add smoke coverage proving:

- `/openapi.json` still works
- `/health` still works
- the app factory still returns a valid FastAPI app after MCP mounting

### Verification

The branch should finish with:

- targeted backend pytest coverage for the new MCP integration
- regenerated OpenAPI artifacts if the HTTP contract changes
- a final verification run showing the implemented tests passing

## Risks And Mitigations

### Risk: exposing too much operational power

Mitigation:
- use explicit allowlist route maps
- exclude known write/admin prefixes by default

### Risk: generated MCP names are noisy or unstable

Mitigation:
- keep the first iteration small and curated
- add explicit MCP naming overrides for key routes if discovery quality is poor

### Risk: lifecycle conflicts when mounting the MCP app

Mitigation:
- isolate MCP creation in its own module
- verify app startup through tests using the real app factory

## Success Criteria

- An external MCP client can connect to Helaicopter's local backend and discover resources/tools for analytics and evaluation workflows.
- Agents can read core data from conversations, analytics, history, plans, projects, and orchestration inspection surfaces.
- Agents can trigger conversation evaluations through the MCP server.
- Sensitive backend control surfaces remain unavailable through MCP.
