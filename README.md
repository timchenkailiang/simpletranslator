# Simple PDF to CSV Translator & Merger

A modular application designed to convert various Purchase Order PDF formats (e.g., Globe, Jeffco, Series 16) into structured CSV files, validate the data, and optionally merge the results into an Excel template.

## Features

*   **GUI Application**: A user-friendly interface (`gui_app.py`) for processing single files.
    *   **Dynamic Converter Loading**: Easily switch between different PDF formats.
    *   **Searchable Dropdown**: Quick access to tools with type-to-search functionality.
    *   **Validator Integration**: Automatically checks converted data for logic errors (e.g., Qty * Price = Amount).
    *   **Excel Merger**: Merges extracted PDF data (like Price and Quantity) into an existing Excel template.
*   **Batch Processing (CLI)**: A script (`main_convert.py`) to process entire folders of PDFs at once.
*   **Extensible Architecture**: Add new converters by simply dropping a `.py` script into the folder and adding it to `tools.json`.

## Quick Start

### 1. GUI Application
Run the graphical interface:
```bash
python3 gui_app.py
```
1.  **Select Converter**: Choose the format that matches your PDF (e.g., "Globe").
2.  **Select File**: Browse for your source PDF.
3.  **Convert**: Click "Convert & Validate".
4.  **(Optional) Merge**: Select an Excel template, define column mappings, and merge.

### 2. Batch Processing
Run the batch converter:
```bash
python3 main_convert.py
```
*Note: Currently, this requires PDFs to be pre-sorted into folders like `source/Globe`, `source/Jeffco`, etc.*

## Project Structure

*   `gui_app.py`: Main application window.
*   `tools.json`: Configuration file storing available converters and their settings.
*   `main_convert.py`: CLI script for batch processing.
*   `merge_to_excel.py`: Logic for merging CSV data into Excel files.
*   `validate_output.py`: Common validation logic used by all converters.
*   `convert_*.py`: Individual layout parsers for different vendors.

## Future Updates / Roadmap

**Batch Run Enhancement**: 
Currently, `main_convert.py` relies on a strict folder structure (e.g., needing a `source/Globe` folder) to determine which converter script to use. 
**Future Goal**: Implement smart detection logic or a flat-file batch processor where the user can select a converter and a folder of mixed files, removing the need for manual folder sorting.
