"""Proof pipeline workflows: connected paths through client, wrap, correlation, exporters.

These run in-process against the package surface only — not deployed-system E2E,
not multi-repository integration. They span more than a single unit but stay inside
one interpreter with no real remote ingest.
"""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

import pytest

from intentproof import (
    ExecutionEvent,
    IntentProofClient,
    IntentProofConfig,
    MemoryExporter,
    run_with_correlation_id,
)
from intentproof.exporters import (
    HTTP_EXPORTER_FALLBACK_BODY,
    BoundedQueueExporter,
    HttpExporter,
    safe_json_envelope,
)

_ISO_MS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_pipeline_record_execution_proof_sync_ok_path() -> None:
    """Typical flow: isolated client, defaults + wrap options, proof in MemoryExporter."""
    mem = MemoryExporter(max_events=50)
    client = IntentProofClient(
        IntentProofConfig(
            exporters=[mem],
            default_attributes={"service": "payments", "env": "test"},
        ),
    )

    @client.wrap(
        intent="Capture authorized funds",
        action="stripe.payment_intent.capture",
        attributes={"step": "capture"},
    )
    def capture(pi_id: str) -> dict[str, str]:
        return {"status": "succeeded", "id": pi_id}

    with run_with_correlation_id("req-proof-1"):
        out = capture("pi_abc")

    assert out["status"] == "succeeded"

    events = mem.get_events()
    assert len(events) == 1
    ev = events[0]

    assert ev["intent"] == "Capture authorized funds"
    assert ev["action"] == "stripe.payment_intent.capture"
    assert ev["status"] == "ok"
    assert ev["correlationId"] == "req-proof-1"
    assert ev["attributes"] == {"service": "payments", "env": "test", "step": "capture"}
    assert ev["inputs"] == ["pi_abc"]
    assert ev["output"] == {"status": "succeeded", "id": "pi_abc"}

    assert _ISO_MS.match(ev["startedAt"])
    assert _ISO_MS.match(ev["completedAt"])
    assert isinstance(ev["durationMs"], int) and ev["durationMs"] >= 0
    assert ev["startedAt"] <= ev["completedAt"]


def test_pipeline_wrap_raises_emit_error_event_and_capture_error() -> None:
    mem = MemoryExporter()
    client = IntentProofClient(
        IntentProofConfig(exporters=[mem], include_error_stack=False),
    )

    def decline(_: str) -> None:
        raise RuntimeError("card declined")

    run = client.wrap(
        intent="Capture",
        action="stripe.capture",
        capture_error=lambda _e: {"code": "card_declined"},
        fn=decline,
    )

    with pytest.raises(RuntimeError, match="declined"):
        run("pi_x")

    ev = mem.get_events()[0]
    assert ev["status"] == "error"
    assert ev["error"]["name"] == "RuntimeError"
    assert "stack" not in ev["error"]
    assert ev["output"] == {"code": "card_declined"}


@pytest.mark.asyncio
async def test_pipeline_async_wrap_error_path() -> None:
    mem = MemoryExporter()
    client = IntentProofClient(IntentProofConfig(exporters=[mem]))

    @client.wrap(intent="async", action="async.fail")
    async def boom() -> None:
        raise ValueError("async err")

    with pytest.raises(ValueError):
        await boom()

    assert mem.get_events()[0]["status"] == "error"


def test_pipeline_http_exporter_posts_json_envelope() -> None:
    captured: dict[str, bytes] = {}

    def fake_urlopen(req: object, timeout: float = 30.0, **_kwargs: object) -> object:
        r = MagicMock()
        r.read.return_value = b"{}"
        captured["data"] = getattr(req, "data", b"")
        return r

    mem = MemoryExporter()
    http = HttpExporter("http://collector.test/ingest", await_each=True, timeout_ms=5_000)
    client = IntentProofClient(IntentProofConfig(exporters=[mem, http]))

    with patch("urllib.request.urlopen", fake_urlopen):
        client.wrap(intent="HTTP proof", action="test.http", fn=lambda: 42)()

    body = json.loads(captured["data"].decode())
    assert body["intentproof"] == "1"
    assert body["event"]["intent"] == "HTTP proof"
    assert body["event"]["output"] == 42


def test_pipeline_bounded_queue_drains_to_inner_exporter() -> None:
    """Events pass through BoundedQueueExporter to an inner MemoryExporter."""
    mem = MemoryExporter()
    bq = BoundedQueueExporter(exporter=mem, max_concurrent=2, max_queue=100)
    client = IntentProofClient(IntentProofConfig(exporters=[bq]))
    for i in range(4):
        client.wrap({"intent": "i", "action": "a"}, lambda x=i: x)()
    bq.flush()
    assert len(mem.get_events()) == 4


def test_pipeline_safe_json_envelope_triple_fallback() -> None:
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

    def bust(*_a: object, **_k: object) -> str:
        raise TypeError("no")

    with patch("intentproof.exporters.json.dumps", side_effect=bust):
        assert safe_json_envelope(ev) == HTTP_EXPORTER_FALLBACK_BODY
