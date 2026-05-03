"""MemoryExporter, HttpExporter, BoundedQueueExporter, safe_json_envelope."""

from __future__ import annotations

import asyncio
import threading
import time
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from intentproof.exporters import (
    BoundedQueueExporter,
    HttpExporter,
    MemoryExporter,
    safe_json_envelope,
)
from intentproof.types import ExecutionEvent


def ev(**kw: object) -> ExecutionEvent:
    fields = {
        "id": "e",
        "intent": "i",
        "action": "a",
        "inputs": {},
        "status": "ok",
        "started_at": "s",
        "completed_at": "c",
        "duration_ms": 0,
    }
    fields.update(kw)
    return ExecutionEvent(**fields)


def test_memory_exporter_ring_and_validation() -> None:
    with pytest.raises(TypeError):
        MemoryExporter(max_events=0)
    m = MemoryExporter(max_events=2)
    for i in range(3):
        m.export(ev(id=str(i)))
    got = m.get_events()
    assert len(got) == 2 and got[0]["id"] == "1"
    m.clear()
    assert m.get_events() == []


def test_safe_json_partial_fallback() -> None:
    e = ev()
    with patch("intentproof.exporters.json.dumps") as dmp:
        dmp.side_effect = [TypeError("first"), '{"intentproof":"1","eventPartial":{}}']
        out = safe_json_envelope(e)
        assert "intentproof" in out


def test_http_exporter_paths() -> None:
    with pytest.raises(TypeError):
        HttpExporter("")
    with pytest.raises(TypeError):
        HttpExporter("http://x", timeout_ms=0)

    err: list[BaseException] = []

    def on_err(ex: BaseException, _e: ExecutionEvent) -> None:
        err.append(ex)

    http = HttpExporter("http://example.test/", on_error=on_err, await_each=True, timeout_ms=1500)

    def bad_body(_e: ExecutionEvent) -> str:
        raise RuntimeError("bad")

    http._body_fn = bad_body  # type: ignore[method-assign]

    wire = ev()
    with patch("urllib.request.urlopen") as uo:
        uo.return_value.__enter__.return_value.read.return_value = b"{}"
        http.export(wire)

    http.shutdown()
    http.export(wire)
    assert any("shut down" in str(x) for x in err)

    err.clear()
    http2 = HttpExporter("http://example.test/", on_error=on_err, await_each=True)

    def not_str(_e: ExecutionEvent) -> object:
        return 123

    http2._body_fn = not_str  # type: ignore[method-assign]
    with patch("urllib.request.urlopen") as uo:
        uo.return_value.__enter__.return_value.read.return_value = b"{}"
        http2.export(wire)
    req = uo.call_args[0][0]
    assert req.data == b"123"

    err.clear()
    http3 = HttpExporter("http://example.test/", on_error=on_err, await_each=True)

    from urllib.error import HTTPError

    def raise_http(*_a: object, **_k: object) -> object:
        raise HTTPError("u", 500, "m", {}, BytesIO(b"x"))

    with patch("urllib.request.urlopen", raise_http):
        http3.export(wire)

    err.clear()

    def raise_os(*_a: object, **_k: object) -> object:
        raise OSError("n")

    with patch("urllib.request.urlopen", raise_os):
        http3.export(wire)
    assert err


def test_http_flush_second_loop_iteration() -> None:
    h = HttpExporter("http://example.test/", await_each=False)
    blocker = threading.Event()

    def slow_uo(*_a: object, **_k: object) -> object:
        blocker.wait(timeout=5)
        ctx = MagicMock()
        ctx.__enter__.return_value.read.return_value = b"{}"
        ctx.__exit__.return_value = None
        return ctx

    w = ev()
    with patch("urllib.request.urlopen", slow_uo):
        h.export(w)
        h.export(w)
        done = threading.Event()

        def run_flush() -> None:
            h.flush()
            done.set()

        threading.Thread(target=run_flush, daemon=True).start()
        time.sleep(0.05)
        blocker.set()
        assert done.wait(timeout=10)


