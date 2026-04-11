"""SimpleTranslator — entry point.

Usage:
    python main.py          Launch the GUI application.
"""

import tkinter as tk

from utils import setup_logging
from ui.app import ConverterApp


def main():
    setup_logging()
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
