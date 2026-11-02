#!/usr/bin/env bash
# Runs scripts/gdp-refresh.sh every day at 19:00 (this Mac's time) with launchd, after MoSPI's usual 16:00 IST
# release time. If the Mac is asleep then, it runs when it wakes. The job always runs the script as it is on
# origin/main, whatever branch this working folder is on.
#
#   scripts/gdp-refresh-schedule.sh install     # or reinstall after moving the repository
#   scripts/gdp-refresh-schedule.sh uninstall
#   scripts/gdp-refresh-schedule.sh status
#
# Log: ~/Library/Logs/india-data-review/gdp-refresh.log

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="in.k4tech.india-data-review.gdp-refresh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/india-data-review"
LAUNCHER="$HOME/Library/Application Support/india-data-review/gdp-refresh-launcher.sh"
DOMAIN="gui/$(id -u)"

case "${1:-}" in
  install)
    mkdir -p "$LOG_DIR" "$(dirname "$PLIST")" "$(dirname "$LAUNCHER")"
    {
      echo '#!/bin/bash'
      echo '# Written by scripts/gdp-refresh-schedule.sh: runs the GDP refresh script from origin/main.'
      echo 'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH" GIT_TERMINAL_PROMPT=0'
      printf 'REPO=%q\n' "$REPO"
      cat <<'LAUNCHER'
git -C "$REPO" fetch --quiet origin main 2>/dev/null # may fail just after waking; the refresh retries
script="$(mktemp "${TMPDIR:-/tmp}/gdp-refresh.XXXXXX")"
if ! git -C "$REPO" show origin/main:scripts/gdp-refresh.sh >"$script"; then
  rm -f "$script"
  osascript -e 'display notification "Could not read scripts/gdp-refresh.sh from origin/main." with title "India Data Review: GDP refresh"'
  exit 1
fi
/bin/bash "$script" "$REPO"
status=$?
rm -f "$script"
exit $status
LAUNCHER
    } >"$LAUNCHER"
    chmod +x "$LAUNCHER"
    cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$LAUNCHER</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$LOG_DIR/gdp-refresh.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/gdp-refresh.log</string>
</dict>
</plist>
EOF
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Installed: daily at 19:00. Log: $LOG_DIR/gdp-refresh.log"
    echo "Run it now: launchctl kickstart $DOMAIN/$LABEL"
    ;;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST" "$LAUNCHER"
    echo "Removed."
    ;;
  status)
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E 'state|last exit|runs' || echo "Not installed."
    ;;
  *)
    echo "usage: $0 install | uninstall | status" >&2
    exit 2
    ;;
esac
