"""assert_wrap_options_shape and assert_attributes_record."""

from __future__ import annotations

import pytest

from intentproof.validation import assert_attributes_record, assert_wrap_options_shape


def test_assert_wrap_options_shape_valid_minimal() -> None:
    assert_wrap_options_shape({"intent": "i", "action": "a"})


def test_assert_wrap_options_shape_rejects() -> None:
    with pytest.raises(TypeError, match="intent"):
        assert_wrap_options_shape({"intent": 1, "action": "a"})
    with pytest.raises(TypeError, match="intent"):
        assert_wrap_options_shape({"intent": "", "action": "a"})
    with pytest.raises(TypeError, match="action"):
        assert_wrap_options_shape({"intent": "i", "action": 1})
    with pytest.raises(TypeError, match="action"):
        assert_wrap_options_shape({"intent": "i", "action": ""})
    with pytest.raises(TypeError, match="correlation_id"):
        assert_wrap_options_shape({"intent": "i", "action": "a", "correlation_id": 1})
    with pytest.raises(TypeError, match="correlation_id"):
        assert_wrap_options_shape({"intent": "i", "action": "a", "correlation_id": "  "})
    with pytest.raises(TypeError, match="include_error_stack"):
        assert_wrap_options_shape({"intent": "i", "action": "a", "include_error_stack": 1})
    with pytest.raises(TypeError, match="max_depth"):
        assert_wrap_options_shape({"intent": "i", "action": "a", "max_depth": "x"})
    with pytest.raises(TypeError, match="redact_keys"):
        assert_wrap_options_shape({"intent": "i", "action": "a", "redact_keys": "x"})
    with pytest.raises(TypeError, match="capture_input"):
        assert_wrap_options_shape({"intent": "i", "action": "a", "capture_input": 1})


def test_assert_attributes_record() -> None:
    assert_attributes_record("label", {"k": 1})
    with pytest.raises(TypeError, match="plain object"):
        assert_attributes_record("x", [])
    with pytest.raises(TypeError, match="keys must be strings"):
        assert_attributes_record("x", {1: "a"})
    with pytest.raises(TypeError, match="must be a string"):
        assert_attributes_record("x", {"k": object()})


def test_serialize_opts_from_wrap_options() -> None:
    from intentproof.validation import serialize_opts_from_wrap_options

    s = serialize_opts_from_wrap_options(
        {
            "intent": "i",
            "action": "a",
            "max_depth": 3,
            "max_keys": 10,
            "max_string_length": 100,
        },
    )
    assert s.max_depth == 3
    assert s.max_string_length == 100
