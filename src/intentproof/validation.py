from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypedDict, cast

from intentproof.snapshot import SerializeOptions


class WrapOptions(TypedDict, total=False):
    intent: str
    action: str
    correlation_id: str
    attributes: dict[str, str | int | float | bool]
    capture_input: Callable[..., Any]
    capture_output: Callable[..., Any]
    capture_error: Callable[..., Any]
    include_error_stack: bool
    max_depth: int
    max_keys: int
    redact_keys: list[str] | tuple[str, ...] | set[str] | frozenset[str]
    max_string_length: int
    fn: Callable[..., Any]


def assert_wrap_options_shape(options: Mapping[str, Any]) -> None:
    """Runtime validation for wrap options (intent, action, correlation id, attributes, …)."""
    intent = options.get("intent")
    action = options.get("action")

    if not isinstance(intent, str):
        msg = f'IntentProofClient: "intent" must be a string, got {type(intent).__name__}'
        raise TypeError(msg)
    if len(intent.strip()) == 0:
        msg = 'IntentProofClient: "intent" must be a non-empty string (trimmed length is 0)'
        raise TypeError(msg)
    if not isinstance(action, str):
        msg = f'IntentProofClient: "action" must be a string, got {type(action).__name__}'
        raise TypeError(msg)
    if len(action.strip()) == 0:
        msg = 'IntentProofClient: "action" must be a non-empty string (trimmed length is 0)'
        raise TypeError(msg)

    cid = options.get("correlation_id")
    if cid is not None:
        if not isinstance(cid, str):
            msg = (
                f'IntentProofClient: "correlation_id" must be a string when provided, '
                f"got {type(cid).__name__}"
            )
            raise TypeError(msg)
        if len(cid.strip()) == 0:
            msg = (
                'IntentProofClient: "correlation_id" must be a non-empty string when provided '
                "(trimmed length is 0)"
            )
            raise TypeError(msg)

    if options.get("attributes") is not None:
        assert_attributes_record("WrapOptions.attributes", options["attributes"])

    ioes = options.get("include_error_stack")
    if ioes is not None and not isinstance(ioes, bool):
        msg = (
            f'IntentProofClient: "include_error_stack" must be a boolean when provided, '
            f"got {type(ioes).__name__}"
        )
        raise TypeError(msg)

    for nk, typ in (
        ("max_depth", int),
        ("max_keys", int),
        ("max_string_length", int),
    ):
        v = options.get(nk)
        if v is not None and not isinstance(v, typ):
            msg = f"{nk} must be {typ.__name__} when provided"
            raise TypeError(msg)

    rk = options.get("redact_keys")
    if rk is not None and not isinstance(rk, (list, tuple, set, frozenset)):
        msg = "redact_keys must be a list, tuple, set, or frozenset when provided"
        raise TypeError(msg)

    for key in ("capture_input", "capture_output", "capture_error"):
        hook = options.get(key)
        if hook is not None and not callable(hook):
            msg = f"{key} must be callable when provided"
            raise TypeError(msg)


def assert_attributes_record(label: str, value: Any) -> None:
    if value is None or not isinstance(value, Mapping) or isinstance(value, (str, bytes, list)):
        msg = f"IntentProofClient: {label} must be a plain object, got {type(value).__name__}"
        raise TypeError(msg)
    o = cast(Mapping[Any, Any], value)
    for key in list(o.keys()):
        v = o[key]
        if not isinstance(key, str):
            msg = f"IntentProofClient: {label} keys must be strings"
            raise TypeError(msg)
        if not isinstance(v, (str, int, float, bool)):
            msg = (
                f"IntentProofClient: {label}[{key!r}] must be a string, number, or boolean, "
                f"got {type(v).__name__}"
            )
            raise TypeError(msg)


def serialize_opts_from_wrap_options(options: Mapping[str, Any]) -> SerializeOptions:
    return SerializeOptions(
        max_depth=options.get("max_depth") if "max_depth" in options else None,
        max_keys=options.get("max_keys") if "max_keys" in options else None,
        redact_keys=cast(Any, options.get("redact_keys")),
        max_string_length=(
            options.get("max_string_length") if "max_string_length" in options else None
        ),
    )
