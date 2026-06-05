from pathlib import Path
import re
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILES = [
    {
        "path": BASE_DIR / "data" / "agriculture" / "Cereal_Supply_Balance.xlsx",
        "group": "cereals",
    },
    {
        "path": BASE_DIR / "data" / "agriculture" / "Field_Crop_Supply_Balance.xlsx",
        "group": "field_crops",
    },
]

OUTPUT_FILE = BASE_DIR / "data" / "agriculture" / "supply_balance_master.csv"
UNKNOWN_FILE = BASE_DIR / "data" / "agriculture" / "supply_balance_unknown_rows.csv"


CROP_ALIASES = {
    "cereals_total": ["cereals, total", "cereals total"],
    "wheat": ["wheat"],
    "maize": ["maize", "corn"],
    "rice": ["rice"],
    "barley": ["barley"],
    "rye": ["rye"],
    "oats": ["oats"],
    "triticale": ["triticale"],
    "potato": ["potato"],
    "soybean": ["soybean", "soya"],
    "sunflower": ["sunflower"],
    "rapeseed": ["rape", "rapeseed"],
    "sugar_beet": ["sugar beet"],
    "peas": ["peas"],
    "beans": ["beans"],
}

CROP_HU = {
    "cereals_total": "Gabonafélék összesen",
    "wheat": "Búza",
    "maize": "Kukorica",
    "rice": "Rizs",
    "barley": "Árpa",
    "rye": "Rozs",
    "oats": "Zab",
    "triticale": "Tritikálé",
    "potato": "Burgonya",
    "soybean": "Szója",
    "sunflower": "Napraforgó",
    "rapeseed": "Repce",
    "sugar_beet": "Cukorrépa",
    "peas": "Borsó",
    "beans": "Bab",
}

CATEGORY_ALIASES = {
    "harvested_area": ["harvested area"],
    "production": ["total harvested production"],
    "yield": ["average yield"],
    "imports": ["imports"],
    "exports": ["exports"],
    "opening_stock": ["initial stock", "opening stock"],
    "closing_stock": ["closing stock"],
    "total_resource": ["total resource"],
    "total_use": ["total use"],
    "food_use": ["domestic food consumption", "personal consumption", "for human consumption"],
    "feed_use": ["feed consumption", "fodder"],
    "industrial_use": ["industrial processing", "for industrial purposes", "processing"],
    "seed_use": ["seed consumption", "seed"],
    "other_use": ["other consumption", "other"],
    "loss": ["loss"],
    "domestic_purchases": ["domestic purchases"],
    "sales": ["sales"],
    "intermediate_consumption": ["intermediate consumption"],
    "procurement_price": ["average procurement price"],
    "market_price": ["average market price"],
}

