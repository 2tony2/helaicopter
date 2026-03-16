#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TICKETS_DIR="$ROOT_DIR/docs/codex-rollout"
LOG_DIR="$ROOT_DIR/var/codex-rollout"

START_AT=1
END_AT=999
BASE_BRANCH=""
MODEL=""
MERGE_STRATEGY="squash"
ENABLE_SEARCH=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/run-codex-rollout.sh [options]

Sequentially runs tracked ticket prompts through Codex CLI, then commits, pushes,
opens a PR, and merges it back to the repo default branch.

Options:
  --start-at N         Start at ticket number N
  --end-at N           Stop after ticket number N
  --base-branch NAME   Override the detected base branch
  --model NAME         Pass a specific model to codex exec
  --merge-strategy S   One of: squash, merge, rebase (default: squash)
  --search             Enable Codex web search for ticket runs
  --dry-run            Print actions without executing Codex/GitHub mutations
  -h, --help           Show this help
EOF
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

detect_base_branch() {
  if [[ -n "$BASE_BRANCH" ]]; then
    printf '%s\n' "$BASE_BRANCH"
    return
  fi

  local remote_head
  remote_head="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
  if [[ -n "$remote_head" ]]; then
    printf '%s\n' "${remote_head#origin/}"
    return
  fi

  remote_head="$(git remote show origin 2>/dev/null | sed -n '/HEAD branch/s/.*: //p' | head -n 1)"
  if [[ -n "$remote_head" ]]; then
    printf '%s\n' "$remote_head"
    return
  fi

  if git show-ref --verify --quiet refs/heads/main; then
    printf 'main\n'
    return
  fi

  if git show-ref --verify --quiet refs/heads/master; then
    printf 'master\n'
    return
  fi

  fail "Could not determine the base branch."
}

ensure_clean_tree() {
  local status
  status="$(git status --porcelain)"
  if [[ -n "$status" ]]; then
    fail "Working tree is not clean. Commit or stash changes before running the rollout."
  fi
}

ticket_number() {
  local ticket_file="$1"
  local name
  name="$(basename "$ticket_file")"
  name="${name#ticket-}"
  printf '%s\n' "${name%%-*}"
}

ticket_title() {
  local ticket_file="$1"
  sed -n '1s/^# //p' "$ticket_file"
}

commit_title() {
  local title="$1"
  printf '%s\n' "$title" | sed -E 's/^Ticket [0-9]+: //'
}

