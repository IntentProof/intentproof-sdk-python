# Changelog

Repository: [IntentProof Python SDK (`intentproof-sdk-python`)](https://github.com/IntentProof/intentproof-sdk-python).

All notable changes to this repository are documented here. **PyPI** releases use SemVer for the **`intentproof-sdk`** distribution (`version` in [`pyproject.toml`](pyproject.toml)); tag releases in Git to match published versions.

## Unreleased

- None yet.

## 0.1.3 — 2026-05-08

- **Conformance pipeline hardening:** pin to `spec-v2.0.1`, keep canonical
  spec checks green when protected branches reject push-back, and continue
  uploading conformance report/certificate artifacts for each run.
- **Cert-bot loop prevention:** skip conformance publish follow-up when the
  cert bot is the actor and ignore conformance-only root JSON pushes on
  `main`/`master` to prevent repeated CI churn.
- **CI/documentation cleanup:** tighten workflow token permissions, simplify
  publish gating conditions, and refresh README conformance guidance to match
  current spec-pinned behavior.
- **Tooling polish:** normalize formatting in schema-model generation tooling to
  keep static checks and generated diffs stable.

## 0.1.2 — 2026-05-06

- **Generated model authority:** shift wire-model ownership to
  `src/intentproof/generated` from `intentproof-spec` schemas (embedded
  normative schema dicts, fingerprint artifact, and schema validation helpers
  exported from `intentproof`).
- **Codegen/drift hardening:** add deterministic model generation and enforce
  drift policy (`generate_schema_models.py`, `verify-generated-types.sh`,
  `check-no-bundled-schema.sh`, `check-consumer-spec-pin.sh`, delegated
  `check-no-handwritten-model-types.sh`).
- **CI/release hardening:** pin spec checkout by declared `spec-commit`; add
  hardening and spec-golden-parity jobs; require no-handwritten-model checks in
  release preflight; publish conformance report artifacts with standardized SDK
  metadata.
- **Parity bootstrap fix:** install dev dependencies in
  `scripts/verify-generated-types.sh` so generated-type checks resolve
  `datamodel-code-generator` metadata in clean runners.
- **Tests/docs updates:** expand conformance and schema-validation coverage;
  update README/tox workflow docs for spec-first development.

## 0.1.1 — 2026-05-04

- **Security:** upgrade **pip** to **≥26.1** after Python setup in the composite **`.github/actions/setup-python-pip`** action, and in the default **`[testenv]`** via **`commands_pre`**, addressing **CVE-2026-3219** and **CVE-2026-6357**.
- **CI:** add **`intentproof-spec`** job—checkout [`intentproof-spec`](https://github.com/IntentProof/intentproof-spec) and run **`scripts/run-conformance.sh`** (canonical Vitest conformance oracle).
- **Local spec checks:** add **`scripts/spec-conformance.sh`** and **`tox -e spec`** (sibling **`../intentproof-spec`** or **`INTENTPROOF_SPEC_ROOT`**).
- **Docs:** add this **`CHANGELOG.md`** (aligned with the [spec repo changelog](https://github.com/IntentProof/intentproof-spec/blob/main/CHANGELOG.md)); refresh **`README.md`**—positioning, pinned PyPI/GitHub install guidance, reorganized API reference tables, **`intentproof-spec`** section, vulnerability reporting link, and related edits.
- **Packaging metadata:** update **`description`** and **`keywords`** in **`pyproject.toml`**.
- **Repo layout:** remove **`.gitlab-ci.yml`** (GitLab CI mirror).

## 0.1.0 — 2026-05-04

- **`intentproof`** package: client, **`wrap`** / capture helpers, **`HttpExporter`**, correlation utilities.
- **Quality:** **tox** environments for **ruff**, pytest with a **100%** line-coverage gate, and a multi-Python (**3.11–3.14**) test matrix.
- **CI:** GitHub Actions workflows for **`pip-audit`** and **tox**; composite action to set up Python and cache **pip**/**tox** dependencies. Repository included an optional **`.gitlab-ci.yml`** mirroring those checks for GitLab.
