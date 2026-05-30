# intentproof-sdk-python

[![CI](https://github.com/IntentProof/intentproof-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/IntentProof/intentproof-sdk-python/actions/workflows/ci.yml)

Python SDK for emitting signed IntentProof execution events.

## Who uses this

Python application authors who need the same wrap/exporter/outbox contract as
the Node and Go SDKs for signed execution events.

## Status

Early scaffolding repo for IntentProof's Python SDK. Tracks the
Node SDK's wrap()/exporter/outbox contract so a Python application
can emit and verify the same signed execution events.

## Install

```bash
pip install intentproof
```

For development in this repository:

```bash
pip install -e ".[dev]"
```

## Verify

Cross-language signing fixtures in CI match
[`intentproof-spec`](https://github.com/IntentProof/intentproof-spec) golden
vectors. Run `pytest` locally before publishing.

## Test

```bash
pytest
bash ./scripts/run-coverage-gate.sh
```

Tiered coverage: **90%** total and **95%** on `src/intentproof/` (see
`scripts/README-coverage-tiers.md`).

## Release

PyPI packages are published from maintainer release workflows in
[`intentproof-tools`](https://github.com/IntentProof/intentproof-tools) using
Sigstore-attested artifacts. See
[`docs/release-signing.md`](https://github.com/IntentProof/intentproof-tools/blob/main/docs/release-signing.md).

## Documentation hub

Per-repo README files plus
[`intentproof-infra`](https://github.com/IntentProof/intentproof-infra) for
self-host install and image verification. Docs site deferred — see
[`docs-hub-decision.md`](https://github.com/IntentProof/intentproof-infra/blob/main/docs/docs-hub-decision.md).

## Support

Report bugs, API gaps, and conformance findings via
[GitHub Issues](https://github.com/IntentProof/intentproof-sdk-python/issues).
See [`CONTRIBUTING.md`](CONTRIBUTING.md). Security reports:
[`SECURITY.md`](SECURITY.md).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and
[`TRADEMARK.md`](TRADEMARK.md).
