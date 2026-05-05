from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intentproof.generated.execution_event import (
    ExecutionError,
    IntentProofExecutionEventV1,
    JsonValue,
    Status,
)
from intentproof.generated.intentproof_config import IntentProofRuntimeConfigV1
from intentproof.generated.intentproof_config import WrapOptionsV1 as IntentProofWrapOptionsV1

JsonScalar = str | int | float | bool | None
Attributes = dict[str, JsonScalar]

UNDEFINED = object()

# Wire execution record — schema-generated (see ``src/intentproof/generated/``).
ExecutionEvent = IntentProofExecutionEventV1

# Structured error payload on events (same shape as JSON Schema ``ExecutionError``).
ExecutionErrorSnapshot = ExecutionError


@dataclass
class IntentProofConfig:
    """Partial updates: use ``UNDEFINED`` sentinel on fields you do not want to change."""

    exporters: Any = UNDEFINED
    on_exporter_error: Any = UNDEFINED
    default_attributes: Any = UNDEFINED
    include_error_stack: Any = UNDEFINED


__all__ = [
    "UNDEFINED",
    "Attributes",
    "ExecutionError",
    "ExecutionErrorSnapshot",
    "ExecutionEvent",
    "IntentProofConfig",
    "IntentProofExecutionEventV1",
    "IntentProofRuntimeConfigV1",
    "IntentProofWrapOptionsV1",
    "JsonScalar",
    "JsonValue",
    "Status",
]
