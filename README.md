# Simple PDF to CSV Translator & Merger

A modular, three-layer application that converts vendor-specific Purchase Order
PDFs (Globe, Jeffco, Millarco / Series 16) into structured CSV files, validates
the data, and merges the results into an Excel template.

## Architecture

The project follows a clean three-layer design:

| Layer | Package | Purpose |
|-------|---------|---------|
| **1 — Converters** | `converters/` | PDF → CSV.  One module per vendor format. |
| **2 — Engine** | `engine/` | CSV → Excel insertion + validation.  PDF-agnostic. |
| **3 — UI** | `ui/` | Tkinter GUI (profiles, searchable dropdowns, tool CRUD). |

## Quick Start

### Install dependencies
```bash
pip install -r requirements.txt
```

### Launch the GUI
```bash
python main.py
```

1.  **Select Converter** — choose the format that matches your PDF (e.g. "Globe").
2.  **Select PDF** — browse for the source file.
3.  **Convert & Validate** — click the convert button.
4.  **(Optional) Merge** — pick an Excel template, map columns, and run.

### Run a converter directly (CLI)
```bash
python converters/globe.py path/to/file.pdf            # single file
python converters/globe.py                              # batch (source/Globe/)
```

## Project Structure

```
simpletranslator/
├── converters/               # Layer 1 — PDF-to-CSV parsers
│   ├── __init__.py           #   Dynamic loader helper
│   ├── base.py               #   BaseConverter interface docs
│   ├── globe.py              #   Globe PO (Spanish / English)
│   ├── jeffco.py             #   Jeffco PO
│   └── millarco.py           #   Series 16 / Millarco PO
│
├── engine/                   # Layer 2 — Insertion & validation
│   ├── __init__.py
│   ├── insert.py             #   CSV → Excel merge (PDF-agnostic)
│   ├── pipeline.py           #   Orchestrates extract → validate → insert
│   └── validate.py           #   Numeric, math & encoding checks
│
├── ui/                       # Layer 3 — Front-end
│   ├── __init__.py
│   ├── widgets.py            #   SearchableDropdown widget
│   └── app.py                #   ConverterApp main window
│
├── config/                   # Configuration
│   ├── tools.json            #   Registered converters
│   └── merge_profiles.json   #   Saved merge profiles
│
├── main.py                   # Entry point
├── utils.py                  # Logging setup, number parsing
├── requirements.txt          # Python dependencies
└── README.md
```

## Adding a New Converter

1. Create `converters/my_vendor.py` with a `process_file(input_path, output_path)` function (return `True`/`False`).
2. Optionally add metadata constants: `FORMAT_NAME`, `COLUMNS`, `VALIDATION_RULES`.
3. Register it in the GUI via the **+** button, or add an entry to `config/tools.json`.

## Future Updates / Roadmap

*   **Batch GUI mode** — select a converter + folder of mixed files without manual sorting.
*   **Web UI** — swap the Tkinter front-end for a browser-based interface (layers 1 & 2 stay unchanged).

---

## Assumptions & Constraints

This section documents all implicit assumptions made across the codebase.
Understanding these is critical when working with new PDF formats, languages,
or Excel templates.

### CSV & Data Structure

| Assumption | Location | Impact |
|---|---|---|
| **First CSV column is always the lookup key** | `engine/insert.py`, `engine/validate.py` | The entire merge matches rows by `columns[0]`. No configuration to choose a different key column. |
| **Key matching is case-sensitive** | `engine/insert.py` | CSV key `"ABC123"` won't match Excel cell `"abc123"`. Column *header* matching is case-insensitive, but row-value matching is not. |
| **First occurrence wins in Excel lookup** | `engine/insert.py` | If a key value appears multiple times in the Excel template, only the first (topmost) row is updated. |
| **No duplicate CSV column names** | All converters | `_find_name_icase()` returns the first match; duplicate column names cause silent data loss. |
| **CSV encoding is always UTF-8** | `engine/pipeline.py`, `engine/validate.py` | Files opened with `encoding="utf-8"`. Non-UTF-8 CSVs (e.g. latin-1 from older tools) will fail. |

### Excel Template

| Assumption | Location | Impact |
|---|---|---|
| **XLSX format only (not `.xls`)** | `engine/insert.py` | Output path derived via `.replace(".xlsx", "_merged.xlsx")`. Old `.xls` files produce invalid output names. |
| **Active sheet is the target** | `engine/insert.py` | `ws = wb.active` — only the active sheet is read/written. Multi-sheet templates require the target sheet to be active. |
| **Template read with `header=None`** | `engine/insert.py` | All rows (including header) are scanned for lookup values. The header row is treated as data too. |
| **`Pcs/Ctn` and `Pcs/Plt` columns required for qty recalculation** | `engine/insert.py` | If either column is missing, recalculation is silently disabled and the raw CSV quantity is used. |

