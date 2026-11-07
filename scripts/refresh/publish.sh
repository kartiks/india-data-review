#!/usr/bin/env bash
# The publish job: pushes the refresh commit from the run's artifact (package.sh) to main, or, when the data has
# new text, to a branch with a pull request. Runs only git and gh: it installs and builds nothing, and never checks
# out the refresh commit. Run from a clone of the repository whose origin it can push to.
#
#   publish.sh <artifact folder>
#
# Environment: GITHUB_REPOSITORY (owner/name), GITHUB_SERVER_URL, GITHUB_RUN_ID, GH_TOKEN (for gh), and optionally
# RUN_URL (the run's page, for the pull request) and PYTHON (default python3).
#
# The refresh job ran package installs and builds with a read-only token, so nothing it hands over is trusted beyond
# the commit itself, which is checked: it must be one commit on top of main or a commit in main's history, changing
# only plain files (mode 100644, or deleted) in the sources/ and data/ of areas the weekly refresh commits
# (REFRESH_AREAS, which must also be in site/src/data/areas.json). Whether its data has new text is worked out here,
# with pipeline_common.labels from this checkout run by the runner's own python3 (standard library only), not read
# from the artifact.
#
# - New text in the data: push branch data-refresh/<date> and open a pull request listing it.
# - Otherwise push to main. If main moved after the refresh job checked the commit (it replays and re-checks the
#   commit itself if main moved during the refresh), this job cannot run the checks again, so the commit goes to a
#   branch and a pull request instead.
# - If GitHub Actions may not open pull requests (Settings > Actions > General), the branch stays and the run fails
#   with a link to compare it with main.

set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/refresh/lib.sh
. "$here/lib.sh"

REFRESH_AREAS="gdp jobs-prices" # the areas data-refresh.yml refreshes and commits
refuse() {
  echo "::error::$*. Not pushed." >&2
  exit 1
}

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

# The areas committed: ones the weekly refresh commits, and areas of the site.
[ -n "$committed" ] || refuse "meta.txt names no area committed"
for area in $committed; do
  case " $REFRESH_AREAS " in *" $area "*) ;; *) refuse "'$area' is not an area the weekly refresh commits ($REFRESH_AREAS)" ;; esac
  grep -q "\"id\": *\"$area\"" "$here/../../site/src/data/areas.json" ||
    refuse "'$area' is not an area in site/src/data/areas.json"
done

# The refresh commit, from the bundle. main is fetched first: the bundle needs the commit it builds on, which must be
# main or a commit in main's history.
git fetch --quiet --no-tags origin main
if ! git cat-file -e "$base^{commit}" 2>/dev/null || ! git merge-base --is-ancestor "$base" origin/main; then
  refuse "The refresh commit builds on $base, which is neither main nor a commit in main's history"
fi
git bundle verify --quiet "$art/refresh.bundle" >/dev/null
git fetch --quiet --no-tags "$art/refresh.bundle" "+refs/heads/data-refresh:refs/data-refresh/tip"
[ "$(git rev-parse refs/data-refresh/tip)" = "$tip" ] || refuse "The bundle's commit is not the one meta.txt names ($tip)"

# One commit on top of base, changing only plain files in the committed areas' sources/ and data/. --no-renames, so
# a file moved into data/ counts as deleted where it was; --raw, for each file's new mode (no symlinks 120000,
# submodules 160000 or executables 100755).
[ "$(git rev-list --parents -n 1 "$tip")" = "$tip $base" ] || refuse "The bundle is not one commit on top of $base"
bad=""
while IFS= read -r -d '' info && IFS= read -r -d '' f; do
  mode="$(printf '%s' "$info" | cut -d ' ' -f 2)" area="${f%%/*}" rest="${f#*/}"
  case " $committed " in *" $area "*) ;; *) bad="$bad $f"; continue ;; esac
  case "$rest" in sources/?* | data/?*) ;; *) bad="$bad $f"; continue ;; esac
  case "$mode" in 100644 | 000000) ;; *) bad="$bad $f(mode $mode)" ;; esac
done < <(git diff --raw --no-renames --no-abbrev -z "$base" "$tip")
[ -z "$bad" ] || refuse "The refresh commit changes more than plain files in the sources/ and data/ of $committed:$bad"

# New text in each committed area's data/, base against tip, worked out here.
labels_md="$(mktemp)" labels_changed=false
for area in $committed; do
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/old" "$tmp/new"
  if git cat-file -e "$base:$area/data" 2>/dev/null; then git archive "$base" -- "$area/data" | tar -x -C "$tmp/old"; fi
  if git cat-file -e "$tip:$area/data" 2>/dev/null; then git archive "$tip" -- "$area/data" | tar -x -C "$tmp/new"; fi
  mkdir -p "$tmp/new/$area/data"
  code=0
  (cd "$here/../../shared/pipeline" && "${PYTHON:-python3}" -B -s -m pipeline_common.labels \
    "$tmp/old/$area/data" "$tmp/new/$area/data") >"$tmp/labels.md" || code=$?
  case "$code" in
    0) ;;
    1)
      labels_changed=true
      { echo "### $area"; echo; cat "$tmp/labels.md"; echo; } >>"$labels_md"
      ;;
    *) refuse "Could not compare the text in $area/data (pipeline_common.labels exit $code)" ;;
  esac
  rm -rf "$tmp"
done

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
    if [ -s "$labels_md" ]; then
      echo
      echo "## New text in the data"
      echo
      echo "Figures, dates, months, quarters and years are left out (pipeline_common/labels.py)."
      echo
      cat "$labels_md"
    fi
  } >"$body"
  if [ "$(wc -c <"$body")" -gt 60000 ]; then # GitHub takes up to 65,536 characters
    head -c 60000 "$body" >"$body.cut"
    printf '\n\n… cut here: the full list is in the publish job'"'"'s log.\n' >>"$body.cut"
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

if [ "$labels_changed" = true ]; then
  echo "New text in the data:"
  cat "$labels_md"
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
