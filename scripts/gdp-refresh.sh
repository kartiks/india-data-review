#!/usr/bin/env bash
# Daily GDP refresh. Runs on this Mac (scripts/gdp-refresh-schedule.sh install), or by hand at any time:
#
#   scripts/gdp-refresh.sh [path to the repository]
#
# MoSPI's API keeps only the latest estimate for the 2022-23 series and for quarters, so each release overwrites the
# one before. This re-downloads MoSPI's files into a clean copy of origin/main. If any changed, the old versions are
# kept under gdp/sources/snapshots/ and the change is committed; it is pushed to main only if the local CI
# (scripts/ci.sh, from origin/main) passes. Otherwise the commit is kept on a local branch gdp-refresh-<date>-<time>,
# so no download is lost. Your working folder is never touched. Any run that changes something or fails ends with
# a macOS notification.

set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
export GIT_TERMINAL_PROMPT=0 # never wait for a password nobody will type

REPO="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_HINT="See ~/Library/Logs/india-data-review/gdp-refresh.log"
WORK=""
LOCK=""

notify() {
  echo "$1"
  osascript -e "display notification \"$1\" with title \"India Data Review: GDP refresh\"" >/dev/null 2>&1 || true
}
fail() { notify "$1 $LOG_HINT"; exit 1; }
cleanup() {
  if [ -n "$WORK" ]; then git -C "$REPO" worktree remove --force "$WORK" 2>/dev/null || rm -rf "$WORK"; fi
  git -C "$REPO" worktree prune 2>/dev/null
  if [ -n "$LOCK" ]; then rm -rf "$LOCK"; fi
}

echo "== $(date '+%Y-%m-%d %H:%M:%S %Z')"
GIT_DIR_COMMON="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" ||
  fail "$REPO is not the India Data Review repository."

# One run at a time. The lock holds the PID of its run; a lock left by a run that was killed is cleared.
lock="$GIT_DIR_COMMON/gdp-refresh.lock"
if ! mkdir "$lock" 2>/dev/null; then
  pid="$(cat "$lock/pid" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then echo "Another refresh is running (PID $pid)."; exit 0; fi
  echo "Clearing a lock left by an earlier run."
  rm -rf "$lock"
  mkdir "$lock" || fail "Could not take the lock $lock."
fi
LOCK="$lock"
echo $$ >"$LOCK/pid"
trap cleanup EXIT

# After the Mac wakes, the network can take a minute to come back.
for try in 1 2 3 4 5; do
  git -C "$REPO" fetch --quiet origin main && break
  [ "$try" = 5 ] && fail "Could not reach GitHub."
  sleep 60
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/india-data-review-gdp-refresh.XXXXXX")"
git -C "$REPO" worktree add --quiet --detach "$WORK" origin/main || fail "Could not make a clean copy of main."

(cd "$WORK/gdp/pipeline" && uv run --locked python -m gdp_pipeline --refresh-nas)
refresh=$?

if [ -z "$(git -C "$WORK" status --porcelain -- gdp/sources/raw gdp/sources/snapshots)" ]; then
  [ "$refresh" -ne 0 ] && fail "Refresh failed; MoSPI's files are unchanged."
  echo "No change in MoSPI's files."
  exit 0
fi

git -C "$WORK" status --short -- gdp/sources
git -C "$WORK" add gdp/sources gdp/data
if ! git -C "$WORK" commit --quiet -m "GDP: MoSPI data refreshed $(date +%Y-%m-%d)"; then
  kept="$WORK"
  WORK="" # keep the folder: it holds the only copy of the new downloads
  fail "MoSPI data changed but could not be committed. The downloads are in $kept."
fi

keep() {
  local branch
  branch="gdp-refresh-$(date +%Y-%m-%d-%H%M)"
  if git -C "$REPO" branch "$branch" "$(git -C "$WORK" rev-parse HEAD)"; then
    fail "MoSPI data changed but $1. Kept on local branch $branch."
  fi
  kept="$WORK"
  WORK=""
  fail "MoSPI data changed but $1, and branch $branch could not be made. The downloads are in $kept."
}

[ "$refresh" -eq 0 ] || keep "a GDP check failed"
"$WORK/scripts/ci.sh" HEAD || keep "the local CI failed"

if ! git -C "$WORK" push --quiet origin HEAD:main; then
  base="$(git -C "$WORK" rev-parse HEAD~1)"
  git -C "$WORK" fetch --quiet origin main || keep "the push to main failed"
  # Only worth retrying if main moved while this ran: replay the commit on top and check again.
  [ "$(git -C "$WORK" rev-parse origin/main)" != "$base" ] || keep "the push to main failed"
  git -C "$WORK" rebase --quiet origin/main || { git -C "$WORK" rebase --abort; keep "it could not be rebased onto main"; }
  "$WORK/scripts/ci.sh" HEAD || keep "the local CI failed after rebasing"
  git -C "$WORK" push --quiet origin HEAD:main || keep "the push to main failed"
fi
notify "MoSPI data changed: pushed to main ($(git -C "$WORK" rev-parse --short HEAD))."
