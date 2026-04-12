"""Shared path helpers and logging configuration for SimpleTranslator."""

import logging
import logging.handlers
import os
import platform
import re
import shutil
import sys


def get_install_dir():
    """Return the application install / project root directory (read-only).

    In a frozen (PyInstaller) build this is the directory containing the
    executable.  In development it is the project root (parent of ``src/``).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # In development: this file lives at src/utils.py → project root is one up.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_user_data_dir():
    """Return a per-user writable directory for configs, data, and logs.

    In development mode this falls back to the project root so the
    workflow stays unchanged.  In a frozen (PyInstaller) build it uses
    the OS-standard application-data location.
    """
    if getattr(sys, "frozen", False):
        system = platform.system()
        if system == "Darwin":
            base = os.path.expanduser("~/Library/Application Support")
        elif system == "Windows":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.environ.get(
                "XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        data_dir = os.path.join(base, "SimpleTranslator")
    else:
        data_dir = get_install_dir()
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_resource_path(relative_path):
    """Resolve *relative_path* — checks user data dir, install dir, src/, then bundle."""
    # 1. User data directory (user-added converters, edited configs)
    user_path = os.path.join(get_user_data_dir(), relative_path)
    if os.path.exists(user_path):
        return user_path

    # 2. Install / project directory
    install_path = os.path.join(get_install_dir(), relative_path)
    if os.path.exists(install_path):
        return install_path

    # 3. src/ subdirectory (development layout)
    src_path = os.path.join(get_install_dir(), "src", relative_path)
    if os.path.exists(src_path):
        return src_path

    # 4. PyInstaller bundle
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(bundled):
            return bundled

    return user_path  # fall back (for error reporting)


def ensure_config_exists(filename):
    """Copy a default config from install dir / bundle into the user data dir."""
    dest = os.path.join(get_user_data_dir(), filename)
    dest_dir = os.path.dirname(dest)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    if not os.path.exists(dest):
        sources = [os.path.join(get_install_dir(), filename)]
        if getattr(sys, "frozen", False):
            sources.append(os.path.join(sys._MEIPASS, filename))
        for src in sources:
            try:
                if os.path.exists(src):
                    shutil.copy2(src, dest)
                    break
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Error copying default %s: %s", filename, exc)
    return dest


def setup_logging():
    """Configure root logger with console and rotating file handlers."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    root_logger.setLevel(logging.DEBUG)

    brief_fmt = logging.Formatter("%(levelname)s: %(message)s")
    full_fmt = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s: %(message)s")

    # Console — INFO and above
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(brief_fmt)
    root_logger.addHandler(console)

    # File — DEBUG and above, rotating 2 MB × 3 backups
    try:
        log_path = os.path.join(get_user_data_dir(), "simpletranslator.log")
        fh = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(full_fmt)
        root_logger.addHandler(fh)
    except Exception:
        pass  # if we can't write logs, keep going


def parse_localized_number(value):
    """Parse EU/US formatted numeric text into float; return None on failure."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return None

    clean = value.strip()
    if not clean:
        return None

    # Strip common currency noise
    clean = clean.replace("USD", "").replace("$", "").replace("€", "").strip()

    # EU thousands separator: 2.000,00
    if re.search(r"\.\d{3},", clean):
        clean = clean.replace(".", "").replace(",", ".")
    # US thousands separator: 2,000.00
    elif re.search(r",\d{3}\.", clean):
        clean = clean.replace(",", "")
    # Dot-only, might be thousands: 1.120 -> 1120
    elif "," not in clean and "." in clean:
        parts = clean.split(".")
        # A leading "0" (e.g. "0.818") is always a decimal, never thousands.
        if len(parts) > 1 and parts[0] != "0" and all(len(p) == 3 for p in parts[1:]):
            clean = clean.replace(".", "")
    # Comma-only decimal: 1234,56
    elif "," in clean and "." not in clean:
        clean = clean.replace(",", ".")

    try:
        return float(clean)
    except ValueError:
        return None


def smart_number_convert(value):
    """Return parsed float for localized numeric text, else original value."""
    parsed = parse_localized_number(value)
    return parsed if parsed is not None else value


def normalize_eu_number(value):
    """Convert EU-formatted numeric text to a clean decimal string for CSV.

    Examples:
        ``"504,00"``    → ``"504"``
        ``"2.000,00"``  → ``"2000"``
        ``"0,818"``     → ``"0.818"``
        ``"8.904,96"``  → ``"8904.96"``
        ``"576"``       → ``"576"``  (unchanged)

    Returns the original value when it cannot be parsed as a number.
    """
    parsed = parse_localized_number(value)
    if parsed is None:
        return value
    if parsed == int(parsed):
        return str(int(parsed))
    return str(parsed)


def normalize_integer_like_text(value):
    """Strip thousands separators from integer-like text for CSV safety."""
    if not isinstance(value, str):
        return value

    clean = value.strip()
    if not clean:
        return clean

    if "." in clean and "," not in clean:
        parts = clean.split(".")
        if len(parts) > 1 and all(part.isdigit() for part in parts) and all(
                len(part) == 3 for part in parts[1:]):
            return "".join(parts)

    if "," in clean and "." not in clean:
        parts = clean.split(",")
        if len(parts) > 1 and all(part.isdigit() for part in parts) and all(
                len(part) == 3 for part in parts[1:]):
            return "".join(parts)

    return clean


def normalize_numeric_columns(df, columns):
    """Apply ``normalize_eu_number`` to selected dataframe columns in place."""
    for col in columns:
        if col and col in df.columns:
            df[col] = df[col].apply(normalize_eu_number)
    return df
