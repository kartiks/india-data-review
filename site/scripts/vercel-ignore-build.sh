#!/usr/bin/env bash
# Vercel's "Ignored Build Step" (ignoreCommand in vercel.json). Vercel runs it from site/ before each build:
# exit 0 skips the deployment, exit 1 builds it.
#
# The site is built only from site/ and each area's data/ folder, so a commit that changes nothing there (pipeline
# code, sources, READMEs, .github/) would deploy the same pages again and store another full copy (~100 MB).
# Compare with the last commit Vercel deployed on this branch; build whenever that comparison can't be made.

set -uo pipefail

PREV="${VERCEL_GIT_PREVIOUS_SHA:-}"
if [ -z "$PREV" ]; then
  echo "Build: first deployment on this branch."
  exit 1
fi
if [ "$(git rev-parse HEAD)" = "$(git rev-parse --verify --quiet "$PREV^{commit}")" ]; then
  # Git pushes never deploy an already-deployed commit again, so this is a Redeploy someone asked for
  # (e.g. after changing an environment variable).
  echo "Build: redeploy of the last deployed commit."
  exit 1
fi
if ! git cat-file -e "$PREV^{commit}" 2>/dev/null; then
  echo "Build: the last deployed commit ($PREV) is not in Vercel's clone, so the change can't be checked."
  exit 1
fi

# site/ and every area's data/ folder (the areas are listed in src/data/areas.json).
if ! AREA_IDS="$(node -p 'require("./src/data/areas.json").map((a) => a.id).join(" ")')" || [ -z "$AREA_IDS" ]; then
  echo "Build: could not read the list of areas."
  exit 1
fi
PATHS=(.)
for id in $AREA_IDS; do PATHS+=("../$id/data"); done
git diff --quiet "$PREV" HEAD -- "${PATHS[@]}"
case $? in
  0)
    echo "Skip: nothing the site is built from changed since $PREV."
    exit 0
    ;;
  1)
    echo "Build: changed since $PREV:"
    git diff --name-only "$PREV" HEAD -- "${PATHS[@]}" | sed -n 1,20p
    exit 1
    ;;
  *)
    echo "Build: git diff failed."
    exit 1
    ;;
esac
