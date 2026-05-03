from __future__ import annotations

from typing import Any

from intentproof.types import ExecutionEvent


def execution_event_to_wire(event: ExecutionEvent) -> dict[str, Any]:
    """Wire / verifier shape (camelCase); omits unset optional fields for compact JSON."""
    out: dict[str, Any] = {
        "id": event.id,
        "intent": event.intent,
        "action": event.action,
        "inputs": event.inputs,
        "status": event.status,
        "startedAt": event.started_at,
        "completedAt": event.completed_at,
        "durationMs": event.duration_ms,
    }
    if event.correlation_id is not None:
        out["correlationId"] = event.correlation_id
    if event.status == "ok" or event.output is not None:
        out["output"] = event.output
    if event.error is not None:
        out["error"] = event.error
    if event.attributes is not None and len(event.attributes) > 0:
        out["attributes"] = event.attributes
    return out
