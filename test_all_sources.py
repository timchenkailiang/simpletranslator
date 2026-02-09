import os
import glob
import pandas as pd
import importlib.util
import sys

# Define known profiles to test
PROFILES = {
    "Globe": {
        "folder": "source/Globe",
        "converter": "convert_globe.py",
        "required_cols": ["Item", "Price", "Quantity"]
    },
    "Jeffco": {
        "folder": "source/Jeffco",
        "converter": "convert_jeffco.py",
        "required_cols": ["Item", "PartNo", "Quantity"] # Jeffco seems to use Item or PartNo
    },
    "Series_16": {
        "folder": "source/Series_16",
        "converter": "convert_pdf.py", # Assuming generic convert_pdf handles Series 16 based on "11082" regex logic seen in convert_pdf
        "required_cols": ["Itemno", "Quantity", "Unit price"]
    }
}

def load_converter(script_path):
    spec = importlib.util.spec_from_file_location("dynamic_converter", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dynamic_converter"] = module
    spec.loader.exec_module(module)
    return module

def test_all_sources():
    print("=== STARTING COMPREHENSIVE SOURCE TEST ===")
    
    for name, config in PROFILES.items():
        print(f"\n\nTesting Group: {name}")
        folder = config["folder"]
        converter_script = config["converter"]
        required_cols = config["required_cols"]
        
        if not os.path.exists(folder):
            print(f"Skipping {name}: Folder {folder} not found.")
            continue
            
        pdf_files = glob.glob(os.path.join(folder, "*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {folder}")
            continue
            
        print(f"Found {len(pdf_files)} PDFs using converter {converter_script}")
        
        # Load the converter module
        try:
            module = load_converter(converter_script)
        except Exception as e:
            print(f"Failed to load converter {converter_script}: {e}")
            continue

        for pdf_path in pdf_files:
            print(f"-- Processing {os.path.basename(pdf_path)} --")
            output_csv = pdf_path.replace(".pdf", "_TEST.csv")
            try:
                # Run the process_file function
                if hasattr(module, 'process_file'):
                    success = module.process_file(pdf_path, output_csv)
                else:
                    print("Error: Converter has no process_file method")
                    success = False
                
                if success and os.path.exists(output_csv):
                    # Validate content
                    df = pd.read_csv(output_csv)
                    cols = list(df.columns)
                    print(f"   Columns: {cols}")
                    
                    missing = [c for c in required_cols if not any(c.lower() in col.lower() for col in cols)]
                    
                    if missing:
                        print(f"   WARNING: Potential missing/renamed columns: {missing}")
                    else:
                        print("   Input columns: OK")
                        
                    print(f"   Rows: {len(df)}")
                    
                    # Cleanup test file
                    os.remove(output_csv)
                else:
                    print("   Conversion FAILED (No CSV produced)")
            except Exception as e:
                print(f"   CRASHED: {e}")

if __name__ == "__main__":
    test_all_sources()
