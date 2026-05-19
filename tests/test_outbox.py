"""Outbox persistence, chain state, and transaction behavior."""

from __future__ import annotations

import pytest

from intentproof.outbox import Outbox
from intentproof.signing import SENTINEL_PREV_HASH, event_content_hash


def _sample_event(event_id: str, correlation_id: str, position: int, prev_hash: str) -> dict:
    body = {
        "schema": "intentproof.event.v1",
        "event_id": event_id,
        "correlation_id": correlation_id,
        "chain_position": position,
        "prev_event_hash": prev_hash,
        "status": "ok",
    }
    return body, event_content_hash(body)


def test_append_and_query_events(tmp_path) -> None:
    outbox = Outbox(str(tmp_path / "outbox.db"))
    body = {"event_id": "evt_1", "status": "ok"}
    outbox.append("evt_1", body)
    assert outbox.get_events() == [body]
    outbox.close()


def test_record_chained_event_builds_chain(tmp_path) -> None:
    outbox = Outbox(str(tmp_path / "outbox.db"))

    def build_first(pos: int, prev: str) -> tuple[dict, str]:
        event = {
            "event_id": "evt_a",
            "correlation_id": "corr-1",
            "chain_position": pos,
            "prev_event_hash": prev,
        }
        return event, event_content_hash(event)

    outbox.record_chained_event("corr-1", "evt_a", build_first)

    def build_second(pos: int, prev: str) -> tuple[dict, str]:
        event = {
            "event_id": "evt_b",
            "correlation_id": "corr-1",
            "chain_position": pos,
            "prev_event_hash": prev,
        }
        return event, event_content_hash(event)

    outbox.record_chained_event("corr-1", "evt_b", build_second)

    state = outbox.get_chain_state("corr-1")
    assert state is not None
    assert state["position"] == 2
    assert len(outbox.get_events()) == 2
    outbox.close()


def test_append_with_chain_state_and_set_chain_state(tmp_path) -> None:
    outbox = Outbox(str(tmp_path / "outbox.db"))
    body, event_hash = _sample_event("evt_1", "corr-x", 1, SENTINEL_PREV_HASH)
    outbox.append_with_chain_state("evt_1", body, "corr-x", 1, event_hash)

    state = outbox.get_chain_state("corr-x")
    assert state == {"position": 1, "hash": event_hash}

    body2, hash2 = _sample_event("evt_2", "corr-x", 2, event_hash)
    outbox.set_chain_state("corr-x", 2, hash2)
    outbox.append_with_chain_state("evt_2", body2, "corr-x", 2, hash2)

    assert outbox.get_chain_state("corr-x") == {"position": 2, "hash": hash2}
    outbox.close()


def test_record_chained_event_rolls_back_on_duplicate_id(tmp_path) -> None:
    outbox = Outbox(str(tmp_path / "outbox.db"))
    body, event_hash = _sample_event("evt_dup", "corr-dup", 1, SENTINEL_PREV_HASH)
    outbox.append_with_chain_state("evt_dup", body, "corr-dup", 1, event_hash)

    def build_duplicate(_pos: int, _prev: str) -> tuple[dict, str]:
        dup_body, dup_hash = _sample_event("evt_dup", "corr-dup", 2, event_hash)
        return dup_body, dup_hash

    with pytest.raises(Exception):
        outbox.record_chained_event("corr-dup", "evt_dup", build_duplicate)

    assert outbox.get_chain_state("corr-dup") == {"position": 1, "hash": event_hash}
    outbox.close()


def test_get_chain_state_missing_returns_none(tmp_path) -> None:
    outbox = Outbox(str(tmp_path / "outbox.db"))
    assert outbox.get_chain_state("missing") is None
    outbox.close()


def test_append_with_chain_state_rolls_back_on_failure(tmp_path) -> None:
    outbox = Outbox(str(tmp_path / "outbox.db"))
    body, event_hash = _sample_event("evt_1", "corr-rb", 1, SENTINEL_PREV_HASH)
    outbox.append_with_chain_state("evt_1", body, "corr-rb", 1, event_hash)

    with pytest.raises(Exception):
        outbox.append_with_chain_state("evt_1", body, "corr-rb", 2, event_hash)

    assert outbox.get_chain_state("corr-rb") == {"position": 1, "hash": event_hash}
    outbox.close()
