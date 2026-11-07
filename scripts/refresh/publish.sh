#!/usr/bin/env bash
# The publish job: pushes the refresh commit from the run's artifact (package.sh) to main, or, when the data has
# new text, to a branch with a pull request. Runs only git and gh: it installs and builds nothing, and never checks
# out the refresh commit. Run from a clone of the repository whose origin it can push to.
#
#   publish.sh <artifact folder>
#
# Environment: GITHUB_REPOSITORY (owner/name), GITHUB_SERVER_URL, GITHUB_RUN_ID, GH_TOKEN (for gh), and optionally
# RUN_URL (the run's page, for the pull request).
#
# - New text in the data (labels.md): push branch data-refresh/<date> and open a pull request listing it.
# - Otherwise push to main. If main moved after the refresh job checked the commit (it replays and re-checks the
#   commit itself if main moved during the refresh), this job cannot run the checks again, so the commit goes to a
#   branch and a pull request instead.
# - If GitHub Actions may not open pull requests (Settings > Actions > General), the branch stays and the run fails
#   with a link to compare it with main.

set -euo pipefail
# shellcheck source=scripts/refresh/lib.sh
. "$(dirname "$0")/lib.sh"

art="$1"
[ -f "$art/meta.txt" ] || { echo "::error::$art/meta.txt is missing: the refresh job did not finish packing." >&2; exit 1; }
if [ "$(meta publish "$art/meta.txt")" != true ]; then
  echo "Nothing to publish."
  exit 0
fi
base="$(meta base "$art/meta.txt")" tip="$(meta tip "$art/meta.txt")" committed="$(meta committed "$art/meta.txt")"
held="$(meta held "$art/meta.txt")" date="$(meta date "$art/meta.txt")"
repo="${GITHUB_REPOSITORY:?}" server="${GITHUB_SERVER_URL:-https://github.com}" run_id="${GITHUB_RUN_ID:-$(date +%s)}"
run_url="${RUN_URL:-$server/$repo/actions/runs/$run_id}"

# The refresh commit, from the bundle. main is fetched first: the bundle needs the commit it builds on.
git fetch --quiet --no-tags origin main
git cat-file -e "$base^{commit}" || { echo "::error::The refresh commit builds on $base, which is not on main." >&2; exit 1; }
git bundle verify --quiet "$art/refresh.bundle" >/dev/null
git fetch --quiet --no-tags "$art/refresh.bundle" "+refs/heads/data-refresh:refs/data-refresh/tip"
if [ "$(git rev-parse refs/data-refresh/tip)" != "$tip" ]; then
  echo "::error::The bundle's commit is not the one meta.txt names ($tip)." >&2
  exit 1
fi

# The refresh job ran package installs and builds, so check that what it hands over is one commit on top of base
# that changes only the committed areas' sources/ and data/.
if [ "$(git rev-list --parents -n 1 "$tip")" != "$tip $base" ]; then
  echo "::error::The bundle is not one commit on top of $base; not pushed." >&2
  exit 1
fi
outside=""
while IFS= read -r f; do
  area="${f%%/*}" rest="${f#*/}"
  case " $committed " in *" $area "*) ;; *) outside="$outside $f"; continue ;; esac
  case "$rest" in sources/* | data/*) ;; *) outside="$outside $f" ;; esac
done < <(git diff --name-only "$base" "$tip")
if [ -n "$outside" ]; then
  echo "::error::The refresh commit changes files outside the sources/ and data/ of $committed:$outside. Not pushed." >&2
  exit 1
fi

summary() { printf '%s\n' "$*" >>"${GITHUB_STEP_SUMMARY:-/dev/null}"; }

# Push the commit to a new branch and open a pull request. $1: why, as the pull request's first paragraph.
pull_request() {
  local why="$1" branch="data-refresh/$date" body url
  if git ls-remote --exit-code --heads origin "$branch" >/dev/null; then branch="$branch-$run_id"; fi
  git push --quiet origin "$tip:refs/heads/$branch"
  echo "Pushed branch $branch"
  body="$(mktemp)"
  {
    echo "$why"
    echo
    echo "Areas: $committed. Run: $run_url"
    if [ -n "$held" ]; then echo "Held back (sources changed but the refresh failed; not in this pull request): $held."; fi
    if [ -s "$art/notices.md" ]; then echo; echo "## Notices"; echo; cat "$art/notices.md"; fi
    if [ -s "$art/labels.md" ]; then
      echo
      echo "## New text in the data"
      echo
      echo "Figures, dates, months, quarters and years are left out (pipeline_common/labels.py)."
      echo
      cat "$art/labels.md"
    fi
  } >"$body"
  if [ "$(wc -c <"$body")" -gt 60000 ]; then # GitHub takes up to 65,536 characters
    head -c 60000 "$body" >"$body.cut"
    printf '\n\n… cut here: the full list is labels.md in the run'"'"'s artifact.\n' >>"$body.cut"
    mv "$body.cut" "$body"
  fi
  if url="$(gh pr create --repo "$repo" --base main --head "$branch" \
    --title "Data refresh $date: $committed" --body-file "$body")"; then
    echo "::notice::Opened $url"
    summary "Data refresh $date: pull request $url"
    return 0
  fi
  echo "::error::Could not open a pull request (if GitHub Actions may not create pull requests: Settings > Actions > General > \"Allow GitHub Actions to create and approve pull requests\"). The refresh commit is on branch $branch: open the pull request yourself from $server/$repo/compare/main...$branch?expand=1" >&2
  summary "Data refresh $date: branch $branch, no pull request: $server/$repo/compare/main...$branch?expand=1"
  return 1
}

if [ "$(meta labels_changed "$art/meta.txt")" = true ]; then
  pull_request "This weekly data refresh adds text that is not in the data on main (listed below), so it waits for review instead of going live. Its checks and the local CI passed. Merge it when the new text looks right."
  exit $?
fi

if git push --quiet origin "$tip:refs/heads/main"; then
  echo "Pushed $(git log -1 --format='%h %s' "$tip") to main"
  summary "Data refresh $date: pushed to main ($committed)"
  exit 0
fi
git fetch --quiet --no-tags origin main
if [ "$(git rev-parse origin/main)" = "$base" ]; then
  echo "::error::The push was refused or failed although main has not moved. Either main does not let github-actions[bot] push (branch protection or a ruleset that requires a pull request), or it was a network error: re-run the workflow." >&2
  exit 1
fi
echo "main moved after the refresh job checked the commit"
pull_request "main moved after this weekly data refresh was checked, so it was not pushed. Run scripts/ci.sh on this branch and merge it if it passes."
