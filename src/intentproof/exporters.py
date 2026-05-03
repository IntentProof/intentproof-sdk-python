from __future__ import annotations

import asyncio
import inspect
import json
import logging
import math
import threading
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Literal, Protocol, runtime_checkable

from intentproof._wire import execution_event_to_wire
from intentproof.types import ExecutionEvent

_log = logging.getLogger("intentproof")

QueueOverflowStrategy = Literal["drop-newest", "drop-oldest"]

HTTP_EXPORTER_FALLBACK_BODY = '{"intentproof":"1","eventSerializeFailed":true}'


def safe_json_envelope(event: ExecutionEvent) -> str:
    try:
        wire = execution_event_to_wire(event)
        return json.dumps({"intentproof": "1", "event": wire}, default=str)
    except BaseException:
        try:
            wire = execution_event_to_wire(event)
            partial = {
                "intentproof": "1",
                "eventPartial": {
                    "id": wire.get("id"),
                    "action": wire.get("action"),
                    "intent": wire.get("intent"),
                    "status": wire.get("status"),
                    "correlationId": wire.get("correlationId"),
                    "startedAt": wire.get("startedAt"),
                    "completedAt": wire.get("completedAt"),
                    "durationMs": wire.get("durationMs"),
                },
                "note": "full event not JSON-serializable",
            }
            return json.dumps(partial, default=str)
        except BaseException:
            return HTTP_EXPORTER_FALLBACK_BODY


@runtime_checkable
class Exporter(Protocol):
    def export(self, event: ExecutionEvent) -> Any: ...


class MemoryExporter:
    """Ring buffer of wire-shaped events in memory (tests and local inspection)."""

    __slots__ = ("_events", "_lock", "_max_events")

    def __init__(self, *, max_events: int = 1000) -> None:
        fin = isinstance(max_events, (int, float)) and math.isfinite(float(max_events))
        if not fin or max_events < 1:
            msg = 'MemoryExporter: "max_events" must be a finite number >= 1'
            raise TypeError(msg)
        self._max_events = int(max_events)
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def export(self, event: ExecutionEvent) -> None:
        wire = execution_event_to_wire(event)
        with self._lock:
            self._events.append(wire)
            overflow = len(self._events) - self._max_events
            if overflow > 0:
                del self._events[0:overflow]

    def get_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def flush(self) -> None:
        return None


class HttpExporter:
    """POST execution events as JSON with default envelope and serialization fallbacks."""

    __slots__ = (
        "url",
        "method",
        "headers",
        "_body_fn",
        "await_each",
        "timeout_ms",
        "on_error",
        "_closed",
        "_in_flight",
        "_flight_lock",
    )

    def __init__(
        self,
        url: str,
        *,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        body: Callable[[ExecutionEvent], str] | None = None,
        await_each: bool = False,
        timeout_ms: int | None = None,
        on_error: Callable[[BaseException, ExecutionEvent], None] | None = None,
    ) -> None:
        if not isinstance(url, str) or len(url.strip()) == 0:
            msg = 'HttpExporter: "url" must be a non-empty string'
            raise TypeError(msg)
        self.url = url
        self.method = (method or "POST").strip() or "POST"
        raw = headers or {}
        self.headers = {"content-type": "application/json", **raw}
        self._body_fn = body or safe_json_envelope
        self.await_each = bool(await_each)
        if timeout_ms is not None:
            tm_ok = isinstance(timeout_ms, (int, float)) and math.isfinite(float(timeout_ms))
            if not tm_ok or timeout_ms <= 0:
                msg = 'HttpExporter: "timeout_ms" must be a finite number > 0 when set'
                raise TypeError(msg)
            self.timeout_ms = int(timeout_ms)
        else:
            self.timeout_ms = None
        self.on_error = on_error
        self._closed = False
        self._in_flight: set[Any] = set()
        self._flight_lock = threading.Lock()

    def _track(self, fut: Any) -> None:
        with self._flight_lock:
            self._in_flight.add(fut)

        def _done(_f: Any) -> None:
            with self._flight_lock:
                self._in_flight.discard(fut)

        fut.add_done_callback(_done)

    def export(self, event: ExecutionEvent) -> Any:
        if self._closed:
            if self.on_error is not None:
                self.on_error(RuntimeError("HttpExporter has been shut down"), event)
            return None

        try:
            payload = self._body_fn(event)
        except BaseException as err:
            if self.on_error is not None:
                self.on_error(err, event)
            payload = safe_json_envelope(event)

        if not isinstance(payload, str):
            payload = str(payload)

        def run() -> None:
            try:
                req = urllib.request.Request(
                    self.url,
                    data=payload.encode("utf-8"),
                    method=self.method,
                    headers=dict(self.headers),
                )
                timeout = self.timeout_ms / 1000.0 if self.timeout_ms is not None else None
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    resp.read()
            except urllib.error.HTTPError as e:
                e.read()
                if self.on_error is not None:
                    self.on_error(e, event)
            except BaseException as e:
                if self.on_error is not None:
                    self.on_error(e, event)

        fut = _GLOBAL_HTTP_EXECUTOR.submit(run)
        self._track(fut)
        if self.await_each:
            fut.result()
        return None

    def flush(self) -> None:
        while True:
            with self._flight_lock:
                if not self._in_flight:
                    return None
                pending = list(self._in_flight)
            wait(pending, return_when=ALL_COMPLETED)

    def shutdown(self) -> None:
        self._closed = True
        self.flush()


