from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

_DEFAULT_MAX_DEPTH = 6
_DEFAULT_MAX_KEYS = 50


def _snapshot_limit(n: int | None, fallback: int) -> int:
    if n is None:
        return fallback
    if not isinstance(n, (int, float)) or not math.isfinite(float(n)):
        return fallback
    i = int(n)
    return fallback if i < 0 else i


def _snapshot_string_limit(n: int | None) -> int | None:
    if n is None:
        return None
    if not isinstance(n, (int, float)) or not math.isfinite(float(n)):
        return None
    i = int(n)
    return None if i < 0 else i


def _normalize_redact_set(
    redact_keys: list[str] | tuple[str, ...] | set[str] | frozenset[str] | None,
) -> set[str] | None:
    if not redact_keys:
        return None
    out: set[str] = set()
    for k in redact_keys:
        if isinstance(k, str) and len(k) > 0:
            out.add(k.lower())
    return out or None


def _should_redact_key(key: str, redact: set[str] | None) -> bool:
    if not redact:
        return False
    return key.lower() in redact


def _truncate_string(s: str, max_len: int | None) -> str:
    if max_len is None or len(s) <= max_len:
        return s
    n = len(s) - max_len
    return f"{s[:max_len]}…[truncated {n} chars]"


class SerializeOptions:
    """Options controlling depth, key count, string truncation, and redaction for ``snapshot``."""

    __slots__ = ("max_depth", "max_keys", "redact_keys", "max_string_length")

    def __init__(
        self,
        *,
        max_depth: int | None = None,
        max_keys: int | None = None,
        redact_keys: list[str] | tuple[str, ...] | set[str] | frozenset[str] | None = None,
        max_string_length: int | None = None,
    ) -> None:
        self.max_depth = _snapshot_limit(max_depth, _DEFAULT_MAX_DEPTH)
        self.max_keys = _snapshot_limit(max_keys, _DEFAULT_MAX_KEYS)
        self.redact_keys = redact_keys
        self.max_string_length = _snapshot_string_limit(max_string_length)

    def snapshot_kwargs(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "max_depth": self.max_depth,
            "max_keys": self.max_keys,
            "redact_keys": self.redact_keys,
        }
        if self.max_string_length is not None:
            d["max_string_length"] = self.max_string_length
        return d


def snapshot(
    value: Any,
    *,
    max_depth: int | None = None,
    max_keys: int | None = None,
    redact_keys: list[str] | tuple[str, ...] | set[str] | frozenset[str] | None = None,
    max_string_length: int | None = None,
) -> Any:
    opts = SerializeOptions(
        max_depth=max_depth,
        max_keys=max_keys,
        redact_keys=redact_keys,
        max_string_length=max_string_length,
    )
    redact = _normalize_redact_set(opts.redact_keys) if opts.redact_keys else None
    stack: set[int] = set()

    def walk(v: Any, depth: int) -> Any:
        if v is None:
            return None
        t = type(v)
        if t is str:
            return _truncate_string(v, opts.max_string_length)
        if t is bool or t is int:
            return v
        if t is float:
            x = float(v)
            if math.isnan(x) or math.isinf(x):
                return str(x)
            return x
        if t is bytes:
            return _truncate_string(
                v.decode("utf-8", errors="replace"),
                opts.max_string_length,
            )
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, UUID):
            return str(v)
        if isinstance(v, Enum):
            return v.name
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if callable(v):
            name = getattr(v, "__name__", None) or "anonymous"
            return f"[Function {name}]"

        if isinstance(v, (list, tuple)):
            oid = id(v)
            if oid in stack:
                return "[Circular]"
            stack.add(oid)
            try:
                if depth >= opts.max_depth:
                    return "[Array]"
                seq = list(v)[: opts.max_keys]
                return [walk(item, depth + 1) for item in seq]
            finally:
                stack.discard(oid)

        if isinstance(v, (set, frozenset)):
            if depth >= opts.max_depth:
                return "[Array]"
            seq = list(v)[: opts.max_keys]
            return [walk(item, depth + 1) for item in seq]

        if isinstance(v, Mapping):
            oid = id(v)
            if oid in stack:
                return "[Circular]"
            stack.add(oid)
            try:
                if depth >= opts.max_depth:
                    return "[Object]"
                out: dict[str, Any] = {}
                keys = list(v.keys())
                for n, k in enumerate(keys):
                    if n >= opts.max_keys:
                        out["…"] = f"{len(keys) - opts.max_keys} more keys"
                        break
                    sk = str(k)
                    try:
                        if _should_redact_key(sk, redact):
                            out[sk] = "[REDACTED]"
                        else:
                            out[sk] = walk(v[k], depth + 1)
                    except Exception:
                        out[sk] = "[Unserializable]"
                return out
            finally:
                stack.discard(oid)

        if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
            oid = id(v)
            if oid in stack:
                return "[Circular]"
            stack.add(oid)
            try:
                if depth >= opts.max_depth:
                    return "[Array]"
                seq = list(v)[: opts.max_keys]
                return [walk(item, depth + 1) for item in seq]
            finally:
                stack.discard(oid)

        try:
            return str(v)
        except Exception:
            return "[Unserializable]"

    try:
        return walk(value, 0)
    except Exception:
        return "[SnapshotError]"
