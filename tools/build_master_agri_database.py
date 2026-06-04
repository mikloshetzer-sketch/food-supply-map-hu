# Food Supply Map HU - Agriculture Database Builder
# Biztonságos verzió: csak a data/agriculture mappában dolgozik.
# Nem módosítja a régi dashboard fájljait.

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AGRI_DIR = ROOT / "data" / "agriculture"

FILES = {
    "population": AGRI_DIR / "population_ksh.xlsx",
    "area": AGRI_DIR / "crop_area_ksh_1990_2025.xlsx",
    "yield": AGRI_DIR / "crop_yield_ksh_1990_2025.xlsx",
    "production": AGRI_DIR / "crop_total_production_ksh_1990_2025.xlsx",
    "climate": AGRI_DIR / "precipitation_hungary_1990_2025.xlsx",
}

OUT_MASTER = AGRI_DIR / "master_agri_database.csv"
OUT_CLIMATE = AGRI_DIR / "climate_station_yearly.csv"

CROP_NAME_MAP = {
    "Búza": "wheat",
    "Kukorica": "maize",
    "Árpa összesen": "barley",
    "Rozs": "rye",
    "Zab": "oats",
    "Szójabab": "soybean",
    "Napraforgómag": "sunflower",
    "Repcemag": "rapeseed",
    "Cukorrépa": "sugar_beet",
    "Burgonya": "potato",
}

FOOD_NEED_KG_PER_CAPITA = {
    "wheat": 120,
    "maize": 80,
    "barley": 15,
    "rye": 5,
    "oats": 5,
    "soybean": 8,
    "sunflower": 10,
    "rapeseed": 5,
    "sugar_beet": 35,
    "potato": 55,
}

WATER_NEED_MID_MM = {
    "wheat": 550,
    "maize": 650,
    "barley": 500,
    "rye": 500,
    "oats": 500,
    "soybean": 600,
    "sunflower": 600,
    "rapeseed": 550,
    "sugar_beet": 650,
    "potato": 550,
}

def clean_number(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, str):
        x = x.strip().replace(" ", "").replace(",", ".")
        if x in ("", "..", "…", "-", "nan"):
            return np.nan
    try:
        return float(x)
    except Exception:
        return np.nan

def read_first_sheet(path):
    if not path.exists():
        raise FileNotFoundError(f"Hiányzó fájl: {path}")
    return pd.read_excel(path, sheet_name=0)

def normalize_crop_table(path, value_name):
    df = read_first_sheet(path)
    df = df.rename(columns={df.columns[0]: "year"})
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["year"].between(1990, 2025)]

    keep_cols = ["year"] + [c for c in df.columns if c in CROP_NAME_MAP]
    df = df[keep_cols]

    long_df = df.melt(id_vars="year", var_name="crop_hu", value_name=value_name)
    long_df["crop"] = long_df["crop_hu"].map(CROP_NAME_MAP)
    long_df[value_name] = long_df[value_name].apply(clean_number)
    return long_df[["year", "crop", "crop_hu", value_name]]

def load_population(path):
    df = read_first_sheet(path)
    df = df.rename(columns={df.columns[0]: "year", df.columns[1]: "population_thousand"})
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["year"].between(1990, 2025)]
    df["population"] = df["population_thousand"].apply(clean_number) * 1000
    return df[["year", "population"]]

