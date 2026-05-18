"""HTTP export helpers for hosted ingest."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping


def ingest_request_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("INTENTPROOF_INGEST_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def post_execution_event(ingest_url: str, event: Mapping[str, Any]) -> None:
    body = json.dumps(event).encode("utf-8")
    request = urllib.request.Request(
        ingest_url,
        data=body,
        headers=ingest_request_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status not in (200, 202):
                raise RuntimeError(f"ingest POST returned {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"ingest POST {exc.code}: {detail}") from exc
