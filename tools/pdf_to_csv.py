# tools/pdf_to_csv.py
import re
import csv
from pathlib import Path

import pdfplumber

PDF_PATH = Path("data/feed_mills.pdf")  # ide tedd a PDF-et (átnevezve)
OUT_CSV  = Path("data/feed_producers.csv")

HEADERS = [
    "reg_no", "activity", "company", "address", "site", "notes", "tse"
]

def looks_like_data_row(c0: str) -> bool:
    c0 = (c0 or "").strip()
    # tipikus kezdet: "α HU ..." vagy "HU ..." vagy szám
    return bool(re.match(r"^(α\s*HU|HU|\d)", c0))

def main():
    if not PDF_PATH.exists():
        raise SystemExit(f"Nem találom: {PDF_PATH} (tedd ide a PDF-et és nevezd át feed_mills.pdf-re)")

    rows = []
    with pdfplumber.open(str(PDF_PATH)) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            for r in table:
                if not r or len(r) != 7:
                    continue
                if looks_like_data_row(r[0]):
                    rows.append([x if x is not None else "" for x in r])

    if not rows:
        raise SystemExit("Nem sikerült táblázat-sorokat kinyerni a PDF-ből.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows)

    print(f"OK: {OUT_CSV} készült. Sorok: {len(rows)}")

if __name__ == "__main__":
    main()