def load_climate(path):
    raw = pd.read_excel(path, sheet_name=0, header=None)
    years = [int(y) for y in raw.iloc[0, 1:].tolist() if pd.notna(y) and str(y).replace(".0","").isdigit()]
    year_cols = list(range(1, 1 + len(years)))

    metric = None
    records = []

    metric_map = {
        "Átlagos középhőmérséklet": "avg_temp_c",
        "Csapadékösszeg": "precip_mm",
        "Napfénytartam": "sunshine_hours",
        "Napsütés": "sunshine_hours",
    }

    for _, row in raw.iloc[1:].iterrows():
        first = row.iloc[0]
        if pd.isna(first):
            continue

        label = str(first).strip()

        matched_metric = None
        for key, val in metric_map.items():
            if key.lower() in label.lower():
                matched_metric = val
                break

        if matched_metric:
            metric = matched_metric
            continue

        if metric is None:
            continue

        station = label
        values = row.iloc[year_cols].tolist()

        for year, value in zip(years, values):
            if 1990 <= int(year) <= 2025:
                records.append({
                    "year": int(year),
                    "station": station,
                    metric: clean_number(value)
                })

    if not records:
        return pd.DataFrame(columns=["year", "avg_temp_c", "precip_mm", "sunshine_hours"])

    climate_long = pd.DataFrame(records)

    # mérőállomás-éves tábla
    station_df = climate_long.groupby(["year", "station"], as_index=False).first()
    station_df.to_csv(OUT_CLIMATE, index=False, encoding="utf-8-sig")

    # országos átlag: mérőállomások egyszerű átlaga
    national = station_df.groupby("year", as_index=False).agg({
        "avg_temp_c": "mean",
        "precip_mm": "mean",
        "sunshine_hours": "mean",
    })

    for col in ["avg_temp_c", "precip_mm", "sunshine_hours"]:
        national[col] = national[col].round(2)

    return national

def risk_level(self_sufficiency_ratio, water_balance_mm):
    if pd.isna(self_sufficiency_ratio) or pd.isna(water_balance_mm):
        return "unknown"
    if self_sufficiency_ratio < 1 and water_balance_mm < -150:
        return "critical"
    if self_sufficiency_ratio < 1 or water_balance_mm < -100:
        return "high"
    if self_sufficiency_ratio < 1.5 or water_balance_mm < 0:
        return "medium"
    return "low"

def main():
    print("Food Supply Map HU - Agriculture Database Builder")
    print("Csak az új agriculture modulban dolgozom.")

    AGRI_DIR.mkdir(parents=True, exist_ok=True)

    population = load_population(FILES["population"])
    area = normalize_crop_table(FILES["area"], "area_kha")
    crop_yield = normalize_crop_table(FILES["yield"], "yield_kg_ha")
    production = normalize_crop_table(FILES["production"], "production_t")
    climate = load_climate(FILES["climate"])

    master = area.merge(crop_yield, on=["year", "crop", "crop_hu"], how="outer")
    master = master.merge(production[["year", "crop", "production_t"]], on=["year", "crop"], how="outer")
    master = master.merge(population, on="year", how="left")
    master = master.merge(climate, on="year", how="left")

    master["area_ha"] = master["area_kha"] * 1000
    master["yield_t_ha"] = master["yield_kg_ha"] / 1000

    master["food_need_kg_per_capita"] = master["crop"].map(FOOD_NEED_KG_PER_CAPITA)
    master["food_need_t"] = master["population"] * master["food_need_kg_per_capita"] / 1000

    master["required_area_ha"] = master["food_need_t"] / master["yield_t_ha"]
    master["self_sufficiency_ratio"] = master["production_t"] / master["food_need_t"]
    master["supported_population"] = master["production_t"] * 1000 / master["food_need_kg_per_capita"]

    master["water_need_mid_mm"] = master["crop"].map(WATER_NEED_MID_MM)
    master["water_balance_mm"] = master["precip_mm"] - master["water_need_mid_mm"]

    master["risk_level"] = master.apply(
        lambda r: risk_level(r["self_sufficiency_ratio"], r["water_balance_mm"]),
        axis=1
    )

    cols = [
        "year", "crop", "crop_hu",
        "area_kha", "area_ha",
        "yield_kg_ha", "yield_t_ha",
        "production_t",
        "population",
        "food_need_kg_per_capita",
        "food_need_t",
        "required_area_ha",
        "self_sufficiency_ratio",
        "supported_population",
        "avg_temp_c",
        "precip_mm",
        "sunshine_hours",
        "water_need_mid_mm",
        "water_balance_mm",
        "risk_level",
    ]

    master = master[cols].sort_values(["year", "crop"])

    numeric_cols = master.select_dtypes(include=[np.number]).columns
    master[numeric_cols] = master[numeric_cols].round(3)

    master.to_csv(OUT_MASTER, index=False, encoding="utf-8-sig")

    print(f"Kész: {OUT_MASTER}")
    print(f"Sorok száma: {len(master)}")
    print(f"Klíma mérőállomás fájl: {OUT_CLIMATE}")
    print("A régi dashboard fájljai nem módosultak.")

if __name__ == "__main__":
    main()

