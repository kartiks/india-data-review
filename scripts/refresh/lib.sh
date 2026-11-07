# Helpers the weekly refresh's scripts share (.github/workflows/data-refresh.yml). Sourced, not run.
# shellcheck shell=bash

# A step output: appended to $GITHUB_OUTPUT on GitHub, and printed.
output() {
  local key="$1"
  shift
  printf '%s=%s\n' "$key" "$*" >>"${GITHUB_OUTPUT:-/dev/null}"
  printf '%s=%s\n' "$key" "$*"
}

# The value of key in a key=value file (meta.txt in the run's artifact). The file is read, never sourced.
meta() {
  sed -n "s/^$1=//p" "$2" | head -n 1
}

# Where run-area.sh keeps each area's output for package.sh.
log_dir() {
  printf '%s\n' "${LOG_DIR:-${RUNNER_TEMP:-/tmp}/refresh-logs}"
}

# The date a refresh is named by (India time), unless REFRESH_DATE says otherwise.
refresh_date() {
  printf '%s\n' "${REFRESH_DATE:-$(TZ=Asia/Kolkata date +%Y-%m-%d)}"
}
