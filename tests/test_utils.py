"""Tests for utils — number parsing, normalisation, and helper functions."""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils import (
    parse_localized_number,
    smart_number_convert,
    normalize_eu_number,
    normalize_integer_like_text,
)


class TestParseLocalizedNumber(unittest.TestCase):
    """parse_localized_number covers EU, US, and edge-case formats."""

    # ── US format ─────────────────────────────────────────────────────
    def test_us_thousands(self):
        self.assertAlmostEqual(parse_localized_number("2,000.50"), 2000.50)

    def test_us_simple_decimal(self):
        self.assertAlmostEqual(parse_localized_number("123.45"), 123.45)

    # ── EU format ─────────────────────────────────────────────────────
    def test_eu_thousands(self):
        self.assertAlmostEqual(parse_localized_number("2.000,50"), 2000.50)

    def test_eu_comma_decimal(self):
        self.assertAlmostEqual(parse_localized_number("1234,56"), 1234.56)

    def test_eu_only_comma_small(self):
        self.assertAlmostEqual(parse_localized_number("0,818"), 0.818)

    # ── Currency noise ────────────────────────────────────────────────
    def test_strip_usd(self):
        self.assertAlmostEqual(parse_localized_number("USD 100.00"), 100.0)

    def test_strip_dollar_sign(self):
        self.assertAlmostEqual(parse_localized_number("$50"), 50.0)

    def test_strip_euro_sign(self):
        self.assertAlmostEqual(parse_localized_number("€1234,56"), 1234.56)

    # ── Integer-like with dot thousands ───────────────────────────────
    def test_dot_only_thousands(self):
        self.assertAlmostEqual(parse_localized_number("1.120"), 1120.0)

    # ── Sub-unit decimals (leading zero) ──────────────────────────────
    def test_sub_dollar_3dp(self):
        """0.818 must be treated as decimal, not EU thousands."""
        self.assertAlmostEqual(parse_localized_number("0.818"), 0.818)

    def test_sub_dollar_3dp_low(self):
        self.assertAlmostEqual(parse_localized_number("0.327"), 0.327)

    def test_sub_dollar_3dp_round(self):
        self.assertAlmostEqual(parse_localized_number("0.110"), 0.110)

    def test_sub_dollar_2dp(self):
        self.assertAlmostEqual(parse_localized_number("0.50"), 0.50)

    # ── Edge cases ────────────────────────────────────────────────────
    def test_none(self):
        self.assertIsNone(parse_localized_number(None))

    def test_empty_string(self):
        self.assertIsNone(parse_localized_number(""))

    def test_whitespace(self):
        self.assertIsNone(parse_localized_number("   "))

    def test_plain_int(self):
        self.assertAlmostEqual(parse_localized_number("576"), 576.0)

    def test_int_passthrough(self):
        self.assertAlmostEqual(parse_localized_number(42), 42.0)

    def test_float_passthrough(self):
        self.assertAlmostEqual(parse_localized_number(3.14), 3.14)

    def test_unparseable_text(self):
        self.assertIsNone(parse_localized_number("Total"))

    def test_non_string_type(self):
        self.assertIsNone(parse_localized_number([1, 2]))


class TestSmartNumberConvert(unittest.TestCase):
    def test_numeric_string(self):
        self.assertAlmostEqual(smart_number_convert("1.234,56"), 1234.56)

    def test_non_numeric_returns_original(self):
        self.assertEqual(smart_number_convert("hello"), "hello")

    def test_none_returns_none(self):
        self.assertIsNone(smart_number_convert(None))


class TestNormalizeEuNumber(unittest.TestCase):
    def test_integer_result(self):
        self.assertEqual(normalize_eu_number("504,00"), "504")

    def test_large_integer(self):
        self.assertEqual(normalize_eu_number("2.000,00"), "2000")

    def test_decimal_result(self):
        self.assertEqual(normalize_eu_number("0,818"), "0.818")

    def test_large_decimal(self):
        self.assertEqual(normalize_eu_number("8.904,96"), "8904.96")

    def test_plain_integer(self):
        self.assertEqual(normalize_eu_number("576"), "576")

    def test_unparseable(self):
        self.assertEqual(normalize_eu_number("N/A"), "N/A")


class TestNormalizeIntegerLikeText(unittest.TestCase):
    def test_dot_thousands(self):
        self.assertEqual(normalize_integer_like_text("1.200"), "1200")

    def test_comma_thousands(self):
        self.assertEqual(normalize_integer_like_text("1,200"), "1200")

    def test_no_separator(self):
        self.assertEqual(normalize_integer_like_text("500"), "500")

    def test_non_string(self):
        self.assertEqual(normalize_integer_like_text(42), 42)

    def test_empty(self):
        self.assertEqual(normalize_integer_like_text(""), "")

    def test_decimal_not_thousands(self):
        # "12.34" — the part after dot is NOT 3 digits, so no stripping
        self.assertEqual(normalize_integer_like_text("12.34"), "12.34")


if __name__ == "__main__":
    unittest.main()
