import pdfplumber

pdf_path = "source/PO16665.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    words = page.extract_words()
    # Print lines that might contain "11011" (Itemno)
    lines = []
    # simple grouping
    words.sort(key=lambda x: x['top'])
    for w in words:
        print(f"{w['text']} ", end="")
        if w['text'] == "11011":
            print("\nFOUND ITEMNO\n")
