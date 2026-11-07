#!/usr/bin/env bash
# Commits the areas whose sources changed and whose refresh passed, in one commit on the current branch.
#
#   commit.sh <area>=<outcome>...      e.g. commit.sh gdp=success jobs-prices=failure
#
# outcome is the area's refresh step outcome (success or failure). An area whose downloaded sources did not change
# is left alone; one whose sources changed but whose refresh failed is held back (left uncommitted, for the run's
# artifact). Step outputs: committed and held (space-separated areas). Run from the repository's top folder.

set -euo pipefail
# shellcheck source=scripts/refresh/lib.sh
. "$(dirname "$0")/lib.sh"

committed="" held=""
for pair in "$@"; do
  area="${pair%%=*}" outcome="${pair#*=}"
  if [ -z "$(git status --porcelain -- "$area/sources/raw" "$area/sources/snapshots")" ]; then
    echo "$area: no change in its sources ($outcome)"
  elif [ "$outcome" = success ]; then
    echo "$area: sources changed and every check passed"
    git status --short -- "$area/sources"
    git add -- "$area/sources" "$area/data"
    committed="$committed $area"
  else
    echo "::warning::$area: sources changed but the refresh failed; not committed (see the run's artifact)"
    held="$held $area"
  fi
done
committed="${committed# }" held="${held# }"

if [ -n "$committed" ]; then
  git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit --quiet -m "Data refresh $(refresh_date): $committed"
  git show --stat --format='%h %s' HEAD | sed -n 1,40p
fi
output committed "$committed"
output held "$held"
