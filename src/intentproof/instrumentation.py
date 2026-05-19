"""wrap(), correlation context, and subject mapping."""

from __future__ import annotations

import inspect
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, TypeVar

import ulid as _ulid

from intentproof import client
from intentproof.signing import event_content_hash, sign_event

_correlation_id: ContextVar[str | None] = ContextVar(
    "intentproof_correlation_id", default=None
)

F = TypeVar("F", bound=Callable[..., Any])


def run_with_correlation_id(correlation_id: str, fn: Callable[[], Any]) -> Any:
    token = _correlation_id.set(correlation_id)
    try:
        return fn()
    finally:
        _correlation_id.reset(token)


def push_subject_mapping(
    source_id: str, subject_type: str, subject_id: str
) -> None:
    """Record a subject mapping (no-op until reconciliation storage lands)."""
    del source_id, subject_type, subject_id


def _new_correlation_id() -> str:
    current = _correlation_id.get()
    if current:
        return current
    return f"req_{_ulid.new()}"


def _iso_timestamp(ms: int) -> str:
    return (
        datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _untrusted_payload(inputs: list[Any], output: Any, status: str) -> bool:
    if inputs:
        return True
    return status == "ok" and output is not None


def _record_execution(
    *,
    intent: str,
    action: str,
    correlation_id: str,
    event_id: str,
    t0_ms: int,
    t1_ms: int,
    inputs: list[Any],
    output: Any,
    status: str,
    error_obj: dict[str, Any] | None,
) -> None:
    outbox = client.get_outbox()

    def build_signed(chain_pos: int, prev_hash: str) -> tuple[dict[str, Any], str]:
        event: dict[str, Any] = {
            "schema": "intentproof.event.v1",
            "event_id": event_id,
            "tenant_id": client.get_tenant_id(),
            "instance_id": client.get_instance_id(),
            "correlation_id": correlation_id,
            "provenance_class": "sdk_attested_evidence",
            "prev_event_hash": prev_hash,
            "chain_position": chain_pos,
            "intent": intent,
            "action": action,
            "status": status,
            "started_at": _iso_timestamp(t0_ms),
            "completed_at": _iso_timestamp(t1_ms),
            "duration_ms": t1_ms - t0_ms,
            "inputs": inputs,
            "output": output if status == "ok" else None,
            "error": error_obj,
            "attributes": {},
            "untrusted_payload": _untrusted_payload(inputs, output, status),
            "spec_version": "1.0.0",
            "sdk_version": client.SDK_VERSION,
        }
        signed = sign_event(event, client.get_private_key(), client.get_instance_id())
        return signed, event_content_hash(signed)

    signed = outbox.record_chained_event(correlation_id, event_id, build_signed)

    exporter = client.get_exporter()
    if exporter is not None:
        exporter.enqueue(signed)


def wrap(
    intent: str,
    action: str,
    fn: F,
) -> F:
    """Wrap a callable to emit signed ExecutionEvent.v1 records."""

    if inspect.iscoroutinefunction(fn):

        @wraps(fn)
        async def async_wrapped(*args: Any, **kwargs: Any) -> Any:
            t0_ms = int(time.time() * 1000)
            correlation_id = _new_correlation_id()
            event_id = str(_ulid.new())
            status = "ok"
            error_obj: dict[str, Any] | None = None
            result: Any = None
            reraise: BaseException | None = None

            try:
                result = await fn(*args, **kwargs)
            except BaseException as exc:
                status = "error"
                error_obj = {"message": str(exc)}
                reraise = exc

            t1_ms = int(time.time() * 1000)
            try:
                _record_execution(
                    intent=intent,
                    action=action,
                    correlation_id=correlation_id,
                    event_id=event_id,
                    t0_ms=t0_ms,
                    t1_ms=t1_ms,
                    inputs=list(args),
                    output=result,
                    status=status,
                    error_obj=error_obj,
                )
            except BaseException as record_exc:
                if reraise is not None:
                    raise reraise from record_exc
                raise
            if reraise is not None:
                raise reraise
            return result

        return async_wrapped  # type: ignore[return-value]

    @wraps(fn)
    def sync_wrapped(*args: Any, **kwargs: Any) -> Any:
        t0_ms = int(time.time() * 1000)
        correlation_id = _new_correlation_id()
        event_id = str(_ulid.new())
        status = "ok"
        error_obj: dict[str, Any] | None = None
        result: Any = None
        reraise: BaseException | None = None

        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            status = "error"
            error_obj = {"message": str(exc)}
            reraise = exc

        t1_ms = int(time.time() * 1000)
        try:
            _record_execution(
                intent=intent,
                action=action,
                correlation_id=correlation_id,
                event_id=event_id,
                t0_ms=t0_ms,
                t1_ms=t1_ms,
                inputs=list(args),
                output=result,
                status=status,
                error_obj=error_obj,
            )
        except BaseException as record_exc:
            if reraise is not None:
                raise reraise from record_exc
            raise
        if reraise is not None:
            raise reraise
        return result

    return sync_wrapped  # type: ignore[return-value]
