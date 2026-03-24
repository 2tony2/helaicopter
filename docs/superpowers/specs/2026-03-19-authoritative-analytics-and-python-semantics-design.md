# Authoritative Analytics And Python Semantics Design

## Executive Summary

Helaicopter should remain a local-first single-user system, but its data model and analytics stack need a strict source-of-truth realignment. The immediate target state is:

- DuckDB becomes the authoritative store for historical analytics.
- Python becomes the only ingestion and semantics layer.
- SQLite remains the operational store for fast point reads and workflow state.
- OATS orchestration artifacts remain file-backed operationally, but their parsed records flow into analytics facts.
- Near-real-time freshness is delivered through incremental micro-batch refresh, not full destructive rebuilds.

This design intentionally does not add multi-user primitives, auth, tenancy, or remote deployment concerns. Those are out of scope for the current product direction.

## Product And Architectural Decisions

### Local-first scope

The system is explicitly optimized for local-first, single-user use. This phase does not add:

- authentication or RBAC
- tenant or user identifiers on domain entities
- remote coordination or shared persistence contracts

This keeps the architecture aligned with the actual deployment model and avoids contaminating the data model with speculative multi-tenant concerns.

### DuckDB as authoritative analytics

DuckDB should become the single historical analytics source for:

- dashboards
- time-series aggregates
- model and provider breakdowns
- cost reporting
- orchestration analytics

SQLite may still participate in live or current-window supplementation when a request overlaps data not yet materialized into DuckDB, but historical reads should not be recomputed from SQLite.

### Python-owned semantics and ingestion

The TypeScript export bridge is transitional and should be retired. Python should own:

- parsing and extraction from Claude/Codex artifacts
- semantic normalization
- pricing and model matching
- long-context premium rules
- status vocabulary mapping
- token field alias reconciliation
- persistence preparation for both OLTP and OLAP

The frontend should stop computing business metrics independently.

### Orchestration analytics included

OATS is in scope for the first implementation program. Its runtime and terminal artifacts should remain file-based for operational simplicity, but the backend should ingest them into analytical fact tables so orchestration behavior can be queried alongside conversation usage.

### Near-real-time freshness

Historical analytics should move from destructive rebuilds to incremental refresh. The first implementation target is minutes-level freshness via polling or micro-batch refresh of changed local artifacts. Full filesystem event plumbing is not required in the first version.

## Goals

- Establish one canonical semantic definitions layer in Python.
- Remove duplicate cost and status logic across backend, refresh, warehouse, and frontend.
- Replace the TypeScript export pipeline with Python-native extraction.
- Make DuckDB the authoritative read path for historical analytics.
- Add orchestration fact coverage to the warehouse.
- Replace destructive full refresh as the normal operating path with idempotent incremental updates.
- Separate event-time and source-file-time semantics.
- Reduce frontend normalization and business-logic drift.

## Non-Goals

- Multi-user deployment support
- Remote or cloud-first orchestration
- Enterprise semantic-layer tooling adoption such as dbt metrics or Cube in this phase
- Replacing OATS filesystem persistence as the operational source of truth
- Reworking the product around batch-only analytics

## Current Problems To Resolve

### Semantic duplication

Metric and contract logic is currently split across:

- frontend pricing and cost helpers
- Python analytics calculations
- refresh-time cost persistence
- frontend normalization aliases
- orchestration status display logic

This allows different screens and storage layers to disagree about the same underlying conversation or run.

### Destructive refresh behavior

The current pipeline clears operational conversation data and recreates DuckDB on refresh. That is acceptable for bootstrapping but incompatible with near-real-time operation, failure isolation, and historical continuity.

### Contract masking

The frontend proxy-based normalization layer hides transport drift instead of forcing explicit contract alignment. This reduces breakage visibility and makes it easier for backend and frontend field semantics to quietly diverge.

### Orchestration analytics isolation

OATS holds high-value execution and audit data, but that data does not currently feed the analytics warehouse. As a result, cross-domain operational questions cannot be answered from one analytical surface.

## Target Architecture

### Data zones

The system should operate as four practical zones:

1. Raw artifact zone
   - Claude/Codex/OATS files on disk
   - source-faithful, append-friendly, operationally independent

