"""
Pipeline — orchestrates the extract → validate → insert flow.

This module is the **single source of truth** for the application's
business logic sequence.  The UI layer (or a future CLI) calls one of
these functions and receives structured results.

Progress feedback is handled via an optional ``on_progress(percent, message)``
callback so the caller can update a progress bar without the pipeline
knowing anything about Tkinter or any other UI framework.
"""

import csv
import logging
import os

from converters import load_converter_module
from engine.validate import validate_csv
from engine.insert import process_insert, NoMatchesFoundError
from utils import get_resource_path
from i18n import t

logger = logging.getLogger(__name__)


def _resolve_col_by_position(col_name, actual_headers, columns_meta):
    """Resolve a metadata column name to the actual CSV header by position.

    When a converter's VALIDATION_RULES or other metadata uses English
    column names (e.g. ``"Quantity"``) but the PDF was in another language
    (producing ``"Cantidad"`` in the CSV), this function maps via the
    positional index in the converter's ``COLUMNS`` list.

    Returns the resolved name, or the original *col_name* unchanged.
    """
    if not col_name or not columns_meta or not actual_headers:
        return col_name
    if col_name in actual_headers:
        return col_name
    try:
        idx = [c.lower() for c in columns_meta].index(col_name.lower())
        if idx < len(actual_headers):
            return actual_headers[idx]
    except ValueError:
        pass
    return col_name


def _resolve_validation_rules(rules, actual_headers, columns_meta):
    """Resolve all column names in a validation_rules dict."""
    if not rules:
        return rules
    resolved = {}
    for key, col_name in rules.items():
        if col_name:
            resolved[key] = _resolve_col_by_position(
                col_name, actual_headers, columns_meta)
        else:
            resolved[key] = col_name
    return resolved


# ── Public API ────────────────────────────────────────────────────────

def run_full_pipeline(pdf_path, csv_path, excel_path,
                      converter_module, pdf_cols, excel_cols,
                      output_path, on_progress=None,
                      qty_csv_col=None,
                      qty_increase_ratio=0.15, qty_decrease_ratio=0.15):
    """
    Complete pipeline: extract PDF → validate CSV → insert into Excel.

    Args:
        pdf_path:          Path to the source PDF.
        csv_path:          Path where intermediate CSV will be written.
        excel_path:        Path to the Excel template.
        converter_module:  Already-loaded converter module (has ``process_file``).
        pdf_cols:          List of CSV column names to read.
        excel_cols:        List of Excel column headers to write into.
        output_path:       Where to save the output Excel file.
        on_progress:       Optional ``(percent, message) → None`` callback.
        qty_csv_col:       CSV column name for quantity (enables recalculation).

    Returns:
        Path to the saved output file.

    Raises:
        RuntimeError:        If PDF → CSV conversion fails.
        NoMatchesFoundError: If no CSV keys match any Excel row.
    """

    fmt_name = getattr(converter_module, "FORMAT_NAME", "Unknown")
    logger.info("=== Full Pipeline started ===")
    logger.info("  PDF:       %s", pdf_path)
    logger.info("  CSV:       %s", csv_path)
    logger.info("  Excel:     %s", excel_path)
    logger.info("  Output:    %s", output_path)
    logger.info("  Converter: %s", fmt_name)
    logger.info("  Mapping:   %s → %s", pdf_cols, excel_cols)

    # Auto-detect quantity column from converter metadata when not explicit
    if qty_csv_col is None:
        rules = getattr(converter_module, "VALIDATION_RULES", None)
        if rules and rules.get("qty"):
            qty_csv_col = rules["qty"]
            logger.info("  Qty col:   %s (auto-detected from VALIDATION_RULES)",
                        qty_csv_col)
    if qty_csv_col:
        logger.info("  Qty col:   %s", qty_csv_col)

    # ── Step 1: Extract (PDF → CSV) ──────────────────────────────────
    logger.info("--- Step 1/3: Extract (PDF → CSV) ---")
    _notify(on_progress, 45, t("pipeline.converting_pdf_csv"))
    success = converter_module.process_file(pdf_path, csv_path)

    if not success:
        if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
            logger.warning("Converter returned False but CSV exists — continuing.")
        else:
            logger.error("PDF → CSV conversion failed (no output).")
            raise RuntimeError("PDF to CSV conversion failed.")
    else:
        csv_size = os.path.getsize(csv_path) if os.path.exists(csv_path) else 0
        logger.info("Extract complete — CSV size: %d bytes", csv_size)

    # Resolve column names against actual CSV headers.
    # VALIDATION_RULES may use English names (e.g. "Quantity") but the
    # converter can output localised headers (e.g. "Cantidad") depending
    # on the source PDF language.  Match by position in COLUMNS metadata.
    with open(csv_path, encoding="utf-8") as f:
        actual_headers = next(csv.reader(f))
    columns_meta = getattr(converter_module, "COLUMNS", None)

    if qty_csv_col:
        resolved = _resolve_col_by_position(
            qty_csv_col, actual_headers, columns_meta)
        if resolved != qty_csv_col:
            logger.info("  Qty col:   '%s' not in CSV, resolved to "
                        "'%s' by COLUMNS position",
                        qty_csv_col, resolved)
            qty_csv_col = resolved

    # Count rows extracted from PDF (header excluded)
    with open(csv_path, encoding="utf-8") as f:
        rows_extracted = sum(1 for _ in f) - 1
    logger.info("Rows extracted from PDF: %d", rows_extracted)

    # ── Step 2: Validate (QA checks on CSV) ──────────────────────────
    logger.info("--- Step 2/3: Validate CSV ---")
    _notify(on_progress, 60, t("pipeline.validating_csv"))
    fmt = getattr(converter_module, "FORMAT_NAME", None)
    rules = getattr(converter_module, "VALIDATION_RULES", None)
    rules = _resolve_validation_rules(rules, actual_headers, columns_meta)
    flagged_cells, rows_removed = validate_csv(
        csv_path, format_name=fmt, validation_rules=rules)
    logger.info("Validation complete — %d cell(s) flagged, %d row(s) removed",
                len(flagged_cells), rows_removed)

    # ── Step 3: Insert (CSV → Excel) ─────────────────────────────────
    logger.info("--- Step 3/3: Insert (CSV → Excel) ---")
    _notify(on_progress, 75, t("pipeline.inserting_csv_excel"))
    try:
        insert_result = process_insert(
            csv_path, excel_path, pdf_cols, excel_cols,
            output_path=output_path,
            flagged_cells=flagged_cells,
            qty_csv_col=qty_csv_col,
            qty_increase_ratio=qty_increase_ratio,
            qty_decrease_ratio=qty_decrease_ratio,
        )
    except NoMatchesFoundError as e:
        e.stats["rows_extracted"] = rows_extracted
        e.stats["rows_removed"] = rows_removed
        e.stats["cells_flagged"] = len(flagged_cells)
        raise

    result = {
        "output_path": insert_result["output_path"],
        "rows_extracted": rows_extracted,
        "rows_removed": rows_removed,
        "cells_flagged": len(flagged_cells),
        "total_csv_rows": insert_result["total_csv_rows"],
        "rows_matched": insert_result["rows_matched"],
        "rows_not_found": insert_result["rows_not_found"],
        "red_cells": insert_result["red_cells"],
        "yellow_cells": insert_result["yellow_cells"],
        "missing_columns": insert_result.get("missing_columns", []),
        "qty_recalc_disabled": insert_result.get("qty_recalc_disabled", False),
    }

    logger.info("=== Full Pipeline finished — saved to %s ===", result["output_path"])
    _notify(on_progress, 100, t("pipeline.success", path=result["output_path"]))
    return result


