import unittest
import os
import pandas as pd
from smart_extractor import SmartExtractor

class TestJeffcoBug(unittest.TestCase):
    def setUp(self):
        # Use absolute path just in case, or relative from workspace root
        self.pdf_path = os.path.abspath("source/PO 35306 - Jeffco.pdf")
        self.output_csv = os.path.abspath("output/test_jeffco_bug.csv")
        
    def test_antal_lev_merge_bug(self):
        # Configuration that causes the bug
        config = [{
            "pdf_path": self.pdf_path,
            "output_csv_path": self.output_csv,
            "start_anchor": "Antal Lev. part. Nr. Vort part Nr. Ønsket lev. Pris USD",
            "columns": ["Antal", "Lev. part. Nr.", "Vort part Nr.", "Ønsket lev.", "Pris USD"],
            "end_anchor": "FORTSÆTTES",
            "example_row": {
                "Antal": "6720STK",
                # "Lev. part. Nr." is intentionally OMITTED to simulate the bug
                "Vort part Nr.": "661001",
                "Ønsket lev.": "1-12-25"
            }
        }]
        
        extractor = SmartExtractor(config_data=config)
        extractor.extract_all()
        
        self.assertTrue(os.path.exists(self.output_csv))
        df = pd.read_csv(self.output_csv, dtype=str)
        
        # Find the row with 6720
        target_rows = df[df['Antal'].str.contains("6720", na=False)]
        self.assertFalse(target_rows.empty, "Could not find row with 6720")
        
        row = target_rows.iloc[0]
        antal_val = str(row['Antal']).replace(" ", "")
        
        print(f"DEBUG: Extracted Antal: '{antal_val}'")
        print(f"DEBUG: Extracted Lev: '{row['Lev. part. Nr.']}'")

        # The bug: Antal contains the next column value
        self.assertNotIn("661001", antal_val, "Antal column merged with partial Lev. part. Nr.!")
        
        # Also verify Lev. part. Nr. captured the value
        lev_val = str(row['Lev. part. Nr.']).strip()
        # Note: If Antal didn't eat it, it should be in Lev. part. Nr.
        # But since Lev. part. Nr. is missing in config, its "zone" is defined by the gap.
        # If Antal is properly bounded, the gap starts correctly.
        self.assertIn("661001", lev_val, "Lev. part. Nr. failed to capture its data")

if __name__ == '__main__':
    unittest.main()
