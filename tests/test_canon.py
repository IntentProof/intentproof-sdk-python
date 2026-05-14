"""Tests for the RFC 8785 JCS canonicalizer."""

import math
import os
import unittest

from intentproof.canon import canonicalize


# Ported from intentproof-spec/conformance/jcs_vectors.ts
_PORTED_VECTORS = [
    ({"b": 2, "a": 1}, '{"a":1,"b":2}'),
    ({"b": "2", "a": "1"}, '{"a":"1","b":"2"}'),
    ({"c": 0, "b": [], "a": {}}, '{"a":{},"b":[],"c":0}'),
    ({"11": "eleven", "10": "ten", "1": "one"}, '{"1":"one","10":"ten","11":"eleven"}'),
    ({"b": 1.2, "a": 1.0}, '{"a":1,"b":1.2}'),
    ({"b": True, "a": False}, '{"a":false,"b":true}'),
    ({"b": None, "a": None}, '{"a":null,"b":null}'),
    ({"b": [3, 2, 1], "a": [1, 2, 3]}, '{"a":[1,2,3],"b":[3,2,1]}'),
    ({"unicode": "é", "ascii": "e"}, '{"ascii":"e","unicode":"é"}'),
    ({"slash": "a/b", "backslash": "a\\b"}, '{"backslash":"a\\\\b","slash":"a/b"}'),
]


class TestPortedVectors(unittest.TestCase):
    def test_vectors(self):
        for inp, expected in _PORTED_VECTORS:
            with self.subTest(inp=inp):
                self.assertEqual(canonicalize(inp), expected)


class TestPrimitives(unittest.TestCase):
    def test_null(self):
        self.assertEqual(canonicalize(None), "null")

    def test_true(self):
        self.assertEqual(canonicalize(True), "true")

    def test_false(self):
        self.assertEqual(canonicalize(False), "false")

    def test_empty_string(self):
        self.assertEqual(canonicalize(""), '""')

    def test_empty_object(self):
        self.assertEqual(canonicalize({}), "{}")

    def test_empty_array(self):
        self.assertEqual(canonicalize([]), "[]")

    def test_ascii_string(self):
        self.assertEqual(canonicalize("hello"), '"hello"')


class TestLiteralFallbackForTokenPrefixes(unittest.TestCase):
    """Words that start like JSON literals but are not valid single JSON values."""

    def test_null_false_true_prefixes_decode_as_strings(self):
        cases = [
            ("null_pointer", '"null_pointer"'),
            ("false_alarm", '"false_alarm"'),
            ("nothing", '"nothing"'),
            ("true_love", '"true_love"'),
        ]
        for inp, expected in cases:
            with self.subTest(inp=inp):
                self.assertEqual(canonicalize(inp), expected)


class TestStringEscapes(unittest.TestCase):
    def test_minimal_escapes(self):
        cases = [
            ('"', '"\\\""'),
            ('\\', '"\\\\"'),
            ('\b', '"\\b"'),
            ('\f', '"\\f"'),
            ('\n', '"\\n"'),
            ('\r', '"\\r"'),
            ('\t', '"\\t"'),
            ('\x00', '"\\u0000"'),
            ('\x01', '"\\u0001"'),
            ('\x1f', '"\\u001f"'),
            ('/', '"/"'),
            ('\x7f', '"\x7f"'),
            ('a\u0080b', '"a\u0080b"'),
            ('\U0001F600', '"\U0001F600"'),
        ]
        for inp, expected in cases:
            with self.subTest(inp=inp):
                self.assertEqual(canonicalize(inp), expected)


