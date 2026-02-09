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

def extract_globe_data(pdf_path):
    print(f"Extracting Globe data from {os.path.basename(pdf_path)}...")
    data_rows = []
    
    # Store detected column headers (detected once)
    detected_headers = {
        "Item": "Item",
        "Description": "Description",
        "Quantity": "Quantity",
        "Price": "Price", 
        "Amount": "Amount",
        "Delivery": "Delivery"
    }
    headers_found = False

    with pdfplumber.open(pdf_path) as pdf:
        # Loop through pages since orders might span multiple
        for page in pdf.pages:
            words = page.extract_words()
            
            # Group by top
            lines = {}
            for w in words:
                top_key = int(w['top'])
                # Fuzzy match lines
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
            
            # Attempt header detection on the first page if not found
            if not headers_found:
                for key in sorted_line_keys:
                    line_words = lines[key]
                    line_words.sort(key=lambda x: x['x0'])
                    text_line = " ".join([w['text'] for w in line_words]).lower()
                    
                    # Heuristics for header line
                    if "quantity" in text_line or "cantidad" in text_line or "description" in text_line or "descripcion" in text_line:
                        # This is likely the header row. Let's capture the actual text at the known positions
                        
                        # Initialize buckets for header text parts
                        header_parts = {
                            "Item": [],
                            "Description": [],
                            "Quantity": [],
                            "Price": [],
                            "Amount": [],
                            "Delivery": []
                        }

                        for w in line_words:
                            x = w['x0']
                            txt = w['text']
                            # Map text to our known columns based on pos
                            if x < 100: header_parts["Item"].append(txt)
                            elif 100 <= x < 260: header_parts["Description"].append(txt)
                            elif 260 <= x < 330: header_parts["Quantity"].append(txt) # Slightly wider range for header text
                            elif 330 <= x < 420: header_parts["Price"].append(txt) # Widened range to catch "Price" at x=355
                            elif 440 <= x < 490: header_parts["Amount"].append(txt)
                            elif x > 490: header_parts["Delivery"].append(txt)
                        
                        # Join parts and update detected_headers
                        for k, parts in header_parts.items():
                            if parts:
                                detected_headers[k] = " ".join(parts)

                        headers_found = True
                        print(f"Detected headers: {detected_headers}")
                        break

            for key in sorted_line_keys:
                line_words = lines[key]
                line_words.sort(key=lambda x: x['x0'])
                
                if not line_words: continue
                
                # Check if first word is a long digit string (Item No)
                # Relaxed condition: Item numbers can contain letters (e.g., 001070252018P02)
                first = line_words[0]
                if first['x0'] < 50 and len(first['text']) >= 10:
                    # Likely a data row
                    # 000461200000102 (35) | 1461.200-BL (107) | ESCUADRA (158) | FIJA (196) | 504,00 (284) | UN (317) | 0,818/UN (384) | 412,27 (465) | 29/12/2025 (502)
                    
                    item_no = first['text']
                    
                    # Columns based on X coordinates from inspection:
                    # ItemNo: < 50
                    # Description/Ref: 107 - ~270
                    # Quantity: ~284 (aligned right usually, but start around 270)
                    # Unit: ~317
                    # Price: ~384
                    # Amount: ~465
                    # ETD: ~502
                    
                    # Let's segregate words by x position
                    desc_words = []
                    qty_word = ""
                    price_word = ""
                    amount_word = ""
                    etd_word = ""
                    
                    for w in line_words[1:]:
                        x = w['x0']
                        text = w['text']
                        
                        if 100 <= x < 260:
                            desc_words.append(text)
                        elif 260 <= x < 310:
                            # Quantity often has formatting 504,00
                            # Sometimes UN is here if aligned differently, but usually UN is > 310
                            if any(c.isdigit() for c in text):
                                qty_word = text
                        elif 360 <= x < 420:
                            # Price often 0,818/UN
                            price_word = text
                        elif 440 <= x < 490:
                            amount_word = text
                        elif x > 490:
                            etd_word = text
                            
                    description = " ".join(desc_words)
                    
                    # Clean up Price (remove /UN)
                    if "/" in price_word:
                        price_word = price_word.split("/")[0]
                        
                    row_data = {
                        detected_headers.get("Item", "Item"): clean_text(item_no),
                        detected_headers.get("Description", "Description"): clean_text(description),
                        # Keep original detected headers if present, else fallback
                        detected_headers.get("Quantity", "Quantity"): clean_text(qty_word),
                        detected_headers.get("Price", "Price"): clean_text(price_word),
                        detected_headers.get("Amount", "Amount"): clean_text(amount_word),
                        detected_headers.get("Delivery", "Delivery"): clean_text(etd_word)
                    }
                    data_rows.append(row_data)

    return data_rows, detected_headers

def process_file(input_path, output_path=None):
    if not output_path:
        # Save to output/Globe directory by default
        base_name = os.path.basename(input_path).replace(".pdf", ".csv")
        output_dir = os.path.join("output", "Globe")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_path = os.path.join(output_dir, base_name)
        
    print(f"Processing Globe file: {input_path}")
    try:
        data, headers_map = extract_globe_data(input_path)
        if data:
            df = pd.DataFrame(data)
            
            # Only rename columns internally if we failed to detect anything meaningful, otherwise keep them
            # But wait, the GUI/Merge logic needs to know the column names.
            # If we keep "Cantidad", the user must assume "Cantidad" in the GUI. THIS IS WHAT THE USER ASKED FOR.
            
            # We enforce the "Item" column to be "Item" for the merge logic to work automatically?
            # actually merge_to_excel.py has heuristic for "Item" detection.
            # But the user specifically asked "can we keep that language as well?".
            
            # So we will NOT rename to English hardcodes if we detected something.
            # But we still want to ensure we have valid CSV.
            
            df.to_csv(output_path, index=False)
            print(f"Saved {output_path}")
            return True
        else:
            print("No data extracted.")
            return False
    except Exception as e:
        print(f"Error: {e}")
        raise e

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        # Fallback for manual running without args
        source_dir = "source/Globe"
        output_dir = "output/Globe"
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
        
        for pdf_file in pdf_files:
            try:
                process_file(pdf_file)
            except Exception as e:
                print(f"Error processing {pdf_file}: {e}")
