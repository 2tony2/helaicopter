# Run: Cleanup, OpenAPI, And Docs Research

## Tasks

### cleanup_legacy_naming
Title: T001 Remove Or Rename Legacy Surfaces

Audit the repo for `legacy` naming that is no longer accurate. Remove dead legacy-only code, and rename still-active surfaces to non-legacy names where the old naming is misleading.

Acceptance criteria:
- dead legacy-only code paths are removed
- still-active user-facing or developer-facing `legacy` names are renamed when they are no longer actually legacy
- docs and comments are updated to match the new naming
- compatibility is preserved where outright renames would break active callers without a transition

Notes:
- prioritize active Oats, legacy orchestration, orchestration, and API surfaces
- produce a short inventory of what was removed vs renamed
- do not do speculative cleanup outside names that are clearly misleading or dead

Validation override:
- uv run pytest -q tests/test_cli_runtime.py tests/test_api_orchestration.py
- npm run lint

### openapi_specs_and_sidebar
Title: T002 Generate OpenAPI Artifacts And Add API Sidebar Links

Create OpenAPI artifacts for all available APIs exposed by this repo, make those artifacts easy to inspect/download, and add them to the Next.js app sidebar API section.

Acceptance criteria:
- OpenAPI specs exist for the APIs exposed by the backend
- generated artifacts are stored in a stable repo-local location
- the Next.js app sidebar exposes links to the generated OpenAPI artifacts
- docs explain how to regenerate the specs
- artifact generation is scriptable and repeatable

Notes:
- include downloadable artifacts, not just in-memory routes
- prefer one obvious generation path over multiple competing scripts
- make the sidebar labels clear about which spec each link represents

Validation override:
- uv run pytest -q tests/test_api_bootstrap.py tests/test_api_orchestration.py tests/test_api_legacy-orchestration_orchestration.py
- npm run lint

### docs_framework_research
Title: T003 Research Documentation Framework Options

Research documentation framework options for this repo, including Sphinx, Next.js-native documentation approaches, and whatever OpenClaw is using. Produce a concrete recommendation set with tradeoffs and next-step options.

Acceptance criteria:
- research covers at least Sphinx, a Next.js-native docs path, and OpenClaw’s approach
- output includes pros/cons, migration cost, authoring ergonomics, API docs fit, and hosting fit
- output identifies one recommended default and one viable alternative
- findings are written to a repo-local document for later decision-making

Notes:
- this is a research task, not a full implementation task
- include practical fit for Helaicopter’s existing stack and repo layout
- prefer actionable recommendations over broad survey text

Validation override:
- test -f docs/documentation-framework-research.md
