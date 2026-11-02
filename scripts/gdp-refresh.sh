#!/usr/bin/env bash
# Daily GDP refresh. Runs on this Mac (scripts/gdp-refresh-schedule.sh install), or by hand at any time.
#
# MoSPI's API keeps only the latest estimate for the 2022-23 series and for quarters, so each release overwrites the
# one before. This re-downloads MoSPI's files into a clean copy of origin/main. If any changed, the old versions are
# kept under gdp/sources/snapshots/ and the change is committed; it is pushed to main only if the local CI
# (scripts/ci.sh) passes. Otherwise the commit is kept on a local branch gdp-refresh-<date>, so no download is lost.
# Your working folder is never touched. Each run ends with a macOS notification unless nothing changed.

set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="${TMPDIR:-/tmp}/india-data-review-gdp-refresh.lock"
WORK=""

notify() {
  echo "$1"
  osascript -e "display notification \"$1\" with title \"India Data Review: GDP refresh\"" >/dev/null 2>&1 || true
}
cleanup() {
  if [ -n "$WORK" ]; then git -C "$REPO" worktree remove --force "$WORK" 2>/dev/null || rm -rf "$WORK"; fi
  git -C "$REPO" worktree prune
  rmdir "$LOCK" 2>/dev/null || true
}

echo "== $(date '+%Y-%m-%d %H:%M:%S %Z')"
if ! mkdir "$LOCK" 2>/dev/null; then echo "Another refresh is running ($LOCK)."; exit 0; fi
trap cleanup EXIT

# After the Mac wakes, the network can take a minute to come back.
for try in 1 2 3 4 5; do
  git -C "$REPO" fetch --quiet origin main && break
  if [ "$try" = 5 ]; then notify "Could not reach GitHub. See ~/Library/Logs/india-data-review/gdp-refresh.log"; exit 1; fi
  sleep 60
done

WORK="$(mktemp -d "${TMPDIR:-/tmp}/india-data-review-gdp-refresh.XXXXXX")"
git -C "$REPO" worktree add --quiet --detach "$WORK" origin/main || exit 1

(cd "$WORK/gdp/pipeline" && uv run --locked python -m gdp_pipeline --refresh-nas)
refresh=$?

if [ -z "$(git -C "$WORK" status --porcelain -- gdp/sources/raw gdp/sources/snapshots)" ]; then
  if [ "$refresh" -ne 0 ]; then notify "Refresh failed with no new data. See the log."; exit 1; fi
  echo "No change in MoSPI's files."
  exit 0
fi

git -C "$WORK" status --short -- gdp/sources
git -C "$WORK" add gdp/sources gdp/data
git -C "$WORK" commit --quiet -m "GDP: MoSPI data refreshed $(date +%Y-%m-%d)" || exit 1

keep() {
  local branch="gdp-refresh-$(date +%Y-%m-%d)"
  git -C "$REPO" branch --force "$branch" "$(git -C "$WORK" rev-parse HEAD)"
  notify "MoSPI data changed but $1. Kept on local branch $branch; see the log."
  exit 1
}

[ "$refresh" -eq 0 ] || keep "a GDP check failed"
"$WORK/scripts/ci.sh" HEAD || keep "the local CI failed"

if ! git -C "$WORK" push --quiet origin HEAD:main; then
  # main moved while this ran: replay the commit on top and check again.
  git -C "$WORK" pull --quiet --rebase origin main || { git -C "$WORK" rebase --abort; keep "it could not be rebased onto main"; }
  "$WORK/scripts/ci.sh" HEAD || keep "the local CI failed after rebasing"
  git -C "$WORK" push --quiet origin HEAD:main || keep "the push to main failed"
fi
notify "MoSPI data changed: pushed to main ($(git -C "$WORK" rev-parse --short HEAD))."
