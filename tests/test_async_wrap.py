"""Async wrap behavior tests."""

from __future__ import annotations

import asyncio

import pytest

from intentproof import client, configure, run_with_correlation_id, wrap


def test_cancelled_error_not_recorded(tmp_path) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_async",
    )

    async def cancelled() -> None:
        raise asyncio.CancelledError()

    fn = wrap(intent="Test", action="test.action", fn=cancelled)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(fn())

    assert client.get_outbox().get_events() == []


def test_async_wrap_records_success(tmp_path) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_async",
    )

    async def add(a: int, b: int) -> int:
        return a + b

    fn = wrap(intent="Async", action="async.add", fn=add)
    result = run_with_correlation_id("corr-async-ok", lambda: asyncio.run(fn(2, 3)))

    assert result == 5
    events = client.get_outbox().get_events()
    assert len(events) == 1
    assert events[0]["status"] == "ok"
    assert events[0]["output"] == 5


def test_async_wrap_records_error(tmp_path) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_async",
    )

    async def boom() -> None:
        raise ValueError("async boom")

    fn = wrap(intent="Async", action="async.boom", fn=boom)
    with pytest.raises(ValueError, match="async boom"):
        asyncio.run(fn())

    events = client.get_outbox().get_events()
    assert events[-1]["status"] == "error"
    assert events[-1]["error"] == {"message": "async boom"}


def test_async_wrap_preserves_app_error_when_record_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_async",
    )

    async def boom() -> None:
        raise ValueError("async boom")

    fn = wrap(intent="Async", action="async.boom", fn=boom)

    def fail_record(**_kwargs: object) -> None:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(
        "intentproof.instrumentation._record_execution", fail_record
    )

    with pytest.raises(ValueError, match="async boom") as exc_info:
        asyncio.run(fn())

    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_async_wrap_record_failure_without_app_error_logs_and_returns(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_async",
    )

    async def ok() -> int:
        return 1

    fn = wrap(intent="Async", action="async.ok", fn=ok)

    def fail_record(**_kwargs: object) -> None:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(
        "intentproof.instrumentation._record_execution", fail_record
    )

    with caplog.at_level("WARNING", logger="intentproof.instrumentation"):
        assert asyncio.run(fn()) == 1
    assert any(
        "execution record failed" in record.message for record in caplog.records
    )
