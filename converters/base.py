"""
Base converter interface — documents the contract every converter must follow.

Subclassing ``BaseConverter`` is *optional*.  The plugin system only requires
a module-level ``process_file(input_path, output_path)`` function.

Modules can also expose these constants for richer integration with the
validation and UI layers:

    FORMAT_NAME: str          Human-readable name  (e.g. "Globe")
    COLUMNS: list[str]        Expected output CSV columns
    VALIDATION_RULES: dict    Maps 'qty', 'price', 'amount' → column names
"""


class BaseConverter:
    """Optional base class — provides IDE hints and documents the interface."""

    FORMAT_NAME: str = "Unknown"
    COLUMNS: list = []
    VALIDATION_RULES: dict = {}  # {"qty": col, "price": col, "amount": col}

    def process_file(self, input_path: str, output_path: str | None = None) -> bool:
        """Convert *input_path* (PDF) → *output_path* (CSV).  Return True on success."""
        raise NotImplementedError("Subclasses must implement process_file()")
