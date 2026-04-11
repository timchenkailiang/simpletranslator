"""Jeffco PO converter — strict x-coordinate column buckets."""

import logging
import pdfplumber
import pandas as pd
import re
import os
import glob
import sys
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Converter metadata ────────────────────────────────────────────────
FORMAT_NAME = "Jeffco"
COLUMNS = ["Our Part No", "Quantity", "Your Part No", "Price USD", "Del. date", "Description"]
VALIDATION_RULES = {"qty": "Quantity", "price": "Price USD", "amount": None}


# ── Helpers ───────────────────────────────────────────────────────────

def clean_text(text):
    if not isinstance(text, str):
        return text
    text = text.replace('\xad', '').replace('\u00ad', '').replace('\u2011', '-')
    return text.strip()


# ── Core extraction ───────────────────────────────────────────────────

def extract_jeffco_data(pdf_path):
    logger.info("Extracting Jeffco data from %s", os.path.basename(pdf_path))
    data_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()

            words.sort(key=lambda w: (round(w['top']), w['x0']))

            # Group words into lines
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

            for i, key in enumerate(sorted_line_keys):
                line_words = lines[key]
                line_words.sort(key=lambda x: x['x0'])
                line_text = " ".join([w['text'] for w in line_words])

                if "STK" in line_text:
                    parts = line_text.split()

                    if len(parts) >= 4:
                        qty_word = ""
                        your_part_no_parts = []
                        our_part_no_parts = []
                        etd_word = ""
                        price_word = ""

                        filtered_words = [w for w in line_words if w['text'] != "STK"]

                        for w in filtered_words:
                            x = w['x0']
                            text = w['text']

                            if x < 130:
                                if any(c.isdigit() for c in text):
                                    qty_word = text
                            elif 130 <= x < 250:
                                your_part_no_parts.append(text)
                            elif 250 <= x < 370:
                                our_part_no_parts.append(text)
                            elif 370 <= x < 450:
                                etd_word = text
                            elif x >= 450:
                                price_word = text

                        your_part_no = " ".join(your_part_no_parts)
                        our_part_no = " ".join(our_part_no_parts).replace(" ", "")

                        if not price_word:
                            if line_words[-1]['x0'] > 440:
                                last_word = line_words[-1]
                                if (last_word['text'] != etd_word and
                                        last_word['text'] != qty_word):
                                    price_word = last_word['text']

                        # Look for description in the next line (same page)
                        description_parts = []
                        if i + 1 < len(sorted_line_keys):
                            next_key = sorted_line_keys[i + 1]
                            next_words = lines[next_key]
                            next_words.sort(key=lambda x: x['x0'])
                            next_text = " ".join([w['text'] for w in next_words])

                            if ("STK" not in next_text and
                                    "---" not in next_text and
                                    "REMARK" not in next_text.upper()):
                                if len(next_words) > 0 and next_words[0]['x0'] > 200:
                                    description_parts.append(next_text)

                        description = " ".join(description_parts)

                        row_data = {
                            "Your Part No": clean_text(your_part_no),
                            "Our Part No": clean_text(our_part_no),
                            "Description": clean_text(description),
                            "Quantity": clean_text(qty_word),
                            "Price USD": clean_text(price_word),
                            "Del. date": clean_text(etd_word)
                        }
                        data_rows.append(row_data)

    return data_rows


# ── Standard interface ────────────────────────────────────────────────

def process_file(input_path, output_path=None):
    if not output_path:
        base_name = os.path.basename(input_path).replace(".pdf", ".csv")
        output_dir = os.path.join("output", "Jeffco")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, base_name)

    logger.info("Processing Jeffco file: %s", input_path)
    try:
        data = extract_jeffco_data(input_path)
        if data:
            df = pd.DataFrame(data)
            cols = ["Our Part No", "Quantity", "Your Part No",
                    "Price USD", "Del. date", "Description"]
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            df = df[cols]
            df.to_csv(output_path, index=False)
            logger.info("Saved %s", output_path)
            return True
        else:
            logger.warning("No data extracted.")
            return False
    except Exception as e:
        logger.error("Error: %s", e)
        raise e


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(sys.argv) > 1:
        process_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        source_dir = "source/Jeffco"
        output_dir = "output/Jeffco"
        os.makedirs(output_dir, exist_ok=True)

        pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
        for pdf_file in pdf_files:
            try:
                process_file(pdf_file)
            except Exception as e:
                logger.error("Error processing %s: %s", pdf_file, e)
