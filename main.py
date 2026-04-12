"""SimpleTranslator — entry point.

Usage:
    python main.py          Launch the GUI application.
"""

import os
import sys
import tkinter as tk

# Ensure the src/ package directory is importable.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from utils import setup_logging
from i18n import load_saved_language
from ui.app import ConverterApp


def main():
    setup_logging()
    load_saved_language()
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
