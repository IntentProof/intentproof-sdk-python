"""Keypair load edge cases and permission warnings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from intentproof.keys import load_or_create_keypair


def test_load_retries_until_keypair_is_written(tmp_path: Path) -> None:
    key_path = tmp_path / "keypair.json"
    key_path.write_text("", encoding="utf-8")
    payload = {
        "privateKey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "instanceId": "inst_retry",
    }
    attempts = {"count": 0}

    def read_text(self: Path, *args: object, **kwargs: object) -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return ""
        return json.dumps(payload)

    with patch.object(Path, "read_text", read_text):
        kp = load_or_create_keypair(tmp_path)

    assert kp.instance_id == "inst_retry"


def test_load_or_create_keypair_races_on_file_exists(tmp_path: Path) -> None:
    payload = {
        "privateKey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "instanceId": "inst_race",
    }
    key_path = tmp_path / "keypair.json"

    def write_then_lose_race(path: Path, _pl: dict[str, str]) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")
        raise FileExistsError

    with patch(
        "intentproof.keys._write_keypair_file",
        side_effect=write_then_lose_race,
    ):
        kp = load_or_create_keypair(tmp_path)

    assert key_path.exists()
    assert kp.instance_id == "inst_race"


def test_write_keypair_cleans_up_on_failure(tmp_path: Path) -> None:
    from contextlib import contextmanager

    key_path = tmp_path / "keypair.json"

    class FailingWriter:
        def write(self, _data: str) -> int:
            raise OSError("disk full")

        def flush(self) -> None:
            return None

        def fileno(self) -> int:
            return 1

        def __enter__(self) -> "FailingWriter":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    @contextmanager
    def failing_fdopen(fd: int, *args: object, **kwargs: object):
        del fd, args, kwargs
        yield FailingWriter()

    with patch("intentproof.keys.os.fdopen", side_effect=failing_fdopen):
        with pytest.raises(OSError, match="disk full"):
            load_or_create_keypair(tmp_path)

    assert not key_path.exists()


def test_load_rejects_invalid_keypair_shape(tmp_path: Path) -> None:
    key_path = tmp_path / "keypair.json"
    key_path.write_text(json.dumps({"privateKey": 1, "instanceId": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid keypair file"):
        load_or_create_keypair(tmp_path)


def test_chmod_warning_when_permissions_cannot_be_set(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    payload = {
        "privateKey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "instanceId": "inst_perm",
    }
    (tmp_path / "keypair.json").write_text(json.dumps(payload), encoding="utf-8")

    with patch("intentproof.keys.os.chmod", side_effect=OSError("read-only fs")):
        with caplog.at_level("WARNING"):
            kp = load_or_create_keypair(tmp_path)

    assert kp.instance_id == "inst_perm"
    assert any("could not set" in record.message for record in caplog.records)
