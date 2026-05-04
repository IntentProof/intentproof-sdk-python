#!/usr/bin/env bash
# Resolve the IntentProof specification checkout (directory name intentproof-spec) and run its canonical conformance script (Vitest oracle).
# CI checks out the spec repo explicitly; locally use a sibling clone or INTENTPROOF_SPEC_ROOT.
set -euo pipefail

sdk_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
spec_root="${INTENTPROOF_SPEC_ROOT:-}"

if [[ -z "$spec_root" ]]; then
  sibling="${sdk_root}/../intentproof-spec"
  if [[ -f "${sibling}/package.json" && -d "${sibling}/schema" ]]; then
    spec_root="$(cd "$sibling" && pwd)"
  fi
fi

if [[ -z "$spec_root" || ! -f "${spec_root}/scripts/run-conformance.sh" ]]; then
  echo "IntentProof specification checkout (intentproof-spec) not found." >&2
  echo "  Clone https://github.com/intentproof/intentproof-spec next to this repo (../intentproof-spec), or set INTENTPROOF_SPEC_ROOT to the spec checkout." >&2
  exit 1
fi

exec bash "${spec_root}/scripts/run-conformance.sh" "$spec_root"
