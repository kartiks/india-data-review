#!/usr/bin/env bash
# Dry run of the weekly refresh's scripts (scripts/refresh/, used by .github/workflows/data-refresh.yml) against a
# temporary local repository: commit, held-back areas, out-of-date data, releases due, push, replay when main moved,
# the pull request for new text, and the refusals. No network: origin is a local bare repository, gh is a stub on PATH, the
# local CI is a stub, and uv runs offline (the label diff needs shared/pipeline's environment, which
# `uv run --locked` in shared/pipeline sets up). scripts/ci.sh runs it; it takes a few seconds.
#
#   scripts/test-refresh.sh

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
R="$REPO/scripts/refresh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test-refresh.XXXXXX")"
trap '[ -n "${KEEP:-}" ] || rm -rf "$TMP"' EXIT

export UV_OFFLINE=1 REFRESH_DATE=2026-11-08 GITHUB_REPOSITORY=owner/repo GITHUB_SERVER_URL=https://github.example
export GITHUB_RUN_ID=42 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.com GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.com
unset GITHUB_OUTPUT GITHUB_STEP_SUMMARY GH_TOKEN

# Stubs: gh records its arguments and the pull request body; the local CI records each run.
mkdir -p "$TMP/bin"
cat >"$TMP/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >>"$STUBS/gh.log"
while [ $# -gt 0 ]; do [ "$1" = --body-file ] && cp "$2" "$STUBS/pr-body.md"; shift; done
if [ -e "$STUBS/gh-fails" ]; then echo "GitHub Actions is not permitted to create or approve pull requests" >&2; exit 1; fi
echo "https://github.example/owner/repo/pull/7"
EOF
cat >"$TMP/bin/fake-ci" <<'EOF'
#!/usr/bin/env bash
echo "ci $* on $(git log -1 --format=%s HEAD~1)" >>"$STUBS/ci.log"
[ ! -e "$STUBS/ci-fails" ]
EOF
chmod +x "$TMP/bin/gh" "$TMP/bin/fake-ci"
export PATH="$TMP/bin:$PATH" REFRESH_CI="$TMP/bin/fake-ci"

passed=0
fail() { echo "FAIL [$scenario]: $*" >&2; exit 1; }
ok() { passed=$((passed + 1)); }
expect() { # description, then a command that must succeed
  local what="$1"
  shift
  "$@" || fail "$what"
  ok
}
same() { [ "$1" = "$2" ] || fail "$3: expected '$2', got '$1'"; ok; }
has() { grep -qF -- "$2" "$1" || fail "$1 does not contain '$2'"; ok; }
lacks() { if grep -qF -- "$2" "$1"; then fail "$1 contains '$2'"; fi; ok; }
out() { sed -n "s/^$1=//p" "$S/github_output" | tail -n 1; }

write() { mkdir -p "$(dirname "$1")" && printf '%s\n' "$2" >"$1"; }

# A fresh origin with two areas, a clone of it as the refresh job's checkout ($S/work), and a clone for pushing
# other people's commits to main ($S/other).
new_scenario() {
  scenario="$1"
  S="$TMP/$scenario"
  export STUBS="$S" GITHUB_OUTPUT="$S/github_output"
  mkdir -p "$S"
  git init --quiet --bare --initial-branch=main "$S/origin.git"
  git clone --quiet "$S/origin.git" "$S/seed" 2>/dev/null
  (
    cd "$S/seed"
    write README.md "test"
    write gdp/sources/raw/nas.json '{"rows": 10}'
    write gdp/sources/manifest.json '{"nas": "a"}'
    write gdp/data/gdp.json '{"generated_at": "2026-11-01T00:00:00+00:00", "units": "₹ crore", "growth": {"2024-25": 6.5}}'
    write gdp/data/validation_report.md "# GDP: PASSED"
    write gdp/data/validation_summary.json '{"result": "PASSED"}'
    write jobs-prices/sources/raw/plfs.json '{"rows": 5}'
    write jobs-prices/data/plfs.csv $'state,year,value\nKerala,2024-25,10.5'
    write jobs-prices/data/validation_report.md "# Jobs: PASSED"
    write jobs-prices/data/validation_summary.json '{"result": "PASSED"}'
    git add -A && git commit --quiet -m "Start" && git push --quiet origin main
  )
  git clone --quiet "$S/origin.git" "$S/work"
  git clone --quiet "$S/origin.git" "$S/other"
  START="$(git -C "$S/work" rev-parse HEAD)"
}

# What the refresh steps write.
gdp_new_figures() { # a revision and a new year: figures and a period only
  write gdp/sources/raw/nas.json '{"rows": 11}'
  write gdp/sources/snapshots/2026-11-08T093000Z/nas.json '{"rows": 10}'
  write gdp/data/gdp.json '{"generated_at": "2026-11-08T00:00:00+00:00", "units": "₹ crore", "growth": {"2024-25": 6.6, "2025-26": 7.4}}'
}
jobs_new_state() { # new text: a state
  write jobs-prices/sources/raw/plfs.json '{"rows": 6}'
  write jobs-prices/data/plfs.csv $'state,year,value\nKerala,2024-25,10.5\nLadakh,2024-25,3.1'
}
jobs_downloaded() { # sources changed (the refresh then failed)
  write jobs-prices/sources/raw/plfs.json '{"rows": 6}'
}
other_commit() { # someone merges a pull request into main: $1 file, $2 content
  (cd "$S/other" && git pull --quiet origin main && write "$1" "$2" && git add -A &&
    git commit --quiet -m "Other change" && git push --quiet origin main)
}

# The refresh job after the area steps: commit, local CI, fetch main and replay, pack.
commit() { (cd "$S/work" && "$R/commit.sh" "$@") >"$S/commit.log" 2>&1 || fail "commit.sh failed: $(tail -n 5 "$S/commit.log")"; }
ci() { (cd "$S/work" && "$REFRESH_CI" HEAD); }
replay() { (cd "$S/work" && git fetch --quiet --no-tags origin main && "$R/replay.sh") >"$S/replay.log" 2>&1; }
package() { # CI_OK
  (cd "$S/work" && COMMITTED="$(out committed)" HELD="$(out held)" CI_OK="$1" ON_MAIN=true STALE=false \
    LOG_DIR="$S/logs" "$R/package.sh" "$S/artifact" gdp jobs-prices) >"$S/package.log" 2>&1 ||
    fail "package.sh failed: $(tail -n 5 "$S/package.log")"
}
# The publish job: a new clone at the commit the run started from, the artifact, and publish.sh.
publish() {
  git clone --quiet "$S/origin.git" "$S/pub"
  git -C "$S/pub" checkout --quiet --detach "$START"
  (cd "$S/pub" && "$R/publish.sh" "$S/artifact") >"$S/publish.log" 2>&1
}
origin_main() { git -C "$S/origin.git" rev-parse main; }
branch_exists() { git -C "$S/origin.git" rev-parse --verify --quiet "refs/heads/$1" >/dev/null; }

# ---------------------------------------------------------------------------------------------------------------
new_scenario quiet-week
commit gdp=success jobs-prices=success
same "$(out committed)" "" "committed"
same "$(git -C "$S/work" rev-parse HEAD)" "$START" "no commit"
package false
same "$(sed -n 's/^publish=//p' "$S/artifact/meta.txt")" false "publish"
expect "no bundle" test ! -e "$S/artifact/refresh.bundle"
has "$S/artifact/files/gdp/data/validation_report.md" "PASSED"

# ---------------------------------------------------------------------------------------------------------------
new_scenario numbers-pushed-held-back
(cd "$S/work" && gdp_new_figures && jobs_downloaded)
commit gdp=success jobs-prices=failure
same "$(out committed)" gdp "committed"
same "$(out held)" jobs-prices "held"
has "$S/commit.log" "::warning::jobs-prices: sources changed but the refresh failed"
same "$(git -C "$S/work" log -1 --format=%s)" "Data refresh 2026-11-08: gdp" "commit message"
same "$(git -C "$S/work" diff --name-only HEAD~1 HEAD | tr '\n' ' ')" \
  "gdp/data/gdp.json gdp/sources/raw/nas.json gdp/sources/snapshots/2026-11-08T093000Z/nas.json " "committed files"
ci
replay
same "$(out moved)" false "moved"
same "$(wc -l <"$S/ci.log" | tr -d ' ')" 1 "local CI runs"
package true
same "$(out publish)" true "publish"
same "$(out labels_changed)" false "labels_changed"
expect "no labels.md" test ! -e "$S/artifact/labels.md"
has "$S/artifact/files/jobs-prices/sources/raw/plfs.json" '"rows": 6'
expect "committed files are in the bundle, not files/" test ! -e "$S/artifact/files/gdp/sources/raw/nas.json"
publish || fail "publish: $(cat "$S/publish.log")"
same "$(origin_main)" "$(git -C "$S/work" rev-parse HEAD)" "origin main"
has "$S/publish.log" "Pushed"
expect "gh not called" test ! -e "$S/gh.log"

# ---------------------------------------------------------------------------------------------------------------
new_scenario out-of-date-and-notices
mkdir -p "$S/logs"
code=0
LOG_DIR="$S/logs" "$R/run-area.sh" jobs-prices 5m bash -c 'echo "::notice::A new release is due"; echo "FAIL: out of date: CPI 2026-09" >&2; exit 10' \
  >"$S/run.log" || code=$?
same "$code" 0 "exit 10 passes"
same "$(out stale)" true "stale"
has "$S/logs/jobs-prices.log" "FAIL: out of date"
code=0
LOG_DIR="$S/logs" "$R/run-area.sh" gdp 5m bash -c 'echo checks failed; exit 3' >"$S/run.log" || code=$?
same "$code" 3 "other exit statuses are passed on"
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
package true
has "$S/artifact/notices.md" "- ::notice::A new release is due"
has "$S/artifact/notices.md" "- FAIL: out of date: CPI 2026-09"
has "$S/artifact/logs/gdp.log" "checks failed"

new_scenario release-due
mkdir -p "$S/logs"
code=0
LOG_DIR="$S/logs" "$R/run-area.sh" budget-due 5m bash -c 'echo "ok: budget 2026-27 is in"; echo "WARNING: slow" >&2
  echo "DUE: Union Budget 2027-28: it is on indiabudget.gov.in. budget/README.md, Adding a new budget"; exit 11' \
  >"$S/run.log" || code=$?
same "$code" 11 "a due release fails its step"
same "$(out exit_code)" 11 "exit_code"
code=0
LOG_DIR="$S/logs" "$R/run-area.sh" gdp-due 5m bash -c 'echo Traceback >&2; exit 1' >"$S/run.log" || code=$?
same "$code" 1 "a crash fails its step"
same "$(out exit_code)" 1 "exit_code"
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
replay
package true
same "$(out publish)" true "a due release does not hold back the data"
has "$S/artifact/notices.md" "- DUE: Union Budget 2027-28: it is on indiabudget.gov.in."
lacks "$S/artifact/notices.md" "ok: budget"
code=0
LOG_DIR="$S/logs" "$R/check-due.sh" budget-due=11 gdp-due=1 >"$S/due.log" || code=$?
same "$code" 1 "check-due fails the run"
has "$S/due.log" "::error::Union Budget 2027-28: it is on indiabudget.gov.in. budget/README.md, Adding a new budget (budget-due)"
has "$S/due.log" "::error::gdp-due crashed (exit 1)"
has "$S/artifact/notices.md" "- WARNING: slow" # a probe that could not tell is shown
has "$S/package.log" "::warning::slow"
LOG_DIR="$S/logs" "$R/check-due.sh" budget-due= gdp-due=0 >"$S/due.log" || fail "nothing due should pass"
ok
has "$S/due.log" "budget-due: skipped (did not run)"
has "$S/due.log" "gdp-due: nothing due"

# ---------------------------------------------------------------------------------------------------------------
new_scenario main-moved-during-refresh
(cd "$S/work" && gdp_new_figures && jobs_downloaded)
commit gdp=success jobs-prices=failure
ci
other_commit README.md "changed by a pull request"
replay || fail "replay: $(cat "$S/replay.log")"
same "$(out moved)" true "moved"
same "$(tail -n 1 "$S/ci.log")" "ci HEAD on Other change" "local CI runs again on top of the new main"
has "$S/work/jobs-prices/sources/raw/plfs.json" '"rows": 6' # the held-back download survives the rebase
package true
publish || fail "publish: $(cat "$S/publish.log")"
same "$(git -C "$S/origin.git" log -1 --format=%s main)" "Data refresh 2026-11-08: gdp" "main"
same "$(git -C "$S/origin.git" log -1 --format=%s main~1)" "Other change" "main~1"

new_scenario replay-conflict
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
other_commit gdp/data/gdp.json '{"edited": "by hand"}'
if replay; then fail "replay should fail on a conflict"; fi
has "$S/replay.log" "does not apply on top of main"
expect "rebase aborted" test ! -d "$S/work/.git/rebase-merge"

# ---------------------------------------------------------------------------------------------------------------
new_scenario main-moved-after-check
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
replay
package true
other_commit README.md "changed by a pull request"
moved_main="$(origin_main)"
publish || fail "publish: $(cat "$S/publish.log")"
same "$(origin_main)" "$moved_main" "main is not changed"
expect "branch pushed" branch_exists data-refresh/2026-11-08
has "$S/gh.log" "gh pr create --repo owner/repo --base main --head data-refresh/2026-11-08"
has "$S/pr-body.md" "main moved after this weekly data refresh was checked"

new_scenario push-refused
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
replay
package true
write "$S/origin.git/hooks/pre-receive" $'#!/usr/bin/env bash\ngrep -q " refs/heads/main$" && { echo "protected" >&2; exit 1; }\nexit 0'
chmod +x "$S/origin.git/hooks/pre-receive"
if publish; then fail "publish should fail when main refuses the push"; fi
has "$S/publish.log" "The push was refused or failed although main has not moved"
same "$(origin_main)" "$START" "main is not changed"
expect "no branch" test ! -e "$S/gh.log"

# ---------------------------------------------------------------------------------------------------------------
new_scenario new-text-pull-request
write "$S/logs/gdp-due.log" "DUE: RBI monetary policy statement: the latest is 70 days old. gdp/README.md"
(cd "$S/work" && gdp_new_figures && jobs_new_state)
commit gdp=success jobs-prices=success
same "$(out committed)" "gdp jobs-prices" "committed"
replay
package true
same "$(out labels_changed)" true "labels_changed"
has "$S/artifact/labels.md" "### jobs-prices"
has "$S/artifact/labels.md" "Ladakh"
lacks "$S/artifact/labels.md" "### gdp"
publish || fail "publish: $(cat "$S/publish.log")"
same "$(origin_main)" "$START" "main is not changed"
same "$(git -C "$S/origin.git" rev-parse data-refresh/2026-11-08)" "$(git -C "$S/work" rev-parse HEAD)" "branch"
has "$S/gh.log" "--title Data refresh 2026-11-08: gdp jobs-prices"
has "$S/pr-body.md" "adds text that is not in the data on main"
has "$S/pr-body.md" "  - \`Ladakh\`"
has "$S/pr-body.md" "- DUE: RBI monetary policy statement: the latest is 70 days old."

new_scenario new-text-no-pull-requests-allowed
(cd "$S/work" && jobs_new_state)
commit gdp=success jobs-prices=success
replay
package true
git -C "$S/other" push --quiet origin "HEAD:refs/heads/data-refresh/2026-11-08" # an earlier run's branch
touch "$S/gh-fails"
if publish; then fail "publish should fail when no pull request can be opened"; fi
same "$(git -C "$S/origin.git" rev-parse data-refresh/2026-11-08-42)" "$(git -C "$S/work" rev-parse HEAD)" "branch"
has "$S/publish.log" "https://github.example/owner/repo/compare/main...data-refresh/2026-11-08-42?expand=1"
same "$(origin_main)" "$START" "main is not changed"

# ---------------------------------------------------------------------------------------------------------------
new_scenario ci-failed
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
package false
same "$(out publish)" false "publish"
git -C "$S/work" bundle verify --quiet "$S/artifact/refresh.bundle" >/dev/null 2>&1 || fail "no bundle in the artifact"
ok
publish
has "$S/publish.log" "Nothing to publish"
same "$(origin_main)" "$START" "main is not changed"

new_scenario commit-outside-data-refused
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
(cd "$S/work" && write scripts/evil.sh "curl evil" && git add -A && git commit --quiet --amend --no-edit)
replay
package true
if publish; then fail "publish should refuse a commit outside sources/ and data/"; fi
has "$S/publish.log" "changes more than plain files in the sources/ and data/ of gdp: scripts/evil.sh"
same "$(origin_main)" "$START" "main is not changed"

# The publish job trusts nothing from the refresh job but the commit, and checks that.
amend() { (cd "$S/work" && "$@" && git add -A && git commit --quiet --amend --no-edit); }
set_meta() { sed "s/^$1=.*/$1=$2/" "$S/artifact/meta.txt" >"$S/meta" && mv "$S/meta" "$S/artifact/meta.txt"; }
refused() { # what the error must say
  if publish; then fail "publish should refuse: $1"; fi
  has "$S/publish.log" "$1"
  same "$(origin_main)" "$START" "main is not changed"
  expect "no pull request" test ! -e "$S/gh.log"
}

new_scenario rename-into-data-refused
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
amend git mv README.md gdp/data/readme.txt # would delete README.md
replay
package true
refused "and data/ of gdp: README.md"

new_scenario symlink-refused
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
amend ln -s ../../README.md gdp/data/linked.json
replay
package true
refused "gdp/data/linked.json(mode 120000)"

new_scenario executable-refused
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
amend bash -c 'printf "#!/bin/sh\n" >gdp/sources/raw/run.sh && chmod +x gdp/sources/raw/run.sh'
replay
package true
refused "gdp/sources/raw/run.sh(mode 100755)"

new_scenario area-not-refreshed-refused
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
amend write budget/data/fiscal.json '{"changed": true}'
replay
package true
set_meta committed "gdp budget"
refused "'budget' is not an area the weekly refresh commits (gdp jobs-prices)"

new_scenario base-not-on-main-refused
(cd "$S/work" && write gdp/sources/manifest.json '{"nas": "b"}' && git add -A && git commit --quiet -m "Not on main" &&
  git push --quiet origin HEAD:refs/heads/elsewhere)
(cd "$S/work" && gdp_new_figures)
commit gdp=success jobs-prices=success
package true
refused "which is neither main nor a commit in main's history"

new_scenario labels-worked-out-by-publish
(cd "$S/work" && jobs_new_state)
commit gdp=success jobs-prices=success
replay
package true
set_meta labels_changed false # the artifact says no new text; publish works it out itself
publish || fail "publish: $(cat "$S/publish.log")"
same "$(origin_main)" "$START" "main is not changed"
has "$S/pr-body.md" "  - \`Ladakh\`"

echo "Refresh scripts dry run: $passed checks passed"
