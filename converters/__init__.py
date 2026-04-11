"""
Converter package — PDF-to-CSV parsers for various PO formats.

Each converter module must expose:
    process_file(input_path, output_path=None) -> bool

Optional module-level constants for richer integration:
    FORMAT_NAME: str
    COLUMNS: list[str]
    VALIDATION_RULES: dict  (keys: 'qty', 'price', 'amount')
"""

import importlib.util
import logging
import os
import sys

logger = logging.getLogger(__name__)


def load_converter_module(script_path):
    """
    Dynamically load a converter module from a file path.

    Args:
        script_path: Absolute or relative path to the .py converter script.

    Returns:
        The loaded module object.

    Raises:
        FileNotFoundError: If the script does not exist.
        AttributeError: If the script has no ``process_file`` function.
    """
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Converter script not found: {script_path}")

    # Use a unique module name per file to avoid collisions
    mod_name = f"converter_{os.path.basename(script_path).replace('.py', '')}"
    spec = importlib.util.spec_from_file_location(mod_name, script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, "process_file"):
        raise AttributeError(
            f"Converter '{script_path}' must define a "
            f"'process_file(input_path, output_path)' function."
        )

    return module
