# Run: ty Cutover And CI Reliability

This run spec operationalizes `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-19-ty-cutover-ci-reliability.md` as six OATS tasks executed through Prefect. Treat that implementation plan as authoritative for file scope, exact verification commands, and sequencing details.

## Tasks

### contract_flip
Title: T001 Replace pyright Contracts With ty

Implement Task 1 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-19-ty-cutover-ci-reliability.md`.

Rewrite the repository contracts around `ty`: update `pyproject.toml`, `.github/workflows/backend-quality.yml`, `docs/python-backend-type-system-baseline.md`, `tests/test_backend_type_system_rollout.py`, and `uv.lock`; remove the stale `pyright` baseline JSON; and make sure the guardrail tests describe `ty` as the only required type checker over all `python/**`.

Acceptance criteria:
- `pyright` is removed from the active repo contract surface
- `ty` is configured as the required type checker
- the baseline doc and workflow both describe the widened `python/**` scope
- the updated guardrail test passes
- the widened `ty` command is run once after the contract flip to confirm the remaining backlog

Notes:
- follow Task 1 in the implementation plan exactly, including the `ty.toml` fallback contingency if `pyproject.toml` cannot express the needed `ty` configuration cleanly
- rewrite every `pyright`-specific assertion in `tests/test_backend_type_system_rollout.py`, including the later wave-ten baseline assertions
- do not start fixing the wider `ty` backlog in this task beyond what is required to make the contract flip coherent

Validation override:
- uv run --group dev pytest -q tests/test_backend_type_system_rollout.py
- uv run --group dev ty check python --output-format concise --error-on-warning

### hygiene_blockers
Title: T002 Clear Initial Ruff And Server-Side ty Blockers
Depends on: contract_flip

Implement Task 2 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-19-ty-cutover-ci-reliability.md`.

Remove the currently reproduced low-risk blockers: unused imports, the missing `RunRuntimeState` import, the Prefect port `tags` inference issue, stale `type: ignore` comments in `server/dependencies.py`, and the FastAPI middleware typing mismatch in `server/main.py`.

Acceptance criteria:
- the initial `ruff` failures are removed
- the narrow `ty` failures in the Prefect port and FastAPI server files are removed
- the FastAPI smoke/bootstrap tests still pass

Notes:
- keep this task focused on the hygiene and server wiring fixes from the plan
- preserve runtime behavior; only make the smallest typing-safe change that satisfies `ty`

Validation override:
- uv run --group dev pytest -q tests/test_api_bootstrap.py tests/test_api_smoke.py
- uv run --group dev ruff check python/helaicopter_api/application/gateway.py python/helaicopter_api/application/orchestration.py python/helaicopter_api/application/prefect_orchestration.py python/helaicopter_api/ports/prefect.py python/helaicopter_api/server/dependencies.py python/helaicopter_api/server/main.py tests/oats/test_prefect_deployments.py
- uv run --group dev ty check python/helaicopter_api/ports/prefect.py python/helaicopter_api/server/dependencies.py python/helaicopter_api/server/main.py --error-on-warning

### api_type_narrowing
Title: T003 Fix API Adapter And Application ty Narrowing
Depends on: hygiene_blockers

Implement Task 3 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-19-ty-cutover-ci-reliability.md`.

Burn down the nominal-ID, literal, union-attribute, subprocess-result, and TypedDict-key diagnostics across the API adapters, application layer, bootstrap wiring, and pure conversation DAG helpers.

Acceptance criteria:
- API adapter/application modules stop passing raw `str` values into `NewType` and `Literal` boundaries
- union payloads are narrowed before member-specific attribute access
- local plan-source and Codex payload TypedDicts match the keys actually read
- the targeted API tests still pass
- `ty` passes for the API cluster

Notes:
- follow the plan’s file list and helper patterns rather than inventing a wider abstraction layer
- fix only the real diagnostics surfaced by `ty`; do not opportunistically refactor unrelated application code

Validation override:
- uv run --group dev pytest -q tests/test_api_conversations.py tests/test_api_evaluation_prompts.py tests/test_api_evaluations.py tests/test_api_orchestration.py tests/test_api_plans.py tests/test_api_analytics.py
- uv run --group dev ty check python/helaicopter_api/adapters python/helaicopter_api/application python/helaicopter_api/bootstrap python/helaicopter_api/pure --output-format concise --error-on-warning

### db_payload_alignment
Title: T004 Align Database TypedDict Payloads With Runtime Construction
Depends on: contract_flip

Implement Task 4 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-19-ty-cutover-ci-reliability.md`.

Fix the database-side TypedDict and nominal-ID diagnostics by making the declared payload shapes match the payloads the runtime actually builds, wrapping string IDs in the declared `NewType`s, and preserving TypedDict shapes during normalization.

Acceptance criteria:
- database TypedDict definitions match the keys the runtime builders populate
- helper functions in `python/helaicopter_db/utils.py` return the declared `NewType`s
- database tests still pass
- `ty` passes for the targeted DB cluster

Notes:
- follow Task 4 from the implementation plan closely
- keep casing aligned with the actual payload boundary instead of forcing mismatched internal renames

Validation override:
- uv run --group dev pytest -q tests/test_api_database.py tests/test_backend_settings.py tests/test_export_types.py
- uv run --group dev ty check python/helaicopter_api/application/database.py python/helaicopter_db/refresh.py python/helaicopter_db/status.py python/helaicopter_db/utils.py --output-format concise --error-on-warning

### oats_runtime_typing
Title: T005 Make OATS Runtime And Prefect Modules ty-Clean
Depends on: contract_flip

Implement Task 5 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-19-ty-cutover-ci-reliability.md`.

Fix the `python/oats/**` type backlog: provider and status literal narrowing, runner event TypedDicts, `SessionId`/`TaskId` wrapping, Prefect overload typing, runtime imports, and the `python/oats/runner.py` stream-handle/write diagnostics.

Acceptance criteria:
- OATS runtime modules stop assigning generic `str` where domain `Literal` or `NewType` values are declared
- runner TypedDicts match the event keys the code reads
- runner stream-handle annotations and writes satisfy `ty`
- OATS/Prefect tests still pass
- `ty` passes for `python/oats`

Notes:
- follow Task 5 from the implementation plan exactly
- use explicit annotations or casts only where they reflect the actual runtime surface, not as blanket suppression

Validation override:
- uv run --group dev pytest -q tests/test_cli_runtime.py tests/test_runner.py tests/oats/test_prefect_compiler.py tests/oats/test_prefect_flows.py tests/oats/test_prefect_tasks.py tests/oats/test_prefect_worktree.py
- uv run --group dev ty check python/oats --output-format concise --error-on-warning

### final_burndown
Title: T006 Full Repo ty Burn-Down And Final Verification
Depends on: api_type_narrowing, db_payload_alignment, oats_runtime_typing

Implement Task 6 from `/Users/tony/Code/helaicopter/docs/superpowers/plans/2026-03-19-ty-cutover-ci-reliability.md`.

Run the widened `ty` command over all `python/**`, fix any remaining diagnostics in place, then run the full lint, test, and type-check commands and verify there are no stale `pyright` references left in the active contract files.

Acceptance criteria:
- `uv run --group dev ty check python --error-on-warning` passes
- `uv run --group dev ruff check python tests` passes
- `uv run --group dev pytest -q` passes
- active contract files and source no longer reference `pyright`

Notes:
- historical mentions in old plans/specs may remain; only the active contract files named in Task 6 should be treated as blockers
- if any residual diagnostics remain after Tasks 2-5, fix only the files actually reported by the final widened `ty` run

Validation override:
- uv run --group dev ruff check python tests
- uv run --group dev pytest -q
- uv run --group dev ty check python --error-on-warning
- rg -n "pyright" pyproject.toml uv.lock .github/workflows/backend-quality.yml docs/python-backend-type-system-baseline.md tests/test_backend_type_system_rollout.py python -S
