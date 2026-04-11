"""Shared path helpers and logging configuration for SimpleTranslator."""

import logging
import logging.handlers
import os
import platform
import shutil
import sys


def get_install_dir():
    """Return the application install / project root directory (read-only).

    In a frozen (PyInstaller) build this is the directory containing the
    executable.  In development it is the project root.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


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
    """Resolve *relative_path* — checks user data dir, install dir, then bundle."""
    # 1. User data directory (user-added converters, edited configs)
    user_path = os.path.join(get_user_data_dir(), relative_path)
    if os.path.exists(user_path):
        return user_path

    # 2. Install / project directory
    install_path = os.path.join(get_install_dir(), relative_path)
    if os.path.exists(install_path):
        return install_path

    # 3. PyInstaller bundle
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
