import pdfplumber
import pandas as pd
import sys
import re
import os
import glob

def convert_pdf_to_csv(pdf_path, csv_path):
    print(f"Processing {pdf_path}...")
    
    # Modified regex to be more flexible with the Description part
    # Specifically handling "Brand: HOME It®" which appears immediately after Itemno
    # The layout inspection showed: "11082 Brand: HOME It® 576 4 1.152,00..."
    # The previous regex expected whitespace between columns.
    
    # Let's try to infer columns based on the strict structure of the numbers at the end.
    # The suffix is consistently: Master Inner Quantity UnitPrice Amount ETD
    # Master: int
    # Inner: int
    # Quantity: number like 1.152,00
    # UnitPrice: number like 7,69
    # Amount: number like 8.858,88
    # ETD: date like 30-12-2025
    
    # We will use search from the end of the line backwards.
    
    data = []
    headers = ["Itemno", "Description", "Master", "Inner", "Quantity", "Unit price", "Amount", "ETD"]
    
    # Regex for the trailing data columns
    # \s+(\d+)\s+(\d+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.\-]+.*)$
    # Master Inner Qty UnitPrice Amount ETD
    tail_pattern = re.compile(r"\s+(\d+)\s+(\d+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.\-]+.*)$")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            for line in text.split('\n'):
                # Look for the tail pattern at the end of the line
                tail_match = tail_pattern.search(line)
                if tail_match:
                    # Captured groups for the tail
                    master, inner, qty, unit_price, amount, etd = tail_match.groups()
                    
                    # Clean up ETD (remove soft hyphens if any, and other non-standard hyphens)
                    # The user sees "blocks", which often suggests non-breaking hyphens or other variants.
                    # We will replace common hyphen-like characters with a standard ASCII hyphen.
                    etd = etd.replace('\xad', '-').replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')

                    # Helper function to clean common text artifacts
                    def clean_text(text):
                        if not text: return text
                        # Replace soft hyphens and other invisible/problematic chars
                        return text.replace('\xad', '-').replace('\u00ad', '-').replace('\u2011', '-')

                    # Everything before the tail is "Itemno Description"
                    # split point
                    head = line[:tail_match.start()].strip()
                    
                    # The head should start with Itemno (digits)
                    # Use split(maxsplit=1) to separate Itemno from Description
                    parts = head.split(maxsplit=1)
                    if len(parts) == 2 and parts[0].isdigit():
                        itemno = parts[0]
                        description = clean_text(parts[1])
                        
                        # Special handling for "Brand:" appearing in description
                        # If description starts with "Brand:", check if subsequent lines contain more info
                        # However, for now, the user only asked for columns and their value. 
                        # The extracted description for 11082 is "Brand: HOME It®".
                        # This seems to be what is on the line. 
                        # If the user wants the FULL description which might span multiple lines, that is more complex.
                        # Based on "i only need columns and their value", we assume the value present on the line is sufficient
                        # or at least what is structurally available.
                        # But wait, looking at 11082 in the pdf text context:
                        # 22: 11082 Brand: HOME It® 576 4 1.152,00 7,69 8.858,88 30­12­2025
                        # The "Description" column visually seems to be just "Brand: HOME It®" on that line.
                        # But looking at item 10200:
                        # "Matt black hooks 20x25mm for acoustic panels, 2 pieces, SLIM end hook."
                        # This looks like a proper description.
                        # The items 11082, 11094, 16808 seem to have "Brand: HOME It®" where the description usually is.
                        # This might be valid data for those rows in this specific PDF format.
                        
                        data.append([itemno, description, master, inner, qty, unit_price, amount, etd])

    if not data:
        print("No matching table data found.")
        return

    # Create a DataFrame
    df = pd.DataFrame(data, columns=headers)
    
    # Save to CSV
    df.to_csv(csv_path, index=False)
    print(f"Saved to {csv_path}")

def main():
    source_dir = "source/Series_16"
    output_dir = "output/Series_16"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)
        csv_name = file_name.replace(".pdf", ".csv")
        csv_path = os.path.join(output_dir, csv_name)
        
        convert_pdf_to_csv(pdf_path, csv_path)

if __name__ == "__main__":
    main()
