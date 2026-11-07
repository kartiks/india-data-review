#!/usr/bin/env bash
# Packs what the refresh job made into the run's artifact, for the publish job (which pushes it) and for people
# (kept 90 days). Run from the repository's top folder, after commit.sh (and replay.sh).
#
#   package.sh <artifact folder> <area>...
#
# Environment: COMMITTED and HELD (commit.sh's outputs), CI_OK (true if the local CI passed on the commit, also
# after a replay), ON_MAIN (true if the run is on main), STALE (true if hand-added data is out of date: the base-2024
# CPI), and optionally LOG_DIR (run-area.sh's logs) and REFRESH_DATE.
#
# The artifact holds:
#   meta.txt        key=value lines: committed, held, base and tip (the commit before the refresh commit, and it),
#                   date, stale, labels_changed, publish (true when the publish job should push it)
#   refresh.bundle  the refresh commit (git bundle, branch data-refresh), if there is one
#   labels.md       text that is new in a committed area's data/ (pipeline_common.labels), if any
#   notices.md      DUE: lines (release-due commands), ::notice:: lines and out-of-date messages from the logs, if any
#   files/          each area's validation report and summary, and every changed file not committed (held back)
#   logs/           each area's refresh output
# Step outputs: publish, labels_changed.

set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/refresh/lib.sh
. "$here/lib.sh"

out="$1"
shift
areas=("$@")
COMMITTED="${COMMITTED:-}" HELD="${HELD:-}"
mkdir -p "$out/files" "$out/logs"

# Each area's validation report and summary, and changed files that were not committed.
paths=()
for area in "${areas[@]}"; do paths+=("$area/sources" "$area/data"); done
{
  git ls-files --modified --others --exclude-standard -- "${paths[@]}"
  for area in "${areas[@]}"; do
    for f in validation_report.md validation_summary.json; do
      [ -f "$area/data/$f" ] && echo "$area/data/$f"
    done
  done
} | sort -u | while IFS= read -r f; do
  [ -f "$f" ] || continue
  mkdir -p "$out/files/$(dirname "$f")"
  cp "$f" "$out/files/$f"
done
logs="$(log_dir)"
if [ -d "$logs" ]; then cp -R "$logs"/. "$out/logs/"; fi

base="" tip="" labels_changed=false
if [ -n "$COMMITTED" ]; then
  base="$(git rev-parse HEAD~1)" tip="$(git rev-parse HEAD)"
  git branch --force data-refresh "$tip"
  git bundle create "$out/refresh.bundle" "$base..data-refresh"
  git branch --delete --force data-refresh >/dev/null

  # Text that is new in each committed area's data/, against the commit before.
  labels="${LABELS_PROJECT:-$here/../../shared/pipeline}"
  tmp="$(mktemp -d)"
  for area in $COMMITTED; do
    mkdir -p "$tmp/$area/old" "$tmp/$area/new"
    if git cat-file -e "$base:$area/data" 2>/dev/null; then
      git archive "$base" -- "$area/data" | tar -x -C "$tmp/$area/old"
    fi
    git archive "$tip" -- "$area/data" | tar -x -C "$tmp/$area/new"
    code=0
    uv run --quiet --locked --project "$labels" python -m pipeline_common.labels \
      "$tmp/$area/old/$area/data" "$tmp/$area/new/$area/data" >"$tmp/$area.md" || code=$?
    case "$code" in
      0) ;;
      1)
        labels_changed=true
        { echo "### $area"; echo; cat "$tmp/$area.md"; echo; } >>"$out/labels.md"
        ;;
      *)
        rm -rf "$tmp"
        echo "::error::Could not compare the text in $area/data (pipeline_common.labels exit $code)." >&2
        exit 1
        ;;
    esac
  done
  rm -rf "$tmp"
  if [ "$labels_changed" = true ]; then
    echo "New text in the data (the publish job opens a pull request instead of pushing to main):"
    cat "$out/labels.md"
  fi
fi

# Notices from the areas' refresh output, for the pull request.
if [ -d "$logs" ]; then
  grep -h -e '^DUE: ' -e '^::notice' -e '^FAIL: out of date' "$logs"/*.log 2>/dev/null | sed 's/^/- /' \
    >"$out/notices.md" || true
  if [ -s "$out/notices.md" ]; then
    { echo "### Notices"; echo; cat "$out/notices.md"; } >>"${GITHUB_STEP_SUMMARY:-/dev/null}"
  else
    rm -f "$out/notices.md"
  fi
fi

publish=false
if [ -n "$COMMITTED" ] && [ "${CI_OK:-false}" = true ] && [ "${ON_MAIN:-false}" = true ]; then
  publish=true
fi
{
  echo "committed=$COMMITTED"
  echo "held=$HELD"
  echo "base=$base"
  echo "tip=$tip"
  echo "date=$(refresh_date)"
  echo "stale=${STALE:-false}"
  echo "labels_changed=$labels_changed"
  echo "publish=$publish"
} >"$out/meta.txt"
cat "$out/meta.txt"
find "$out" -type f | sed -n 1,60p
output publish "$publish"
output labels_changed "$labels_changed"