2. Canonical semantic zone
   - Python-owned normalized records and shared definitions
   - transient in process, optionally persisted in SQLite where operationally useful

3. Operational zone
   - SQLite
   - conversations, messages, evaluations, refresh state, operational orchestration references

4. Analytical zone
   - DuckDB
   - authoritative historical analytics for conversations and orchestration runs

### Store responsibilities

#### SQLite

SQLite remains responsible for:

- detailed conversation records
- messages, blocks, plans, tasks, subagents
- evaluation jobs and prompts
- refresh bookkeeping
- operational metadata used by non-analytical endpoints
- optional current-window supplement reads for near-real-time analytics

#### DuckDB

DuckDB becomes responsible for:

- historical analytics aggregates and facts
- historical cost reporting
- provider/model/tool/subagent trend analysis
- orchestration run and task analytics
- any API endpoint whose primary job is historical reporting

### Serving rules

- `/analytics` and other historical analytics endpoints should read DuckDB.
- If the response window overlaps data not yet materialized, the backend may merge a bounded SQLite supplement for the most recent interval.
- Conversation detail endpoints remain operational and continue reading SQLite-backed data.
- The frontend consumes server-computed metrics and status decorations instead of rederiving them.

## Component Boundaries

### 1. Python semantics package

Create a dedicated Python package, such as `python/helaicopter_semantics/`, that owns:

- canonical pricing tables
- model matching and provider resolution
- long-context premium rules
- canonical status enums and mapping rules
- token field alias registry
- canonical derived cost calculations
- helper types used by ingestion and warehouse loading

No other layer should maintain independent copies of this logic.

### 2. Python ingestion adapters

Claude, Codex, and OATS adapters should parse raw artifacts into canonical Python records. The adapters should normalize field names and semantics before persistence code sees them.

### 3. Incremental refresh pipeline

Replace the single destructive path with two supported modes:

- bootstrap/full reconciliation for first load or recovery
- steady-state incremental refresh for changed artifacts only

Incremental refresh should key records by stable business identity plus source-artifact change metadata.

### 4. SQLite operational persistence

SQLite models should be extended to support idempotent ingest and provenance. At minimum, operational entities should carry:

- `record_source`
- `loaded_at`
- `first_ingested_at`
- `last_refreshed_at`
- separated event-time and file-time fields where currently conflated

### 5. DuckDB warehouse loaders

Warehouse loading should upsert changed dimensions and facts instead of recreating the entire database during normal operation.

### 6. API and frontend contract cleanup

The backend should expose authoritative computed values. The frontend should:

- remove local cost computation for authoritative numbers
- remove required fields that the backend does not supply
- reduce normalization to explicit transport mappings
- surface contract mismatch early rather than silently proxying alternate keys forever

## Canonical Semantic Definitions

The semantic layer must define the following explicitly.

### Pricing

- canonical pricing table by model family and exact model
- canonical model matching fallback rules
- canonical long-context premium behavior
- canonical cache token billing behavior by provider

### Status vocabulary

- canonical orchestration run statuses
- canonical orchestration task statuses
- mapping rules from OATS runtime state and terminal records
- backend-owned derived display tones and stale-state interpretation

### Token field aliases

The backend should normalize provider-specific token field variants into one canonical vocabulary. The semantic layer should explicitly own mapping rules such as:

- `cache_creation_tokens`
- `cache_creation_input_tokens`
- `cache_write_tokens`
- `cache_read_tokens`
- `cache_read_input_tokens`

### Time semantics

Separate:

- event created time
- event ended time
- source file modified time
- ingest/load time
- last refreshed time

`last_updated_at` should stop serving as a mixed semantic placeholder for all of these.

## Data Model Changes

### Operational model changes

Conversation-related operational records should preserve:

- source provenance
- ingest timestamps
- event timestamps
- deterministic identity keys for idempotent update

Project identity should be promoted from emergent aggregation behavior into an explicit operational entity if project-level governance or historical project analysis is needed.

### Warehouse dimensions

The warehouse should maintain or extend:

- `dim_dates`
- `dim_projects`
- `dim_models`
- `dim_tools`
- `dim_subagent_types`
- `dim_providers`

`dim_dates` should be enriched with normal calendar attributes useful for reporting.

