import pdfplumber
import pandas as pd
import re
import os
import json # Import json for loading configuration

def extract_pdf_to_csv(pdf_path, output_csv_path, start_marker, columns, end_marker=None):
    """
    Extracts a table from a PDF file based on a start marker and specific columns.
    
    Args:
        pdf_path (str): Path to the input PDF file.
        output_csv_path (str): Path to output the CSV file.
        start_marker (str): The text string indicating where the table or data starts.
        columns (list): List of column names to extract.
        end_marker (str, optional): Text string indicating where data ends.
    """
    
    data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        # Iterate through pages to find the start marker and extract data
        start_processing = False
        
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
                
            lines = text.split('\n')
            
            for line in lines:
                # Check for start marker to begin processing
                if start_marker in line:
                    start_processing = True
                    continue # Skip the marker line itself
                
                # Check for end marker to stop processing (if provided)
                if end_marker and end_marker in line:
                    start_processing = False
                    break
                
                if start_processing:
                    # Basic extraction logic - this will likely need refinement based on
                    # the specific layout of the user's PDF.
                    
                    parts = line.split()
                    
                    # Skip if it looks like a header line repeated
                    if parts[0] in [c.split()[0] for c in columns]:
                        continue
                    
                    row_data = {}
                    
                    # Strategy: Use pdfplumber's table extraction if possible, but since we are iterating text lines:
                    # We will try a flexible parsing strategy.
                    
                    # Logic for PO16665 (Variable description length)
                    start_col_name = columns[0]
                    if start_col_name == "Itemno.":
                        required_tail_len = 6 # Master, Inner, Qty, Unit, Amount, ETD
                        if len(parts) >= 1 + required_tail_len:
                            # Heuristic: Check if the first part is likely an Item No (numeric)
                            # This filters out garbage lines like "C: 86 ..."
                            if not parts[0].replace('.','').isdigit():
                                continue

                            row_data["Itemno."] = parts[0]
                            row_data["ETD"] = parts[-1]
                            row_data["Amount"] = parts[-2]
                            row_data["Unit price"] = parts[-3]
                            row_data["Quantity"] = parts[-4]
                            row_data["Inner"] = parts[-5]
                            row_data["Master"] = parts[-6]
                            
                            # Port matches nothing in this line example, maybe ignore or empty
                            row_data["Port"] = "" 
                            
                            # Description is everything else
                            desc_parts = parts[1:-required_tail_len]
                            row_data["Description"] = " ".join(desc_parts)
                            
                            data.append(row_data)
                            continue

                    # Logic for PO 35306
                    # Cols: ["Antal", "Lev. part. Nr.", "Vort part Nr.", "Ønsket lev.", "Pris USD"]
                    # Line: 3600 STK 60090 0237 1-12-25
                    # Parts: ['3600', 'STK', '60090', '0237', '1-12-25']
                    
                    if start_col_name == "Antal" and len(parts) >= 5:
                        # Improved logic based on vertical alignment and user requirements:
                        # 1. "Lev. part. Nr." is usually empty, EXCEPT for lines like "6720 STK 661001..." where 661001 is the Lev part #.
                        #    In the sample "3600 STK 60090 ...", "60090" is actually the start of "Vort part Nr." which consists of two numbers "60090 0237".
                        # 2. "Vort part Nr." should combine the two numbers (e.g. "60090 0237").
                        
                        # Let's map parts by index first:
                        # 0: Antal (3600)
                        # 1: Unit (STK) - ignore
                        
                        # Part 2: "60090" or "661001"
                        # Part 3: "0237" or "66100"
                        # Part 4: "1" or "1-12-25"
                        
                        # If we look at the coordinates (heuristic logic here without x-coords usage for simplicity first):
                        # The user says:
                        # - "Lev. part. Nr." should be empty EXCEPT for 6720 line.
                        # - "Vort part Nr." should be "60090 0237".
                        
                        # Validating the "6720" line:
                        # "6720 STK 661001 66100 1 1-12-25" -> 6 parts?
                        # Terminal output showed: 
                        # "6720 STK 661001 66100 1 1-12-25"
                        # Wait, earlier terminal output: "6720 STK 661001 66100 1 1-12-25" 
                        # Let's re-examine that specific line in parts.
                        
                        row_data["Antal"] = parts[0]
                        row_data["Pris USD"] = "" # Default empty as per previous obs
                        row_data["Ønsket lev."] = parts[-1] # Date seems always last
                        
                        # Handle the middle parts
                        # We have parts[2] to parts[-1] remaining.
                        middle_parts = parts[2:-1]
                        
                        # Case 1: Standard line "3600 STK 60090 0237 1-12-25"
                        # middle_parts = ["60090", "0237"]
                        # These should be combined into "Vort part Nr."
                        # "Lev. part. Nr." should be empty.
                        
                        # Case 2: Special line "6720 STK 661001 66100 1 1-12-25"
                        # middle_parts = ["661001", "66100", "1"]
                        # "661001" aligns with "Lev. part. Nr." header visually? 
                        # From user request: "6720 stk one" should have Lev. part. Nr populated.
                        # So "661001" -> Lev. part. Nr.
                        # "66100 1" -> Vort part Nr.
                        
                        # How to distinguish?
                        # Check count of middle parts?
                        # If 2 parts: likely "Vort part Nr." split.
                        # If 3 parts: likely "Lev. part. Nr." + "Vort part Nr." split.
                        
                        if len(middle_parts) == 2:
                            row_data["Lev. part. Nr."] = ""
                            row_data["Vort part Nr."] = f"{middle_parts[0]}{middle_parts[1]}"
                        elif len(middle_parts) == 3:
                            row_data["Lev. part. Nr."] = middle_parts[0]
                            row_data["Vort part Nr."] = f"{middle_parts[1]}{middle_parts[2]}"
                        else:
                            # Fallback if unsure
                            row_data["Lev. part. Nr."] = ""
                            row_data["Vort part Nr."] = "".join(middle_parts)

                        data.append(row_data)
                        continue

                    # Fallback to naive
                    if len(parts) >= len(columns):
                         for i, col in enumerate(columns):
                             if i < len(parts):
                                 row_data[col] = parts[i]
                         data.append(row_data)

    if data:
        df = pd.DataFrame(data)
        # Ensure only requested columns are in output
        final_df = df[columns] if set(columns).issubset(df.columns) else df
        final_df.to_csv(output_csv_path, index=False)
        print(f"Successfully created {output_csv_path}")
    else:
        print(f"No data found for {pdf_path} with marker '{start_marker}'")

def load_config(config_path="config.json"):
    """
    Loads the configuration for file processing from a JSON file.
    
    Args:
        config_path (str): Path to the configuration JSON file.
        
    Returns:
        list: List of file processing configurations.
    """
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file {config_path} not found. Please ensure it exists.")
        return []

if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)
    
    files_to_process = load_config()
    
    if not files_to_process:
        print("No files configured to process.")
    
    for file_info in files_to_process:
        extract_pdf_to_csv(
            file_info["pdf_path"], 
            file_info["output_csv_path"], 
            file_info["start_anchor"], 
            file_info["columns"],
            file_info.get("end_anchor")
        )
