"""Validate wire-shaped payloads against normative JSON Schemas (embedded at codegen time)."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from intentproof.generated.normative_schemas import (
    EXECUTION_EVENT_SCHEMA,
    INTENTPROOF_CONFIG_SCHEMA,
    WRAP_OPTIONS_SCHEMA,
)

_fc = Draft202012Validator.FORMAT_CHECKER
_execution_validator = Draft202012Validator(EXECUTION_EVENT_SCHEMA, format_checker=_fc)
_wrap_options_validator = Draft202012Validator(WRAP_OPTIONS_SCHEMA, format_checker=_fc)
_config_validator = Draft202012Validator(INTENTPROOF_CONFIG_SCHEMA, format_checker=_fc)


def _assert_schema(name: str, validator: Draft202012Validator, obj: Any) -> None:
    errs = sorted(validator.iter_errors(obj), key=lambda e: str(e.path))
    if not errs:
        return
    parts: list[str] = []
    for e in errs:
        p = "/".join(str(x) for x in e.path) if e.path else "/"
        parts.append(f"{p}: {e.message}")
    msg = f"{name} failed JSON Schema validation: " + "; ".join(parts)
    raise ValueError(msg)


def validate_execution_event_wire(obj: dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``obj`` is not a valid ExecutionEvent v1 wire object."""
    _assert_schema("ExecutionEvent", _execution_validator, obj)


def validate_wrap_options_wire(obj: dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``obj`` is not a valid WrapOptions v1 object."""
    _assert_schema("WrapOptions", _wrap_options_validator, obj)


def validate_intentproof_config_wire(obj: dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``obj`` is not a valid IntentProof runtime config v1 object."""
    _assert_schema("IntentProofConfig", _config_validator, obj)


def assert_valid_execution_event_wire(obj: dict[str, Any]) -> None:
    """Alias for :func:`validate_execution_event_wire` (fail-fast helper)."""
    validate_execution_event_wire(obj)


__all__ = [
    "assert_valid_execution_event_wire",
    "validate_execution_event_wire",
    "validate_intentproof_config_wire",
    "validate_wrap_options_wire",
]
