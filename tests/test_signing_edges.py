"""Signing verification edge cases."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentproof.signing import verify_event_signature


def test_verify_rejects_missing_signature() -> None:
    private_key = Ed25519PrivateKey.generate()
    event = {"schema": "intentproof.event.v1", "event_id": "evt_unsigned"}
    assert verify_event_signature(event, private_key.public_key()) is False


def test_verify_rejects_tampered_signature() -> None:
    private_key = Ed25519PrivateKey.generate()
    digest = b"\x00" * 32
    signature = base64.b64encode(private_key.sign(digest)).decode("ascii")
    event = {
        "schema": "intentproof.event.v1",
        "signature": {"value": signature},
    }
    other_key = Ed25519PrivateKey.generate()
    assert verify_event_signature(event, other_key.public_key()) is False
