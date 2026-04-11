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
│   ├── merge.py              #   CSV → Excel merge (PDF-agnostic)
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
