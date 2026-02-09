import pdfplumber
import pandas as pd
import re
import os
import glob
import sys
from datetime import datetime

def clean_text(text):
    if not isinstance(text, str):
        return text
    # Replace soft hyphens and other problematic characters using known unicode points
    text = text.replace('\xad', '').replace('\u00ad', '').replace('\u2011', '-')
    return text.strip()

def extract_jeffco_data(pdf_path):
    print(f"Extracting Jeffco data from {os.path.basename(pdf_path)}...")
    data_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        # Assuming single page for now based on samples, but could loop
        page = pdf.pages[0] 
        words = page.extract_words()
        
        # 1. Identify rows by looking for "STK" which seems to be the unit in Quantity column
        #    Format: Quantity Unit PartNo1 PartNo2 Date
        #    Example: 1000 STK 60020 0107 15-10-26
        
        # Sort words vertically then horizontally
        words.sort(key=lambda w: (round(w['top']), w['x0']))
        
        # Helper to group words into lines
        lines = {}
        for w in words:
            # Group by simple integer top to handle slight misalignments
            top_key = int(w['top'])
            # Check if we can merge with a very close existing line
            found_key = None
            for k in lines:
                if abs(k - top_key) < 3:
                    found_key = k
                    break
            
            if found_key:
                lines[found_key].append(w)
            else:
                lines[top_key] = [w]
                
        sorted_line_keys = sorted(lines.keys())
        
        # Iterate through lines to find Item rows
        for i, key in enumerate(sorted_line_keys):
            line_words = lines[key]
            line_words.sort(key=lambda x: x['x0'])
            line_text = " ".join([w['text'] for w in line_words])
            
            # Heuristic: Identify a main item row by containing STK and having a date-like structure at the end
            # or simply based on columns. Since "STK" is consistent in samples:
            if "STK" in line_text:
                # Structure seems to be: QTY | UNIT | PART_NO_1 | PART_NO_2 | DATE | PRICE?
                # However, looking at the layout:
                # 1000 STK 60020 0107 15-10-26
                # SHELF BRACKET 250X300MM (Next Line)
                
                # Let's try to parse the current line
                parts = line_text.split()
                
                # Basic validation
                if len(parts) >= 4:
                    # Mapping based on headers x0:
                    # Quantity: ~61
                    # Your part No: ~139-200
                    # Our part No: ~289-343
                    # Del date: ~379-410
                    # Price: ~469
                    
                    # Current row words:
                    # 1000 (85) | STK (115) | 60020 (295) | 0107 (331) | 15-10-26 (379)
                    
                    # Clearer extraction by x-coordinate bucketing
                    qty_word = ""
                    your_part_no_parts = []
                    our_part_no_parts = []
                    etd_word = ""
                    price_word = ""
                    
                    # Filter out STK if it appears in quantity area
                    filtered_words = [w for w in line_words if w['text'] != "STK"]
                    
                    for w in filtered_words:
                        x = w['x0']
                        text = w['text']
                        
                        if x < 130:
                            if any(c.isdigit() for c in text): # qty is numeric
                                qty_word = text
                        elif 130 <= x < 250:
                            # Your Part No column
                            your_part_no_parts.append(text)
                        elif 250 <= x < 370:
                            # Our Part No column
                            our_part_no_parts.append(text)
                        elif 370 <= x < 450:
                            # Date
                            etd_word = text
                        elif x >= 450:
                            price_word = text

                    your_part_no = " ".join(your_part_no_parts)
                    our_part_no = " ".join(our_part_no_parts).replace(" ", "")
                    
                    # Fix: Date sometimes spills over or Price is empty
                    # If etd_word ends with a price-like number or is very long, check split
                    # Basic x-coord is: Del date ~379-410, Price ~469
                    # Looking at debug output: Del. date header at x379. Price header at x469.
                    # Data: 15-10-26 at x379. No text > 450 in the sample rows!
                    # "15-10-26" is clearly the date.
                    # It seems some POs like PO32357 actually DO NOT have prices listed on the line.
                    
                    # Make sure we didn't miss it if it's slightly shifted
                    if not price_word:
                         # Try a wider search for the last element if it's far to the right
                         if line_words[-1]['x0'] > 440:
                             last_word = line_words[-1]
                             # If it wasn't caught in the >450 bucket (maybe it was 445)
                             if last_word['text'] != etd_word and last_word['text'] != qty_word:
                                 price_word = last_word['text']

                    # Now look for description in the NEXT line(s)
                    # We look for lines between current line and next "STK" line
                    description_parts = []
                    
                    # Look ahead
                    if i + 1 < len(sorted_line_keys):
                        next_key = sorted_line_keys[i+1]
                        next_words = lines[next_key]
                        next_words.sort(key=lambda x: x['x0'])
                        next_text = " ".join([w['text'] for w in next_words])
                        
                        # Check if next line is another item or footer
                        if "STK" not in next_text and "---" not in next_text and "REMARK" not in next_text.upper():
                            # It's likely the description
                            # Check indentation - descriptions seem indented or aligned with PartNo (x295)
                            # Inspection showed Description start x295
                            if len(next_words) > 0 and next_words[0]['x0'] > 200:
                                description_parts.append(next_text)
                    
                    description = " ".join(description_parts)
                    
                    row_data = {
                        "Your Part No": clean_text(your_part_no),
                        "Our Part No": clean_text(our_part_no),
                        "Description": clean_text(description),
                        "Quantity": clean_text(qty_word),
                        "Price USD": clean_text(price_word),
                        "Del. date": clean_text(etd_word)
                    }
                    data_rows.append(row_data)

    return data_rows

def process_file(input_path, output_path=None):
    if not output_path:
        # Default to output/Jeffco if no output path specified
        base_name = os.path.basename(input_path).replace(".pdf", ".csv")
        output_dir = os.path.join("output", "Jeffco")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_path = os.path.join(output_dir, base_name)

    print(f"Processing Jeffco file: {input_path}")
    try:
        data = extract_jeffco_data(input_path)
        if data:
            df = pd.DataFrame(data)
            cols = ["Our Part No", "Quantity", "Your Part No", "Price USD", "Del. date", "Description"]
            for c in cols:
                if c not in df.columns: df[c] = ""
            df = df[cols]
            df.to_csv(output_path, index=False)
            print(f"Saved {output_path}")
            return True
        else:
            print("No data extracted.")
            return False
    except Exception as e:
        print(f"Error: {e}")
        raise e

def main():
    # Check for CLI arguments
    if len(sys.argv) > 1:
        process_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
        return

    # Default Batch Mode
    source_dir = "source/Jeffco"
    output_dir = "output/Jeffco"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
    
    for pdf_file in pdf_files:
        try:
            filename = os.path.basename(pdf_file).replace(".pdf", ".csv")
            output_path = os.path.join(output_dir, filename)
            
            data = extract_jeffco_data(pdf_file)
            
            if data:
                df = pd.DataFrame(data)
                
                # Desired output columns
                # We want: Our Part No, Quantity, Your Part No, Price USD, Del. date, Description
                cols = ["Our Part No", "Quantity", "Your Part No", "Price USD", "Del. date", "Description"]
                
                # Ensure they exist
                for c in cols:
                    if c not in df.columns:
                        df[c] = ""
                
                df = df[cols]
                df.to_csv(output_path, index=False)
                print(f"Saved {output_path}")
            else:
                print(f"No data extracted for {pdf_file}")
                
        except Exception as e:
            print(f"Error processing {pdf_file}: {e}")

if __name__ == "__main__":
    main()
