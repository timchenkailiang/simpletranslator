
import re

def _infer_regex_type(text, is_multi_token):
    # Remove common punctuation and Spaces for type checking
    clean = text.replace(" ", "").replace(".", "").replace(",", "").replace("-", "")
    # Remove unicode non-breaking hyphens or other common noise if found
    clean = clean.replace("\xad", "") 
    
    print(f"Text: '{text}', Clean: '{clean}', IsDigit: {clean.isdigit()}")

    if clean.isdigit():
            if is_multi_token:
                return r"[\d,.\-\xad\s]+"
            return r"[\d,.\-\xad]+"
    
    if is_multi_token:
            return r".+?"
            
    if " " in text.strip():
            return r".+?"
            
    return r"\S+"

print("Testing Itemno '11011':")
print(_infer_regex_type("11011", False))

print("Testing Master '2.240':")
print(_infer_regex_type("2.240", False))

print("Testing Header 'Itemno.':")
print(_infer_regex_type("Itemno.", False))

print("Testing Noise 'C:':")
print(_infer_regex_type("C:", False))
