#!/usr/bin/env bash
# Fail if this SDK's declared IntentProof spec version does not match spec.json from the checkout.
# Usage: check-sdk-spec-pin.sh /absolute/or/relative/path/to/intentproof-spec
set -euo pipefail

spec_root="$(cd "$1" && pwd)"
sdk_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "${spec_root}/spec.json" ]]; then
  echo "check-sdk-spec-pin: not a spec checkout (missing spec.json): ${spec_root}" >&2
  exit 2
fi

spec_version="$(python3 -c "import json, pathlib, sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text())['version'])" "${spec_root}/spec.json")"

declared="$(cd "$sdk_root" && python3 -c "
import tomllib
from pathlib import Path
p = Path('pyproject.toml')
data = tomllib.loads(p.read_text(encoding='utf-8'))
print(data['tool']['intentproof']['spec-version'])
")"

if [[ "$declared" != "$spec_version" ]]; then
  echo "check-sdk-spec-pin: pyproject [tool.intentproof] spec-version=${declared} but spec.json version=${spec_version}" >&2
  exit 1
fi

echo "SDK spec pin OK (${spec_version})"
