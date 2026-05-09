#!/usr/bin/env bash
# Fail if this repository's declared IntentProof spec version + commit pins do not match the spec checkout.
# Usage: check-consumer-spec-pin.sh /absolute/or/relative/path/to/intentproof-spec
set -euo pipefail

spec_root="$(cd "$1" && pwd)"
sdk_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec bash "${spec_root}/scripts/check-consumer-spec-pins.sh" "${sdk_root}" "${spec_root}"
