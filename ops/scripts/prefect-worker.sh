#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export PREFECT_HOME="${PREFECT_HOME:-${REPO_ROOT}/.oats/prefect-home}"
export PREFECT_API_URL="${PREFECT_API_URL:-http://127.0.0.1:4200/api}"
export PREFECT_WORK_POOL="${PREFECT_WORK_POOL:-local-macos}"

mkdir -p "${PREFECT_HOME}" "${REPO_ROOT}/.oats/logs"

cd "${REPO_ROOT}"
exec caffeinate -dimsu \
  uv run prefect worker start --pool local-macos --name "$(hostname -s)-local-macos"
