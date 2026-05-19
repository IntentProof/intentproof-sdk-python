"""Instance keypair persistence."""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import ulid as _ulid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Keypair:
    private_key: str
    instance_id: str


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _ensure_key_permissions(key_path: Path) -> None:
    try:
        os.chmod(key_path, 0o600)
    except OSError as exc:
        logger.warning(
            "[intentproof] could not set %s to mode 0600: %s",
            key_path,
            exc,
        )


def _write_keypair_file(key_path: Path, payload: dict[str, str]) -> None:
    content = json.dumps(payload, indent=2) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(key_path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    except Exception:
        key_path.unlink(missing_ok=True)
        raise


def _load_keypair(key_path: Path) -> Keypair:
    _ensure_key_permissions(key_path)
    raw = key_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return Keypair(
        private_key=data["privateKey"],
        instance_id=data["instanceId"],
    )


def load_or_create_keypair(data_dir: Path) -> Keypair:
    key_path = data_dir / "keypair.json"
    if key_path.exists():
        return _load_keypair(key_path)

    private_key = base64.b64encode(os.urandom(32)).decode("ascii")
    kp = Keypair(
        private_key=private_key,
        instance_id=f"inst_{_ulid.new()}",
    )
    try:
        _write_keypair_file(
            key_path,
            {"privateKey": kp.private_key, "instanceId": kp.instance_id},
        )
    except FileExistsError:
        return _load_keypair(key_path)
    return kp
