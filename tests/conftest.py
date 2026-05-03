from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_default_intentproof_client() -> None:
    import intentproof.sdk as intentproof_sdk

    intentproof_sdk._client_singleton = None
    yield
    intentproof_sdk._client_singleton = None
