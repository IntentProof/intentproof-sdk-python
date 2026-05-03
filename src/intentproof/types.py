from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

JsonScalar = str | int | float | bool | None
Attributes = dict[str, JsonScalar]

UNDEFINED = object()


@dataclass(slots=True)
class ExecutionEvent:
    id: str
    intent: str
    action: str
    inputs: Any
    status: Literal["ok", "error"]
    started_at: str
    completed_at: str
    duration_ms: int
    correlation_id: str | None = None
    output: Any | None = None
    error: dict[str, Any] | None = None
    attributes: Attributes | None = None


@dataclass
class IntentProofConfig:
    """Partial updates: use ``UNDEFINED`` sentinel on fields you do not want to change."""

    exporters: Any = UNDEFINED
    on_exporter_error: Any = UNDEFINED
    default_attributes: Any = UNDEFINED
    include_error_stack: Any = UNDEFINED
