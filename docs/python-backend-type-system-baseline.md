# Python Backend Type-System Baseline

This document records the Wave 0 through Wave 10 backend type-system enforcement path from the 2026-03-18 master plan.

## Initial backend pyright scope

The initial advisory pyright lane is intentionally narrow. It includes only:

- `python/helaicopter_api/server`
- `python/helaicopter_api/schema`
- `python/helaicopter_api/ports`
- `python/oats/models.py`

The committed `pyproject.toml` config keeps `pythonVersion = "3.13"`, `typeCheckingMode = "strict"`, and resolves local imports through the repo `python/` source root.

## Recorded baseline

- Command: `pyright --outputjson`
- Pyright version: `1.1.407`
- Files analyzed: `24`
- Initial scoped backlog: `43 errors`
- Raw snapshot: [`docs/superpowers/baselines/2026-03-18-python-backend-pyright-baseline.json`](/Users/tony/Code/helaicopter/docs/superpowers/baselines/2026-03-18-python-backend-pyright-baseline.json)

The initial backlog was dominated by strict-mode unknown-type findings in boundary models plus missing type arguments on legacy raw payload seams. That starting snapshot remains the historical baseline for the rollout.

## Wave 0 guardrails

These guards freeze the pre-migration boundary shape so later waves cannot drift silently:

- No new family-local `_to_camel` helpers beyond the current schema files:
  - `python/helaicopter_api/schema/database.py`
  - `python/helaicopter_api/schema/evaluations.py`
  - `python/helaicopter_api/schema/orchestration.py`
  - `python/helaicopter_api/schema/subscriptions.py`
- No new public raw `dict[str, Any]` boundary seams beyond the current baseline counts:
  - `python/helaicopter_api/schema/conversations.py`: `3`
  - `python/helaicopter_api/ports/app_sqlite.py`: `4`
  - `python/helaicopter_api/ports/claude_fs.py`: `1`
- Conversation and analytics HTTP surfaces remain deferred legacy contracts in this wave. Do not change their casing behavior here.
- Do not widen the pyright include list until the current scoped backlog is green and the master plan explicitly schedules the expansion.

## Wave 10 enforcement state

The scoped backend pyright lane is now green and remains intentionally narrow.
pyright is required for the scoped backend surface.

- `ruff` is required.
- `pytest` is required.
- `pyright` is required for the scoped backend surface.

The include list is still limited to:

- `python/helaicopter_api/server`
- `python/helaicopter_api/schema`
- `python/helaicopter_api/ports`
- `python/oats/models.py`

Do not widen that required scope until the next scheduled expansion starts from this green base.

## Next scheduled pyright expansion

Next planned pyright expansion, only after this required scope stays green:

- `2026-03-25`: add `tests/` to the pyright include list and burn down that new backlog before making it required.
- `2026-04-01`: evaluate `python/helaicopter_db` for inclusion only after `tests/` is green inside CI on the still-narrow backend base.

Until those dates and prerequisites are met, keep the required scope unchanged and keep `python/helaicopter_db` outside the enforced include list.
