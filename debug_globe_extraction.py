import pdfplumber

pdf_path = "source/Globe/51075 Globe 124533.pdf"

print(f"Opening {pdf_path}...")
with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"--- Page {i+1} ---")
        words = page.extract_words()
        
        # 1. SCAN ALL WORDS RAW
        print("Scanning raw words for target '001070252018P02'...")
        found_raw = False
        for w in words:
            if "001070252018P02" in w['text']:
                print(f"!!! FOUND RAW MATCH !!!")
                print(f"Text: {w['text']}")
                print(f"X0: {w['x0']}, Top: {w['top']}, Bottom: {w['bottom']}")
                found_raw = True
        
        if not found_raw:
            print("Target not found in raw word list for this page.")

        # Group words by line (y-tolerance)
        words.sort(key=lambda w: (w['top'], w['x0']))
        
        lines = []
        if not words:
            continue
            
        current_line = [words[0]]
        for w in words[1:]:
            # If vertical distance is small, same line
            if abs(w['top'] - current_line[-1]['top']) < 3:
                current_line.append(w)
            else:
                lines.append(current_line)
                current_line = [w]
        lines.append(current_line)

        # Print the start of each line to see what we are filtering
        for line_words in lines:
            if not line_words:
                continue
            
            first = line_words[0]
            text = first['text']

            # If this is the line containing our target, print everything about it
            if "001070252018P02" in [w['text'] for w in line_words]:
                print(f"\n****** LINE WITH TARGET ******")
                for w in line_words:
                     print(f"  '{w['text']}' -> X0: {w['x0']:.2f}")
                print("*****************************\n")
            
            # Print EVERY line's starting text to see what is there
            print(f"Line Start: '{text}' | X0: {first['x0']:.2f}")

            # Check specifically for the missing item
            if "001070252018P02" in text:
                print(f"\n[FOUND TARGET] Text: '{text}'")
                print(f"X0: {first['x0']}")
                print(f"Is Digit? {text.isdigit()}")
                print(f"Length: {len(text)}")
                print(f"Full Line: {' '.join([w['text'] for w in line_words])}\n")
            
            # Print potential candidates that failed
            if first['x0'] < 50 and len(text) > 10:
                 print(f"Candidate: '{text}' | Digit: {text.isdigit()} | X0: {first['x0']:.2f}")