class TestNumberFormatting(unittest.TestCase):
    def test_number_cases(self):
        # Test via JSON string input so the original textual form is preserved.
        cases = [
            ("0", "0"),
            ("-0", "0"),
            ("1", "1"),
            (" 1 ", "1"),
            ("\n1\t", "1"),
            ("-1", "-1"),
            ("1.0", "1"),
            ("1.5", "1.5"),
            ("-1.5", "-1.5"),
            ("100", "100"),
            ("0.1", "0.1"),
            ("0.001", "0.001"),
            ("1e2", "100"),
            ("1e21", "1e+21"),
            ("1e20", "100000000000000000000"),
            ("1e-6", "0.000001"),
            ("1e-7", "1e-7"),
            ("1.5e-7", "1.5e-7"),
            ("9007199254740992", "9007199254740992"),
            ("1e22", "1e+22"),
        ]
        for inp, expected in cases:
            with self.subTest(inp=inp):
                self.assertEqual(canonicalize(inp), expected)

    def test_python_floats(self):
        self.assertEqual(canonicalize(1.0), "1")
        self.assertEqual(canonicalize(100.0), "100")
        self.assertEqual(canonicalize(0.1), "0.1")
        self.assertEqual(canonicalize(1e20), "100000000000000000000")
        self.assertEqual(canonicalize(1e21), "1e+21")
        self.assertEqual(canonicalize(1e-6), "0.000001")
        self.assertEqual(canonicalize(1e-7), "1e-7")
        self.assertEqual(canonicalize(123000.0), "123000")

    def test_rejects_non_finite(self):
        for v in [float('nan'), float('inf'), float('-inf')]:
            with self.subTest(v=v):
                with self.assertRaises(ValueError):
                    canonicalize(v)

    def test_rejects_non_finite_json(self):
        for s in ["NaN", "Infinity", "-Infinity"]:
            with self.subTest(s=s):
                with self.assertRaises(ValueError):
                    canonicalize(s)


class TestUTF16KeyOrdering(unittest.TestCase):
    def test_supplementary_before_bmp(self):
        """Supplementary plane keys sort before BMP U+E000 under UTF-16."""
        inp = {"\uE000": 1, "\U0001F600": 2}
        out = canonicalize(inp)
        sup_idx = out.find("\U0001F600")
        bmp_idx = out.find("\uE000")
        self.assertGreater(sup_idx, -1)
        self.assertGreater(bmp_idx, -1)
        self.assertLess(sup_idx, bmp_idx)


class TestArrayOrder(unittest.TestCase):
    def test_preserved(self):
        self.assertEqual(
            canonicalize([3, 1, 2, "z", "a"]),
            '[3,1,2,"z","a"]'
        )


class TestNestedObjects(unittest.TestCase):
    def test_nested_sorted(self):
        self.assertEqual(
            canonicalize('{"z":{"b":2,"a":1},"a":[{"c":3,"b":2}]}'),
            '{"a":[{"b":2,"c":3}],"z":{"a":1,"b":2}}'
        )


class TestDuplicateKeys(unittest.TestCase):
    def test_rejects_duplicates(self):
        with self.assertRaises(ValueError):
            canonicalize('{"a":1,"a":2}')


class TestTrailingTokens(unittest.TestCase):
    def test_rejects_trailing_value(self):
        with self.assertRaises(ValueError):
            canonicalize('{} {}')

    def test_rejects_trailing_garbage(self):
        with self.assertRaises(ValueError):
            canonicalize('{}x')


class TestMalformedJSON(unittest.TestCase):
    def test_rejects_unclosed_object(self):
        with self.assertRaises(ValueError):
            canonicalize('{')


class TestPolicyBodyCrossCheck(unittest.TestCase):
    def test_byte_equality_with_go_fixture(self):
        body = {
            "schema": "intentproof.policy.v1",
            "policy_id": "tnt.test",
            "policy_version": 1,
            "tenant_id": "tnt",
            "spec_version": "1.0.0",
            "scope": {"any_event_action_in": ["a"]},
            "rules": [
                {
                    "id": "r1",
                    "category": "required",
                    "severity": "high",
                    "spec": {"action": "a"},
                },
            ],
        }
        got = canonicalize(body)
        fixture_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "policy_body_canon.json"
        )
        with open(fixture_path, "r", encoding="utf-8") as f:
            want = f.read()
        self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()
