"""SDK configuration and shared runtime state."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from intentproof.http_exporter import HttpExporter, resolve_ingest_url
from intentproof.keys import ensure_dir, load_or_create_keypair
from intentproof.outbox import Outbox
from intentproof.signing import load_private_key

if TYPE_CHECKING:
    from intentproof.signing import Ed25519PublicKey

SDK_VERSION = "python@0.1.0"


def default_data_dir() -> Path:
    """Default SDK data directory (resolved lazily for container imports)."""
    return Path.home() / ".intentproof" / "sdk-python"

_instance_private_key: Ed25519PrivateKey | None = None
_instance_id: str | None = None
_tenant_id: str = "tnt_default"
_outbox: Outbox | None = None
_exporter: HttpExporter | None = None
_data_dir: Path | None = None


def configure(
    *,
    db_path: str | None = None,
    tenant_id: str | None = None,
    data_dir: str | Path | None = None,
    ingest_url: str | None = None,
) -> None:
    global _instance_private_key, _instance_id, _tenant_id, _outbox, _exporter, _data_dir

    if _exporter is not None:
        _exporter.flush()
    if _outbox is not None:
        _outbox.close()

    _data_dir = Path(data_dir) if data_dir else default_data_dir()
    ensure_dir(_data_dir)

    kp = load_or_create_keypair(_data_dir)
    _instance_private_key = load_private_key(kp.private_key)
    _instance_id = kp.instance_id
    _tenant_id = (
        tenant_id
        or os.environ.get("INTENTPROOF_TENANT_ID", "").strip()
        or "tnt_default"
    )

    resolved_db = db_path or os.environ.get("INTENTPROOF_OUTBOX_PATH", "").strip()
    if not resolved_db:
        resolved_db = str(_data_dir / "outbox.db")
    _outbox = Outbox(resolved_db)

    ingest = resolve_ingest_url(ingest_url)
    _exporter = HttpExporter(ingest) if ingest else None


def flush() -> None:
    if _exporter is not None:
        _exporter.flush()


def get_outbox() -> Outbox:
    if _outbox is None:
        raise RuntimeError("SDK not configured: call configure() before use")
    return _outbox


def get_instance_id() -> str:
    if _instance_id is None:
        raise RuntimeError("SDK not configured: call configure() before get_instance_id()")
    return _instance_id


def get_private_key() -> Ed25519PrivateKey:
    if _instance_private_key is None:
        raise RuntimeError("SDK not configured: call configure() before signing")
    return _instance_private_key


def get_tenant_id() -> str:
    return _tenant_id


def get_exporter() -> HttpExporter | None:
    return _exporter


def get_public_key() -> "Ed25519PublicKey":
    return get_private_key().public_key()
