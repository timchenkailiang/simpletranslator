
#!/usr/bin/env python3
"""
pdf_to_excel_auto.py

Automate "PDF PO -> matched Excel" for your current two formats:

A) Jeffco Requisition PDF (example: "PO 35306 - Jeffco.pdf")
   Line pattern:
     <qty> STK <lev_part> <vort_part tokens...> <date>
   - Description is the following lines until the next row
   - match_key = lev_part + vort_part
   - Special-case: if lev_part == vort_part => match_key = lev_part

B) Millarco Purchase Order PDF (example: "PO16665.pdf")
   - Detect by presence of: "Itemno.", "Unit price", "ETD"
   - Row lines end with ETD date (some PDFs include soft-hyphen, we normalize it)
   - match_key = itemno

Master Excel (.xls/.xlsx)
   - The script tries to find a key column among common names:
     客人货号 / Itemno / Your no. / etc.
   - If the master is .xls and xlrd is missing, we auto-convert via LibreOffice (soffice).

Output .xlsx includes:
  - po_lines      (parsed rows from PDF)
  - matched       (left-join PDF rows to master by match_key)
  - missing_keys  (keys that didn't match master)

Usage:
  python pdf_to_excel_auto.py --pdf "PO 35306 - Jeffco.pdf" --master "35317.xls" --out "PO35306_out.xlsx"
  python pdf_to_excel_auto.py --pdf "PO16665.pdf" --master "16665-全部.xls" --out "PO16665_out.xlsx"

Dependencies:
  pip install pdfplumber pandas openpyxl
  (optional) LibreOffice/soffice installed for .xls conversion fallback
"""

import re
import subprocess
import tempfile
import shutil
from pathlib import Path
import argparse

import pandas as pd
import pdfplumber


def read_pdf_text(pdf_path: Path) -> str:
    """Extract text from all pages and normalize soft hyphen to '-'."""
    texts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            texts.append((page.extract_text() or "").replace("\xad", "-"))
    return "\n".join(texts)


def detect_template(pdf_path: Path) -> str:
    text = read_pdf_text(pdf_path)
    if ("Itemno." in text) and ("Unit price" in text) and ("ETD" in text):
        return "millarco_po"
    return "jeffco_req"


def parse_jeffco_requisition(pdf_path: Path) -> pd.DataFrame:
    text = read_pdf_text(pdf_path)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    stop_words = {"Requisition", "Jeffco", "Supplier", "Delivery", "Date", "Item", "Sida", "Page"}
    row_start = re.compile(
        r"^(?P<qty>\d+)\s+(?P<unit>[A-Z]{2,4})\s+(?P<lev>\d+)\s+(?P<vort_tokens>(?:\d+\s*)+?)\s+(?P<date>\d{1,2}-\d{1,2}-\d{2})$"
    )

    rows = []
    i = 0
    while i < len(lines):
        m = row_start.match(lines[i])
        if not m:
            i += 1
            continue

        qty = int(m.group("qty"))
        unit = m.group("unit")
        lev = m.group("lev")
        vort_tokens = m.group("vort_tokens").split()
        vort_part = "".join(vort_tokens)
        date = m.group("date")

        desc_parts = []
        j = i + 1
        while j < len(lines) and not row_start.match(lines[j]):
            ln = lines[j]
            if any(sw.lower() in ln.lower() for sw in stop_words):
                j += 1
                continue
            if re.fullmatch(r"[\d\.,\-]+", ln):
                j += 1
                continue
            desc_parts.append(ln)
            j += 1

        description = " ".join(desc_parts).strip()
        match_key = lev if lev == vort_part else f"{lev}{vort_part}"

        rows.append(
            {
                "qty": qty,
                "unit": unit,
                "lev_part": lev,
                "vort_part_raw": " ".join(vort_tokens),
                "vort_part": vort_part,
                "date": date,
                "description": description,
                "match_key": match_key,
            }
        )
        i = j

    return pd.DataFrame(rows)


