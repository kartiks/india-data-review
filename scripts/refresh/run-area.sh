#!/usr/bin/env bash
# Runs one area's refresh with a time limit, keeping its output in $LOG_DIR/<area>.log (default
# $RUNNER_TEMP/refresh-logs) for the run's artifact.
#
#   run-area.sh <area> <time limit, e.g. 30m> <command...>
#
# Exit 10 from the pipeline means every check passed but data added by hand is out of date (jobs and prices: the
# base-2024 CPI). The area is still committed, so this prints stale=true as a step output and exits 0; the
# workflow fails the run at the end. Any other exit status is passed on.

set -euo pipefail
# shellcheck source=scripts/refresh/lib.sh
. "$(dirname "$0")/lib.sh"

area="$1" limit="$2"
shift 2
log="$(log_dir)/$area.log"
mkdir -p "$(dirname "$log")"

limited=("$@")
if command -v timeout >/dev/null; then
  limited=(timeout "$limit" "$@")
else
  echo "(no timeout command here: running $area without its $limit limit)"
fi

code=0
PYTHONUNBUFFERED=1 "${limited[@]}" 2>&1 | tee "$log" || code=$?
if [ "$code" -eq 10 ]; then
  output stale true
  exit 0
fi
exit "$code"
