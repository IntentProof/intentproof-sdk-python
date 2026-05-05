"""Normative JSON Schema validation helpers."""

from __future__ import annotations

import pytest

from intentproof.schema_validate import (
    validate_execution_event_wire,
    validate_intentproof_config_wire,
    validate_wrap_options_wire,
)


def _minimal_ok_event() -> dict[str, object]:
    return {
        "id": "e1",
        "intent": "do thing",
        "action": "svc.op",
        "status": "ok",
        "inputs": {},
        "startedAt": "2020-01-01T00:00:00.000Z",
        "completedAt": "2020-01-01T00:00:01.000Z",
        "durationMs": 0,
        "output": None,
    }


def test_validate_execution_event_wire_ok() -> None:
    validate_execution_event_wire(_minimal_ok_event())  # no exception


def test_validate_execution_event_wire_rejects_bad_type() -> None:
    bad = _minimal_ok_event()
    bad["durationMs"] = "nope"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="JSON Schema validation"):
        validate_execution_event_wire(bad)


def test_validate_wrap_options_wire_minimal() -> None:
    validate_wrap_options_wire({})


def test_validate_wrap_options_wire_rejects_extra_top_level() -> None:
    with pytest.raises(ValueError, match="JSON Schema validation"):
        validate_wrap_options_wire({"notAField": 1})


def test_validate_intentproof_config_minimal() -> None:
    validate_intentproof_config_wire({"version": 1})


def test_validate_intentproof_config_rejects_bad_version() -> None:
    with pytest.raises(ValueError, match="JSON Schema validation"):
        validate_intentproof_config_wire({"version": 2})
