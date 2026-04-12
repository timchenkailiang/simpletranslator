"""Tests for converters.__init__ — dynamic converter loading."""

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

from converters import load_converter_module


class TestLoadConverterModule(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_valid_converter(self):
        script = os.path.join(self.tmpdir, "good.py")
        with open(script, "w") as f:
            f.write(
                'FORMAT_NAME = "Test"\n'
                'COLUMNS = ["A", "B"]\n'
                'VALIDATION_RULES = {"qty": "A"}\n'
                'def process_file(input_path, output_path=None):\n'
                '    return True\n'
            )
        mod = load_converter_module(script)
        self.assertTrue(hasattr(mod, "process_file"))
        self.assertEqual(mod.FORMAT_NAME, "Test")

    def test_missing_script_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_converter_module("/nonexistent/converter.py")

    def test_missing_process_file_raises(self):
        script = os.path.join(self.tmpdir, "bad.py")
        with open(script, "w") as f:
            f.write("x = 1\n")
        with self.assertRaises(AttributeError):
            load_converter_module(script)

    def test_no_format_name_defaults(self):
        """Converter without FORMAT_NAME still loads (getattr defaults)."""
        script = os.path.join(self.tmpdir, "minimal.py")
        with open(script, "w") as f:
            f.write(
                'def process_file(input_path, output_path=None):\n'
                '    return True\n'
            )
        mod = load_converter_module(script)
        self.assertEqual(getattr(mod, "FORMAT_NAME", "Unknown"), "Unknown")

    def test_builtin_globe_converter(self):
        script = str(SRC_DIR / "converters" / "globe.py")
        mod = load_converter_module(script)
        self.assertEqual(mod.FORMAT_NAME, "Globe")
        self.assertIn("qty", mod.VALIDATION_RULES)

    def test_builtin_jeffco_converter(self):
        script = str(SRC_DIR / "converters" / "jeffco.py")
        mod = load_converter_module(script)
        self.assertEqual(mod.FORMAT_NAME, "Jeffco")

    def test_builtin_millarco_converter(self):
        script = str(SRC_DIR / "converters" / "millarco.py")
        mod = load_converter_module(script)
        self.assertEqual(mod.FORMAT_NAME, "Series 16")


if __name__ == "__main__":
    unittest.main()
