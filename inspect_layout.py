import pdfplumber

def inspect_layout(pdf_path):
    print(f"Inspecting layout for {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            # unique top values for lines
            # Find the words for "11082"
            target_words = [w for w in words if "11082" in w['text']]
            if target_words:
                print(f"Found '11082' on page {page.page_number}")
                for tw in target_words:
                    top = tw['top']
                    bottom = tw['bottom']
                    # Get all words on this approximate line
                    line_words = [w for w in words if abs(w['top'] - top) < 5]
                    # Sort by x
                    line_words.sort(key=lambda x: x['x0'])
                    
                    print(f"Line at top={top}:")
                    print(" ".join([w['text'] for w in line_words]))
                    
                    # Check lines just below it to see if description continues or is mistakenly placed elsewhere
                    print("Lines below:")
                    below_words = [w for w in words if top < w['top'] < bottom + 20] # 20 units below
                    # Group by top to see lines
                    below_lines = {}
                    for bw in below_words:
                        t = round(bw['top'], 1)
                        if t not in below_lines: below_lines[t] = []
                        below_lines[t].append(bw)
                    
                    for t in sorted(below_lines.keys()):
                        l = below_lines[t]
                        l.sort(key=lambda x: x['x0'])
                        print(f"  Top {t}: " + " ".join([w['text'] for w in l]))

def inspect_jeffco(pdf_path):
    print(f"Inspecting layout for {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        
        # Look for the header line
        headers = [w for w in words if w['text'] in ["Quantity", "Price", "USD", "Del.", "date", "Your", "part", "Our", "No."]]
        print("--- HEADERS ---")
        # Sort headers by x0 to visualize order
        headers.sort(key=lambda x: x['x0'])
        for h in headers:
            print(f"Text: {h['text']}, x0: {h['x0']}, top: {h['top']}")
            
        # Look for a sample data row (e.g., matching "STK")
        data_sample = [w for w in words if "STK" in w['text']]
        print("\n--- DATA SAMPLES (STK) ---")
        for d in data_sample[:3]:
            # Get words on the same line
            line_words = [w for w in words if abs(w['top'] - d['top']) < 3]
            line_words.sort(key=lambda x: x['x0'])
            print(f"Row at top {d['top']}: " + " | ".join([f"{w['text']} ({int(w['x0'])})" for w in line_words]))
            
            # Look at the line immediately below (finding description)
            next_line_words = [w for w in words if 8 < (w['top'] - d['top']) < 20]
            next_line_words.sort(key=lambda x: x['x0'])
            if next_line_words:
                print(f"  > Next line: " + " | ".join([f"{w['text']} ({int(w['x0'])})" for w in next_line_words]))

def inspect_globe(pdf_path):
    print(f"Inspecting layout for {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words()
        
        # Look for the header line
        # Globe headers: Item, Denomination, Quantity, Price, (USD), Amount, Deliv. Dt.
        headers = [w for w in words if w['text'] in ["Price", "USD", "(USD)", "Quantity", "Amount", "Deliv.", "Dt."]]
        print("--- HEADERS ---")
        headers.sort(key=lambda x: x['x0'])
        for h in headers:
            print(f"Text: {h['text']}, x0: {h['x0']}, top: {h['top']}")

        print("\n--- ALL WORDS AROUND HEADER ---")
        # Find likely header row
        header_y = 0
        if headers:
            header_y = headers[0]['top']
            
        header_words = [w for w in words if abs(w['top'] - header_y) < 10]
        header_words.sort(key=lambda x: x['x0'])
        for w in header_words:
             print(f"Word: {w['text']}, x0: {w['x0']}, top: {w['top']}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if "Globe" in path:
            inspect_globe(path)
        else:
            inspect_jeffco(path)
    else:
        inspect_jeffco("source/Jeffco/35369.pdf")
