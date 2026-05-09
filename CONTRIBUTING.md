# Contributing

Cross-repository **pins**, **`INTENTPROOF_*`** environment variables, and script naming are documented in the **[`intentproof-spec` CONTRIBUTING guide](https://github.com/IntentProof/intentproof-spec/blob/main/CONTRIBUTING.md#terminology-shared-with-sdk-repos)**.

Typical local checks (see **`tox.ini`**):

```bash
pip install "tox>=4"
tox run -e static
tox run -e cov
```

- **Spec Conformance** (`.github/workflows/spec-conformance.yml`): pull requests and `workflow_dispatch` — **`tox run -e static,cov`**, then **`scripts/spec-conformance.sh`**; uploads a conformance report artifact (no signing secrets).
- **Conformance Attestation** (`.github/workflows/conformance-attestation.yml`): trusted runs on **`main`**/**`master`** — same shape as **`intentproof-api`**: PEM secret checks, signed certificate, validation, artifact upload, optional cert-bot commit of root conformance JSON.

PyPI releases use **`release.yml`** (trusted publisher / OIDC). For undisclosed security issues, use [**Security**](https://github.com/IntentProof/intentproof-sdk-python/security) advisories.
