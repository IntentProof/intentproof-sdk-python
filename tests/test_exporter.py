import os

from intentproof.exporter import ingest_request_headers


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


def test_ingest_request_headers_omits_authorization_without_token() -> None:
    previous = os.environ.get("INTENTPROOF_INGEST_TOKEN")
    os.environ.pop("INTENTPROOF_INGEST_TOKEN", None)
    try:
        headers = ingest_request_headers()
        assert "Authorization" not in headers
    finally:
        if previous is not None:
            os.environ["INTENTPROOF_INGEST_TOKEN"] = previous
