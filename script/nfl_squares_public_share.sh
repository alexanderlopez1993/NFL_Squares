#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_SCRIPT="$PROJECT_DIR/script/nfl_squares_server.sh"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/public_tunnel.log"
PID_FILE="$LOG_DIR/public_tunnel.pid"
ORIGIN_URL="http://127.0.0.1:8000"

cloudflared_bin() {
  command -v cloudflared 2>/dev/null || true
}

tunnel_pid() {
  local pid

  if [[ ! -s "$PID_FILE" ]]; then
    return 1
  fi

  pid="$(cat "$PID_FILE")"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    printf '%s\n' "$pid"
    return 0
  fi

  return 1
}

public_url() {
  if [[ -f "$LOG_FILE" ]]; then
    grep -Eo 'https://[-[:alnum:]]+\.trycloudflare\.com' "$LOG_FILE" | tail -n 1 || true
  fi
}

ensure_cloudflared() {
  if [[ -z "$(cloudflared_bin)" ]]; then
    printf 'cloudflared is not installed. Install Cloudflare Tunnel, then run this again.\n' >&2
    exit 46
  fi
}

ensure_server_running() {
  if ! "$SERVER_SCRIPT" status | grep -q '^running:'; then
    "$SERVER_SCRIPT" start
  fi
}

status_tunnel() {
  local pid
  local url

  if pid="$(tunnel_pid)"; then
    url="$(public_url)"
    printf 'running:%s:%s\n' "$pid" "${url:-starting}"
  else
    printf 'stopped::\n'
  fi
}

start_tunnel() {
  local cloudflared
  local pid
  local url

  mkdir -p "$LOG_DIR"
  if pid="$(tunnel_pid)"; then
    url="$(public_url)"
    printf 'Public share already running as PID %s.\n%s\n' "$pid" "${url:-URL is still starting.}"
    return 0
  fi

  ensure_cloudflared
  ensure_server_running
  : > "$LOG_FILE"

  cloudflared="$(cloudflared_bin)"
  nohup "$cloudflared" tunnel --url "$ORIGIN_URL" > "$LOG_FILE" 2>&1 &
  printf '%s\n' "$!" > "$PID_FILE"

  for _ in {1..20}; do
    url="$(public_url)"
    if [[ -n "$url" ]]; then
      printf 'Public share started.\n%s\n' "$url"
      return 0
    fi
    sleep 1
  done

  printf 'Public share is starting, but the URL was not ready yet. Check %s.\n' "$LOG_FILE" >&2
  exit 1
}

stop_tunnel() {
  local pid

  if ! pid="$(tunnel_pid)"; then
    : > "$PID_FILE"
    printf 'Public share is already stopped.\n'
    return 0
  fi

  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  : > "$PID_FILE"
  printf 'Public share stopped.\n'
}

open_public() {
  local url

  url="$(public_url)"
  if [[ -z "$url" ]]; then
    printf 'No public share URL is available.\n' >&2
    exit 3
  fi
  open "$url/boards/dashboard/"
}

case "${1:-status}" in
  start)
    start_tunnel
    ;;
  stop)
    stop_tunnel
    ;;
  status)
    status_tunnel
    ;;
  open)
    open_public
    ;;
  url)
    public_url
    ;;
  *)
    printf 'Usage: %s {start|stop|status|open|url}\n' "$0" >&2
    exit 64
    ;;
esac
