from __future__ import annotations

from datetime import UTC, datetime


def utc_iso_ms(dt: datetime | None = None) -> str:
    """UTC instant as ``YYYY-MM-DDTHH:MM:SS.sssZ`` (millisecond precision, ``Z`` suffix)."""
    if dt is None:
        dt = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC)
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}Z"
