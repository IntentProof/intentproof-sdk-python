from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest


def _resolve_spec_root() -> Path | None:
    env = os.environ.get("INTENTPROOF_SPEC_ROOT", "").strip()
    if env:
        p = Path(env).resolve()
        if (p / "spec.json").is_file():
            return p
    repo_root = Path(__file__).resolve().parents[2]
    sibling = (repo_root.parent / "intentproof-spec").resolve()
    if (sibling / "spec.json").is_file():
        return sibling
    return None


SPEC_ROOT = _resolve_spec_root()


@pytest.mark.skipif(SPEC_ROOT is None, reason="requires intentproof-spec checkout")
def test_generated_fingerprint_matches_pinned_spec() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert SPEC_ROOT is not None
    spec_root = SPEC_ROOT
    spec = json.loads((spec_root / "spec.json").read_text(encoding="utf-8"))
    fp = json.loads(
        (repo_root / "src" / "intentproof" / "generated" / "spec_fingerprint.json").read_text(
            encoding="utf-8"
        )
    )

    assert fp["specVersion"] == spec["version"]
    assert fp["algorithm"] == "sha256"
    assert fp["generator"]["name"] == "datamodel-code-generator"
    assert isinstance(fp["generator"]["version"], str)
    assert fp["generator"]["version"].strip()

    lines: list[str] = []
    for rel in sorted(spec["schemas"].values()):
        raw = (spec_root / rel).read_text(encoding="utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert fp["files"][rel] == digest
        lines.append(f"{rel}:{digest}")

    expected_aggregate = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    assert fp["aggregate"] == expected_aggregate
