#!/usr/bin/env bash
# CI-parity coverage gate for local checkpoints and manual runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
  export PATH="$ROOT/.venv/bin:$PATH"
else
  PYTHON=python3
fi

COVERAGE=()
if command -v coverage >/dev/null 2>&1; then
  COVERAGE=(coverage)
elif "$PYTHON" -m coverage --version >/dev/null 2>&1; then
  COVERAGE=("$PYTHON" -m coverage)
else
  echo "coverage CLI not found; install dev deps with: pip install -e \".[dev]\"" >&2
  exit 2
fi

"$PYTHON" -m pytest -q
"${COVERAGE[@]}" json -o coverage.json
exec bash ./scripts/check-coverage.sh coverage.json
