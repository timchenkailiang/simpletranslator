"""Pytest configuration — ensure src/ is importable and provide common paths."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"

# Make the src/ package importable for all tests.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
