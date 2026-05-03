"""IntentProofClient, helpers, exporter hooks, async paths."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import pytest

from intentproof import (
    IntentProofClient,
    IntentProofConfig,
    MemoryExporter,
    client,
    create_intent_proof_client,
    get_intent_proof_client,
    run_with_correlation_id,
)
from intentproof.sdk import (
    IntentProofConfig as ICfg,
)
from intentproof.sdk import (
    _assert_exporter_at_index,
    _default_on_exporter_error,
    _maybe_schedule_awaitable,
    _to_error_snapshot,
    merge_attrs,
)
from intentproof.types import UNDEFINED, ExecutionEvent
from intentproof.validation import assert_wrap_options_shape


class CE(BaseException):
    pass


def test_merge_attrs_and_error_snapshot() -> None:
    assert merge_attrs({"a": 1}, None) == {"a": 1}
    assert merge_attrs({}, {}) is None
    snap = _to_error_snapshot(CE("x"), True)
    assert snap["name"] == "Error" and "stack" not in snap


def test_default_on_exporter_error_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    ev = ExecutionEvent(
        id="1",
        intent="i",
        action="a",
        inputs={},
        status="ok",
        started_at="s",
        completed_at="c",
        duration_ms=0,
    )
    _default_on_exporter_error(ValueError("e"), ev)
    assert any("exporter error" in r.message for r in caplog.records)


def test_configure_and_singleton_and_proxy() -> None:
    a = get_intent_proof_client()
    b = get_intent_proof_client()
    assert a is b
    assert create_intent_proof_client() is not a

    mem = MemoryExporter()
    get_intent_proof_client().configure(IntentProofConfig(exporters=[mem]))
    client.wrap(intent="p", action="p.x", fn=lambda: 0)()
    assert mem.get_events()[-1]["action"] == "p.x"


def test_assert_exporter_at_index() -> None:
    with pytest.raises(TypeError, match="exporters\\[0\\]"):
        _assert_exporter_at_index(None, 0)
    with pytest.raises(TypeError, match="exporters\\[1\\]"):
        _assert_exporter_at_index(object(), 1)


def test_configure_bad_exporter_list() -> None:
    with pytest.raises(TypeError, match="exporters\\[1\\]"):
        IntentProofClient(IntentProofConfig(exporters=[MemoryExporter(), object()]))


def test_configure_validation_and_undefined() -> None:
    c = IntentProofClient()
    with pytest.raises(TypeError, match="on_exporter_error"):
        c.configure(ICfg(on_exporter_error="n"))
    with pytest.raises(TypeError, match="include_error_stack"):
        c.configure(ICfg(include_error_stack="y"))
    with pytest.raises(TypeError, match="default_attributes"):
        c.configure(ICfg(default_attributes=[]))

    mem = MemoryExporter()
    c.configure(IntentProofConfig(exporters=[mem]))
    c.configure(ICfg(exporters=UNDEFINED, on_exporter_error=UNDEFINED))
    c.wrap(intent="i", action="a", fn=lambda: 1)()
    assert len(mem.get_events()) == 1


def test_wrap_forms_and_correlation() -> None:
    mem = MemoryExporter()
    c = IntentProofClient(IntentProofConfig(exporters=[mem]))

    run = c.wrap(
        {"intent": "t", "action": "t.a", "capture_input": lambda a: {"n": a[0]}}, lambda x: x * 2
    )
    assert run(3) == 6

    with pytest.raises(TypeError, match="callable fn"):
        c.wrap(intent="i", action="a", fn=object())

    assert c._resolve_correlation_id("   ") is None
    with run_with_correlation_id("cid"):
        assert c._resolve_correlation_id(None) == "cid"

    assert c.get_correlation_id() is None

    with pytest.raises(TypeError):
        c.with_correlation("not-callable")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        c.with_correlation(1, lambda: None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        c.with_correlation("r", "x")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        c.with_correlation()  # type: ignore[call-arg]
    assert c.with_correlation(lambda: 1) == 1
    assert c.with_correlation("  ", lambda: 2) == 2
    assert c.with_correlation("ok", lambda: 3) == 3


def test_capture_fallbacks() -> None:
    mem = MemoryExporter()
    c = IntentProofClient(IntentProofConfig(exporters=[mem]))

    def bad_in(_a: object) -> dict[str, Any]:
        raise RuntimeError("n")

    c.wrap({"intent": "i", "action": "a", "capture_input": bad_in}, lambda: 1)()
    assert mem.get_events()[-1]["inputs"] == []

    mem2 = MemoryExporter()
    c2 = IntentProofClient(IntentProofConfig(exporters=[mem2]))

    def bad_out(_o: object) -> object:
        raise RuntimeError("n")

    c2.wrap({"intent": "i", "action": "a", "capture_output": bad_out}, lambda: {"k": 1})()
    assert mem2.get_events()[-1]["output"] == {"k": 1}


def test_exporter_sync_error_and_awaitable_export() -> None:
    class Boom:
        def export(self, _e: ExecutionEvent) -> None:
            raise ValueError("b")

    class CoroEx:
        def export(self, _e: ExecutionEvent) -> object:
            async def inner() -> None:
                await asyncio.sleep(0)

            return inner()

    mem = MemoryExporter()
    c = IntentProofClient(IntentProofConfig(exporters=[Boom(), mem]))
    c.wrap(intent="i", action="a", fn=lambda: 1)()

    mem2 = MemoryExporter()
    c2 = IntentProofClient(IntentProofConfig(exporters=[CoroEx(), mem2]))
    c2.wrap(intent="i", action="a", fn=lambda: 1)()
    for _ in range(200):
        if mem2.get_events():
            break
        time.sleep(0.01)
    assert mem2.get_events()


def test_emit_handler_raises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)

    def bad_handler(_e: BaseException, _ev: ExecutionEvent) -> None:
        raise RuntimeError("h")

    mem = MemoryExporter()
    c = IntentProofClient(IntentProofConfig(exporters=[Boom(), mem], on_exporter_error=bad_handler))
    c.wrap(intent="i", action="a", fn=lambda: 1)()
    assert any("on_exporter_error failed" in r.message for r in caplog.records)


class Boom:
    def export(self, _e: ExecutionEvent) -> None:
        raise ValueError("b")


def test_maybe_schedule_on_err_raises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)

    async def bad() -> None:
        raise ValueError("inner")

    def on_err(_e: BaseException, _ev: ExecutionEvent) -> None:
        raise RuntimeError("on")

    ev = ExecutionEvent(
        id="1",
        intent="i",
        action="a",
        inputs={},
        status="ok",
        started_at="s",
        completed_at="c",
        duration_ms=0,
    )
    _maybe_schedule_awaitable(bad(), on_err, ev)
    for _ in range(200):
        if any("on_exporter_error failed" in r.message for r in caplog.records):
            break
        time.sleep(0.01)


@pytest.mark.asyncio
async def test_flush_shutdown_variants() -> None:
    mem = MemoryExporter()

    class FlushAwait:
        def export(self, _e: ExecutionEvent) -> None:
            return None

        def flush(self) -> Any:
            async def f() -> None:
                return None

            return f()

        def shutdown(self) -> Any:
            async def s() -> None:
                return None

            return s()

    class ShutdownFlushAwait:
        def export(self, _e: ExecutionEvent) -> None:
            return None

        def shutdown(self) -> None:
            pass

        def flush(self) -> Any:
            async def f() -> None:
                return None

            return f()

    class OnlyFlush:
        def export(self, _e: ExecutionEvent) -> None:
            return None

        def flush(self) -> None:
            return None

    class NoFlush:
        def export(self, _e: ExecutionEvent) -> None:
            return None

    c = IntentProofClient(IntentProofConfig(exporters=[mem, FlushAwait(), ShutdownFlushAwait()]))
    await c.flush()
    await c.shutdown()

    c2 = IntentProofClient(IntentProofConfig(exporters=[NoFlush(), mem]))
    await c2.flush()

    c3 = IntentProofClient(IntentProofConfig(exporters=[OnlyFlush()]))
    await c3.shutdown()

    class AwaitFlushOnly:
        def export(self, _e: ExecutionEvent) -> None:
            return None

        def flush(self) -> Any:
            async def f() -> None:
                return None

            return f()

    await IntentProofClient(IntentProofConfig(exporters=[AwaitFlushOnly()])).shutdown()


@pytest.mark.asyncio
async def test_async_wrap_and_error_paths() -> None:
    mem = MemoryExporter()
    c = IntentProofClient(IntentProofConfig(exporters=[mem]))

    @c.wrap(intent="a", action="a.b")
    async def add(x: int, y: int) -> int:
        await asyncio.sleep(0)
        return x + y

    assert await add(1, 2) == 3

    async def boom() -> None:
        raise RuntimeError("e")

    def bad_cap(_e: BaseException) -> object:
        raise RuntimeError("cap")

    w = c.wrap({"intent": "i", "action": "a", "capture_error": bad_cap}, boom)
    with pytest.raises(RuntimeError):
        await w()


def test_decorator_wrap_style() -> None:
    mem = MemoryExporter()
    c = IntentProofClient(IntentProofConfig(exporters=[mem]))

    @c.wrap(intent="i", action="a")
    def f() -> int:
        return 9

    assert f() == 9


def test_assert_wrap_public_api() -> None:
    assert_wrap_options_shape({"intent": "i", "action": "a"})
