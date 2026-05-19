#!/usr/bin/env bash

set -euo pipefail

MIN_COVERAGE="${1:-95}"

COVERAGE=()
if command -v coverage >/dev/null 2>&1; then
  COVERAGE=(coverage)
else
  for py in python python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -m coverage --version >/dev/null 2>&1; then
      COVERAGE=("$py" -m coverage)
      break
    fi
  done
fi

if [[ ${#COVERAGE[@]} -eq 0 ]]; then
  echo "coverage CLI not found; install dev deps with: pip install -e \".[dev]\"" >&2
  exit 2
fi

TOTAL_LINE="$("${COVERAGE[@]}" report --include='src/intentproof/*' | awk '/^TOTAL/{print; exit}')"
if [[ -z "$TOTAL_LINE" ]]; then
  echo "unable to read total coverage; run pytest with --cov first" >&2
  exit 2
fi

TOTAL_PERCENT="$(printf '%s' "$TOTAL_LINE" | awk '{print $NF}' | tr -d '%')"

echo "Total coverage: ${TOTAL_PERCENT}%"
echo "Minimum required: ${MIN_COVERAGE}%"

if awk -v got="$TOTAL_PERCENT" -v min="$MIN_COVERAGE" 'BEGIN { exit !(got + 0 >= min + 0) }'; then
  echo "PASS: coverage threshold met"
  exit 0
fi

echo "FAIL: coverage threshold not met" >&2
exit 1
