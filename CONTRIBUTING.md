# Contributing

Cross-repository **pins**, **`INTENTPROOF_*`** environment variables, and script naming are documented in the **[`intentproof-spec` CONTRIBUTING guide](https://github.com/IntentProof/intentproof-spec/blob/main/CONTRIBUTING.md#terminology-shared-with-sdk-repos)**.

Typical local checks (see **`tox.ini`**):

```bash
pip install "tox>=4"
tox run -e static
tox run -e cov
```

PyPI releases use **`release.yml`** (trusted publisher / OIDC). For undisclosed security issues, use [**Security**](https://github.com/IntentProof/intentproof-sdk-python/security) advisories.
