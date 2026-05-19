"""SDK wrap, outbox, and signing tests."""

from __future__ import annotations

import base64
import json
import tempfile
import threading
from pathlib import Path

import pytest

from intentproof import client, configure, flush, run_with_correlation_id, wrap
from intentproof.signing import (
    canonicalize_event,
    event_content_hash,
    load_private_key,
    sign_event,
    verify_event_signature,
)


@pytest.fixture
def sdk_dirs(tmp_path: Path) -> tuple[str, str]:
    data_dir = tmp_path / "data"
    db_path = str(tmp_path / "outbox.db")
    return str(db_path), str(data_dir)


def test_persists_keypair_across_configure(sdk_dirs: tuple[str, str]) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    id1 = client.get_instance_id()
    pub1 = client.get_public_key().public_bytes_raw()

    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    id2 = client.get_instance_id()
    pub2 = client.get_public_key().public_bytes_raw()

    assert id1 == id2
    assert pub1 == pub2


def test_generates_new_keypair_for_fresh_data_dir(
    sdk_dirs: tuple[str, str],
) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    id1 = client.get_instance_id()

    fresh_dir = Path(data_dir).parent / "fresh"
    configure(db_path=db_path, data_dir=str(fresh_dir), tenant_id="tnt_a")
    id2 = client.get_instance_id()

    assert id1 != id2


def test_produces_signed_event_with_sentinel_prev_hash(
    sdk_dirs: tuple[str, str],
) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")

    fn = wrap(intent="Test", action="test.action", fn=lambda x: x * 2)

    run_with_correlation_id("corr-1", lambda: fn(5))

    events = client.get_outbox().get_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["chain_position"] == 1
    assert (
        ev["prev_event_hash"]
        == "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )
    assert ev["signature"]["alg"] == "ed25519"
    assert ev["signature"]["value"]
    assert ev["provenance_class"] == "sdk_attested_evidence"
    assert ev["untrusted_payload"] is True


def test_wrap_records_from_worker_thread(sdk_dirs: tuple[str, str]) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    fn = wrap(intent="Test", action="test.action", fn=lambda x: x + 1)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            run_with_correlation_id("corr-worker", lambda: fn(2))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=2.0)

    assert not errors
    events = client.get_outbox().get_events()
    assert any(e["correlation_id"] == "corr-worker" for e in events)


def test_configure_closes_previous_outbox(sdk_dirs: tuple[str, str]) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    first = client.get_outbox()

    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    second = client.get_outbox()

    assert first is not second
    fn = wrap(intent="Test", action="test.action", fn=lambda x: x + 1)
    run_with_correlation_id("corr-reconfig", lambda: fn(1))
    assert len(client.get_outbox().get_events()) == 1


def test_chain_continuity_across_reconfigure(sdk_dirs: tuple[str, str]) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    fn = wrap(intent="Test", action="test.action", fn=lambda x: x * 2)
    run_with_correlation_id("corr-2", lambda: fn(1))

    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    fn2 = wrap(intent="Test", action="test.action", fn=lambda x: x * 2)
    run_with_correlation_id("corr-2", lambda: fn2(2))

    events = client.get_outbox().get_events()
    assert len(events) == 2
    ev2 = next(e for e in events if e["chain_position"] == 2)
    assert ev2["prev_event_hash"].startswith("sha256:")
    assert (
        ev2["prev_event_hash"]
        != "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )


def test_correlation_isolation(sdk_dirs: tuple[str, str]) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    fn = wrap(intent="Test", action="test.action", fn=lambda x: x * 2)

    run_with_correlation_id("corr-a", lambda: fn(1))
    run_with_correlation_id("corr-b", lambda: fn(2))

    events = client.get_outbox().get_events()
    ev_a = next(e for e in events if e["correlation_id"] == "corr-a")
    ev_b = next(e for e in events if e["correlation_id"] == "corr-b")
    assert ev_a["chain_position"] == 1
    assert ev_b["chain_position"] == 1


def test_verifiable_ed25519_signature(sdk_dirs: tuple[str, str]) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")
    fn = wrap(intent="Test", action="test.action", fn=lambda x: x * 2)
    run_with_correlation_id("corr-verify", lambda: fn(7))

    ev = next(
        e
        for e in client.get_outbox().get_events()
        if e["correlation_id"] == "corr-verify"
    )
    assert verify_event_signature(ev, client.get_public_key())


def test_wrap_preserves_app_exception_when_record_fails(
    sdk_dirs: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")

    def boom() -> None:
        raise ValueError("boom")

    fn = wrap(intent="Test", action="test.action", fn=boom)

    def fail_record(**_kwargs: object) -> None:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(
        "intentproof.instrumentation._record_execution", fail_record
    )

    with pytest.raises(ValueError, match="boom") as exc_info:
        fn()

    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_wrap_reraises_exception(sdk_dirs: tuple[str, str]) -> None:
    db_path, data_dir = sdk_dirs
    configure(db_path=db_path, data_dir=data_dir, tenant_id="tnt_a")

    def boom() -> None:
        raise ValueError("boom")

    fn = wrap(intent="Test", action="test.action", fn=boom)
    with pytest.raises(ValueError, match="boom"):
        fn()

    events = client.get_outbox().get_events()
    assert events[-1]["status"] == "error"
    assert events[-1]["error"] == {"message": "boom"}


def test_flush_waits_for_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        configure(
            db_path=f"{tmp}/outbox.db",
            data_dir=f"{tmp}/data",
            tenant_id="tnt_a",
            ingest_url="http://127.0.0.1:9/v1/events",
        )
        posted: list[dict] = []

        def fake_post(url: str, event: dict) -> None:
            posted.append(event)

        monkeypatch.setattr(
            "intentproof.http_exporter.post_execution_event", fake_post
        )
        fn = wrap(intent="Export", action="export.test", fn=lambda n: n + 1)
        run_with_correlation_id("corr-export", lambda: fn(1))
        flush()
        assert len(posted) == 1


def test_signing_golden_bytes() -> None:
    fixture_dir = Path(__file__).parent / "fixtures"
    unsigned = json.loads(
        (fixture_dir / "signing_unsigned_event.json").read_text(encoding="utf-8")
    )
    expected_canonical = (
        fixture_dir / "signing_canonical_utf8.txt"
    ).read_text(encoding="utf-8")
    expected_hash = (
        fixture_dir / "signing_event_hash.txt"
    ).read_text(encoding="utf-8").strip()
    expected_sig = (
        fixture_dir / "signing_signature_b64.txt"
    ).read_text(encoding="utf-8").strip()
    private_key_b64 = (
        fixture_dir / "signing_private_key_b64.txt"
    ).read_text(encoding="utf-8").strip()

    assert canonicalize_event(unsigned) == expected_canonical
    private_key = load_private_key(private_key_b64)
    signed = sign_event(unsigned, private_key, "inst_golden_test")
    assert event_content_hash(signed) == expected_hash
    assert signed["signature"]["value"] == expected_sig
    assert verify_event_signature(signed, private_key.public_key())
