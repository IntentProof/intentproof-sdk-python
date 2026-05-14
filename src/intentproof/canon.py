"""RFC 8785 JSON Canonicalization Scheme (JCS) implementation.

Provides ``canonicalize(obj)`` which returns a canonical JSON string
suitable for hashing and signing across languages.
"""

from __future__ import annotations

import json
import math
from typing import Any

__all__ = ["canonicalize"]


class _CanonObject:
    """Intermediate representation for JSON objects (preserves key order)."""

    def __init__(self, pairs: list[tuple[str, Any]] | None = None):
        self.keys: list[str] = []
        self.values: dict[str, Any] = {}
        if pairs:
            for k, v in pairs:
                if k in self.values:
                    raise ValueError(f"duplicate object key: {k}")
                self.keys.append(k)
                self.values[k] = v


def _encode_string(s: str) -> str:
    """Minimal-escape JSON string per RFC 8785 §3.2.2.2."""
    parts = ['"']
    for ch in s:
        cp = ord(ch)
        if ch == '"':
            parts.append('\\"')
        elif ch == '\\':
            parts.append('\\\\')
        elif ch == '\b':
            parts.append('\\b')
        elif ch == '\f':
            parts.append('\\f')
        elif ch == '\n':
            parts.append('\\n')
        elif ch == '\r':
            parts.append('\\r')
        elif ch == '\t':
            parts.append('\\t')
        elif cp < 0x20:
            parts.append(f'\\u{cp:04x}')
        else:
            parts.append(ch)
    parts.append('"')
    return ''.join(parts)


def _to_shortest_scientific(f: float) -> tuple[str, int]:
    """Return (digits, exponent) for shortest scientific notation."""
    s = repr(f)
    if 'e' in s or 'E' in s:
        mantissa, exp_str = s.lower().split('e')
        exp = int(exp_str)
        if '.' in mantissa:
            a, b = mantissa.split('.')
            digits = a + b
        else:
            digits = mantissa
        digits = digits.rstrip('0') or '0'
        return digits, exp
    if '.' in s:
        a, b = s.split('.')
        b = b.rstrip('0')
        if not b:
            return _integer_to_scientific(a)
        all_digits = a + b
        all_digits = all_digits.rstrip('0') or '0'
        digits = all_digits.lstrip('0') or '0'
        leading_zeros = len(all_digits) - len(digits)
        point_pos = len(a)
        exp = point_pos - leading_zeros - 1
        return digits, exp
    return _integer_to_scientific(s)


def _integer_to_scientific(s: str) -> tuple[str, int]:
    if s == '0' or s.lstrip('0') == '':
        return '0', 0
    s = s.lstrip('0')
    trailing = len(s) - len(s.rstrip('0'))
    digits = s.rstrip('0')
    exp = len(digits) - 1 + trailing
    return digits, exp


def _format_es6(f: float) -> str:
    """Format float per ES6 Number.prototype.toString / RFC 8785 §3.2.2.3."""
    if f == 0:
        return '0'
    negative = f < 0
    if negative:
        f = -f
    digits, exp = _to_shortest_scientific(f)
    if digits == '0':
        return '0'
    k = len(digits)
    n = exp + 1
    if k <= n <= 21:
        out = digits + '0' * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + '.' + digits[n:]
    elif -6 < n <= 0:
        out = '0.' + '0' * (-n) + digits
    else:
        mant = digits[0]
        if k > 1:
            mant += '.' + digits[1:]
        es = n - 1
        if es >= 0:
            out = f'{mant}e+{es}'
        else:
            out = f'{mant}e{es}'
    if negative:
        out = '-' + out
    return out


def _encode_int(i: int) -> str:
    if -(2 ** 53) <= i <= 2 ** 53:
        return str(i)
    f = float(i)
    if math.isinf(f):
        raise ValueError(f"out of range integer {i}")
    return _format_es6(f)


def _encode_float(f: float) -> str:
    if math.isnan(f) or math.isinf(f):
        raise ValueError(f"non-finite number {f}")
    return _format_es6(f)


def _encode_object(obj: _CanonObject) -> str:
    keys = list(obj.keys)
    keys.sort(key=lambda k: k.encode('utf-16-be'))
    parts = ['{']
    for i, k in enumerate(keys):
        if i > 0:
            parts.append(',')
        parts.append(_encode_string(k))
        parts.append(':')
        parts.append(_encode_value(obj.values[k]))
    parts.append('}')
    return ''.join(parts)


def _encode_value(value: Any) -> str:
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return _encode_int(value)
    if isinstance(value, float):
        return _encode_float(value)
    if isinstance(value, str):
        return _encode_string(value)
    if isinstance(value, list):
        parts = ['[']
        for i, item in enumerate(value):
            if i > 0:
                parts.append(',')
            parts.append(_encode_value(item))
        parts.append(']')
        return ''.join(parts)
    if isinstance(value, _CanonObject):
        return _encode_object(value)
    raise TypeError(f"unsupported type: {type(value).__name__}")


def _build_tree(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_build_tree(v) for v in value]
    if isinstance(value, dict):
        pairs = []
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"object keys must be strings, got {type(k).__name__}")
            pairs.append((k, _build_tree(v)))
        return _CanonObject(pairs)
    raise TypeError(f"unsupported type: {type(value).__name__}")


class _NotJSON(Exception):
    pass


def _decode_json(s: str) -> Any:
    def _object_pairs_hook(pairs: list[tuple[str, Any]]) -> _CanonObject:
        return _CanonObject(pairs)

    decoder = json.JSONDecoder(
        parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f"non-finite number {c}")),
        object_pairs_hook=_object_pairs_hook,
    )
    try:
        value, idx = decoder.raw_decode(s)
    except json.JSONDecodeError as exc:
        raise _NotJSON from exc
    if s[idx:].strip():
        raise ValueError("trailing data after JSON value")
    return value


def canonicalize(obj: Any) -> str:
    """Return the RFC 8785 canonical JSON encoding of *obj*.

    If *obj* is a ``str`` that begins with a JSON value token, it is
    decoded as JSON and the resulting value is canonicalized.  Otherwise
    it is treated as a literal string value.
    """
    if isinstance(obj, str):
        stripped = obj.strip()
        if not stripped:
            return _encode_string(obj)
        first = stripped[0]
        if first in '{"[-tfnNI' or first.isdigit():
            try:
                tree = _decode_json(obj)
            except _NotJSON:
                if any(ch in stripped for ch in '{}[]:,'):
                    raise ValueError("invalid JSON")
                return _encode_string(obj)
            return _encode_value(tree)
        return _encode_string(obj)
    tree = _build_tree(obj)
    return _encode_value(tree)
