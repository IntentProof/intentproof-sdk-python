"""End-to-end local-loop flows: configure, wrap, outbox, and HTTP export."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from intentproof import client, configure, flush, push_subject_mapping, run_with_correlation_id, wrap
from intentproof.exporter import post_execution_event
from intentproof.http_exporter import HttpExporter, resolve_ingest_url
from intentproof.signing import verify_event_signature


class _IngestHandler(BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).received.append(body)
        self.send_response(202)
        self.end_headers()


@pytest.fixture
def ingest_server() -> tuple[str, type[_IngestHandler]]:
    _IngestHandler.received = []
    server = HTTPServer(("127.0.0.1", 0), _IngestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"
    try:
        yield base_url, _IngestHandler
    finally:
        server.shutdown()
        thread.join(timeout=2.0)


def test_local_loop_wrap_flush_posts_to_ingest(
    tmp_path: Path, ingest_server: tuple[str, type[_IngestHandler]]
) -> None:
    base_url, handler_cls = ingest_server
    data_dir = tmp_path / "data"
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(data_dir),
        tenant_id="tnt_e2e",
        ingest_url=base_url,
    )
    push_subject_mapping("src", "user", "usr_1")

    fn = wrap(intent="Pay", action="payments.charge", fn=lambda amount: amount * 100)
    result = run_with_correlation_id("corr-e2e", lambda: fn(42))
    assert result == 4200

    flush()

    assert len(handler_cls.received) == 1
    posted = handler_cls.received[0]
    assert posted["tenant_id"] == "tnt_e2e"
    assert posted["correlation_id"] == "corr-e2e"
    assert posted["status"] == "ok"
    assert verify_event_signature(posted, client.get_public_key())

    stored = client.get_outbox().get_events()
    assert len(stored) == 1
    assert stored[0]["event_id"] == posted["event_id"]


def test_configure_default_outbox_path_under_data_dir(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    configure(
        data_dir=str(data_dir),
        tenant_id="tnt_default_db",
    )
    assert (data_dir / "outbox.db").exists()


def test_configure_from_environment_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ingest_server: tuple[str, type[_IngestHandler]],
) -> None:
    base_url, _handler_cls = ingest_server
    home = tmp_path / "home"
    home.mkdir()
    custom_db = tmp_path / "env-outbox.db"

    monkeypatch.setenv("INTENTPROOF_TENANT_ID", "tnt_from_env")
    monkeypatch.setenv("INTENTPROOF_OUTBOX_PATH", str(custom_db))
    monkeypatch.setenv("INTENTPROOF_INGEST_URL", base_url)

    with patch.object(Path, "home", return_value=home):
        configure()

    assert client.get_tenant_id() == "tnt_from_env"
    assert custom_db.exists()
    assert (home / ".intentproof" / "sdk-python" / "keypair.json").exists()

    fn = wrap(intent="Env", action="env.test", fn=lambda: "ok")
    run_with_correlation_id("corr-env", fn)
    flush()


def test_resolve_ingest_url_local_ingest_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTENTPROOF_INGEST_URL", raising=False)
    monkeypatch.setenv("INTENTPROOF_USE_LOCAL_INGEST", "1")
    assert resolve_ingest_url() == "http://127.0.0.1:9787/v1/events"


def test_resolve_ingest_url_appends_events_suffix() -> None:
    assert (
        resolve_ingest_url("https://ingest.example.com")
        == "https://ingest.example.com/v1/events"
    )


def test_reconfigure_flushes_previous_exporter(
    tmp_path: Path, ingest_server: tuple[str, type[_IngestHandler]]
) -> None:
    base_url, handler_cls = ingest_server
    data_dir = tmp_path / "data"
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(data_dir),
        tenant_id="tnt_flush",
        ingest_url=base_url,
    )
    fn = wrap(intent="Flush", action="flush.test", fn=lambda: None)
    run_with_correlation_id("corr-flush", fn)

    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(data_dir),
        tenant_id="tnt_flush",
    )

    assert len(handler_cls.received) == 1


def test_http_exporter_surfaces_ingest_url() -> None:
    exporter = HttpExporter("http://127.0.0.1:1/v1/events")
    assert exporter.ingest_url.endswith("/v1/events")


def test_post_execution_event_accepts_200(
    ingest_server: tuple[str, type[_IngestHandler]],
) -> None:
    base_url, handler_cls = ingest_server
    post_execution_event(
        f"{base_url}/v1/events",
        {"schema": "intentproof.event.v1", "event_id": "evt_test"},
    )
    assert len(handler_cls.received) == 1


def test_export_logs_ingest_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    exporter = HttpExporter("http://127.0.0.1:1/v1/events")
    with caplog.at_level("WARNING"):
        exporter._export_one({"schema": "intentproof.event.v1"})
    assert any("ingest export failed" in record.message for record in caplog.records)


def test_wrap_without_inputs_marks_untrusted_when_output_present(
    tmp_path: Path,
) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_trusted",
    )

    fn = wrap(intent="No args", action="trusted.test", fn=lambda: {"ok": True})
    run_with_correlation_id("corr-trusted", fn)

    ev = client.get_outbox().get_events()[0]
    assert ev["untrusted_payload"] is True
    assert ev["inputs"] == []


def test_wrap_without_inputs_and_none_output_is_trusted(
    tmp_path: Path,
) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_none",
    )

    fn = wrap(intent="Void", action="void.test", fn=lambda: None)
    run_with_correlation_id("corr-none", fn)

    ev = client.get_outbox().get_events()[0]
    assert ev["untrusted_payload"] is False


def test_wrap_record_failure_without_app_error_logs_and_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure(
        db_path=str(tmp_path / "outbox.db"),
        data_dir=str(tmp_path / "data"),
        tenant_id="tnt_record",
    )

    def fail_record(**_kwargs: object) -> None:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(
        "intentproof.instrumentation._record_execution", fail_record
    )

    fn = wrap(intent="Record fail", action="record.fail", fn=lambda: 1)
    with caplog.at_level("WARNING", logger="intentproof.instrumentation"):
        assert fn() == 1
    assert any(
        "execution record failed" in record.message for record in caplog.records
    )


def test_sdk_not_configured_errors() -> None:
    import intentproof.client as client_module

    saved = (
        client_module._outbox,
        client_module._instance_id,
        client_module._instance_private_key,
    )
    client_module._outbox = None
    client_module._instance_id = None
    client_module._instance_private_key = None
    try:
        with pytest.raises(RuntimeError, match="SDK not configured"):
            client.get_outbox()
        with pytest.raises(RuntimeError, match="SDK not configured"):
            client.get_instance_id()
        with pytest.raises(RuntimeError, match="SDK not configured"):
            client.get_private_key()
    finally:
        (
            client_module._outbox,
            client_module._instance_id,
            client_module._instance_private_key,
        ) = saved
