#!/usr/bin/env python3
"""
Generate Pydantic models + embedded normative JSON Schemas from intentproof-spec (see spec.json).

- JsonValue recursion is substituted for codegen only (same as other SDKs).
- ``output`` uses schema ``true`` (any JSON) for Pydantic ergonomics (matches relaxed JSON value).
- Does not write *.schema.json into the SDK tree.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_spec_root() -> Path:
    env = os.environ.get("INTENTPROOF_SPEC_ROOT", "").strip()
    if env:
        p = Path(env)
        if (p / "spec.json").is_file():
            return p.resolve()
    sib = _repo_root().parent / "intentproof-spec"
    if (sib / "spec.json").is_file():
        return sib.resolve()
    print(
        "generate_schema_models: set INTENTPROOF_SPEC_ROOT to an intentproof-spec checkout",
        file=sys.stderr,
    )
    sys.exit(1)


def _patch_json_value_for_codegen(schema: dict) -> None:
    schema.setdefault("$defs", {})["JsonValue"] = {
        "anyOf": [
            {"type": "null"},
            {"type": "boolean"},
            {"type": "number"},
            {"type": "string"},
            {"type": "array", "items": True},
            {"type": "object", "additionalProperties": True},
        ]
    }


def _simplify_output_for_pydantic(schema: dict) -> None:
    """Avoid JsonValue RootModel on ``output`` — keep wire as arbitrary JSON."""
    if "properties" in schema and "output" in schema["properties"]:
        schema["properties"]["output"] = True


def _inline_config_wrap_options(schema_dir: Path) -> dict:
    ic = json.loads((schema_dir / "intentproof_config.v1.schema.json").read_text())
    wo = json.loads((schema_dir / "wrap_options.v1.schema.json").read_text())
    ic.setdefault("$defs", {})
    ic["$defs"]["WrapOptionsV1"] = wo
    if "properties" in ic and "defaultWrapOptions" in ic["properties"]:
        ic["properties"]["defaultWrapOptions"] = {"$ref": "#/$defs/WrapOptionsV1"}
    return ic


def _normative_schemas_for_jsonschema(schema_dir: Path) -> tuple[dict, dict, dict]:
    """Embedded dicts for ``jsonschema`` (Draft 2020-12) — config ref inlined."""
    ee = json.loads((schema_dir / "execution_event.v1.schema.json").read_text())
    wo = json.loads((schema_dir / "wrap_options.v1.schema.json").read_text())
    ic = _inline_config_wrap_options(schema_dir)
    return ee, wo, ic


def _patch_config_populate_by_name(py_path: Path) -> None:
    """Allow Python field names (``started_at``) as well as JSON aliases (``startedAt``)."""
    text = py_path.read_text(encoding="utf-8")
    if "populate_by_name" in text:
        return
    for old, new in (
        (
            "    model_config = ConfigDict(\n        extra='forbid',\n    )",
            (
                "    model_config = ConfigDict(\n"
                "        extra='forbid',\n"
                "        populate_by_name=True,\n"
                "    )"
            ),
        ),
        (
            "    model_config = ConfigDict(\n        extra='allow',\n    )",
            (
                "    model_config = ConfigDict(\n"
                "        extra='allow',\n"
                "        populate_by_name=True,\n"
                "    )"
            ),
        ),
    ):
        text = text.replace(old, new)
    py_path.write_text(text, encoding="utf-8")


def _py_json_loads_literal(obj: dict) -> str:
    """Serialize ``obj`` as ``json.loads("...")`` — valid Python, deterministic JSON."""
    raw = json.dumps(obj, sort_keys=True, indent=2)
    return f"json.loads({json.dumps(raw)})"


def _write_normative_schemas_py(out_dir: Path, ee: dict, wo: dict, ic: dict) -> None:
    """Deterministic embedded JSON (sorted keys) for drift-checked CI."""
    path = out_dir / "normative_schemas.py"
    payload = (
        '"""Normative JSON Schema objects for ``jsonschema`` validation (generated)."""\n\n'
        "import json\n\n"
        f"EXECUTION_EVENT_SCHEMA: dict = {_py_json_loads_literal(ee)}\n\n"
        f"WRAP_OPTIONS_SCHEMA: dict = {_py_json_loads_literal(wo)}\n\n"
        f"INTENTPROOF_CONFIG_SCHEMA: dict = {_py_json_loads_literal(ic)}\n"
    )
    path.write_text(payload, encoding="utf-8")


def _write_spec_fingerprint_json(spec_root: Path, out_dir: Path) -> None:
    spec = json.loads((spec_root / "spec.json").read_text(encoding="utf-8"))
    schema_paths = sorted(spec["schemas"].values())
    files: dict[str, str] = {}
    lines: list[str] = []
    for rel in schema_paths:
        raw = (spec_root / rel).read_text(encoding="utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        files[rel] = digest
        lines.append(f"{rel}:{digest}")
    payload = {
        "specVersion": spec["version"],
        "algorithm": "sha256",
        "generator": {
            "name": "datamodel-code-generator",
            "version": metadata.version("datamodel-code-generator"),
        },
        "files": files,
        "aggregate": hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest(),
    }
    (out_dir / "spec_fingerprint.json").write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _run_datamodel(
    *,
    input_path: Path,
    output_path: Path,
    class_name: str,
) -> None:
    cmd = [
        "datamodel-codegen",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--input-file-type",
        "jsonschema",
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.11",
        "--disable-timestamp",
        "--snake-case-field",
        "--class-name",
        class_name,
    ]
    print("+", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def main() -> None:
    spec_root = _resolve_spec_root()
    schema_dir = spec_root / "schema"
    out_dir = _repo_root() / "src" / "intentproof" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    ee_n, wo_n, ic_n = _normative_schemas_for_jsonschema(schema_dir)
    _write_normative_schemas_py(out_dir, ee_n, wo_n, ic_n)
    _write_spec_fingerprint_json(spec_root, out_dir)

    (out_dir / "__init__.py").write_text(
        '"""Models generated from intentproof-spec JSON Schemas — do not edit by hand."""\n\n'
        "from intentproof.generated.execution_event import (\n"
        "    ExecutionError,\n"
        "    IntentProofExecutionEventV1,\n"
        "    JsonValue,\n"
        "    Status,\n"
        ")\n"
        "from intentproof.generated.intentproof_config import (\n"
        "    IntentProofRuntimeConfigV1,\n"
        "    WrapOptionsV1 as IntentProofWrapOptionsV1,\n"
        ")\n"
        "from intentproof.generated.normative_schemas import (\n"
        "    EXECUTION_EVENT_SCHEMA,\n"
        "    INTENTPROOF_CONFIG_SCHEMA,\n"
        "    WRAP_OPTIONS_SCHEMA,\n"
        ")\n\n"
        "__all__ = [\n"
        '    "EXECUTION_EVENT_SCHEMA",\n'
        '    "ExecutionError",\n'
        '    "INTENTPROOF_CONFIG_SCHEMA",\n'
        '    "IntentProofExecutionEventV1",\n'
        '    "IntentProofRuntimeConfigV1",\n'
        '    "IntentProofWrapOptionsV1",\n'
        '    "JsonValue",\n'
        '    "Status",\n'
        '    "WRAP_OPTIONS_SCHEMA",\n'
        "]\n"
    )

    # execution_event (codegen)
    ee = json.loads((schema_dir / "execution_event.v1.schema.json").read_text())
    _patch_json_value_for_codegen(ee)
    _simplify_output_for_pydantic(ee)
    ee_tmp = out_dir / ".codegen_execution_event.schema.json"
    ee_tmp.write_text(json.dumps(ee), encoding="utf-8")
    try:
        _run_datamodel(
            input_path=ee_tmp,
            output_path=out_dir / "execution_event.py",
            class_name="IntentProofExecutionEventV1",
        )
    finally:
        ee_tmp.unlink(missing_ok=True)

    # intentproof_config (wrap_options inlined)
    ic = _inline_config_wrap_options(schema_dir)
    ic_tmp = out_dir / ".codegen_intentproof_config.schema.json"
    ic_tmp.write_text(json.dumps(ic), encoding="utf-8")
    try:
        _run_datamodel(
            input_path=ic_tmp,
            output_path=out_dir / "intentproof_config.py",
            class_name="IntentProofRuntimeConfigV1",
        )
    finally:
        ic_tmp.unlink(missing_ok=True)

    _patch_config_populate_by_name(out_dir / "execution_event.py")
    _patch_config_populate_by_name(out_dir / "intentproof_config.py")

    print(f"Wrote generated models under {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
