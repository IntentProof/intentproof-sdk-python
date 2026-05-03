"""Correlation IDs and run_with_correlation_id."""

from __future__ import annotations

import pytest

from intentproof._correlation import (
    assert_correlation_id,
    get_correlation_id,
)
from intentproof._correlation import (
    run_with_correlation_id as rwcid,
)


def test_assert_correlation_id_ok_and_invalid() -> None:
    assert assert_correlation_id("  x  ") == "x"
    with pytest.raises(TypeError, match="correlation_id"):
        assert_correlation_id(1)
    with pytest.raises(TypeError):
        assert_correlation_id("   ")


def test_run_with_correlation_id_two_arg_and_context() -> None:
    with pytest.raises(TypeError, match="run_with_correlation_id"):
        rwcid("x", "not-callable")  # type: ignore[arg-type]

    assert rwcid("  ok  ", lambda: 7) == 7

    with rwcid("ab"):
        assert get_correlation_id() == "ab"
    assert get_correlation_id() is None