### Column Name Resolution (Localisation)

| Assumption | Location | Impact |
|---|---|---|
| **COLUMNS metadata order must match actual CSV output order** | `engine/pipeline.py` | When CSV headers are localised (e.g. Spanish "Cantidad" instead of English "Quantity"), the pipeline resolves column names by **positional index** in the converter's `COLUMNS` list. If a converter outputs columns in a different order than declared, the mapping breaks silently. |
| **VALIDATION_RULES use English names** | All converters | Rules like `{"qty": "Quantity"}` are defined in English. The pipeline resolves these against actual CSV headers at runtime. If a converter has no `COLUMNS` metadata, localised validation columns can't be resolved. |

### Numeric Formats

| Assumption | Location | Impact |
|---|---|---|
| **EU and US number formats only** | `utils.py` | `parse_localized_number()` handles `1.000,00` (EU) and `1,000.00` (US). Other regional formats (e.g. Indian `1,00,000`) are not supported. |
| **Only `$`, `€`, and `"USD"` stripped from numbers** | `utils.py` | Other currency symbols (¥, £, ₹) embedded in numeric cells will cause parse failures. |
| **Math validation tolerance: ±1.0 or ±1%** | `engine/validate.py` | `Qty × Price = Amount` check allows the larger of 1.0 absolute or 1% relative difference. |
| **Quantity recalculation output: `"original/calculated"` string** | `engine/insert.py` | When recalculation is active, the cell value is a text string like `"504/500"`, not a number. Excel formulas referencing this cell will see text, not a numeric value. |

### Converter PDF Parsing (Positional)

All converters use **x-coordinate bucketing** to assign words to columns.
These thresholds are hardcoded and tuned to specific PDF layouts.

| Converter | Key Assumptions |
|---|---|
| **Globe** | Item number: `x < 50` and `len ≥ 10` characters. Line grouping: y-coordinates within 3 pixels. Column buckets: Item `x < 100`, Description `100–260`, Quantity `260–310`, Price `360–420`, Amount `440–490`, Delivery `x > 490`. |
| **Jeffco** | Data lines must contain `"STK"` marker. Description is on the **next** line (not the item line). Column buckets: Quantity `x < 130`, Your Part No `130–250`, Our Part No `250–370`, ETD `370–450`, Price `x ≥ 450`. |
| **Millarco** | Tail-pattern regex extracts: Master, Inner, Qty, UnitPrice, Amount, ETD from trailing numeric data. Item numbers must be purely numeric and appear first in the line. |

### File System & Configuration

| Assumption | Location | Impact |
|---|---|---|
| **Config files in `config/` subdirectory** | `ui/app.py` | `tools.json` and `merge_profiles.json` paths are hardcoded relative to the data directory. |
| **Only the latest intermediate CSV is kept** | `ui/app.py` | Previous intermediate CSVs are deleted before each run. No history is maintained. |
| **Log files: 2 MB × 3 backups** | `utils.py` | `RotatingFileHandler` keeps at most ~8 MB of log history before overwriting. |
| **Output file naming: `_merged.xlsx` suffix** | `engine/insert.py` | Default output replaces `.xlsx` with `_merged.xlsx`. Re-running on an already-merged file appends again. |

### Quantity Recalculation

| Assumption | Impact |
|---|---|
| **Priority: full pallets first (up, then down), then mixed packing** | The algorithm prefers full-pallet quantities even if a mixed result is closer to the original. |
| **Tolerance < 1 treated as ratio, ≥ 1 treated as exact piece count** | `0.15` → 15% increase allowed. `15` → 15 pieces increase allowed. There is no way to specify a ratio > 1.0 directly. |
| **Zero or negative packing info → recalculation skipped** | If `Pcs/Ctn` or `Pcs/Plt` is 0 or negative, the original quantity is returned unchanged. |

### Red / Yellow Cell Highlighting

| Colour | Meaning |
|---|---|
| **Red** (`#FFC7CE`) | The value written to the Excel cell **differs from the original CSV value** — i.e. it was modified by a transformation (e.g. quantity recalculation). Straight passthrough values get no highlight. |
| **Yellow** (`#FFFF00`) | The cell was flagged by validation (numeric format issue, math mismatch, suspicious characters). |
| **No fill** | The value was passed through from CSV to Excel unchanged, or the cell was skipped because the existing value already matched. |
