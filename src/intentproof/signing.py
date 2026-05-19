"""Ed25519 signing over JCS-canonical execution events."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from intentproof.canon import canonicalize

SENTINEL_PREV_HASH = (
    "sha256:0000000000000000000000000000000000000000000000000000000000000000"
)


def canonicalize_event(event: dict[str, Any]) -> str:
    unsigned = {k: v for k, v in event.items() if k != "signature"}
    return canonicalize(unsigned)


def event_content_hash(event: dict[str, Any]) -> str:
    canonical = canonicalize_event(event)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def sign_event(
    event: dict[str, Any],
    private_key: Ed25519PrivateKey,
    instance_id: str,
) -> dict[str, Any]:
    canonical = canonicalize_event(event)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    signature = private_key.sign(digest)
    signed = dict(event)
    signed["signature"] = {
        "alg": "ed25519",
        "key_id": f"{instance_id}:k1",
        "value": base64.b64encode(signature).decode("ascii"),
    }
    return signed


def verify_event_signature(
    event: dict[str, Any], public_key: Ed25519PublicKey
) -> bool:
    sig_block = event.get("signature")
    if not sig_block:
        return False
    canonical = canonicalize_event(event)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    try:
        public_key.verify(
            base64.b64decode(sig_block["value"]), digest
        )
    except Exception:
        return False
    return True


def load_private_key(raw_b64: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(
        base64.b64decode(raw_b64)
    )
