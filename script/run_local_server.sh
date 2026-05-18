#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/Library/Frameworks/Python.framework/Versions/3.14/bin/python3}"

cd "$PROJECT_DIR"
exec env \
  USE_SQLITE=True \
  ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1,.trycloudflare.com}" \
  "$PYTHON_BIN" manage.py runserver 127.0.0.1:8000 --noreload