def run_extract_only(pdf_path, csv_path, converter_module,
                     on_progress=None):
    """
    Extract + validate only (no Excel insertion).

    Args:
        pdf_path:          Path to the source PDF.
        csv_path:          Path where intermediate CSV will be written.
        converter_module:  Already-loaded converter module.
        on_progress:       Optional ``(percent, message) → None`` callback.

    Returns:
        Tuple of ``(csv_path, flagged_cells)`` where *flagged_cells* is a
        set of ``(key_value, column_name)`` tuples.

    Raises:
        RuntimeError: If conversion produces no data.
    """

    fmt_name = getattr(converter_module, "FORMAT_NAME", "Unknown")
    logger.info("=== Extract-Only Pipeline started ===")
    logger.info("  PDF:       %s", pdf_path)
    logger.info("  CSV:       %s", csv_path)
    logger.info("  Converter: %s", fmt_name)

    # ── Step 1: Extract ──────────────────────────────────────────────
    logger.info("--- Step 1/2: Extract (PDF → CSV) ---")
    _notify(on_progress, 50, t("pipeline.converting_pdf"))
    success = converter_module.process_file(pdf_path, csv_path)

    if not success:
        logger.error("Conversion returned no data.")
        raise RuntimeError("Conversion returned no data.")

    csv_size = os.path.getsize(csv_path) if os.path.exists(csv_path) else 0
    logger.info("Extract complete — CSV size: %d bytes", csv_size)

    # ── Step 2: Validate ─────────────────────────────────────────────
    logger.info("--- Step 2/2: Validate CSV ---")
    _notify(on_progress, 80, t("pipeline.validating"))
    fmt = getattr(converter_module, "FORMAT_NAME", None)
    rules = getattr(converter_module, "VALIDATION_RULES", None)
    columns_meta = getattr(converter_module, "COLUMNS", None)
    with open(csv_path, encoding="utf-8") as f:
        actual_headers = next(csv.reader(f))
    rules = _resolve_validation_rules(rules, actual_headers, columns_meta)
    flagged_cells, rows_removed = validate_csv(
        csv_path, format_name=fmt, validation_rules=rules)

    logger.info("=== Extract-Only Pipeline finished — %d cell(s) flagged, %d row(s) removed ===",
                len(flagged_cells), rows_removed)
    _notify(on_progress, 100, t("pipeline.done"))
    return csv_path, flagged_cells


# ── Internal helpers ──────────────────────────────────────────────────

def _notify(callback, percent, message):
    """Fire the progress callback if provided."""
    if callback:
        callback(percent, message)