def test_bounded_queue_and_strategy() -> None:
    with pytest.raises(TypeError):
        BoundedQueueExporter(exporter=None)  # type: ignore[arg-type]

    mem = MemoryExporter()
    BoundedQueueExporter(exporter=mem, max_queue=float("nan"))

    release = threading.Event()
    gate_started = threading.Event()

    class GateExporter:
        def __init__(self) -> None:
            self._n = 0

        def export(self, _e: ExecutionEvent) -> None:
            self._n += 1
            if self._n == 1:
                gate_started.set()
                assert release.wait(timeout=30)

    drops: list[tuple[str, str]] = []

    def on_drop(e: ExecutionEvent, reason: str) -> None:
        drops.append((e.id, reason))

    b = BoundedQueueExporter(
        exporter=GateExporter(),
        max_concurrent=1,
        max_queue=1,
        strategy="drop-oldest",
        on_drop=on_drop,
    )
    b.export(ev(id="0"))
    assert gate_started.wait(timeout=5)
    b.export(ev(id="1"))
    b.export(ev(id="2"))
    assert drops and drops[0][1] == "queue-overflow-drop-oldest"
    release.set()
    b.flush()

    got_err: list[str] = []

    class Boom:
        def export(self, _e: ExecutionEvent) -> None:
            raise ValueError("x")

    def on_inner(exc: BaseException, _e: ExecutionEvent) -> None:
        got_err.append(type(exc).__name__)

    b2 = BoundedQueueExporter(
        exporter=Boom(),
        max_queue=1,
        max_concurrent=1,
        strategy="drop-newest",
        on_inner_error=on_inner,
    )
    b2.export(ev(id="a"))
    b2.export(ev(id="b"))
    b2.flush()
    assert "ValueError" in got_err

    inner_m = MemoryExporter()
    b3 = BoundedQueueExporter(exporter=inner_m, max_queue=0, max_concurrent=1)
    for i in range(3):
        b3.export(ev(id=str(i)))
    b3.flush()
    assert len(inner_m.get_events()) == 3

    class InnerAwait:
        def export(self, _e: ExecutionEvent) -> Any:
            async def c() -> None:
                await asyncio.sleep(0)

            return c()

    b4 = BoundedQueueExporter(exporter=InnerAwait(), max_queue=10, max_concurrent=2)
    b4.export(ev())
    b4.flush()

    drops_sd: list[str] = []

    def on_sd(_ev: ExecutionEvent, reason: str) -> None:
        drops_sd.append(reason)

    b5 = BoundedQueueExporter(exporter=MemoryExporter(), max_queue=1, on_drop=on_sd)
    b5.export(ev(id="0"))
    b5.shutdown()
    b5.export(ev(id="1"))
    assert "shutdown" in drops_sd

    release_dn = threading.Event()
    started_dn = threading.Event()

    class GateDn:
        def __init__(self) -> None:
            self._n = 0

        def export(self, _e: ExecutionEvent) -> None:
            self._n += 1
            if self._n == 1:
                started_dn.set()
                assert release_dn.wait(timeout=30)

    drops_dn: list[tuple[str, str]] = []
    b_dn = BoundedQueueExporter(
        exporter=GateDn(),
        max_concurrent=1,
        max_queue=1,
        strategy="drop-newest",
        on_drop=lambda e, r: drops_dn.append((e.id, r)),
    )
    b_dn.export(ev(id="0"))
    assert started_dn.wait(timeout=5)
    b_dn.export(ev(id="1"))
    b_dn.export(ev(id="2"))
    assert any(t == ("2", "queue-overflow-drop-newest") for t in drops_dn)
    release_dn.set()
    b_dn.flush()

    BoundedQueueExporter(exporter=MemoryExporter(), max_queue=-5)

    with pytest.raises(TypeError, match="strategy"):
        BoundedQueueExporter(exporter=MemoryExporter(), strategy="invalid")  # type: ignore[arg-type]