pr_body_file() {
  local output_file="$1"
  local ticket_rel="$2"
  local title="$3"
  cat >"$output_file" <<EOF
Automated Codex rollout for \`$title\`.

Source ticket: \`$ticket_rel\`

Runner: \`scripts/run-codex-rollout.sh\`
Mode: \`codex exec --dangerously-bypass-approvals-and-sandbox\`
EOF
}

merge_pr() {
  local pr_ref="$1"
  local strategy_flag

  case "$MERGE_STRATEGY" in
    squash) strategy_flag="--squash" ;;
    merge) strategy_flag="--merge" ;;
    rebase) strategy_flag="--rebase" ;;
    *) fail "Unsupported merge strategy: $MERGE_STRATEGY" ;;
  esac

  if gh pr merge "$pr_ref" "$strategy_flag" --delete-branch; then
    return
  fi

  echo "Direct merge failed; attempting auto-merge for $pr_ref" >&2
  gh pr merge "$pr_ref" "$strategy_flag" --auto --delete-branch
}

wait_for_merged_pr() {
  local pr_ref="$1"
  local waited=0
  local timeout_seconds=1800
  local poll_seconds=15
  local state=""

  while (( waited <= timeout_seconds )); do
    state="$(gh pr view "$pr_ref" --json state -q .state 2>/dev/null || true)"
    if [[ "$state" == "MERGED" ]]; then
      return
    fi
    sleep "$poll_seconds"
    waited=$((waited + poll_seconds))
  done

  fail "Timed out waiting for PR to merge: $pr_ref"
}

run_ticket() {
  local base_branch="$1"
  local ticket_file="$2"
  local number title clean_title branch_name ticket_rel ticket_log last_message_file pr_body_tmp

  number="$(ticket_number "$ticket_file")"
  title="$(ticket_title "$ticket_file")"
  [[ -n "$title" ]] || fail "Could not parse ticket title from $ticket_file"

  clean_title="$(commit_title "$title")"
  branch_name="codex/$(printf '%02d' "$number")-$(slugify "$clean_title")"
  ticket_rel="${ticket_file#$ROOT_DIR/}"
  ticket_log="$LOG_DIR/ticket-${number}.log"
  last_message_file="$LOG_DIR/ticket-${number}-last-message.txt"
  pr_body_tmp="$LOG_DIR/ticket-${number}-pr-body.md"

  echo
  echo "==> Ticket $number: $clean_title"
  echo "    Branch: $branch_name"

  git checkout "$base_branch" >/dev/null
  git pull --ff-only origin "$base_branch"
  git checkout -B "$branch_name" "$base_branch" >/dev/null

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY RUN: would execute Codex for $ticket_rel"
    return
  fi

  local -a codex_cmd
  codex_cmd=(
    codex exec
    --dangerously-bypass-approvals-and-sandbox
    -C "$ROOT_DIR"
    -o "$last_message_file"
  )

  if [[ "$ENABLE_SEARCH" -eq 1 ]]; then
    codex_cmd+=(--search)
  fi

  if [[ -n "$MODEL" ]]; then
    codex_cmd+=(-m "$MODEL")
  fi

  if ! "${codex_cmd[@]}" - <"$ticket_file" | tee "$ticket_log"; then
    fail "Codex failed for ticket $number. See $ticket_log"
  fi

  if [[ "$(git rev-parse --abbrev-ref HEAD)" != "$branch_name" ]]; then
    fail "Branch changed unexpectedly while running ticket $number."
  fi

  if [[ -n "$(git status --porcelain)" ]]; then
    git add -A
    if [[ -n "$(git diff --cached --name-only)" ]]; then
      git commit -m "$clean_title"
    fi
  fi

  if [[ "$(git rev-list --count "${base_branch}..HEAD")" -eq 0 ]]; then
    fail "Ticket $number produced no commits ahead of $base_branch."
  fi

  git push -u origin "$branch_name"

  pr_body_file "$pr_body_tmp" "$ticket_rel" "$title"
  local pr_url
  pr_url="$(
    gh pr create \
      --base "$base_branch" \
      --head "$branch_name" \
      --title "$title" \
      --body-file "$pr_body_tmp"
  )"

  echo "    PR: $pr_url"
  merge_pr "$pr_url"
  wait_for_merged_pr "$pr_url"

  git checkout "$base_branch" >/dev/null
  git pull --ff-only origin "$base_branch"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-at)
      START_AT="$2"
      shift 2
      ;;
    --end-at)
      END_AT="$2"
      shift 2
      ;;
    --base-branch)
      BASE_BRANCH="$2"
      shift 2
      ;;
    --model)
      MODEL="$2"
      shift 2
      ;;
    --merge-strategy)
      MERGE_STRATEGY="$2"
      shift 2
      ;;
    --search)
      ENABLE_SEARCH=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
done

require_cmd git
require_cmd gh
require_cmd codex

[[ -d "$TICKETS_DIR" ]] || fail "Missing tickets directory: $TICKETS_DIR"

mkdir -p "$LOG_DIR"

gh auth status >/dev/null 2>&1 || fail "GitHub CLI is not authenticated."

BASE_BRANCH="$(detect_base_branch)"
ensure_clean_tree

mapfile -t ticket_files < <(find "$TICKETS_DIR" -maxdepth 1 -type f -name 'ticket-*.md' | sort)
[[ "${#ticket_files[@]}" -gt 0 ]] || fail "No ticket prompt files found in $TICKETS_DIR"

for ticket_file in "${ticket_files[@]}"; do
  number="$(ticket_number "$ticket_file")"
  if (( 10#$number < START_AT || 10#$number > END_AT )); then
    continue
  fi
  run_ticket "$BASE_BRANCH" "$ticket_file"
done

echo
echo "Rollout complete."
