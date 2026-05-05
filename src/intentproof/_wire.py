from __future__ import annotations

from typing import Any

from intentproof.generated.execution_event import ExecutionError
from intentproof.types import ExecutionEvent


def execution_error_to_wire(err: ExecutionError) -> dict[str, Any]:
    return err.model_dump(mode="json", exclude_none=True)


def execution_event_to_wire(event: ExecutionEvent) -> dict[str, Any]:
    """Wire / verifier shape (camelCase); omits unset optional fields for compact JSON."""
    data = event.model_dump(by_alias=True, mode="json", exclude_none=True)
    # Whole milliseconds as int (schema ``number`` allows float; wire prefers integers).
    dm = data.get("durationMs")
    if dm is not None:
        data["durationMs"] = int(dm)
    st = data["status"]
    if st == "ok" and "output" not in data:
        data["output"] = None
    elif st != "ok" and data.get("output") is None:
        data.pop("output", None)
    if not data.get("attributes"):
        data.pop("attributes", None)
    return data
