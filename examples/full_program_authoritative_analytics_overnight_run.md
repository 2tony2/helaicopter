# Run: Full Program Authoritative Analytics Overnight

## Tasks

### semantic_foundation
Title: T001 Canonical Python Semantics Foundation
Agent: claude
Model: claude-sonnet-4-5-20250929
Reasoning effort: high

Implement the semantic foundation from `docs/superpowers/specs/2026-03-19-authoritative-analytics-and-python-semantics-design.md`. Create the canonical Python-owned pricing, model matching, long-context premium, token alias, and status vocabulary layer that later tasks depend on. Keep the work bounded to shared semantic definitions and the most obvious contract drift cleanup that unblocks later phases.

Acceptance criteria:
- canonical Python semantic definitions exist for pricing, model matching, token aliases, and orchestration status vocabulary
- backend analytics code can consume the shared semantic layer instead of maintaining its own separate pricing logic
- at least one unsound contract edge is explicitly removed or aligned rather than silently normalized
- focused semantic tests exist and pass

Notes:
- read `docs/superpowers/specs/2026-03-19-authoritative-analytics-and-python-semantics-design.md`
- keep this task foundational; do not begin Python-native ingestion or warehouse cutover here

Validation override:
- uv run --group dev pytest -q tests/test_analytics_core.py tests/oats/test_run_definition_loader.py

### python_ingestion_foundation
Title: T002 Python-Native Ingestion Foundation
Depends on: semantic_foundation
Agent: claude
Model: claude-sonnet-4-5-20250929
Reasoning effort: high

Replace the TypeScript export bridge with Python-native extraction for the authoritative analytics program. Introduce canonical Python extraction flow for Claude and Codex artifacts and wire the refresh pipeline toward Python-owned normalized records.

Acceptance criteria:
- the refresh path no longer depends on `scripts/export-parsed-data.ts` for authoritative ingestion
- Claude and Codex artifact parsing flows feed Python-owned canonical records
- refresh-time cost shaping relies on the shared Python semantics layer
- ingestion-focused tests pass

Notes:
- keep the extraction boundary clean so later storage and warehouse tasks consume normalized Python records
- do not start DuckDB serving cutover in this task

Validation override:
- uv run --group dev pytest -q tests/test_api_conversations.py tests/test_api_analytics.py

### operational_store_migration
Title: T003 SQLite Operational Store Provenance And Time Semantics
Depends on: python_ingestion_foundation

Implement the operational-store changes from the design: provenance metadata, separated event/file/load timestamps, and idempotent update behavior needed for incremental refresh. Focus on SQLite-backed operational models and refresh bookkeeping.

Acceptance criteria:
- operational persistence distinguishes event time from source-file modification time
- provenance and load metadata are present where the design requires them
- refresh logic supports idempotent update instead of destructive-only assumptions
- targeted operational-store tests pass

Notes:
- keep this task focused on SQLite and operational refresh state
- do not cut analytics endpoints to DuckDB in this task

Validation override:
- uv run --group dev pytest -q tests/test_api_conversations.py tests/test_api_database.py

### warehouse_authority_cutover
Title: T004 DuckDB Historical Analytics Authority
Depends on: python_ingestion_foundation, operational_store_migration
Agent: claude
Model: claude-sonnet-4-5-20250929
Reasoning effort: high

Make DuckDB the authoritative historical analytics backend. Extend warehouse loading to consume the canonical Python records, align fact/dimension loading with shared semantics, and route historical analytics reads through DuckDB while keeping bounded current-window supplementation in scope.

Acceptance criteria:
- historical analytics are served from DuckDB
- warehouse loading consumes Python-owned canonical records and shared semantics
- bounded current-window supplementation exists for the newest slice when needed
- analytics cutover tests pass

Notes:
- preserve the local-first architecture and keep SQLite available for operational reads
- do not remove frontend compatibility shims that still depend on backend contract stabilization

Validation override:
- uv run --group dev pytest -q tests/test_api_analytics.py tests/test_api_database.py

### orchestration_analytics
Title: T005 OATS Orchestration Analytics Facts
Depends on: semantic_foundation, python_ingestion_foundation

Ingest OATS runtime and terminal artifacts into analytical fact tables while keeping OATS operational storage file-based. Add the initial orchestration analytics cutover needed for backend and frontend consumption.

Acceptance criteria:
- orchestration run facts exist
- orchestration task-attempt facts exist
- runtime snapshots and terminal run records reconcile under explicit canonical rules
- orchestration analytics tests pass

Notes:
- keep operational OATS persistence file-based
- focus on analytical ingestion and serving, not a storage format rewrite

Validation override:
- uv run --group dev pytest -q tests/oats/test_prefect_flows.py tests/test_api_prefect_orchestration.py

### frontend_simplification
Title: T006 Frontend Removal Of Authoritative Business Logic
Depends on: warehouse_authority_cutover, orchestration_analytics

Remove authoritative business calculations from the frontend once backend contracts are stable. Consume backend-owned analytics and status fields, reduce duplicated cost logic, and tighten transport normalization where the backend is now explicit.

Acceptance criteria:
- frontend no longer computes authoritative analytics cost figures independently
- orchestration and analytics views consume backend-owned status and analytics fields
- known unsound required fields are removed or intentionally supplied
- frontend normalization and rendering tests pass

Notes:
- keep rendering and interaction logic intact
- do not reintroduce proxy masking to hide backend drift

Validation override:
- node --import tsx --test src/lib/client/normalize.test.ts src/lib/client/prefect-normalize.test.ts
- npm run lint -- src/components/orchestration src/components/analytics src/lib/client src/hooks

### near_realtime_polish
Title: T007 Incremental Refresh And Near-Real-Time Polish
Depends on: warehouse_authority_cutover, operational_store_migration

Finish the near-real-time refresh path for the authoritative analytics program. Add polling or micro-batch incremental refresh behavior, tighten cache invalidation, and validate the bounded dual-read behavior for the newest slice.

Acceptance criteria:
- incremental refresh handles changed artifacts without destructive full rebuild as the normal path
- cache invalidation is targeted enough for near-real-time use
- recent-window supplementation behavior is documented and tested
- refresh-path tests pass

Notes:
- do not introduce remote deployment complexity
- keep the solution local-first and minutes-level rather than event-bus-heavy

Validation override:
- uv run --group dev pytest -q tests/test_api_database.py tests/test_api_analytics.py

### final_cutover_and_morning_handoff
Title: T008 Final Cutover, Verification, And Morning Handoff
Depends on: frontend_simplification, near_realtime_polish, orchestration_analytics
Agent: claude
Model: claude-sonnet-4-5-20250929
Reasoning effort: high

Finish the overnight program with broad verification, final docs updates, and a concrete morning handoff. Summarize completed, failed, blocked, and skipped work accurately, and leave the integration branch and PR artifacts in a reviewable state.

Acceptance criteria:
- broad validation runs and the outcome is recorded accurately
- the morning handoff distinguishes completed, failed, blocked, and skipped tasks
- the run leaves reviewable PR artifacts rather than a silent partial cutover
- docs and cutover notes reflect the implemented state

Notes:
- continue autonomously where dependency rules allow, but do not fabricate success
- if broad validation fails, preserve accurate artifacts and summarize the failure instead of discarding the night’s work

Validation override:
- uv run --group dev pytest -q tests/oats/test_run_definition_loader.py tests/test_parser.py
- uv run oats plan examples/full_program_authoritative_analytics_overnight_run.md
