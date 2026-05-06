# Changelog

Repository: [IntentProof Python SDK (`intentproof-sdk-python`)](https://github.com/IntentProof/intentproof-sdk-python).

All notable changes to this repository are documented here. **PyPI** releases use SemVer for the **`intentproof-sdk`** distribution (`version` in [`pyproject.toml`](pyproject.toml)); tag releases in Git to match published versions.

## Unreleased

- **Parity CI bootstrap fix:** `scripts/verify-generated-types.sh` now installs dev dependencies (`python -m pip install -e ".[dev]"`) before model generation so `datamodel-code-generator` metadata is present in clean CI environments.
- **Spec-generated wire models:** Add `src/intentproof/generated` (Pydantic models from intentproof-spec JSON Schemas, embedded normative schema dicts for `jsonschema`, and `spec_fingerprint.json` with spec version plus per-schema and aggregate SHA-256). Route SDK types and wire serialization through these models; add `schema_validate` helpers for execution events, wrap options, and runtime config and export them from `intentproof`.
- **Codegen and drift guards:** Add `scripts/generate_schema_models.py` with pinned `datamodel-code-generator` and deterministic generation; add `scripts/verify-generated-types.sh`, `scripts/check-no-bundled-schema.sh`, and `scripts/check-sdk-spec-pin.sh` enforcing `[tool.intentproof]` `spec-version` and `spec-commit` against the spec checkout.
- **No handwritten schema models:** `scripts/check-no-handwritten-model-types.sh` delegates to `intentproof-spec`’s shared checker (requires a spec checkout via `INTENTPROOF_SPEC_ROOT`, sibling `../intentproof-spec`, or `./intentproof-spec`). Wired into **`tox -e static`**, a dedicated CI job (`no-handwritten-model-types`) that checks out the pinned spec revision without installing the SDK, the Release workflow before build, and release preflight required check-runs.
- **CI and release:** Checkout intentproof-spec at **`pyproject.toml`** `spec-commit` across conformance and policy jobs; add **`hardening`** and **`spec-golden-parity`**; upload conformance report artifact **`conformance-report-python`**; run conformance with replay/metadata env vars; extend **push** triggers to **`master`**; release preflight requires **`no-handwritten-model-types`**, **`hardening`**, **`intentproof-spec`**, **`spec-golden-parity`**, and **`tox`** static/cov matrix successes.
- **Conformance wrapper:** `scripts/spec-conformance.sh` gains spec-pin integration, standardized SDK report metadata (`INTENTPROOF_SDK_NAME`, `INTENTPROOF_SDK_LANGUAGE`, `INTENTPROOF_SDK_VERSION`), and clearer resolution when the spec checkout path is not set.
- **Tests and docs:** Add golden JSONL conformance, spec semantics mirroring, fingerprint validation, schema validation tests, and updates to SDK/exporter/wire tests; refresh **`README.md`** and **`tox.ini`** for the spec-first workflow.

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