### Warehouse facts

Preserve and continue evolving conversation-oriented facts, then add:

- `fact_orchestration_runs`
- `fact_orchestration_task_attempts`
- optional `fact_evaluations` if conversation evaluations need analytical treatment in this phase

Every fact definition should document its grain explicitly in code comments and documentation.

## Refresh And Freshness Design

### Normal operating mode

Near-real-time refresh should operate as a short-interval micro-batch process:

1. discover candidate changed artifacts
2. fingerprint or version them
3. parse and normalize only changed inputs
4. upsert SQLite operational records
5. upsert dependent DuckDB dimensions and facts
6. invalidate only affected caches

### Full reconciliation mode

A bootstrap or repair mode may still support rebuilding state from raw artifacts, but it should be an explicit maintenance path rather than the normal serving workflow.

### Failure handling

- a failed artifact ingest should not destroy previously ingested unaffected analytics
- refresh progress and failure state should be recorded explicitly
- partial failures should surface in status endpoints and logs with artifact-level identification

## API And Frontend Contract Direction

### Backend responsibilities

The backend should compute and serve:

- conversation and analytics cost breakdowns
- long-context premium values
- orchestration status tones and stale-state interpretations
- authoritative analytics series and aggregates

### Frontend responsibilities

The frontend should focus on:

- rendering
- transport normalization during migration
- local interaction state

It should not remain responsible for authoritative business calculations.

### Specific contract cleanup targets

- remove or relax the frontend-only required `evaluation` field on orchestration run records unless the backend adds it intentionally
- replace proxy-based normalization with explicit mappings once transport is stabilized
- align docs and runtime metadata so analytics backend reporting matches real serving behavior

## Migration Plan Shape

The implementation should proceed in phases.

### Phase 1: Canonical semantics and contract cleanup

- build Python semantic definitions
- align backend pricing and status logic on that package
- remove unsound frontend contract assumptions
- update tests around canonical semantics

### Phase 2: Python-native ingestion and incremental operational loading

- replace the TypeScript export bridge
- ingest Claude/Codex artifacts directly in Python
- add provenance and time-semantics fields
- introduce idempotent SQLite upsert behavior

### Phase 3: Warehouse authority and orchestration facts

- add incremental DuckDB loading
- add orchestration fact tables
- cut historical analytics endpoints over to DuckDB
- support bounded live supplementation when needed

### Phase 4: Frontend simplification and near-real-time polish

- remove frontend business logic duplication
- shrink normalization compatibility shims
- tighten cache invalidation and freshness behavior
- update docs to reflect the final architecture

## Risks And Trade-Offs

### Migration risk

The largest delivery risk is changing ingestion, semantics, persistence, and analytics serving simultaneously. This is why the implementation should be phased with explicit cutovers and parity tests.

### Live supplement complexity

Making DuckDB authoritative while preserving near-real-time freshness introduces a bounded dual-read period for very recent data. That is acceptable if the window is small, explicit, and fully backend-controlled.

### Orchestration fact modeling risk

OATS artifacts have both runtime and terminal forms. Fact loading must define clear rules for reconciling mutable in-flight state with terminal immutable records.

### Frontend migration risk

Removing duplicated frontend logic will surface contract gaps that were previously hidden by permissive normalization. That is desirable, but it must be done with explicit transport tests and staged cleanup.

## Testing Strategy

The implementation plan should require:

- semantic golden tests for pricing, model resolution, and status mapping
- ingestion fixture tests for Claude, Codex, and OATS artifacts
- incremental refresh tests for idempotency and update handling
- warehouse parity tests proving materialized analytics match canonical semantic fixtures
- API tests proving historical analytics are DuckDB-backed
- frontend tests focused on rendering and explicit transport normalization only

## Open Questions For Implementation Planning

- whether current-day live supplementation is required from day one or can ship shortly after the DuckDB cutover
- whether project identity needs an explicit operational table immediately or can remain derived until later in the migration
- whether conversation evaluations should become warehouse facts in the same program or the next one
- what exact polling interval satisfies near-real-time expectations without excessive local churn

## Planning Constraint

This design intentionally spans multiple bounded workstreams. The implementation plan should decompose it into sequential milestones that each produce testable working software and avoid a single large cutover.
