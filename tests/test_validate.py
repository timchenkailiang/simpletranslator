"""Tests for engine.validate — CSV validation, row removal, and flagging."""

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine.validate import validate_csv, parse_number, _detect_format, _check_math


# ── Unit tests for helpers ────────────────────────────────────────────

class TestParseNumber(unittest.TestCase):
    def test_valid_int(self):
        self.assertAlmostEqual(parse_number("100"), 100.0)

    def test_valid_decimal(self):
        self.assertAlmostEqual(parse_number("3.14"), 3.14)

    def test_eu_format(self):
        self.assertAlmostEqual(parse_number("1.234,56"), 1234.56)

    def test_empty_string(self):
        self.assertIsNone(parse_number(""))

    def test_nan(self):
        import pandas as pd
        self.assertIsNone(parse_number(pd.NA))

    def test_text(self):
        self.assertIsNone(parse_number("Total"))


class TestDetectFormat(unittest.TestCase):
    def test_globe_english(self):
        cols = ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"]
        name, expected, rules = _detect_format(cols)
        self.assertEqual(name, "Globe")
        self.assertEqual(rules["qty"], "Quantity")

    def test_globe_spanish(self):
        cols = ["Artículo", "Denominación", "Cantidad", "Precio", "Importe", "Entrega"]
        name, expected, rules = _detect_format(cols)
        self.assertEqual(name, "Globe")
        self.assertEqual(rules["qty"], "Cantidad")

    def test_jeffco(self):
        cols = ["Quantity", "Your Part No", "Our Part No", "Price USD", "Del. date", "Description"]
        name, expected, rules = _detect_format(cols)
        self.assertEqual(name, "Jeffco")
        self.assertIsNone(rules["amount"])

    def test_series16_default(self):
        cols = ["Itemno", "Description", "Master", "Inner",
                "Quantity", "Unit price", "Amount", "ETD"]
        name, expected, rules = _detect_format(cols)
        self.assertEqual(name, "Series 16")


class TestCheckMath(unittest.TestCase):
    def test_correct_math(self):
        row = {"Quantity": "10", "Price": "5.0", "Amount": "50.0"}
        ok, calc, actual = _check_math(row, "Quantity", "Price", "Amount")
        self.assertTrue(ok)

    def test_wrong_math(self):
        row = {"Quantity": "10", "Price": "5.0", "Amount": "999.0"}
        ok, calc, actual = _check_math(row, "Quantity", "Price", "Amount")
        self.assertFalse(ok)
        self.assertAlmostEqual(calc, 50.0)

    def test_missing_value(self):
        row = {"Quantity": "10", "Price": "", "Amount": "50"}
        ok, calc, actual = _check_math(row, "Quantity", "Price", "Amount")
        self.assertTrue(ok)  # can't check — treated as pass


# ── Integration tests for validate_csv ────────────────────────────────

class TestValidateCsv(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_csv(self, filename, header, rows):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for row in rows:
                w.writerow(row)
        return path

    def test_clean_csv_no_flags(self):
        path = self._write_csv("clean.csv",
                               ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"],
                               [["A001", "Widget", "10", "5.0", "50.0", "2026-01-01"],
                                ["A002", "Gadget", "20", "3.0", "60.0", "2026-01-02"]])
        flagged, _ = validate_csv(path)
        self.assertEqual(len(flagged), 0)

    def test_invalid_numeric_rows_removed(self):
        """Rows with non-numeric strings in numeric columns get dropped from CSV."""
        path = self._write_csv("dirty.csv",
                               ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"],
                               [["A001", "Widget", "10", "5.0", "50.0", "2026-01-01"],
                                ["Commercial", "Summary", "", "Total", "Total", "(USD)"],
                                ["A002", "Gadget", "20", "3.0", "60.0", "2026-01-02"]])
        flagged, rows_removed = validate_csv(path)
        # The "Commercial" row should have been removed from the CSV
        self.assertEqual(rows_removed, 1)
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # header + 2 data rows (the invalid one was dropped)
        self.assertEqual(len(rows), 3)

    def test_math_mismatch_flagged(self):
        path = self._write_csv("math.csv",
                               ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"],
                               [["A001", "Widget", "10", "5.0", "999.0", "2026-01-01"]])
        flagged, _ = validate_csv(path)
        # Math mismatch flags qty, price, amount for the key
        self.assertIn(("A001", "Quantity"), flagged)
        self.assertIn(("A001", "Price"), flagged)
        self.assertIn(("A001", "Amount"), flagged)

    def test_suspicious_chars_flagged(self):
        # Write the CSV with bytes to preserve the soft hyphen through round-trip
        path = os.path.join(self.tmpdir, "chars.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("Item,Description,Quantity,Price,Amount,Delivery\n")
            f.write("A001,Wid\ufffdget,10,5.0,50.0,2026-01-01\n")
        flagged, _ = validate_csv(path)
        self.assertIn(("A001", "Description"), flagged)

    def test_empty_csv(self):
        path = self._write_csv("empty.csv",
                               ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"],
                               [])
        flagged, _ = validate_csv(path)
        self.assertEqual(len(flagged), 0)

    def test_explicit_format_and_rules(self):
        path = self._write_csv("explicit.csv",
                               ["Key", "Qty", "UnitPrice", "Total"],
                               [["X1", "10", "5", "50"]])
        rules = {"qty": "Qty", "price": "UnitPrice", "amount": "Total"}
        flagged, _ = validate_csv(path, format_name="Custom", validation_rules=rules)
        self.assertEqual(len(flagged), 0)


if __name__ == "__main__":
    unittest.main()
