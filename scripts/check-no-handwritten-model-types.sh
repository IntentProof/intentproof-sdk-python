#!/usr/bin/env bash
# Wrapper: run shared no-handwritten-model/types policy from intentproof-spec.
set -euo pipefail

sdk_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
spec_root="${INTENTPROOF_SPEC_ROOT:-}"

if [[ -z "${spec_root}" ]]; then
  sibling="${sdk_root}/../intentproof-spec"
  if [[ -f "${sibling}/spec.json" ]]; then
    spec_root="$(cd "${sibling}" && pwd)"
  fi
fi

if [[ -z "${spec_root}" ]]; then
  in_repo="${sdk_root}/intentproof-spec"
  if [[ -f "${in_repo}/spec.json" ]]; then
    spec_root="$(cd "${in_repo}" && pwd)"
  fi
fi

if [[ -z "${spec_root}" ]]; then
  echo "check-no-handwritten-model-types: intentproof-spec checkout not found (set INTENTPROOF_SPEC_ROOT or clone ../intentproof-spec)" >&2
  exit 1
fi

if [[ -f "${spec_root}/scripts/check-consumer-no-handwritten-model-types.sh" ]]; then
  exec bash "${spec_root}/scripts/check-consumer-no-handwritten-model-types.sh" "${sdk_root}"
fi

# Backward compatibility for older pinned spec commits (pre-consumer script rename).
exec bash "${spec_root}/scripts/check-sdk-no-handwritten-model-types.sh" "${sdk_root}"