CATEGORY_HU = {
    "harvested_area": "Betakarított terület",
    "production": "Termelés",
    "yield": "Termésátlag",
    "imports": "Import",
    "exports": "Export",
    "opening_stock": "Nyitókészlet",
    "closing_stock": "Zárókészlet",
    "total_resource": "Összes forrás",
    "total_use": "Összes felhasználás",
    "food_use": "Élelmezési felhasználás",
    "feed_use": "Takarmányozás",
    "industrial_use": "Ipari felhasználás",
    "seed_use": "Vetőmag-felhasználás",
    "other_use": "Egyéb felhasználás",
    "loss": "Veszteség",
    "domestic_purchases": "Belföldi beszerzés",
    "sales": "Értékesítés",
    "intermediate_consumption": "Folyó termelőfelhasználás",
    "procurement_price": "Felvásárlási ár",
    "market_price": "Piaci ár",
}


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def clean_number(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(" ", "").replace(",", ".")
        if value in ["", "-", "–", "…", "...", ".."]:
            return None
    try:
        return float(value)
    except Exception:
        return None


def detect_crop_from_header(text: str):
    text = clean_text(text)
    for crop, aliases in CROP_ALIASES.items():
        for alias in aliases:
            if alias in text:
                return crop
    return None


def detect_category(text: str):
    text = clean_text(text)
    for category, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            if alias in text:
                return category
    return None


def detect_unit(label: str, category: str):
    text = clean_text(label)

    if "million huf" in text or "millió ft" in text:
        return "huf_million"

    if "huf per tonne" in text or "huf/tonne" in text:
        return "huf_t"

    if "huf per kilogram" in text or "huf/kg" in text:
        return "huf_kg"

    if "kg/ha" in text:
        return "kg_ha"

    if "hectare" in text or category == "harvested_area":
        return "ha"

    if "tonne" in text or "tons" in text or category in [
        "production",
        "imports",
        "exports",
        "opening_stock",
        "closing_stock",
        "total_resource",
        "total_use",
        "food_use",
        "feed_use",
        "industrial_use",
        "seed_use",
        "other_use",
        "loss",
        "domestic_purchases",
        "sales",
        "intermediate_consumption",
    ]:
        return "t"

    return "value"


def find_header_row(df: pd.DataFrame):
    for idx in range(min(30, len(df))):
        row_text = " | ".join(clean_text(x) for x in df.iloc[idx].tolist())
        if "denomination" in row_text and re.search(r"20[0-3]\d", row_text):
            return idx
    return None


def build_column_map(header_row):
    """
    Returns:
    {
      column_index: {"crop": "wheat", "year": 2020}
    }
    """
    col_map = {}

    for col_idx, value in enumerate(header_row):
        text = clean_text(value)
        if not text:
            continue

        year_match = re.search(r"(19[9]\d|20[0-3]\d)", text)
        if not year_match:
            continue

        year = int(year_match.group(1))
        crop = detect_crop_from_header(text)

        if crop:
            col_map[col_idx] = {
                "crop": crop,
                "year": year,
                "header": str(value),
            }

    return col_map


def build_label(row):
    parts = []

    for value in row[:6]:
        if pd.isna(value):
            continue

        text = str(value).strip()

        if not text:
            continue

        if re.fullmatch(r"[-+]?\d+([.,]\d+)?", text):
            continue

        if re.search(r"(19[9]\d|20[0-3]\d)", text):
            continue

        parts.append(text)

    return " | ".join(parts)


def read_file(file_path: Path, group: str):
    records = []
    unknown = []

    if not file_path.exists():
        raise FileNotFoundError(f"Hiányzó fájl: {file_path}")

    sheets = pd.read_excel(file_path, sheet_name=None, header=None, engine="openpyxl")

    for sheet_name, df in sheets.items():
        df = df.dropna(how="all").dropna(axis=1, how="all")

        if df.empty:
            continue

        header_idx = find_header_row(df)

        if header_idx is None:
            unknown.append({
                "source_file": file_path.name,
                "sheet": sheet_name,
                "reason": "Nem talált fejlécsort",
                "raw_label": "",
            })
            continue

        header_row = df.iloc[header_idx].tolist()
        col_map = build_column_map(header_row)

        if not col_map:
            unknown.append({
                "source_file": file_path.name,
                "sheet": sheet_name,
                "reason": "Nem talált növény+év oszlopokat",
                "raw_label": " | ".join(str(x) for x in header_row if not pd.isna(x)),
            })
            continue

        for row_idx in range(header_idx + 1, len(df)):
            row = df.iloc[row_idx].tolist()
            label = build_label(row)
            label_clean = clean_text(label)

            if not label_clean:
                continue

            category = detect_category(label_clean)

            if category is None:
                unknown.append({
                    "source_file": file_path.name,
                    "sheet": sheet_name,
                    "reason": "Nem azonosított kategória",
                    "raw_label": label,
                })
                continue

            unit = detect_unit(label_clean, category)

            for col_idx, meta in col_map.items():
                value = clean_number(row[col_idx])

                if value is None:
                    continue

                crop = meta["crop"]
                year = meta["year"]

                records.append({
                    "year": year,
                    "crop": crop,
                    "crop_hu": CROP_HU.get(crop, crop),
                    "group": group,
                    "category": category,
                    "category_hu": CATEGORY_HU.get(category, category),
                    "unit": unit,
                    "value": value,
                    "source_file": file_path.name,
                    "sheet": sheet_name,
                    "column_header": meta["header"],
                    "raw_label": label,
                })

    return records, unknown


def main():
    records = []
    unknown = []

    for item in INPUT_FILES:
        rows, unknown_rows = read_file(item["path"], item["group"])
        records.extend(rows)
        unknown.extend(unknown_rows)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "year",
        "crop",
        "crop_hu",
        "group",
        "category",
        "category_hu",
        "unit",
        "value",
        "source_file",
        "sheet",
        "column_header",
        "raw_label",
    ]

    out_df = pd.DataFrame(records, columns=columns)

    if not out_df.empty:
        out_df = out_df.sort_values(["year", "group", "crop", "category", "unit"])
        out_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    else:
        out_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    unknown_df = pd.DataFrame(
        unknown,
        columns=["source_file", "sheet", "reason", "raw_label"]
    )
    unknown_df.to_csv(UNKNOWN_FILE, index=False, encoding="utf-8-sig")

    print(f"Created: {OUTPUT_FILE}")
    print(f"Created: {UNKNOWN_FILE}")
    print(f"Rows: {len(out_df)}")
    print(f"Unknown rows: {len(unknown_df)}")


if __name__ == "__main__":
    main()
