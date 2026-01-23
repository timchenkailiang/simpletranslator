import pdfplumber

pdf_path = "source/PO 35306 - Jeffco.pdf"

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[0]
    words = page.extract_words()
    
    # Filter words around the y-position of the example row (Antal=6720) or just dump them all nicely
    print("--- Words Layout ---")
    # Sort by vertical position
    words.sort(key=lambda w: (w['top'], w['x0']))
    
    # Range of interesting Y
    # Looking for Y where text is "6720"
    target_top = None
    for w in words:
        if "6720" in w['text']:
            target_top = w['top']
            break
            
    if target_top:
        print(f"Focusing on line at top={target_top:.2f}")
        line_words = [w for w in words if abs(w['top'] - target_top) < 5]
        line_words.sort(key=lambda w: w['x0'])
        for w in line_words:
             print(f"'{w['text']}': x0={w['x0']:.2f} x1={w['x1']:.2f}")
    
    # Also look at a 'wide' row like the first one "3600"
    print("\n--- First Data Row (3600) ---")
    first_top = None
    for w in words:
        if "3600" in w['text']:
            first_top = w['top']
            break # Just take the first one found
            
    if first_top:
        line_words = [w for w in words if abs(w['top'] - first_top) < 5]
        line_words.sort(key=lambda w: w['x0'])
        for w in line_words:
             print(f"'{w['text']}': x0={w['x0']:.2f} x1={w['x1']:.2f}")
