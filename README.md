# PDF to CSV Extractor

This application extracts tabular data from PDF files and converts them into CSV format based on configurable rules.

## Setup

1.  **Install Dependencies:**
    Ensure you have Python installed. Then run:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Configure Extraction Rules:**
    Open `config.json` and add an entry for each PDF file you want to process.
    
    Format:
    ```json
    {
        "pdf_path": "path/to/your/file.pdf",
        "output_csv_path": "path/to/output.csv",
        "start_anchor": "Text that appears right before your data starts",
        "columns": ["Column1", "Column2", "Column3"],
        "end_anchor": "Text that appears right after your data ends (optional)"
    }
    ```

2.  **Run the Extractor:**
    ```bash
    python pdf_extractor.py
    ```
    The script will read `config.json`, process the specified files, and generate CSV files in the `output/` folder.

## Key Features

*   **Configurable Anchors:** Uses start and end text markers to locate the table within the PDF.
*   **Custom Parsing Logic:** Includes intelligent column mapping, including handling for some multi-word text fields and date columns (optimized for specific PO formats).
*   **Noise Filtering:** Automatically attempts to filter out non-data lines.
