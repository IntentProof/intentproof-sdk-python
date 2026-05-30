#!/usr/bin/env bash
# Regression test: absolute and relative coverage JSON paths resolve correctly.
set -euo pipefail

root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT

mkdir -p "$root/scripts"
cp "$(dirname "$0")/check-coverage.sh" "$root/scripts/"

cat >"$root/scripts/coverage-tiers.conf" <<'EOF'
TOTAL_MIN=50
CRITICAL_RULES=(
  "95:src/intentproof/"
)
EOF

cat >"$root/coverage.json" <<'EOF'
{
  "files": {
    "src/intentproof/canon.py": {
      "summary": {
        "covered_lines": 2,
        "num_statements": 2,
        "percent_covered": 100.0
      }
    }
  }
}
EOF

if ! (cd "$root" && bash scripts/check-coverage.sh coverage.json >/dev/null); then
  echo "FAIL: relative coverage.json path should pass" >&2
  exit 1
fi

if ! bash "$root/scripts/check-coverage.sh" "$root/coverage.json" >/dev/null; then
  echo "FAIL: absolute coverage.json path should pass" >&2
  exit 1
fi

echo "PASS: coverage JSON path resolution"
