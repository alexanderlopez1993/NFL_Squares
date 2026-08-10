#!/usr/bin/env bash
set -euo pipefail

APP_URL="${1:-${APP_URL:-http://localhost:8000}}"
BASE_URL="${APP_URL%/}"

health_payload="$(curl -fsS "${BASE_URL}/healthz/")"
case "$health_payload" in
  *'"status": "ok"'*'"database": "ok"'*) ;;
  *)
    echo "Health check failed for ${BASE_URL}/healthz/: ${health_payload}" >&2
    exit 1
    ;;
esac

curl -fsS "${BASE_URL}/admin/login/" >/dev/null

echo "Deployment smoke check passed for ${BASE_URL}"
