import pdfplumber
import pandas as pd
import re
import os
import glob
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
    
    with pdfplumber.open(pdf_path) as pdf:
        # Loop through pages since orders might span multiple
        for page in pdf.pages:
            words = page.extract_words()
            
            # Identify rows by looking for the long numeric Item number at the start ~ x35
            # e.g. 000461200000102
            
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
            
            for key in sorted_line_keys:
                line_words = lines[key]
                line_words.sort(key=lambda x: x['x0'])
                
                if not line_words: continue
                
                # Check if first word is a long digit string (Item No)
                first = line_words[0]
                if first['x0'] < 50 and len(first['text']) >= 12 and first['text'].isdigit():
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
                        "Itemno": clean_text(item_no),
                        "Description": clean_text(description),
                        "Master": "", 
                        "Inner": "",  
                        "Quantity": clean_text(qty_word),
                        "Unit price": clean_text(price_word),
                        "Amount": clean_text(amount_word),
                        "ETD": clean_text(etd_word)
                    }
                    data_rows.append(row_data)

    return data_rows

def main():
    source_dir = "source/Globe"
    output_dir = "output/Globe"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
    
    for pdf_file in pdf_files:
        try:
            filename = os.path.basename(pdf_file).replace(".pdf", ".csv")
            output_path = os.path.join(output_dir, filename)
            
            data = extract_globe_data(pdf_file)
            
            if data:
                df = pd.DataFrame(data)

                # Headers found in Globe inspection:
                # Artículo, Denominación, Cantidad, Precio, Importe, Entrega
                
                # Map extracted keys to English names
                # Itemno -> Item
                # Description -> Description
                # Quantity -> Quantity
                # Unit price -> Price
                # Amount -> Amount
                # ETD -> Delivery
                
                df = df.rename(columns={
                    "Itemno": "Item",
                    "Description": "Description",
                    "Quantity": "Quantity",
                    "Unit price": "Price",
                    "Amount": "Amount",
                    "ETD": "Delivery"
                })
                
                cols = ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"]
                
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
