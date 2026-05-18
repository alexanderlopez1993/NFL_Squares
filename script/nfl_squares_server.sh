#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/local_server.log"
HOST="127.0.0.1"
PORT="8000"
APP_URL="http://$HOST:$PORT/boards/dashboard/"
KEYCHAIN_SERVICE="NFL Squares local admin"
KEYCHAIN_ACCOUNT="admin"
LAUNCH_LABEL="com.alexanderlopez.nflsquares.localserver"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
LAUNCH_AGENT_PLIST="$LAUNCH_AGENT_DIR/$LAUNCH_LABEL.plist"
RUNNER_SCRIPT="$PROJECT_DIR/script/run_local_server.sh"
PUBLIC_SHARE_SCRIPT="$PROJECT_DIR/script/nfl_squares_public_share.sh"

server_pid() {
  local pid
  local pids

  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  for pid in $pids; do
    if ps -p "$pid" -o command= | grep -q "manage.py runserver"; then
      printf '%s\n' "$pid"
      return 0
    fi
  done

  return 1
}

write_launch_agent() {
  mkdir -p "$LAUNCH_AGENT_DIR" "$LOG_DIR"
  cat > "$LAUNCH_AGENT_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LAUNCH_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$RUNNER_SCRIPT</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>StandardOutPath</key>
  <string>$LOG_FILE</string>
  <key>StandardErrorPath</key>
  <string>$LOG_FILE</string>
</dict>
</plist>
PLIST
}

require_admin_password() {
  local expected

  expected="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -a "$KEYCHAIN_ACCOUNT" -w 2>/dev/null || true)"
  if [[ -z "$expected" ]]; then
    printf 'No local admin password was found in Keychain item "%s".\n' "$KEYCHAIN_SERVICE" >&2
    exit 45
  fi

  if [[ "${NFL_SQUARES_ADMIN_PASSWORD:-}" != "$expected" ]]; then
    printf 'The local admin password did not match.\n' >&2
    exit 44
  fi
}

status_server() {
  local pid

  if pid="$(server_pid)"; then
    printf 'running:%s:%s\n' "$pid" "$APP_URL"
  else
    printf 'stopped::%s\n' "$APP_URL"
  fi
}

start_server() {
  local pid

  if pid="$(server_pid)"; then
    printf 'Server already running on %s as PID %s.\n' "$APP_URL" "$pid"
    return 0
  fi

  require_admin_password
  write_launch_agent
  launchctl bootout "gui/$UID/$LAUNCH_LABEL" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$UID" "$LAUNCH_AGENT_PLIST"
  launchctl kickstart -k "gui/$UID/$LAUNCH_LABEL"
  sleep 2

  if server_pid >/dev/null; then
    printf 'Server started on %s.\n' "$APP_URL"
  else
    printf 'Server failed to start. Last log lines:\n' >&2
    tail -n 20 "$LOG_FILE" >&2 || true
    exit 1
  fi
}

stop_server() {
  local pid

  if [[ -x "$PUBLIC_SHARE_SCRIPT" ]]; then
    "$PUBLIC_SHARE_SCRIPT" stop >/dev/null 2>&1 || true
  fi

  if ! pid="$(server_pid)"; then
    launchctl bootout "gui/$UID/$LAUNCH_LABEL" >/dev/null 2>&1 || true
    printf 'Server is already stopped.\n'
    return 0
  fi

  launchctl bootout "gui/$UID/$LAUNCH_LABEL" >/dev/null 2>&1 || true
  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  printf 'Server stopped.\n'
}

open_app() {
  if server_pid >/dev/null; then
    open "$APP_URL"
  else
    printf 'Server is stopped.\n' >&2
    exit 3
  fi
}

case "${1:-status}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  status)
    status_server
    ;;
  open)
    open_app
    ;;
  url)
    printf '%s\n' "$APP_URL"
    ;;
  *)
    printf 'Usage: %s {start|stop|status|open|url}\n' "$0" >&2
    exit 64
    ;;
esac
