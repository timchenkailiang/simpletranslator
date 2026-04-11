"""
CSV validation — checks numeric formats, math consistency, and encoding.

Can auto-detect the output format from CSV column names, or accept explicit
metadata from a converter module's ``FORMAT_NAME`` / ``VALIDATION_RULES``.
"""

import logging
import os
import re
import sys
import glob
import pandas as pd

logger = logging.getLogger(__name__)


# ── Number parsing ────────────────────────────────────────────────────

def parse_number(value_str):
    """
    Parse a string into a float, handling common EU / US number formats.

    Returns ``None`` when the value is empty, NaN, or unparseable.
    """
    if pd.isna(value_str) or value_str == "":
        return None

    if not isinstance(value_str, str):
        return float(value_str)

    clean = value_str.strip()
    if not clean:
        return None

    # Strip currency noise
    clean = clean.replace("USD", "").replace("$", "").replace("€", "").strip()

    # EU thousands separator: 2.000,00
    if re.search(r"\.\d{3},", clean):
        clean = clean.replace(".", "").replace(",", ".")
    # US thousands separator: 2,000.00
    elif re.search(r",\d{3}\.", clean):
        clean = clean.replace(",", "")
    # Dot-only, might be thousands: 1.120 → 1120
    elif "," not in clean and "." in clean:
        parts = clean.split(".")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            clean = clean.replace(".", "")
    # Comma-only decimal: 1234,56
    elif "," in clean and "." not in clean:
        clean = clean.replace(",", ".")

    try:
        return float(clean)
    except ValueError:
        return None


# ── Math check ────────────────────────────────────────────────────────

def _check_math(row, qty_col, price_col, amount_col):
    """Return ``(ok, calculated, actual)`` for Qty × Price = Amount."""
    qty = parse_number(row.get(qty_col))
    price = parse_number(row.get(price_col))
    amount = parse_number(row.get(amount_col))

    if qty is not None and price is not None and amount is not None:
        calculated = qty * price
        diff = abs(calculated - amount)
        if diff > 1.0 and diff > (amount * 0.01):
            return False, calculated, amount
    return True, 0, 0


# ── Format detection (fallback when no metadata provided) ─────────────

def _detect_format(columns):
    """
    Auto-detect the CSV format from its column names.

    Returns ``(format_name, expected_cols, validation_rules)``.
    """
    if "Artículo" in columns or "Item" in columns:
        if "Artículo" in columns:
            expected = ["Artículo", "Denominación", "Cantidad",
                        "Precio", "Importe", "Entrega"]
            rules = {"qty": "Cantidad", "price": "Precio", "amount": "Importe"}
        else:
            expected = ["Item", "Description", "Quantity",
                        "Price", "Amount", "Delivery"]
            rules = {"qty": "Quantity", "price": "Price", "amount": "Amount"}
        return "Globe", expected, rules

    if "Our Part No" in columns:
        expected = ["Quantity", "Your Part No", "Our Part No",
                    "Price USD", "Del. date", "Description"]
        rules = {"qty": "Quantity", "price": "Price USD", "amount": None}
        return "Jeffco", expected, rules

    # Default: Series 16 / Millarco
    expected = ["Itemno", "Description", "Master", "Inner",
                "Quantity", "Unit price", "Amount", "ETD"]
    rules = {"qty": "Quantity", "price": "Unit price", "amount": "Amount"}
    return "Series 16", expected, rules


# ── Suspicious character map ──────────────────────────────────────────

SUSPICIOUS_CHARS = {
    "\xad":   "Soft Hyphen",
    "\u00ad": "Soft Hyphen",
    "\u2011": "Non-breaking Hyphen",
    "\ufffd": "Replacement Character",
}


# ── Public API ────────────────────────────────────────────────────────

def validate_csv(file_path, format_name=None, validation_rules=None):
    """
    Validate a single CSV file.

    Args:
        file_path: Path to the CSV file.
        format_name: Optional — skip auto-detection when provided.
        validation_rules: Optional dict with keys ``'qty'``, ``'price'``,
            ``'amount'`` mapping to column names.
    """
    logger.info("Validating %s", file_path)

    try:
        df = pd.read_csv(file_path, dtype=str)
    except Exception as e:
        logger.error("Could not read file %s: %s", file_path, e)
        return

    columns = list(df.columns)

    # Detect or use provided metadata
    if format_name is None or validation_rules is None:
        det_name, expected_cols, det_rules = _detect_format(columns)
        format_name = format_name or det_name
        validation_rules = validation_rules or det_rules
    else:
        expected_cols = None  # skip column-order check

    if expected_cols and columns != expected_cols:
        logger.warning("[%s] Column mismatch. Expected %s, got %s",
                       format_name, expected_cols, columns)

    if df.empty:
        logger.warning("File is empty (no data rows).")
        return

    logger.info("Format: %s | Rows: %d", format_name, len(df))

    # ── Numeric validation ────────────────────────────────────────────
    numeric_issues = 0
    math_issues = 0

    cols_to_check = [
        validation_rules.get(k)
        for k in ("qty", "price", "amount")
        if validation_rules.get(k)
    ]

    for col in cols_to_check:
        if col not in df.columns:
            continue
        for idx, val in df[col].items():
            if parse_number(val) is None and val != "" and not pd.isna(val):
                logger.warning("[Numeric] Row %d col '%s' invalid number: '%s'",
                               idx, col, val)
                numeric_issues += 1

    # ── Math check (Qty × Price = Amount) ─────────────────────────────
    amt_col = validation_rules.get("amount")
    if amt_col and amt_col in df.columns:
        qty_c = validation_rules["qty"]
        prc_c = validation_rules["price"]
        for idx, row in df.iterrows():
            ok, calc, actual = _check_math(row, qty_c, prc_c, amt_col)
            if not ok:
                logger.warning(
                    "[Math] Row %d: %s(%s) × %s(%s) ≠ %s(%s)  [Calc: %.2f]",
                    idx, qty_c, row[qty_c], prc_c, row[prc_c],
                    amt_col, row[amt_col], calc)
                math_issues += 1

    if numeric_issues == 0 and math_issues == 0:
        logger.info("Numeric & Logic checks passed.")

    # ── Suspicious characters ─────────────────────────────────────────
    char_issues = False
    for col in df.columns:
        if df[col].dtype != object:
            continue
        for idx, val in df[col].items():
            if not isinstance(val, str):
                continue
            for char, name in SUSPICIOUS_CHARS.items():
                if char in val:
                    logger.warning("Found %s in row %d, column '%s': '%s'",
                                   name, idx, col, val)
                    char_issues = True

    if not char_issues:
        logger.info("No suspicious characters found.")


def validate_csvs(target_path):
    """Validate all CSV files under *target_path* (file or directory)."""
    if os.path.isfile(target_path):
        csv_files = [target_path]
        logger.info("Validating single file: %s", target_path)
    else:
        csv_files = glob.glob(
            os.path.join(target_path, "**/*.csv"), recursive=True)
        logger.info("Found %d CSV files in %s", len(csv_files), target_path)

    for fp in csv_files:
        validate_csv(fp)


# Backward-compatible alias used by the GUI
validate_file = validate_csv


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    target = sys.argv[1] if len(sys.argv) > 1 else "output"
    validate_csvs(target)
