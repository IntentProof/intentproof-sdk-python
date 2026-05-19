"""Background HTTP export of signed events to ingest."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Mapping

from intentproof.exporter import ingest_request_headers, post_execution_event

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_INGEST_URL = "http://127.0.0.1:9787/v1/events"


def resolve_ingest_url(explicit: str | None = None) -> str | None:
    raw = (explicit or os.environ.get("INTENTPROOF_INGEST_URL", "")).strip()
    if raw:
        return _normalize_ingest_url(raw)
    if os.environ.get("INTENTPROOF_USE_LOCAL_INGEST", "").strip() == "1":
        return DEFAULT_LOCAL_INGEST_URL
    return None


def _normalize_ingest_url(raw: str) -> str:
    trimmed = raw.strip().rstrip("/")
    if trimmed.endswith("/v1/events"):
        return trimmed
    return f"{trimmed}/v1/events"


class HttpExporter:
    def __init__(self, ingest_url: str) -> None:
        self._ingest_url = ingest_url
        self._lock = threading.Lock()
        self._pending: list[threading.Thread] = []

    @property
    def ingest_url(self) -> str:
        return self._ingest_url

    def enqueue(self, event: Mapping[str, Any]) -> None:
        thread = threading.Thread(
            target=self._export_one,
            args=(dict(event),),
            daemon=True,
        )
        with self._lock:
            self._pending.append(thread)
        thread.start()

    def _export_one(self, event: dict[str, Any]) -> None:
        try:
            post_execution_event(self._ingest_url, event)
        except Exception as exc:
            logger.warning("[intentproof] ingest export failed: %s", exc)

    def flush(self) -> None:
        with self._lock:
            threads = list(self._pending)
            self._pending.clear()
        for thread in threads:
            thread.join()
