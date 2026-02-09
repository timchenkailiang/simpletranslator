import os
import glob
import pandas as pd
from convert_globe import extract_globe_data

def test_globe_files():
    source_dir = "source/Globe"
    pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
    
    print(f"Testing {len(pdf_files)} files in {source_dir}...\n")
    
    results = []

    for pdf_path in pdf_files:
        print(f"--- Checking {os.path.basename(pdf_path)} ---")
        try:
            data, headers = extract_globe_data(pdf_path)
            if not data:
                print("FAILED: No data extracted.")
                results.append((pdf_path, "No Data", []))
                continue
                
            df = pd.DataFrame(data)
            cols = list(df.columns)
            print(f"Columns Found: {cols}")
            
            # Check for key columns
            has_item = "Item" in cols
            has_qty = any("uantity" in c or "antidad" in c for c in cols)
            
            # Check for Price specifically
            price_col = None
            for c in cols:
                if "Price" in c or "USD" in c or "Precio" in c:
                    price_col = c
                    break
            
            print(f"Item Column: {'OK' if has_item else 'MISSING'}")
            print(f"Price Column: {price_col if price_col else 'MISSING'}")
            print(f"Rows Extracted: {len(df)}")
            
            # Sample check
            if len(df) > 0 and price_col:
                sample_price = df.iloc[0][price_col]
                print(f"Sample Price: {sample_price}")
            
            results.append((pdf_path, "Success", cols))

        except Exception as e:
            print(f"CRASHED: {e}")
            results.append((pdf_path, f"Error: {e}", []))
        print("\n")

if __name__ == "__main__":
    test_globe_files()
