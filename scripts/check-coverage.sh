#!/usr/bin/env bash
# Tiered statement coverage using coverage.py JSON output.
#
# Usage: check-coverage.sh [coverage_json]
# Default: coverage.json (run pytest with --cov first)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="${ROOT}/scripts/coverage-tiers.conf"
COVERAGE_JSON_ARG="${1:-coverage.json}"

if [[ "$COVERAGE_JSON_ARG" == /* ]]; then
  COVERAGE_JSON_PATH="$COVERAGE_JSON_ARG"
else
  COVERAGE_JSON_PATH="${ROOT}/${COVERAGE_JSON_ARG}"
fi

if [[ ! -f "$CONF" ]]; then
  echo "coverage tiers config not found: $CONF" >&2
  exit 2
fi

# shellcheck disable=SC1090
source "$CONF"

if [[ -z "${TOTAL_MIN:-}" ]]; then
  echo "coverage-tiers.conf must set TOTAL_MIN" >&2
  exit 2
fi

if [[ ! -f "$COVERAGE_JSON_PATH" ]]; then
  echo "coverage json not found: $COVERAGE_JSON_PATH (run pytest with --cov first)" >&2
  exit 2
fi

rules_file="$(mktemp)"
trap 'rm -f "$rules_file"' EXIT
printf '%s\n' "${CRITICAL_RULES[@]}" >"$rules_file"

coverage_percent_display() {
  awk -v c="$1" -v t="$2" 'BEGIN {
    if (t == 0) { print "0.0"; exit }
    printf "%.1f", int(1000 * c / t) / 10
  }'
}

threshold_met() {
  awk -v c="$1" -v t="$2" -v min="$3" \
    'BEGIN { exit !(t > 0 && c * 100 >= t * min) }'
}

report_threshold() {
  local label="$1" covered="$2" total="$3" min="$4"
  local pct
  pct="$(coverage_percent_display "$covered" "$total")"
  echo "${label}: ${pct}% (${covered}/${total} statements), minimum ${min}%"
  if threshold_met "$covered" "$total" "$min"; then
    echo "  PASS"
    return 0
  fi
  echo "  FAIL" >&2
  return 1
}

stats_for_prefix() {
  local prefix="$1"
  python3 - "$COVERAGE_JSON_PATH" "$prefix" <<'PY'
import json
import sys

path = sys.argv[1]
prefix = sys.argv[2]
data = json.load(open(path))
covered = 0
total = 0

def covered_statements(summary, entry, stmts):
    if "covered_lines" in summary:
        return int(summary["covered_lines"])
    missing_lines = entry.get("missing_lines")
    if isinstance(missing_lines, list):
        return stmts - len(missing_lines)
    missing_count = summary.get("missing_lines")
    if isinstance(missing_count, int):
        return stmts - missing_count
    return 0

for file_path, entry in data.get("files", {}).items():
    if prefix not in file_path.replace("\\", "/"):
        continue
    summary = entry.get("summary", {})
    stmts = int(summary.get("num_statements", 0))
    if stmts == 0:
        continue
    total += stmts
    covered += covered_statements(summary, entry, stmts)
print(covered, total)
PY
}

read -r TOTAL_COVERED TOTAL_STMTS <<EOF
$(stats_for_prefix "")
EOF

if [[ -z "$TOTAL_STMTS" || "$TOTAL_STMTS" -eq 0 ]]; then
  echo "unable to read total coverage from $COVERAGE_JSON_PATH" >&2
  exit 2
fi

fail=0
report_threshold "Total coverage" "$TOTAL_COVERED" "$TOTAL_STMTS" "$TOTAL_MIN" || fail=1

echo "Critical tiers:"
while IFS= read -r rule; do
  [[ -n "$rule" ]] || continue
  min="${rule%%:*}"
  prefix="${rule#*:}"
  read -r c t <<EOF
$(stats_for_prefix "$prefix")
EOF
  if [[ "$t" -eq 0 ]]; then
    echo "  ${prefix} (min ${min}%): no statements in profile, FAIL" >&2
    fail=1
    continue
  fi
  report_threshold "  ${prefix}" "$c" "$t" "$min" || fail=1
done <"$rules_file"

if [[ "$fail" -ne 0 ]]; then
  echo "FAIL: coverage threshold not met" >&2
  exit 1
fi

echo "PASS: coverage thresholds met"
exit 0
