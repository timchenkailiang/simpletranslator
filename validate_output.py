import os
import pandas as pd
import glob
import math
import sys

def validate_csvs(target_path):
    # Check if target is a file or directory
    if os.path.isfile(target_path):
        csv_files = [target_path]
        print(f"Validating single file: {target_path}")
    else:
        # Search recursively for csv files in output_dir and its subdirectories
        csv_files = glob.glob(os.path.join(target_path, "**/*.csv"), recursive=True)
        print(f"Found {len(csv_files)} CSV files in {target_path} (recursive)")
    
    for file_path in csv_files:
        print(f"\nValidating {os.path.relpath(file_path, target_path)}...")
        try:
            # Read as string to preserve formatting like "1.120" vs "1.12"
            df = pd.read_csv(file_path, dtype=str)
        except Exception as e:
            print(f"  ERROR: Could not read file. {e}")
            continue
            
        columns = list(df.columns)
        
        # Determine expected columns based on format
        # Heuristic: Check for characteristic columns of each format
        if "Artículo" in columns or "Item" in columns:
             # Globe (English or Spanish headers)
             if "Artículo" in columns:
                 expected_cols = ["Artículo", "Denominación", "Cantidad", "Precio", "Importe", "Entrega"]
             else:
                 expected_cols = ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"]
             format_name = "Globe"
        elif "Our Part No" in columns:
             # Jeffco
             expected_cols = ["Quantity", "Your Part No", "Our Part No", "Price USD", "Del. date", "Description"]
             format_name = "Jeffco"
        else:
             # Default Series 16
             expected_cols = ["Itemno", "Description", "Master", "Inner", "Quantity", "Unit price", "Amount", "ETD"]
             format_name = "Series 16"
             
        # Check column count
        if columns != expected_cols:
            print(f"  WARNING: [{format_name}] Column mismatch. Expected {expected_cols}, got {columns}")
        
        # Check for empty dataframes
        if df.empty:
            print("  WARNING: File is empty (no data rows).")
            continue
            
        print(f"  Rows: {len(df)}")
        
        # --- NEW: Numeric Validation ---
        
        # Define column mappings for validation
        col_map = {}
        if format_name == "Globe":
            col_map = {"qty": "Quantity", "price": "Price", "amount": "Amount"}
        elif format_name == "Jeffco":
            col_map = {"qty": "Quantity", "price": "Price USD", "amount": None} # Jeffco has no amount col in output
        elif format_name == "Series 16":
            col_map = {"qty": "Quantity", "price": "Unit price", "amount": "Amount"}
            
        # 1. Validate Numeric Formats
        numeric_issues = 0
        math_issues = 0
        
        cols_to_check = [c for c in [col_map.get("qty"), col_map.get("price"), col_map.get("amount")] if c]
        
        for col in cols_to_check:
            if col in df.columns:
                for idx, val in df[col].items():
                    parsed = parse_number(val)
                    if parsed is None and val != "" and not pd.isna(val):
                        # It's not empty but failed parsing? Suspicious.
                        print(f"  ISSUE [Numeric]: Row {idx} col '{col}' has invalid number format: '{val}'")
                        numeric_issues += 1

        # 2. Validate Math (Qty * Price = Amount)
        if col_map.get("amount") and col_map.get("amount") in df.columns:
            qty_c = col_map["qty"]
            price_c = col_map["price"]
            amt_c = col_map["amount"]
            
            for idx, row in df.iterrows():
                is_ok, calc, actual = check_math(row, qty_c, price_c, amt_c)
                if not is_ok:
                    print(f"  ISSUE [Math]: Row {idx} {qty_c}({row[qty_c]}) * {price_c}({row[price_c]}) != {amt_c}({row[amt_c]}) [Calc: {calc:.2f}]")
                    math_issues += 1
        
        if numeric_issues == 0 and math_issues == 0:
            print("  Numeric & Logic checks passed.")
            
        # Check for suspicious characters in text columns
        suspicious_chars = {
            '\xad': 'Soft Hyphen',
            '\u00ad': 'Soft Hyphen',
            '\u2011': 'Non-breaking Hyphen',
            '\ufffd': 'Replacement Character'
        }
        
        issues_found = False
        for col in df.columns:
            if df[col].dtype == object:
                for idx, val in df[col].items():
                    if isinstance(val, str):
                        for char, name in suspicious_chars.items():
                            if char in val:
                                print(f"  ISSUE: Found {name} in row {idx}, column '{col}': '{val}'")
                                issues_found = True
        
        if not issues_found:
            print("  No suspicious characters found.")

