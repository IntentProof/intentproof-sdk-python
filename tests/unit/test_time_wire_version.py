"""Timestamps, wire JSON, package version fallback."""

from __future__ import annotations

import importlib
import re
from importlib.metadata import PackageNotFoundError

from intentproof._time import utc_iso_ms
from intentproof._wire import execution_event_to_wire
from intentproof.types import ExecutionEvent

_ISO_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_utc_iso_ms_now_and_naive() -> None:
    assert _ISO_MS.match(utc_iso_ms())
    from datetime import datetime

    s = utc_iso_ms(datetime(2020, 1, 2, 3, 4, 5, 678000))
    assert "2020-01-02" in s and s.endswith("Z")


def test_execution_event_to_wire_optional_fields() -> None:
    base = ExecutionEvent(
        id="1",
        intent="i",
        action="a",
        inputs={},
        status="ok",
        started_at="s",
        completed_at="c",
        duration_ms=1,
    )
    w = execution_event_to_wire(base)
    assert "correlationId" not in w and "attributes" not in w

    w2 = execution_event_to_wire(
        ExecutionEvent(
            id="2",
            intent="i",
            action="a",
            inputs={},
            status="error",
            started_at="s",
            completed_at="c",
            duration_ms=1,
            correlation_id="c",
            output={"o": 1},
            error={"name": "E"},
            attributes={"k": "v"},
        ),
    )
    assert w2["correlationId"] == "c"
    assert w2["attributes"] == {"k": "v"}


def test_version_fallback_when_metadata_missing() -> None:
    import importlib.metadata as imeta
    from unittest.mock import patch

    import intentproof._version as ver

    def boom(_name: str) -> str:
        raise PackageNotFoundError

    with patch.object(imeta, "version", boom):
        importlib.reload(ver)
        assert ver.VERSION == "0.0.0"
    importlib.reload(ver)
