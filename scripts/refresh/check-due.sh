#!/usr/bin/env bash
# Fails the run when a release added by hand is due, or a release-due command crashed. Runs last in the refresh job,
# after the data is committed and packed, so the data is still published.
#
#   check-due.sh <name>=<exit code>...      e.g. check-due.sh budget-due=11 gdp-due=
#
# <name> is the run-area.sh name of a `python -m <area>_pipeline.due` step, whose output is in $LOG_DIR/<name>.log;
# <exit code> is that step's exit_code output (empty when it exited 0). Exit 11: something is due, and each of the
# log's "DUE: <what>: <why>. <where to add it>" lines becomes an error. Anything else non-zero: the command crashed.

set -euo pipefail
# shellcheck source=scripts/refresh/lib.sh
. "$(dirname "$0")/lib.sh"

failed=0
for pair in "$@"; do
  name="${pair%%=*}" code="${pair#*=}"
  log="$(log_dir)/$name.log"
  case "${code:-0}" in
    0) echo "$name: nothing due" ;;
    11)
      failed=1
      while IFS= read -r line; do
        echo "::error::${line#DUE: } ($name)"
      done < <(grep '^DUE: ' "$log" 2>/dev/null || echo "DUE: (no DUE: line in $log)")
      ;;
    *)
      failed=1
      echo "::error::$name crashed (exit $code): read its step's log. The data was still published; whether a release is due was not checked."
      ;;
  esac
done
if [ "$failed" -ne 0 ]; then
  echo "::error::Add each release listed above where its line says (each area's README has the steps); the next refresh then passes."
fi
exit "$failed"
