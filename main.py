"""SimpleTranslator — entry point.

Usage:
    python main.py          Launch the GUI application.
    python main.py --lang zh   Launch with Chinese UI.
"""

import argparse
import os
import sys
import tkinter as tk

# Ensure the src/ package directory is importable.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from utils import setup_logging
from i18n import load_saved_language, save_language, LANGUAGES
from ui.app import ConverterApp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=LANGUAGES.keys(), default=None,
                        help="Set the UI language (e.g. en, zh)")
    args = parser.parse_args()

    setup_logging()

    if args.lang:
        # Installer (or user) requested a specific language — persist it so
        # subsequent launches remember the choice.
        save_language(args.lang)
    else:
        load_saved_language()

    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
