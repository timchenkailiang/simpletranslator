"""Series 16 / Millarco PO converter — tail-matching regex approach."""

import logging
import pdfplumber
import pandas as pd
import sys
import re
import os
import glob

logger = logging.getLogger(__name__)

# ── Converter metadata ────────────────────────────────────────────────
FORMAT_NAME = "Series 16"
COLUMNS = ["Itemno", "Description", "Master", "Inner", "Quantity", "Unit price", "Amount", "ETD"]
VALIDATION_RULES = {"qty": "Quantity", "price": "Unit price", "amount": "Amount"}


# ── Helpers ───────────────────────────────────────────────────────────

def clean_text(text):
    if not text:
        return text
    return text.replace('\xad', '-').replace('\u00ad', '-').replace('\u2011', '-')


# ── Standard interface ────────────────────────────────────────────────

def process_file(input_path, output_path=None):
    if output_path is None:
        output_path = input_path.replace(".pdf", ".csv")
    return convert_pdf_to_csv(input_path, output_path)


def convert_pdf_to_csv(pdf_path, csv_path):
    logger.info("Processing %s", pdf_path)

    data = []
    headers = ["Itemno", "Description", "Master", "Inner",
               "Quantity", "Unit price", "Amount", "ETD"]

    # Regex for the trailing data columns:
    # Master  Inner  Qty  UnitPrice  Amount  ETD
    tail_pattern = re.compile(
        r"\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.\-\u00ad\u2011\u2013\u2014]+.*)$"
    )

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')
                for idx, line in enumerate(lines):
                    tail_match = tail_pattern.search(line)
                    if tail_match:
                        master, inner, qty, unit_price, amount, etd = tail_match.groups()

                        # Normalise hyphen variants in ETD
                        etd = (etd.replace('\xad', '-')
                               .replace('\u2011', '-')
                               .replace('\u2013', '-')
                               .replace('\u2014', '-'))

                        head = line[:tail_match.start()].strip()
                        parts = head.split(maxsplit=1)

                        if parts and parts[0].isdigit():
                            itemno = parts[0]
                            description = ""

                            # Normal case: description is on the same line.
                            if len(parts) == 2:
                                description = clean_text(parts[1])
                            else:
                                # Alternate layout (e.g. some middle pages):
                                # item + numeric columns are on one line and
                                # description appears in following lines.
                                # Try to pick the closest meaningful description.
                                for la in range(idx + 1, min(idx + 40, len(lines))):
                                    probe = lines[la].strip()
                                    if not probe:
                                        continue
                                    if probe.lower().startswith("vendor"):
                                        break
                                    if probe.lower().startswith("itemno"):
                                        break
                                    if probe.lower().startswith("purchase order"):
                                        break
                                    if probe.lower().startswith("brand:"):
                                        description = clean_text(probe)
                                        break

                            data.append([itemno, description, master, inner,
                                         qty, unit_price, amount, etd])
    except Exception as e:
        logger.error("Error reading PDF %s: %s", pdf_path, e)
        return False

    if not data:
        logger.warning("No matching table data found.")
        return False

    df = pd.DataFrame(data, columns=headers)
    df.to_csv(csv_path, index=False)
    logger.info("Saved to %s", csv_path)
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = (sys.argv[2] if len(sys.argv) > 2
                       else input_file.replace(".pdf", ".csv"))
        convert_pdf_to_csv(input_file, output_file)
    else:
        source_dir = "source/Series_16"
        output_dir = "output/Series_16"
        os.makedirs(output_dir, exist_ok=True)

        pdf_files = glob.glob(os.path.join(source_dir, "*.pdf"))
        for pdf_file in pdf_files:
            filename = os.path.basename(pdf_file)
            csv_filename = filename.replace(".pdf", ".csv")
            output_path = os.path.join(output_dir, csv_filename)
            convert_pdf_to_csv(pdf_file, output_path)
