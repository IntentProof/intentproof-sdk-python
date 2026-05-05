# Changelog

Repository: [IntentProof Python SDK (`intentproof-sdk-python`)](https://github.com/IntentProof/intentproof-sdk-python).

All notable changes to this repository are documented here. **PyPI** releases use SemVer for the **`intentproof-sdk`** distribution (`version` in [`pyproject.toml`](pyproject.toml)); tag releases in Git to match published versions.

## Unreleased

- Add spec-driven generated models package under `src/intentproof/generated` (`execution_event`, `intentproof_config`, `normative_schemas`, and package exports) and switch SDK type aliases/wire paths to these generated schema models.
- Add schema validation helpers in `src/intentproof/schema_validate.py` for execution events, wrap options, and runtime config; export them from `intentproof.__init__`.
- Add deterministic codegen pipeline (`scripts/generate_schema_models.py`) that writes embedded normative schemas plus `src/intentproof/generated/spec_fingerprint.json` (spec version + per-schema/aggregate SHA-256 digests).
- Add generated artifact drift checks (`scripts/verify-generated-types.sh`) and bundled schema guard (`scripts/check-no-bundled-schema.sh`) for release hygiene.
- Add explicit no-handwritten-model policy enforcement (`scripts/check-no-handwritten-model-types.sh`) by delegating to the shared `intentproof-spec` checker, with a dedicated CI check-run (`no-handwritten-model-types`), the same step in **`tox -e static`** and release publish (parity with Node/Java), and release preflight gating on that check.
- Strengthen CI/release hardening: add `hardening` job, enforce required check-runs in release preflight, and upload canonical conformance report artifact (`conformance-report-python`).
- Improve spec-conformance wrapper (`scripts/spec-conformance.sh`) with strict spec pin verification (`scripts/check-sdk-spec-pin.sh`), standardized report metadata (`INTENTPROOF_SDK_NAME`, `INTENTPROOF_SDK_LANGUAGE`, `INTENTPROOF_SDK_VERSION`), and `./intentproof-spec` fallback when the env var and sibling clone are absent.
- Pin `datamodel-code-generator` in `pyproject.toml` for stable code generation and make generated headers deterministic (no timestamp/random temp filenames).
- Add/expand tests for spec semantics and generated artifacts: `tests/spec_semantics.py`, `tests/unit/test_spec_golden_conformance.py`, `tests/unit/test_schema_validate.py`, `tests/unit/test_generated_fingerprint.py`, with related SDK/exporter/wire test updates.
- Update docs (`README.md`) and local quality wiring (`tox.ini`) to reflect spec-first model generation, dedicated policy gating, and deduplicated CI enforcement.
- CI: **`no-handwritten-model-types`** job only checks out the SDK + spec and runs the delegated script (no **`pip install`**); **push** triggers also include **`master`** (parity with Node/Java).
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
