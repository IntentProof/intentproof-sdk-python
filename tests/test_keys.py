"""Keypair file permission and import safety tests."""

from __future__ import annotations

import stat
import subprocess
import sys
import threading
from pathlib import Path

from intentproof.keys import Keypair, load_or_create_keypair


def test_new_keypair_created_with_mode_0600(tmp_path: Path) -> None:
    load_or_create_keypair(tmp_path)
    key_path = tmp_path / "keypair.json"
    mode = stat.S_IMODE(key_path.stat().st_mode)
    assert mode == 0o600


def test_concurrent_load_or_create_keypair(tmp_path: Path) -> None:
    """Parallel configure() must not raise when racing on keypair creation."""
    barrier = threading.Barrier(8)
    results: list[Keypair] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            barrier.wait()
            results.append(load_or_create_keypair(tmp_path))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(results) == 8
    assert len({kp.instance_id for kp in results}) == 1


def test_client_module_import_without_home(tmp_path: Path) -> None:
    """import intentproof.client must not resolve Path.home() at import time."""
    script = f"""
from pathlib import Path
from unittest.mock import patch

with patch.object(Path, "home", side_effect=RuntimeError("no home directory")):
    import intentproof.client as client

client.configure(
    data_dir={str(tmp_path)!r},
    db_path={str(tmp_path / "outbox.db")!r},
    tenant_id="tnt_container",
)
print(client.get_instance_id())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.stdout.strip().startswith("inst_")
