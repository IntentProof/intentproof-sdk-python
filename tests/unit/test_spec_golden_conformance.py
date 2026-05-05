"""Parity with intentproof-spec golden/execution_event_cases.jsonl (schema + semantics)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spec_semantics import analyze_execution_event_semantics


def _resolve_spec_root() -> Path | None:
    env = os.environ.get("INTENTPROOF_SPEC_ROOT", "").strip()
    if env:
        p = Path(env)
        if (p / "spec.json").is_file():
            return p.resolve()
    here = Path(__file__).resolve()
    repo = here.parents[2]  # unit -> tests -> repo root
    sib = repo.parent / "intentproof-spec"
    if (sib / "spec.json").is_file():
        return sib.resolve()
    return None


def _load_golden_path(spec_root: Path) -> Path:
    spec = json.loads((spec_root / "spec.json").read_text(encoding="utf-8"))
    rel = spec["goldens"]["execution_events"]
    return (spec_root / rel).resolve()


def _assert_golden_oracle(spec_root: Path) -> None:
    schema_path = spec_root / "schema" / "execution_event.v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    path = _load_golden_path(spec_root)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        case_id = c["caseId"]
        should = c["shouldValidate"]
        event: dict[str, Any] = c["event"]
        schema_ok = validator.is_valid(event)
        sem: list[str] = []
        if schema_ok:
            sem = analyze_execution_event_semantics(event)
        actually_ok = schema_ok and len(sem) == 0
        if actually_ok != should:
            err = _format_schema_errors(validator, event) if not schema_ok else "; ".join(sem)
            msg = (
                f"Golden mismatch {case_id}: shouldValidate={should} "
                f"schema_ok={schema_ok} semantics={sem!r} detail={err}"
            )
            raise AssertionError(msg)


def _format_schema_errors(validator: Draft202012Validator, event: dict[str, Any]) -> str:
    parts: list[str] = []
    for e in sorted(validator.iter_errors(event), key=str):
        p = "/".join(str(x) for x in e.path) if e.path else "/"
        parts.append(f"{p} {e.message}")
    return "; ".join(parts) if parts else "schema invalid"


spec_root = _resolve_spec_root()


@pytest.mark.skipif(
    spec_root is None,
    reason="Set INTENTPROOF_SPEC_ROOT or clone intentproof-spec next to this repository",
)
def test_execution_event_golden_oracle() -> None:
    assert spec_root is not None
    _assert_golden_oracle(spec_root)
