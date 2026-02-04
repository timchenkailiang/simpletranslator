import pdfplumber

def debug_tables(pdf_path):
    print(f"Debug tables for {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for j, table in enumerate(tables):
                print(f"--- Page {i+1} Table {j+1} ---")
                for row in table:
                    # Print row only if it has an item number
                    cleaned_row = [cell.strip().replace('\n', ' ') if cell else "" for cell in row]
                    # Check if first valid cell resembles an item number (digits)
                    first_cell = next((c for c in cleaned_row if c), None)
                    if first_cell and first_cell.isdigit():
                         print(cleaned_row)

if __name__ == "__main__":
    debug_tables("source/Series_16/PO16431.pdf")
