#!/usr/bin/env bash
# Local CI: checks one commit (default HEAD) in a clean temporary copy, so your working folder is never touched.
# Run it on a PR's branch before merging:
#
#   scripts/ci.sh                         # the current commit
#   scripts/ci.sh gdp-scheduled-refresh   # a branch, tag or commit
#
# It passes only if, for every area, the pipeline rebuilds data/ from the committed sources with every check
# passing, the rebuilt data/ matches what is committed (apart from the build time), and the tests pass; and the
# site type-checks and builds. It downloads no data (npm and uv may download packages).

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
REF="${1:-HEAD}"
AREAS=(budget gdp jobs-prices)

SHA="$(git -C "$REPO" rev-parse --verify "$REF^{commit}")"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/india-data-review-ci.XXXXXX")"
cleanup() {
  git -C "$REPO" worktree remove --force "$WORK" 2>/dev/null || rm -rf "$WORK"
  git -C "$REPO" worktree prune
}
trap cleanup EXIT

step() { printf '\n== %s\n' "$*"; }

echo "Local CI for $REF ($(git -C "$REPO" log -1 --format='%h %s' "$SHA"))"
git -C "$REPO" worktree add --quiet --detach "$WORK" "$SHA"

for area in "${AREAS[@]}"; do
  pkg="${area//-/_}_pipeline"
  step "$area: build data and run every check"
  (cd "$WORK/$area/pipeline" && uv run --locked python -m "$pkg")
  step "$area: tests"
  (cd "$WORK/$area/pipeline" && uv run --locked pytest -q)
done

step "Committed data matches the sources (build time aside)"
DATA=() SOURCES=()
for area in "${AREAS[@]}"; do DATA+=("$area/data"); SOURCES+=("$area/sources"); done
# Each build writes its time into "generated_at" (some files are one line of compact JSON), so compare every
# rebuilt file with the committed one after removing that field from both.
STRIP='s/"generated_at": ?"[^"]*"//'
DIFFERS=""
for f in $(git -C "$WORK" diff --name-only -- "${DATA[@]}"); do
  if ! cmp -s <(git -C "$WORK" show "HEAD:$f" | sed -E "$STRIP") <(sed -E "$STRIP" "$WORK/$f"); then
    DIFFERS="$DIFFERS $f"
  fi
done
if [ -n "$DIFFERS" ]; then
  git -C "$WORK" diff --stat -- $DIFFERS >&2
  echo "data/ differs from what the pipelines build:$DIFFERS. Run the pipelines and commit their data/." >&2
  exit 1
fi
if ! git -C "$WORK" diff --quiet -- "${SOURCES[@]}"; then
  git -C "$WORK" diff --stat -- "${SOURCES[@]}" >&2
  echo "Building changed committed files in sources/; the pipelines must not change their sources offline." >&2
  exit 1
fi
NEW="$(git -C "$WORK" ls-files --others --exclude-standard -- "${DATA[@]}" "${SOURCES[@]}")"
if [ -n "$NEW" ]; then
  echo "$NEW" >&2
  echo "The pipelines wrote files that are not committed." >&2
  exit 1
fi

step "site: install, type check, build"
(cd "$WORK/site" && npm ci --no-audit --no-fund --loglevel=error && npm run check && npm run build)

printf '\nLocal CI PASSED for %s (%s)\n' "$REF" "$(git -C "$REPO" rev-parse --short "$SHA")"
