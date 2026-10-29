#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./scripts/dev.sh once to create the project environment and install dependencies." >&2
  exit 1
fi

.venv/bin/python -m pytest
.venv/bin/ruff check .
