#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
REPO_ROOT=${OATS_PROJECT_ROOT:-${SCRIPT_DIR:h:h}}

export OATS_PROJECT_ROOT="${REPO_ROOT}"
export PREFECT_API_URL="${PREFECT_API_URL:-${OATS_PREFECT_API_URL:-http://127.0.0.1:4200/api}}"
export PATH="${HOME}/.local/bin:${PATH}"
cd "${REPO_ROOT}"

exec caffeinate -dimsu uv run prefect worker start --pool "${OATS_PREFECT_WORK_POOL:-local-macos}"
