#!/usr/bin/env bash
# Regenerate intentproof/generated and fail if the tree drifts from committed output.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
python -m pip install -e ".[dev]"
python3 scripts/generate_schema_models.py
ruff format src/intentproof/generated
git diff --exit-code -- src/intentproof/generated
if [[ -n "$(git ls-files --others --exclude-standard -- src/intentproof/generated)" ]]; then
  echo "verify-generated-types: untracked files in src/intentproof/generated after generation" >&2
  git ls-files --others --exclude-standard -- src/intentproof/generated >&2
  exit 1
fi
echo "OK: generated Python models match intentproof-spec"
