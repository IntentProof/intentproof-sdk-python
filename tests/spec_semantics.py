"""
Post-schema semantic checks for ExecutionEvent (mirror of intentproof-spec tests/lib/semantics.ts).
Update both when the spec changes.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any


def _parse_epoch_ms(s: str) -> float | None:
    try:
        t = s.replace("Z", "+00:00")
        d = datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        return d.timestamp() * 1000.0
    except (TypeError, ValueError, OSError):
        return None


def analyze_execution_event_semantics(ev: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    evs = ev

    sa = str(evs.get("startedAt", ""))
    ca = str(evs.get("completedAt", ""))
    started = _parse_epoch_ms(sa)
    completed = _parse_epoch_ms(ca)
    if started is None or completed is None:
        issues.append("startedAt and completedAt MUST parse as Date.parse-compatible timestamps")
        return issues
    if started > completed:
        issues.append("startedAt MUST be <= completedAt")

    duration_ms = float(evs.get("durationMs", float("nan")))
    expected = max(0.0, round(completed - started))
    if math.isnan(duration_ms):
        issues.append("durationMs MUST be a finite number")
    elif abs(duration_ms - expected) > 1.0:
        issues.append(
            f"durationMs ({duration_ms}) MUST match completedAt-startedAt within 1ms "
            f"(expected {expected})"
        )

    cid = evs.get("correlationId")
    if isinstance(cid, str) and len(cid.strip()) == 0:
        issues.append("correlationId MUST be trimmed non-empty when present")

    if evs.get("status") == "ok" and "error" in evs:
        issues.append("status=ok MUST NOT include an error field")

    attrs = evs.get("attributes")
    if attrs is not None and isinstance(attrs, dict):
        for k, v in attrs.items():
            if v is not None and not isinstance(v, (str, int, float, bool)):
                t = type(v).__name__
                issues.append(f"attributes.{k} MUST be string|number|boolean|null (got {t})")

    err = evs.get("error")
    if err is not None and isinstance(err, dict):
        cause = err.get("cause")
        if cause is not None:
            if isinstance(cause, dict):
                name_bad = not isinstance(cause.get("name"), str)
                msg_bad = not isinstance(cause.get("message"), str)
                if name_bad or msg_bad:
                    issues.append(
                        "error.cause MUST be a nested ExecutionError with name and message strings"
                    )
            else:
                issues.append("error.cause MUST be a nested ExecutionError object when present")

    return issues
