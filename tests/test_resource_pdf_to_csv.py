"""Manual-check conversion tests for resource PDFs.

These tests convert known sample PDFs and assert exact CSV output matches fixtures.
"""

import csv
from pathlib import Path
import shutil
import sys
import unittest

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from converters import load_converter_module


class TestResourcePdfToCsv(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.root = root
        cls.resource_dir = root / "tests" / "fixtures" / "pdfs"
        cls.expected_dir = root / "tests" / "fixtures" / "expected_outputs"
        cls.output_dir = root / "intermediate" / "test_resource_outputs"

        if cls.output_dir.exists():
            shutil.rmtree(cls.output_dir)
        cls.output_dir.mkdir(parents=True, exist_ok=True)

    def _run_conversion(self, converter_script: str, input_pdf: str, output_csv: str):
        script_path = str(self.root / "src" / converter_script)
        module = load_converter_module(script_path)

        in_path = self.resource_dir / input_pdf
        out_path = self.output_dir / output_csv

        ok = module.process_file(str(in_path), str(out_path))
        if not ok:
            raise RuntimeError(
                f"Conversion returned no data for {input_pdf} using {converter_script}"
            )

    def _assert_csv_matches_expected(self, output_csv: str):
        actual_path = self.output_dir / output_csv
        expected_path = self.expected_dir / output_csv

        self.assertTrue(expected_path.exists(), f"Missing expected fixture: {expected_path}")
        self.assertTrue(actual_path.exists(), f"Missing generated output: {actual_path}")

        with expected_path.open("r", encoding="utf-8", newline="") as f:
            expected_rows = list(csv.reader(f))
        with actual_path.open("r", encoding="utf-8", newline="") as f:
            actual_rows = list(csv.reader(f))

        self.assertListEqual(
            expected_rows,
            actual_rows,
            f"CSV output mismatch for {output_csv}",
        )

    def test_convert_globe_english_pdf(self):
        output_csv = "51075_Globe_english.csv"
        self._run_conversion(
            converter_script="converters/globe.py",
            input_pdf="51075 Globe english.pdf",
            output_csv=output_csv,
        )
        self._assert_csv_matches_expected(output_csv)

    def test_convert_globe_spanish_pdf(self):
        output_csv = "51075_Globe_spanish.csv"
        self._run_conversion(
            converter_script="converters/globe.py",
            input_pdf="51075 Globe spanish.pdf",
            output_csv=output_csv,
        )
        self._assert_csv_matches_expected(output_csv)

    def test_convert_ipa_pdf(self):
        output_csv = "IPA.csv"
        self._run_conversion(
            converter_script="converters/jeffco.py",
            input_pdf="IPA.pdf",
            output_csv=output_csv,
        )
        self._assert_csv_matches_expected(output_csv)

    def test_convert_po17199_pdf(self):
        output_csv = "PO17199.csv"
        self._run_conversion(
            converter_script="converters/millarco.py",
            input_pdf="PO17199.pdf",
            output_csv=output_csv,
        )
        self._assert_csv_matches_expected(output_csv)


if __name__ == "__main__":
    unittest.main()