_GLOBAL_HTTP_EXECUTOR = ThreadPoolExecutor(
    max_workers=32,
    thread_name_prefix="intentproof-http",
)


async def _await_export_result(r: Any) -> None:
    await r


class BoundedQueueExporter:
    """Bounded concurrency and backlog in front of another exporter."""

    __slots__ = (
        "_inner",
        "_max_concurrent",
        "_max_queue",
        "_strategy",
        "_on_drop",
        "_on_inner_error",
        "_queue",
        "_active",
        "_accepting",
        "_lock",
        "_idle",
        "_executor",
    )

    def __init__(
        self,
        *,
        exporter: Exporter,
        max_concurrent: int = 4,
        max_queue: int = 1000,
        strategy: QueueOverflowStrategy = "drop-newest",
        on_drop: Callable[[ExecutionEvent, str], None] | None = None,
        on_inner_error: Callable[[BaseException, ExecutionEvent], None] | None = None,
    ) -> None:
        ex = getattr(exporter, "export", None)
        if exporter is None or not callable(ex):
            msg = 'BoundedQueueExporter: "exporter" must be an object with an export() method'
            raise TypeError(msg)
        self._inner = exporter
        raw_mc = max_concurrent
        self._max_concurrent = (
            4
            if not isinstance(raw_mc, (int, float)) or not math.isfinite(float(raw_mc))
            else max(1, int(raw_mc))
        )
        raw_q = max_queue
        if not isinstance(raw_q, (int, float)) or not math.isfinite(float(raw_q)):
            self._max_queue = 1000
        else:
            q = int(raw_q)
            if q == 0:
                self._max_queue = 0
            elif q < 0:
                self._max_queue = 1000
            else:
                self._max_queue = q
        if strategy not in ("drop-newest", "drop-oldest"):
            msg = 'BoundedQueueExporter: "strategy" must be "drop-newest" or "drop-oldest"'
            raise TypeError(msg)
        self._strategy = strategy
        self._on_drop = on_drop
        self._on_inner_error = on_inner_error
        self._queue: deque[ExecutionEvent] = deque()
        self._active = 0
        self._accepting = True
        self._lock = threading.Lock()
        self._idle = threading.Condition(self._lock)
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_concurrent,
            thread_name_prefix="intentproof-bounded",
        )

    def _run_inner(self, event: ExecutionEvent) -> None:
        try:
            r = self._inner.export(event)
            if inspect.isawaitable(r):
                asyncio.run(_await_export_result(r))
        except BaseException as exc:
            if self._on_inner_error is not None:
                self._on_inner_error(exc, event)
        finally:
            with self._lock:
                self._active -= 1
                self._pump_locked()
                if len(self._queue) == 0 and self._active == 0:
                    self._idle.notify_all()

    def _pump_locked(self) -> None:
        while self._active < self._max_concurrent and self._queue:
            nxt = self._queue.popleft()
            self._active += 1
            self._executor.submit(self._run_inner, nxt)

    def export(self, event: ExecutionEvent) -> None:
        with self._lock:
            if not self._accepting:
                if self._on_drop is not None:
                    self._on_drop(event, "shutdown")
                return

            cap = float("inf") if self._max_queue <= 0 else self._max_queue

            if len(self._queue) >= cap:
                if self._strategy == "drop-oldest":
                    dropped = self._queue.popleft()
                    if self._on_drop is not None:
                        self._on_drop(dropped, "queue-overflow-drop-oldest")
                    self._queue.append(event)
                else:
                    if self._on_drop is not None:
                        self._on_drop(event, "queue-overflow-drop-newest")
                self._pump_locked()
                return

            self._queue.append(event)
            self._pump_locked()

    def flush(self) -> None:
        with self._idle:
            self._idle.wait_for(lambda: len(self._queue) == 0 and self._active == 0)
        return None

    def shutdown(self) -> None:
        with self._lock:
            self._accepting = False
        self.flush()
        self._executor.shutdown(wait=True)