def parse_millarco_po(pdf_path: Path) -> pd.DataFrame:
    text = read_pdf_text(pdf_path)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    row_re = re.compile(
        r"^(?P<itemno>\d+)\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<master>\d[\d\.,]*)\s+"
        r"(?P<inner>\d+)\s+"
        r"(?P<qty>[\d\.,]+)\s+"
        r"(?P<unit_price>[\d\.,]+)\s+"
        r"(?P<amount>[\d\.,]+)\s+"
        r"(?P<etd>\d{2}-\d{2}-\d{4})$"
    )

    def to_number(s: str):
        if "." in s and "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." not in s:
            s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None

    rows = []
    for ln in lines:
        m = row_re.match(ln)
        if not m:
            continue
        rows.append(
            {
                "itemno": m.group("itemno"),
                "description": m.group("desc").strip(),
                "master": to_number(m.group("master")),
                "inner": int(m.group("inner")),
                "quantity": to_number(m.group("qty")),
                "unit_price": to_number(m.group("unit_price")),
                "amount": to_number(m.group("amount")),
                "etd": m.group("etd"),
                "match_key": m.group("itemno"),
            }
        )
    return pd.DataFrame(rows)


def soffice_convert_xls_to_xlsx(xls_path: Path) -> Path:
    """Convert .xls -> .xlsx via LibreOffice, using a temp user profile to avoid lock/permissions issues."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="lo_out_"))
    profile_dir = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    try:
        cmd = [
            "soffice",
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--norestore",
            f"-env:UserInstallation=file://{profile_dir.as_posix()}",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(tmp_dir),
            str(xls_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        produced = next(tmp_dir.glob("*.xlsx"))
        target = xls_path.parent / (xls_path.stem + ".converted.xlsx")
        produced.replace(target)
        return target
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        shutil.rmtree(profile_dir, ignore_errors=True)


def load_master_any(excel_path: Path) -> pd.DataFrame:
    """Read .xlsx directly; for .xls, either use xlrd (if available) or convert via soffice."""
    try:
        return pd.read_excel(excel_path)
    except ImportError as e:
        if excel_path.suffix.lower() == ".xls" and "xlrd" in str(e).lower():
            xlsx_path = soffice_convert_xls_to_xlsx(excel_path)
            return pd.read_excel(xlsx_path, engine="openpyxl")
        raise


def normalize_master(df: pd.DataFrame) -> pd.DataFrame:
    candidates = ["客人货号", "客人貨號", "Itemno", "Item No", "itemno", "Your no.", "Your No", "Your no", "客戶貨號"]
    key_col = next((c for c in candidates if c in df.columns), None) or df.columns[0]

    out = df.copy()
    out["match_key"] = out[key_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    return out


def run(pdf_path: Path, out_path: Path, master_path: Path | None = None):
    template = detect_template(pdf_path)
    po_df = parse_millarco_po(pdf_path) if template == "millarco_po" else parse_jeffco_requisition(pdf_path)
    if po_df.empty:
        raise RuntimeError(f"No PO lines parsed from {pdf_path} (template={template}). You may need to adjust regex.")

    master_df = normalize_master(load_master_any(master_path))
    merged = po_df.merge(master_df, on="match_key", how="left", suffixes=("", "_master"))

    master_keys = set(master_df["match_key"].astype(str))
    merged["match_flag"] = merged["match_key"].astype(str).apply(lambda k: "matched" if k in master_keys else "missing")

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        po_df.to_excel(writer, sheet_name="po_lines", index=False)
        merged.to_excel(writer, sheet_name="matched", index=False)
        merged.loc[merged["match_flag"] == "missing", ["match_key"]].drop_duplicates().to_excel(
            writer, sheet_name="missing_keys", index=False
        )

    print(f"Done -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run(Path(args.pdf), Path(args.master), Path(args.out))


if __name__ == "__main__":
    main()
