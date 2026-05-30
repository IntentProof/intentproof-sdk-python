#!/usr/bin/env bash
# Regression test: critical tiers must fail when a prefix matches nothing.
set -euo pipefail

root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT

mkdir -p "$root/scripts"
cp "$(dirname "$0")/check-coverage.sh" "$root/scripts/"

cat >"$root/scripts/coverage-tiers.conf" <<'EOF'
TOTAL_MIN=50
CRITICAL_RULES=(
  "95:src/intentproof/missing/"
)
EOF

cat >"$root/coverage.json" <<'EOF'
{
  "files": {
    "src/intentproof/canon.py": {
      "summary": {
        "covered_lines": 2,
        "num_statements": 2,
        "percent_covered": 66.66666666666666
      }
    }
  }
}
EOF

output=""
code=0
output="$(cd "$root" && bash scripts/check-coverage.sh coverage.json 2>&1)" || code=$?

if [[ "$code" -ne 1 ]]; then
  echo "FAIL: expected exit 1 for missing critical prefix, got ${code}" >&2
  echo "$output" >&2
  exit 1
fi

if ! grep -q "no statements in profile, FAIL" <<<"$output"; then
  echo "FAIL: expected critical-prefix failure message, got:" >&2
  echo "$output" >&2
  exit 1
fi

echo "PASS: missing critical prefix fails the gate"
