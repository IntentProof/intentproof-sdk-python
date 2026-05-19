# intentproof-sdk-python

Python SDK for emitting signed IntentProof execution events.

## Status

Early scaffolding repo for IntentProof's Python SDK. Tracks the
Node SDK's wrap()/exporter/outbox contract so a Python application
can emit and verify the same signed execution events.

## Development

```bash
pip install -e ".[dev]"
pytest
```

CI enforces at least 95% line coverage on `src/intentproof/` (see
`pyproject.toml` and `scripts/check-coverage.sh`).

## License

Apache License 2.0 (`LICENSE`).
