"""HTTP exporter response edge cases."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
import urllib.error

from intentproof.exporter import post_execution_event


def test_post_execution_event_wraps_http_error_detail() -> None:
    body = io.BytesIO(b"server error")
    error = urllib.error.HTTPError(
        "http://127.0.0.1:1/v1/events",
        500,
        "Internal Server Error",
        {},
        body,
    )

    with patch("intentproof.exporter.urllib.request.urlopen", side_effect=error):
        with pytest.raises(RuntimeError, match="ingest POST 500: server error"):
            post_execution_event(
                "http://127.0.0.1:1/v1/events",
                {"schema": "intentproof.event.v1"},
            )


def test_post_execution_event_rejects_unexpected_success_status() -> None:
    response = MagicMock()
    response.status = 204
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)

    with patch("intentproof.exporter.urllib.request.urlopen", return_value=response):
        with pytest.raises(RuntimeError, match="ingest POST returned 204"):
            post_execution_event(
                "http://127.0.0.1:1/v1/events",
                {"schema": "intentproof.event.v1"},
            )
