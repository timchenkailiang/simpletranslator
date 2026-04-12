"""Globe PO converter — handles both Spanish and English headers."""

import logging
import pdfplumber
import pandas as pd
import re
import os
import glob
import sys
from datetime import datetime
from utils import normalize_numeric_columns

logger = logging.getLogger(__name__)

# ── Converter metadata ────────────────────────────────────────────────
FORMAT_NAME = "Globe"
COLUMNS = ["Item", "Description", "Quantity", "Price", "Amount", "Delivery"]
VALIDATION_RULES = {"qty": "Quantity", "price": "Price", "amount": "Amount"}


# ── Helpers ───────────────────────────────────────────────────────────

def clean_text(text):
    if not isinstance(text, str):
        return text
    text = text.replace('\xad', '').replace('\u00ad', '').replace('\u2011', '-')
    return text.strip()


# ── Core extraction ───────────────────────────────────────────────────

def extract_globe_data(pdf_path):
    logger.info("Extracting Globe data from %s", os.path.basename(pdf_path))
    data_rows = []

    detected_headers = {
        "Item": "Item",
        "Description": "Description",
        "Quantity": "Quantity",
        "Price": "Price",
        "Amount": "Amount",
        "Delivery": "Delivery"
    }
    headers_found = False

    with pdfplumber.open(pdf_path) as pdf:
        logger.info("PDF has %d page(s)", len(pdf.pages))
        for page in pdf.pages:
            words = page.extract_words()

            # Group by top coordinate
            lines = {}
            for w in words:
                top_key = int(w['top'])
                found_key = None
                for k in lines:
                    if abs(k - top_key) < 3:
                        found_key = k
                        break
                if found_key:
                    lines[found_key].append(w)
                else:
                    lines[top_key] = [w]

            sorted_line_keys = sorted(lines.keys())

            # Attempt header detection on first page
            if not headers_found:
                for key in sorted_line_keys:
                    line_words = lines[key]
                    line_words.sort(key=lambda x: x['x0'])
                    text_line = " ".join([w['text'] for w in line_words]).lower()

                    if ("quantity" in text_line or "cantidad" in text_line or
                            "description" in text_line or "descripcion" in text_line):
                        header_parts = {
                            "Item": [], "Description": [], "Quantity": [],
                            "Price": [], "Amount": [], "Delivery": []
                        }
                        for w in line_words:
                            x = w['x0']
                            txt = w['text']
                            if x < 100:
                                header_parts["Item"].append(txt)
                            elif 100 <= x < 260:
                                header_parts["Description"].append(txt)
                            elif 260 <= x < 330:
                                header_parts["Quantity"].append(txt)
                            elif 330 <= x < 420:
                                header_parts["Price"].append(txt)
                            elif 440 <= x < 490:
                                header_parts["Amount"].append(txt)
                            elif x > 490:
                                header_parts["Delivery"].append(txt)

                        for k, parts in header_parts.items():
                            if parts:
                                detected_headers[k] = " ".join(parts)

                        headers_found = True
                        logger.debug("Detected headers: %s", detected_headers)
                        break

            for key in sorted_line_keys:
                line_words = lines[key]
                line_words.sort(key=lambda x: x['x0'])
                if not line_words:
                    continue

                first = line_words[0]
                if first['x0'] < 50 and len(first['text']) >= 10:
                    item_no = first['text']

                    desc_words = []
                    qty_word = ""
                    price_word = ""
                    amount_word = ""
                    etd_word = ""

                    for w in line_words[1:]:
                        x = w['x0']
                        text = w['text']

                        if 100 <= x < 260:
                            desc_words.append(text)
                        elif 260 <= x < 310:
                            if any(c.isdigit() for c in text):
                                qty_word = text
                        elif 360 <= x < 420:
                            price_word = text
                        elif 440 <= x < 490:
                            amount_word = text
                        elif x > 490:
                            etd_word = text

                    description = " ".join(desc_words)

                    if "/" in price_word:
                        price_word = price_word.split("/")[0]

                    row_data = {
                        detected_headers.get("Item", "Item"): clean_text(item_no),
                        detected_headers.get("Description", "Description"): clean_text(description),
                        detected_headers.get("Quantity", "Quantity"): clean_text(qty_word),
                        detected_headers.get("Price", "Price"): clean_text(price_word),
                        detected_headers.get("Amount", "Amount"): clean_text(amount_word),
                        detected_headers.get("Delivery", "Delivery"): clean_text(etd_word)
                    }
                    data_rows.append(row_data)

    logger.info("Extracted %d data rows from %s", len(data_rows),
                os.path.basename(pdf_path))
    return data_rows, detected_headers


# ── Standard interface ────────────────────────────────────────────────

def process_file(input_path, output_path=None):
    if not output_path:
        base_name = os.path.basename(input_path).replace(".pdf", ".csv")
        output_dir = os.path.join("output", "Globe")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, base_name)

    logger.info("Processing Globe file: %s → %s", input_path, output_path)
    try:
        data, headers_map = extract_globe_data(input_path)
        if data:
            df = pd.DataFrame(data)
            num_cols = [
                headers_map.get("Quantity", "Quantity"),
                headers_map.get("Price", "Price"),
                headers_map.get("Amount", "Amount"),
            ]
            normalize_numeric_columns(df, num_cols)
            logger.debug("Normalised numeric columns: %s", num_cols)
            df.to_csv(output_path, index=False)
            logger.info("Globe conversion complete — %d rows saved to %s",
                        len(df), output_path)
            return True
        else:
            logger.warning("Globe extraction returned 0 rows.")
            return False
    except Exception as e:
        logger.error("Globe conversion failed: %s", e)
        raise e


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(sys.argv) > 1:
        process_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        source_dir = "source/Globe"
        output_dir = "output/Globe"
        os.makedirs(output_dir, exist_ok=True)

        pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
        for pdf_file in pdf_files:
            try:
                process_file(pdf_file)
            except Exception as e:
                logger.error("Error processing %s: %s", pdf_file, e)
