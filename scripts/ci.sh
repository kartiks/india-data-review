#!/usr/bin/env bash
# Local CI: checks one commit (default HEAD) in a clean temporary copy, so your working folder is never touched.
# There is no CI on GitHub: run it on a branch before merging it into main:
#
#   scripts/ci.sh              # the current commit
#   scripts/ci.sh my-branch    # a branch, tag or commit (e.g. origin/main)
#
# It passes only if the Python code passes ruff (settings in ruff.toml); the workflow passes actionlint and the
# shell scripts ShellCheck; the weekly refresh's scripts pass their dry run (scripts/test-refresh.sh); for every
# area, the pipeline rebuilds data/ from the committed sources with every check passing, the rebuilt data/ matches
# what is committed (apart from the build time), and the tests pass; and the site type-checks, passes its tests (if
# it has an npm test script) and builds. It downloads no data (npm and uv may download packages).

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
REF="${1:-HEAD}"
AREAS=(budget gdp jobs-prices)
# Pinned, so a new release cannot fail a commit that passed before. actionlint-py and shellcheck-py are PyPI
# packages of the actionlint and ShellCheck binaries (their versions add a build number), run with uvx.
RUFF_VERSION=0.17.4
ACTIONLINT_VERSION=1.7.12.25  # actionlint 1.7.12
SHELLCHECK_VERSION=0.11.0.1   # ShellCheck 0.11.0

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

step "Python lint (ruff)"
(cd "$WORK" && uvx "ruff@$RUFF_VERSION" check --no-cache .)

step "Workflow and shell script lint (actionlint, shellcheck)"
# actionlint also runs shellcheck on each workflow step's script.
(cd "$WORK" && uvx --from "actionlint-py==$ACTIONLINT_VERSION" --with "shellcheck-py==$SHELLCHECK_VERSION" actionlint)
(cd "$WORK" && git ls-files -z '*.sh' | xargs -0 uvx --from "shellcheck-py==$SHELLCHECK_VERSION" shellcheck -x)

step "shared pipeline code: tests"
(cd "$WORK/shared/pipeline" && uv run --locked pytest -q)

step "Weekly refresh scripts: dry run against a local repository"
"$WORK/scripts/test-refresh.sh"

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
STRIP='s/"generated_at": ?"[^"]*"//g'
DIFFERS=()
while IFS= read -r f; do
  if ! cmp -s <(git -C "$WORK" show "HEAD:$f" | sed -E "$STRIP") <(sed -E "$STRIP" "$WORK/$f"); then
    DIFFERS+=("$f")
  fi
done < <(git -C "$WORK" diff --name-only -- "${DATA[@]}")
if [ ${#DIFFERS[@]} -gt 0 ]; then
  git -C "$WORK" diff --stat -- "${DIFFERS[@]}" >&2
  echo "data/ differs from what the pipelines build: ${DIFFERS[*]}. Run the pipelines and commit their data/." >&2
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

step "site: install, type check, tests, build"
(
  cd "$WORK/site"
  npm ci --no-audit --no-fund --loglevel=error
  npm run check
  if node -e 'process.exit(require("./package.json").scripts?.test ? 0 : 1)'; then
    # CI=true: run the tests once, never in watch mode, even from a terminal.
    CI=true npm test
  else
    echo "(no npm test script)"
  fi
  npm run build
)

printf '\nLocal CI PASSED for %s (%s)\n' "$REF" "$(git -C "$REPO" rev-parse --short "$SHA")"
