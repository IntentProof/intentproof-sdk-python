# intentproof-sdk-python

[![CI](https://github.com/IntentProof/intentproof-sdk-python/actions/workflows/ci.yml/badge.svg)](https://github.com/IntentProof/intentproof-sdk-python/actions/workflows/ci.yml)

Python SDK for signing IntentProof execution events locally.

## Use

- `wrap()` / exporter / outbox aligned with the Node and Go SDKs
- Ed25519 signing and canonical JSON
- No hosted ingest required for local capture and bundle export

## Install

```bash
pip install intentproof
```

Development:

```bash
pip install -e ".[dev]"
pytest
```

Golden vectors: [`intentproof-spec`](https://github.com/IntentProof/intentproof-spec).

## Support

[GitHub Issues](https://github.com/IntentProof/intentproof-sdk-python/issues) —
see [CONTRIBUTING.md](CONTRIBUTING.md). Security reports:
`security@intentproof.io` or a private GitHub Security Advisory.

## License

MIT — see [LICENSE](LICENSE).
