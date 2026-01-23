import pdfplumber

with pdfplumber.open("/Users/tim/Documents/dad/simpletranslator/source/PO 35306 - Jeffco.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        for line in text.split('\n'):
            if "3600" in line:
                print(f"Line found: '{line}'")
