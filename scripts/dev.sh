#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x .venv/bin/python ]]; then
  if command -v python3.13 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.13)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
  else
    echo "Python 3.13 or newer is required." >&2
    exit 1
  fi
  "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else "Python 3.13 or newer is required.")'
  "$PYTHON" -m venv .venv
fi

if [[ ! -f requirements-dev.txt ]]; then
  echo "requirements-dev.txt is missing from the project root." >&2
  exit 1
fi

.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .

mkdir -p var
exec .venv/bin/python -m uvicorn listing_ledger.api:app --host 127.0.0.1 --port "${PORT:-8767}"
