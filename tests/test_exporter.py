import os
import threading

import pytest

from intentproof.exporter import ingest_request_headers
from intentproof.http_exporter import HttpExporter


def test_ingest_request_headers_includes_bearer_token() -> None:
    previous = os.environ.get("INTENTPROOF_INGEST_TOKEN")
    os.environ["INTENTPROOF_INGEST_TOKEN"] = "ingest-secret"
    try:
        headers = ingest_request_headers()
        assert headers["Authorization"] == "Bearer ingest-secret"
    finally:
        if previous is None:
            os.environ.pop("INTENTPROOF_INGEST_TOKEN", None)
        else:
            os.environ["INTENTPROOF_INGEST_TOKEN"] = previous


def test_enqueue_prunes_finished_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    exporter = HttpExporter("http://127.0.0.1:9787/v1/events")
    monkeypatch.setattr(
        "intentproof.http_exporter.post_execution_event",
        lambda _url, _event: None,
    )

    for _ in range(3):
        exporter.enqueue({"schema": "intentproof.event.v1"})

    with exporter._lock:
        threads = list(exporter._pending)
    for thread in threads:
        thread.join(timeout=2.0)

    exporter.enqueue({"schema": "intentproof.event.v1"})

    with exporter._lock:
        assert len(exporter._pending) == 1


def test_enqueue_starts_thread_before_releasing_lock() -> None:
    order: list[str] = []
    inner = threading.Lock()

    class TrackingLock:
        def __enter__(self) -> "TrackingLock":
            inner.acquire()
            return self

        def __exit__(self, *args: object) -> None:
            order.append("lock_release")
            inner.release()

    exporter = HttpExporter("http://127.0.0.1:9787/v1/events")
    exporter._lock = TrackingLock()  # type: ignore[assignment]

    original_start = threading.Thread.start

    def tracked_start(self: threading.Thread) -> None:
        order.append("start")
        original_start(self)

    threading.Thread.start = tracked_start  # type: ignore[method-assign]
    try:
        exporter.enqueue({"schema": "intentproof.event.v1"})
    finally:
        threading.Thread.start = original_start  # type: ignore[method-assign]

    assert order.index("start") < order.index("lock_release")


def test_ingest_request_headers_omits_authorization_without_token() -> None:
    previous = os.environ.get("INTENTPROOF_INGEST_TOKEN")
    os.environ.pop("INTENTPROOF_INGEST_TOKEN", None)
    try:
        headers = ingest_request_headers()
        assert "Authorization" not in headers
    finally:
        if previous is not None:
            os.environ["INTENTPROOF_INGEST_TOKEN"] = previous
