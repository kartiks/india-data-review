#!/usr/bin/env bash
# If main moved while the refresh ran (a pull request was merged), replays the refresh commit (HEAD) on top of
# origin/main and runs the local CI on it again. Fetch origin/main first; this runs no git command that needs a
# token. Step output: moved (true or false). Run from the repository's top folder.
#
# REFRESH_CI replaces scripts/ci.sh (the dry-run test uses it).

set -euo pipefail
# shellcheck source=scripts/refresh/lib.sh
. "$(dirname "$0")/lib.sh"

ci="${REFRESH_CI:-$(dirname "$0")/../ci.sh}"

if [ "$(git rev-parse origin/main)" = "$(git rev-parse HEAD~1)" ]; then
  echo "main has not moved"
  output moved false
  exit 0
fi
echo "main moved while this ran: replaying the refresh commit on top of it"
output moved true
# --autostash sets aside the files of an area that was not committed (its rebuilt data and manifest, or downloads
# held back).
git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  rebase --autostash origin/main || {
  git rebase --abort || true
  echo "::error::The refresh commit does not apply on top of main; nothing is pushed (see the run's artifact)." >&2
  exit 1
}
"$ci" HEAD
