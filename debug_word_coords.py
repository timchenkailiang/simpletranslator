import pdfplumber

pdf_path = "source/PO 35306 - Jeffco.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    words = page.extract_words()
    # Find words near 6720
    target_words = []
    for w in words:
        if "6720" in w['text'] or "661001" in w['text']:
            target_words.append(w)
            
    print("Found words:")
    for w in target_words:
        print(f"Text: '{w['text']}' | x0: {w['x0']:.2f} | x1: {w['x1']:.2f} | Center: {(w['x0']+w['x1'])/2:.2f}")
