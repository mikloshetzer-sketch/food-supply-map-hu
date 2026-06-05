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
    "wheat": ["búza", "wheat"],
    "maize": ["kukorica", "maize", "corn"],
    "barley": ["árpa", "barley"],
    "rye": ["rozs", "rye"],
    "oats": ["zab", "oats"],
    "triticale": ["tritikálé", "triticale"],
    "sunflower": ["napraforgó", "sunflower"],
    "rapeseed": ["repce", "rape", "rapeseed"],
    "soybean": ["szója", "soybean", "soya"],
    "potato": ["burgonya", "potato"],
    "sugar_beet": ["cukorrépa", "sugar beet"],
    "peas": ["borsó", "peas"],
    "beans": ["bab", "beans"],
}

CROP_HU = {
    "wheat": "Búza",
    "maize": "Kukorica",
    "barley": "Árpa",
    "rye": "Rozs",
    "oats": "Zab",
    "triticale": "Tritikálé",
    "sunflower": "Napraforgó",
    "rapeseed": "Repce",
    "soybean": "Szója",
    "potato": "Burgonya",
    "sugar_beet": "Cukorrépa",
    "peas": "Borsó",
    "beans": "Bab",
}

CATEGORY_ALIASES = {
    "production": ["termelés", "termés", "production"],
    "imports": ["import", "imports", "behozatal"],
    "exports": ["export", "exports", "kivitel"],
    "domestic_use": ["belföldi felhasználás", "domestic use", "domestic consumption"],
    "food_use": ["élelmezési", "élelmiszer", "food consumption", "food use"],
    "feed_use": ["takarmány", "feed use", "feeding"],
    "industrial_use": ["ipari", "industrial use"],
    "seed_use": ["vetőmag", "seed"],
    "other_use": ["egyéb", "other"],
    "opening_stock": ["nyitókészlet", "opening stock"],
    "closing_stock": ["zárókészlet", "closing stock"],
    "total_use": ["összes felhasználás", "total use"],
    "harvested_area": ["betakarított terület", "harvested area"],
    "yield": ["termésátlag", "yield"],
}

CATEGORY_HU = {
    "production": "Termelés",
    "imports": "Import",
    "exports": "Export",
    "domestic_use": "Belföldi felhasználás",
    "food_use": "Élelmezési felhasználás",
    "feed_use": "Takarmányozás",
    "industrial_use": "Ipari felhasználás",
    "seed_use": "Vetőmag-felhasználás",
    "other_use": "Egyéb felhasználás",
    "opening_stock": "Nyitókészlet",
    "closing_stock": "Zárókészlet",
    "total_use": "Összes felhasználás",
    "harvested_area": "Betakarított terület",
    "yield": "Termésátlag",
}


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def detect_crop(text: str):
    text = clean_text(text)
    for crop, aliases in CROP_ALIASES.items():
        if any(alias in text for alias in aliases):
            return crop
    return None


def detect_category(text: str):
    text = clean_text(text)
    for category, aliases in CATEGORY_ALIASES.items():
        if any(alias in text for alias in aliases):
            return category
    return None


def detect_unit(text: str):
    text = clean_text(text)

    if "millió ft" in text or "million huf" in text or "huf million" in text:
        return "huf_million"

    if "kg/ha" in text:
        return "kg_ha"

    if "t/ha" in text:
        return "t_ha"

    if "hektár" in text or "ha" in text:
        return "ha"

    if "tonna" in text or "tonnes" in text or "tons" in text or "t " in f"{text} ":
        return "t"

    return "value"


def find_year_columns(df: pd.DataFrame):
    year_cols = {}

    for col in df.columns:
        for row_idx in range(min(10, len(df))):
            val = df.iloc[row_idx, col]
            if pd.isna(val):
                continue

            text = str(val)
            match = re.search(r"(19[9]\d|20[0-3]\d)", text)
            if match:
                year = int(match.group(1))
                if 1990 <= year <= 2035:
                    year_cols[col] = year
                    break

    return year_cols


def row_label(row):
    parts = []
    for value in row:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text:
            continue

        if re.fullmatch(r"(19[9]\d|20[0-3]\d)", text):
            continue

        if re.fullmatch(r"[-+]?\d+([.,]\d+)?", text):
            continue

        parts.append(text)

    return " | ".join(parts)


def read_supply_balance_file(file_path: Path, group: str):
    if not file_path.exists():
        raise FileNotFoundError(f"Hiányzó fájl: {file_path}")

    all_rows = []
    unknown_rows = []

    sheets = pd.read_excel(file_path, sheet_name=None, header=None, engine="openpyxl")

    for sheet_name, df in sheets.items():
        df = df.dropna(how="all").dropna(axis=1, how="all")

        if df.empty:
            continue

        year_cols = find_year_columns(df)

        if not year_cols:
            unknown_rows.append({
                "source_file": file_path.name,
                "sheet": sheet_name,
                "reason": "Nem talált év oszlopokat",
                "raw_label": "",
            })
            continue

        current_crop = None

        for _, row in df.iterrows():
            label = row_label(row)
            label_clean = clean_text(label)

            if not label_clean:
                continue

            detected_crop = detect_crop(label_clean)
            if detected_crop:
                current_crop = detected_crop

            category = detect_category(label_clean)
            unit = detect_unit(label_clean)

            if category is None:
                unknown_rows.append({
                    "source_file": file_path.name,
                    "sheet": sheet_name,
                    "reason": "Nem azonosított kategória",
                    "raw_label": label,
                })
                continue

            crop = detected_crop or current_crop

            if crop is None:
                unknown_rows.append({
                    "source_file": file_path.name,
                    "sheet": sheet_name,
                    "reason": "Nem azonosított növény",
                    "raw_label": label,
                })
                continue

            for col, year in year_cols.items():
                value = row[col]

                if pd.isna(value):
                    continue

                if isinstance(value, str):
                    value = value.replace(" ", "").replace(",", ".")
                    if value in ["", "-", "–"]:
                        continue

                try:
                    value_num = float(value)
                except ValueError:
                    continue

                all_rows.append({
                    "year": year,
                    "crop": crop,
                    "crop_hu": CROP_HU.get(crop, crop),
                    "group": group,
                    "category": category,
                    "category_hu": CATEGORY_HU.get(category, category),
                    "unit": unit,
                    "value": value_num,
                    "source_file": file_path.name,
                    "sheet": sheet_name,
                    "raw_label": label,
                })

    return all_rows, unknown_rows


def main():
    records = []
    unknown = []

    for item in INPUT_FILES:
        rows, unknown_rows = read_supply_balance_file(item["path"], item["group"])
        records.extend(rows)
        unknown.extend(unknown_rows)

    out_df = pd.DataFrame(records)
    unknown_df = pd.DataFrame(unknown)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not out_df.empty:
        out_df = out_df.sort_values(["year", "group", "crop", "category", "unit"])
        out_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=[
            "year", "crop", "crop_hu", "group", "category", "category_hu",
            "unit", "value", "source_file", "sheet", "raw_label"
        ]).to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    if not unknown_df.empty:
        unknown_df.to_csv(UNKNOWN_FILE, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=["source_file", "sheet", "reason", "raw_label"]).to_csv(
            UNKNOWN_FILE, index=False, encoding="utf-8-sig"
        )

    print(f"Created: {OUTPUT_FILE}")
    print(f"Created: {UNKNOWN_FILE}")
    print(f"Rows: {len(out_df)}")
    print(f"Unknown rows: {len(unknown_df)}")


if __name__ == "__main__":
    main()
