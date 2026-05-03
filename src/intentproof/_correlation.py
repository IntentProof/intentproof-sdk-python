from __future__ import annotations

import contextvars
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "intentproof_correlation_id",
    default=None,
)

T = TypeVar("T")


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def assert_correlation_id(correlation_id: Any) -> str:
    if not isinstance(correlation_id, str):
        t = type(correlation_id).__name__
        msg = f'IntentProofClient: "correlation_id" must be a string, got {t}'
        raise TypeError(msg)
    if len(correlation_id.strip()) == 0:
        msg = 'IntentProofClient: "correlation_id" must be a non-empty string (trimmed length is 0)'
        raise TypeError(msg)
    return correlation_id.strip()


@contextmanager
def correlation_scope(correlation_id: str) -> Iterator[None]:
    token = _correlation_id.set(correlation_id)
    try:
        yield
    finally:
        _correlation_id.reset(token)


@contextmanager
def _correlation_context(correlation_id: str) -> Iterator[None]:
    cid = assert_correlation_id(correlation_id)
    with correlation_scope(cid):
        yield


def run_with_correlation_id_call(correlation_id: str, fn: Callable[[], T]) -> T:
    if not callable(fn):
        msg = "IntentProofClient: expected run_with_correlation_id(correlation_id, fn)"
        raise TypeError(msg)
    cid = assert_correlation_id(correlation_id)
    with correlation_scope(cid):
        return fn()


def run_with_correlation_id(
    correlation_id: str,
    fn: Callable[[], T] | None = None,
):
    """Two-argument form runs ``fn`` under a correlation id.

    Single-argument form returns a context manager.
    """
    if fn is not None:
        return run_with_correlation_id_call(correlation_id, fn)
    return _correlation_context(correlation_id)
