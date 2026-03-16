#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
container_name="${HELAICOPTER_CLICKHOUSE_CONTAINER_NAME:-helaicopter-clickhouse}"
image="${HELAICOPTER_CLICKHOUSE_IMAGE:-clickhouse/clickhouse-server:25.3}"
http_port="${HELAICOPTER_CLICKHOUSE_PORT:-8123}"
native_port="${HELAICOPTER_CLICKHOUSE_NATIVE_PORT:-9000}"
data_dir="${HELAICOPTER_CLICKHOUSE_LOCAL_DATA_DIR:-$repo_root/var/clickhouse-local/data}"
log_dir="${HELAICOPTER_CLICKHOUSE_LOCAL_LOG_DIR:-$repo_root/var/clickhouse-local/log}"
clickhouse_user="${HELAICOPTER_CLICKHOUSE_USER:-helaicopter}"
clickhouse_password="${HELAICOPTER_CLICKHOUSE_PASSWORD:-helaicopter}"

mkdir -p "$data_dir" "$log_dir"

if ! docker inspect "$container_name" >/dev/null 2>&1; then
  docker run -d \
    --name "$container_name" \
    -e "CLICKHOUSE_USER=${clickhouse_user}" \
    -e "CLICKHOUSE_PASSWORD=${clickhouse_password}" \
    -e "CLICKHOUSE_DB=default" \
    -p "${http_port}:8123" \
    -p "${native_port}:9000" \
    -v "${data_dir}:/var/lib/clickhouse" \
    -v "${log_dir}:/var/log/clickhouse-server" \
    "$image" >/dev/null
elif [ "$(docker inspect -f '{{.State.Running}}' "$container_name")" != "true" ]; then
  docker start "$container_name" >/dev/null
fi

export HELAICOPTER_CLICKHOUSE_HOST="${HELAICOPTER_CLICKHOUSE_HOST:-127.0.0.1}"
export HELAICOPTER_CLICKHOUSE_PORT="$http_port"
export HELAICOPTER_CLICKHOUSE_NATIVE_PORT="$native_port"
export HELAICOPTER_CLICKHOUSE_USER="$clickhouse_user"
export HELAICOPTER_CLICKHOUSE_PASSWORD="$clickhouse_password"

cd "$repo_root"

uv run python -m helaicopter_db.clickhouse_bootstrap --wait-for-ready "$@"
