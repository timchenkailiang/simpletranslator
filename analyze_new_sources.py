import pdfplumber
import os

def analyze_pdf(path):
    print(f"--- Analyzing {path} ---")
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > 0:
                page = pdf.pages[0]
                text = page.extract_text()
                print(text)
            else:
                print("Empty PDF")
    except Exception as e:
        print(f"Error: {e}")
    print("\n" + "="*50 + "\n")

globe_file = "source/Globe/51075 Globe 124533.pdf"
jeffco_file = "source/Jeffco/35369.pdf"

if os.path.exists(globe_file):
    analyze_pdf(globe_file)
else:
    print(f"File not found: {globe_file}")

if os.path.exists(jeffco_file):
    analyze_pdf(jeffco_file)
else:
    print(f"File not found: {jeffco_file}")
