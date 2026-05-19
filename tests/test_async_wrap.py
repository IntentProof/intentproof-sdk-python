"""Async wrap behavior tests."""

from __future__ import annotations

import asyncio

import pytest

from intentproof import client, configure, wrap


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
