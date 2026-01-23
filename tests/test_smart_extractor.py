import unittest
import os
import pandas as pd
from smart_extractor import SmartExtractor

class TestSmartExtractor(unittest.TestCase):
    def setUp(self):
        self.pdf_path = "/Users/tim/Documents/dad/simpletranslator/source/PO 35306 - Jeffco.pdf"
        self.output_csv_populated = "/Users/tim/Documents/dad/simpletranslator/output/test_jeffco_populated.csv"
        self.output_csv_missing = "/Users/tim/Documents/dad/simpletranslator/output/test_jeffco_missing.csv"

        # Define expected data derived from the provided CSV snippet
        # We enforce strict correctness (e.g. date should be in 'Ønsket lev.', not 'Pris USD')
        self.jeffco_expected_rows = [
            {"Antal": "3600", "Lev. part. Nr.": "", "Vort part Nr.": "600900237", "Ønsket lev.": "1-12-25"},
            {"Antal": "800",  "Lev. part. Nr.": "", "Vort part Nr.": "605100237", "Ønsket lev.": "1-12-25"},
            {"Antal": "1000", "Lev. part. Nr.": "", "Vort part Nr.": "680300437", "Ønsket lev.": "1-12-25"},
            {"Antal": "1500", "Lev. part. Nr.": "", "Vort part Nr.": "680500437", "Ønsket lev.": "1-12-25"},
            {"Antal": "1440", "Lev. part. Nr.": "", "Vort part Nr.": "681400437", "Ønsket lev.": "1-12-25"},
            {"Antal": "6720", "Lev. part. Nr.": "661001", "Vort part Nr.": "661001", "Ønsket lev.": "1-12-25"}, # The populated row
            {"Antal": "2400", "Lev. part. Nr.": "", "Vort part Nr.": "600100107", "Ønsket lev.": "1-12-25"},
            {"Antal": "960",  "Lev. part. Nr.": "", "Vort part Nr.": "681300427", "Ønsket lev.": "1-12-25"},
            {"Antal": "2040", "Lev. part. Nr.": "", "Vort part Nr.": "682100437", "Ønsket lev.": "1-12-25"},
            {"Antal": "3600", "Lev. part. Nr.": "", "Vort part Nr.": "601100237", "Ønsket lev.": "1-12-25"},
        ]

    def verify_jeffco_results(self, csv_path):
        """Helper to verify the content of the extracted CSV against expected rows."""
        self.assertTrue(os.path.exists(csv_path))
        df = pd.read_csv(csv_path, dtype=str)

        for exp in self.jeffco_expected_rows:
            # Find row by Antal and Vort to be unique enough
            matches = df[
                (df['Antal'].str.contains(exp['Antal'], na=False)) & 
                (df['Vort part Nr.'].str.contains(exp['Vort part Nr.'], na=False))
            ]
            
            self.assertFalse(matches.empty, f"Row not found: {exp}")
            row = matches.iloc[0]
            
            # Assert Column Values
            # Lev. part. Nr.
            if exp["Lev. part. Nr."]:
                self.assertIn(exp["Lev. part. Nr."], str(row['Lev. part. Nr.']), f"Mismatch Lev for {exp['Antal']}")
            else:
                val = str(row['Lev. part. Nr.']).strip()
                is_empty = (val == "nan" or val == "" or val == "None")
                self.assertTrue(is_empty, f"Expected empty Lev for {exp['Antal']}, got {val}")
                
            # Ønsket lev. (Date)
            self.assertIn(exp["Ønsket lev."], str(row['Ønsket lev.']), f"Mismatch Date for {exp['Antal']}. Check if it shifted to Pris USD?")

            # Strict Validation for Antal
            vort_val = str(row['Vort part Nr.']).strip()
            antal_val = str(row['Antal']).strip()
            for part in vort_val.split():
                 if len(part) > 4: # heuristics: significant chunks only
                    self.assertNotIn(part, antal_val, f"Merge detected! Antal '{antal_val}' swallowed Vort part '{part}'")
    
    def tearDown(self):
        # Optional: clean up generated CSVs
        pass

    def test_jeffco_populated_example(self):
        """
        Scenario 1: Full example row provided.
        Expect precise column extraction based on exact matches.
        """
        config = [{
            "pdf_path": self.pdf_path,
            "output_csv_path": self.output_csv_populated,
            "start_anchor": "Antal Lev. part. Nr. Vort part Nr. Ønsket lev. Pris USD",
            "columns": ["Antal", "Lev. part. Nr.", "Vort part Nr.", "Ønsket lev.", "Pris USD"],
            "end_anchor": "FORTSÆTTES",
            "example_row": {
                "Antal": "6720",
                "Lev. part. Nr.": "661001",
                "Vort part Nr.": "661001",
                "Ønsket lev.": "1-12-25"
            }
        }]
        
        extractor = SmartExtractor(config_data=config)
        extractor.extract_all()
        
        # Use the helper to verify ALL rows, not just the example one
        self.verify_jeffco_results(self.output_csv_populated)
        
        # Keep specific assertion for the example row logic if you want double-check
        # but verify_jeffco_results covers it too.

    def test_jeffco_imperfect_config_inference(self):
        """
        Scenario 2: The user provides an IMPERFECT config where the example row 
        is a row that NATURALLY has a missing column (Antal=3600, no Lev. part. Nr.).
        
        The extractor must infer the layout and correctly extract ALL rows.
        """
        config = [{
            "pdf_path": self.pdf_path,
            "output_csv_path": self.output_csv_missing,
            "start_anchor": "Antal Lev. part. Nr. Vort part Nr. Ønsket lev. Pris USD",
            "columns": ["Antal", "Lev. part. Nr.", "Vort part Nr.", "Ønsket lev.", "Pris USD"],
            "end_anchor": "FORTSÆTTES",
            "example_row": {
                "Antal": "3600",
                "Vort part Nr.": "600900237",
                "Ønsket lev.": "1-12-25"
            }
        }]
        
        extractor = SmartExtractor(config_data=config)
        extractor.extract_all()
        
        # Use the helper to verify ALL rows
        self.verify_jeffco_results(self.output_csv_missing)

    def test_invalid_example_row_raises_error(self):
        """
        Scenario 3: The user provides an example row that DOES NOT EXIST in the PDF.
        Expect a ValueError to be raised.
        """
        config = [{
            "pdf_path": self.pdf_path,
            "output_csv_path": "output/should_fail.csv",
            "start_anchor": "Antal Lev. part. Nr. Vort part Nr. Ønsket lev. Pris USD",
            "columns": ["Antal", "Lev. part. Nr.", "Vort part Nr.", "Ønsket lev.", "Pris USD"],
            "end_anchor": "FORTSÆTTES",
            "example_row": {
                "Antal": "99999", 
                "Vort part Nr.": "NON_EXISTENT"
            }
        }]
        
        extractor = SmartExtractor(config_data=config)
        
        with self.assertRaises(ValueError) as cm:
            extractor.process_job(config[0])
            
        self.assertIn("Could not learn layout", str(cm.exception))

    def test_partial_match_behavior(self):
        """
        Scenario 4: User provides an example row with ONE wrong value (simulating a typo), 
        but other values match.
        NEW BEHAVIOR: The system should REJECT valid partial matches and raise an error.
        """
        # Delete output if exists
        output_csv = "/Users/tim/Documents/dad/simpletranslator/output/test_partial.csv"
        if os.path.exists(output_csv):
            os.remove(output_csv)

        config = [{
            "pdf_path": self.pdf_path,
            "output_csv_path": output_csv,
            "start_anchor": "Antal Lev. part. Nr. Vort part Nr. Ønsket lev. Pris USD",
            "columns": ["Antal", "Lev. part. Nr.", "Vort part Nr.", "Ønsket lev.", "Pris USD"],
            "end_anchor": "FORTSÆTTES",
            "example_row": {
                "Antal": "99999", # WRONG VALUE
                "Lev. part. Nr.": "661001",
                "Vort part Nr.": "661001",
                "Ønsket lev.": "1-12-25"
            }
        }]
        
        extractor = SmartExtractor(config_data=config)
        
        # This should now FAIL (raise ValueError) instead of creating a file
        with self.assertRaises(ValueError) as cm:
            extractor.process_job(config[0])
            
        self.assertIn("Could not learn layout", str(cm.exception))
        self.assertFalse(os.path.exists(output_csv), "File should NOT be created for partial match")

if __name__ == '__main__':
    unittest.main()
