# Changelog

Repository: [IntentProof Python SDK (`intentproof-sdk-python`)](https://github.com/intentproof/intentproof-sdk-python).

All notable changes to this repository are documented here. **PyPI** releases use SemVer for the **`intentproof-sdk`** distribution (`version` in [`pyproject.toml`](pyproject.toml)); tag releases in Git to match published versions.

## Unreleased

## 0.1.1 — 2026-05-04

- **Security:** upgrade **pip** to **≥26.1** after Python setup in the composite **`.github/actions/setup-python-pip`** action, and in the default **`[testenv]`** via **`commands_pre`**, addressing **CVE-2026-3219** and **CVE-2026-6357**.
- **CI:** add **`intentproof-spec`** job—checkout [`intentproof-spec`](https://github.com/intentproof/intentproof-spec) and run **`scripts/run-conformance.sh`** (canonical Vitest conformance oracle).
- **Local spec checks:** add **`scripts/spec-conformance.sh`** and **`tox -e spec`** (sibling **`../intentproof-spec`** or **`INTENTPROOF_SPEC_ROOT`**).
- **Docs:** add this **`CHANGELOG.md`** (aligned with the [spec repo changelog](https://github.com/intentproof/intentproof-spec/blob/main/CHANGELOG.md)); refresh **`README.md`**—positioning, pinned PyPI/GitHub install guidance, reorganized API reference tables, **`intentproof-spec`** section, vulnerability reporting link, and related edits.
- **Packaging metadata:** update **`description`** and **`keywords`** in **`pyproject.toml`**.
- **Repo layout:** remove **`.gitlab-ci.yml`** (GitLab CI mirror).

## 0.1.0 — 2026-05-04

- **`intentproof`** package: client, **`wrap`** / capture helpers, **`HttpExporter`**, correlation utilities.
- **Quality:** **tox** environments for **ruff**, pytest with a **100%** line-coverage gate, and a multi-Python (**3.11–3.14**) test matrix.
- **CI:** GitHub Actions workflows for **`pip-audit`** and **tox**; composite action to set up Python and cache **pip**/**tox** dependencies. Repository included an optional **`.gitlab-ci.yml`** mirroring those checks for GitLab.
