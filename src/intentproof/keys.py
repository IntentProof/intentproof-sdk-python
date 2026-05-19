"""Instance keypair persistence."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

import ulid as _ulid


@dataclass(frozen=True)
class Keypair:
    private_key: str
    instance_id: str


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_or_create_keypair(data_dir: Path) -> Keypair:
    key_path = data_dir / "keypair.json"
    if key_path.exists():
        raw = key_path.read_text(encoding="utf-8")
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        data = json.loads(raw)
        return Keypair(
            private_key=data["privateKey"],
            instance_id=data["instanceId"],
        )

    private_key = base64.b64encode(os.urandom(32)).decode("ascii")
    kp = Keypair(
        private_key=private_key,
        instance_id=f"inst_{_ulid.new()}",
    )
    key_path.write_text(
        json.dumps(
            {"privateKey": kp.private_key, "instanceId": kp.instance_id},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return kp
