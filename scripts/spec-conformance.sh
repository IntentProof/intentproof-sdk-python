#!/usr/bin/env bash
# Resolve the IntentProof specification checkout (directory name intentproof-spec) and run its canonical conformance oracle.
# CI checks out the spec repo explicitly; locally use a sibling clone or INTENTPROOF_SPEC_ROOT.
set -euo pipefail

sdk_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
spec_root="${INTENTPROOF_SPEC_ROOT:-}"

if [[ -z "$spec_root" ]]; then
  sibling="${sdk_root}/../intentproof-spec"
  if [[ -f "${sibling}/spec.json" && -f "${sibling}/package.json" ]]; then
    spec_root="$(cd "$sibling" && pwd)"
  fi
fi

if [[ -z "$spec_root" ]]; then
  in_repo="${sdk_root}/intentproof-spec"
  if [[ -f "${in_repo}/spec.json" && -f "${in_repo}/package.json" ]]; then
    spec_root="$(cd "$in_repo" && pwd)"
  fi
fi

if [[ -z "$spec_root" || ! -f "${spec_root}/scripts/run-conformance.sh" ]]; then
  echo "IntentProof specification checkout (intentproof-spec) not found." >&2
  echo "  Set INTENTPROOF_SPEC_ROOT, clone ../intentproof-spec beside this repo, or use ./intentproof-spec (e.g. CI checkout)." >&2
  exit 1
fi

bash "${sdk_root}/scripts/check-consumer-spec-pin.sh" "$spec_root"

export INTENTPROOF_SDK_ID="${INTENTPROOF_SDK_ID:-python}"
export INTENTPROOF_SDK_NAME="${INTENTPROOF_SDK_NAME:-intentproof-sdk-python}"
export INTENTPROOF_SDK_LANGUAGE="${INTENTPROOF_SDK_LANGUAGE:-python}"
export INTENTPROOF_SDK_VERSION="${INTENTPROOF_SDK_VERSION:-$(python3 - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)}"

exec bash "${spec_root}/scripts/run-conformance.sh" "$spec_root"