# Standard interface for the GUI
def validate_file(file_path):
    # Wrapper around the existing logic
    # Since validate_csvs handles a single file path gracefully now, we can just call it
    validate_csvs(file_path)

def parse_number(value_str):
    """
    Parses a string into a float, handling common European/US inconsistencies.
    Assumes ',' as decimal separator if '.' is also present as thousands separator.
    Or if only ',' is present.
    """
    if pd.isna(value_str) or value_str == "":
        return None
    
    if not isinstance(value_str, str):
        return float(value_str)
        
    clean = value_str.strip()
    if not clean:
        return None
        
    # Remove currency symbols or typical noise if any (basic cleaning)
    clean = clean.replace("USD", "").replace("$", "").replace("€", "").strip()
    
    # Heuristic for format:
    # 1. "1.234,56" -> European (remove dots, replace comma with dot)
    # 2. "1,234.56" -> US (remove commas)
    # 3. "1234,56"  -> European (replace comma with dot)
    # 4. "1234.56"  -> Standard
    
    # Check if this looks like European with thousands separator (e.g., 2.000,00)
    # A single dot followed by 3 digits and then a comma is a strong signal for thousands separator
    import re
    if re.search(r'\.\d{3},', clean):
         # e.g. 2.000,00 -> remove dot, swap comma
         clean = clean.replace('.', '').replace(',', '.')
    elif re.search(r',\d{3}\.', clean):
         # e.g. 2,000.00 -> remove comma
         clean = clean.replace(',', '')
    # Special Case: "1.120" with no comma. Is it 1120 or 1.12?
    # Context matters, but without comma suffix, it's ambiguous.
    # However, standard floats don't usually trailing zero like 1.120 unless formatted string.
    # In these PDF extracts, typically:
    # - "800" is int
    # - "1.120" is 1120 (thousands sep)
    # - "5,30" is 5.30 (decimal comma)
    # Heuristic: If it contains ONLY dots, and has 3 digits matching \.\d{3}$ or \.\d{3}\., it might be thousands.
    # But prices like 1.125 (small unit price) exist?
    # Let's verify against known currency format. 
    # Usually Quantity is integer-like or high magnitude.
    # Let's assume: If ',' is absent, and '.' represents thousands if followed by 3 digits at end or before another dot.
    
    elif ',' not in clean and '.' in clean:
         # e.g. "1.120" -> Could be 1.12 or 1120
         # If we strictly assume European format because other rows use comma decimals:
         # Then dot is likely thousands separator.
         parts = clean.split('.')
         # If all parts look like groups of digits...
         if len(parts) > 1 and all(len(p)==3 for p in parts[1:]):
              # It's structured like 1.000.000 or 1.000
              clean = clean.replace('.', '')
         # Otherwise leave it (it might be a standard float like 0.818)
         
    elif ',' in clean and '.' not in clean:
        # 1234,56 format
        clean = clean.replace(',', '.')
        
    try:
        return float(clean)
    except ValueError:
        return None

def check_math(row, qty_col, price_col, amount_col):
    qty = parse_number(row.get(qty_col))
    price = parse_number(row.get(price_col))
    amount = parse_number(row.get(amount_col))
    
    if qty is not None and price is not None and amount is not None:
        calculated = qty * price
        # Allow small tolerance for rounding
        # Is the calculated amount close to the extracted amount?
        diff = abs(calculated - amount)
        # Tolerance: 1.0 (currency unit) or 1%
        if diff > 1.0 and diff > (amount * 0.01):
            return False, calculated, amount
    return True, 0, 0

if __name__ == "__main__":
    target = "output"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    
    validate_csvs(target)
