"""snapshot() and SerializeOptions edge coverage."""

from __future__ import annotations

from intentproof.snapshot import SerializeOptions, snapshot


def test_serialize_options_snapshot_kwargs_string_limit() -> None:
    o = SerializeOptions(max_string_length=5)
    d = o.snapshot_kwargs()
    assert d["max_string_length"] == 5


def test_snapshot_limits_and_types() -> None:
    assert snapshot(1, max_depth=float("nan")) == 1
    assert snapshot("hi", max_string_length=float("nan")) == "hi"
    long = "a" * 20
    assert "truncated" in snapshot(long, max_string_length=5)

    x: list[object] = []
    x.append(x)
    assert snapshot(x) == ["[Circular]"]

    assert snapshot(range(3), max_depth=0) == "[Array]"

    big = {str(i): i for i in range(60)}
    out = snapshot(big, max_keys=3)
    assert "…" in out

    class BadStr:
        def __str__(self) -> str:
            raise RuntimeError("no")

    assert snapshot(BadStr()) == "[Unserializable]"

    assert (
        snapshot({"a": 1, "secret": 2}, redact_keys=frozenset({"secret"}))["secret"] == "[REDACTED]"
    )
