# tools/geocode_feed_mills.py
import time
import json
import re
from pathlib import Path

import pandas as pd
import requests

XLSX_PATH = Path("data/feed_mills.xlsx")
OUT_GEOJSON = Path("data/feed_mills.geojson")
CACHE_JSON = Path("data/geocode_cache_feed_mills.json")

# Nominatim (OpenStreetMap) – udvarias limit
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "food-supply-map-hu/1.0 (educational; contact: github repo owner)"

def clean_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def guess_columns(df: pd.DataFrame):
    cols = list(df.columns)

    def find_any(cands):
        lower = {c.lower(): c for c in cols}
        for cand in cands:
            if cand in lower:
                return lower[cand]
        return None

    col_company = find_any(["company","cegnev","cég","cegnév","name","nev","név"])
    col_address = find_any(["address","cim","cím","cim teljes","teljes cim","teljes cím"])
    col_city = find_any(["city","telepules","település","varos","város"])
    return col_company, col_address, col_city

def build_query(address: str, city: str | None):
    a = clean_space(address)
    c = clean_space(city) if city else ""
    # ha a cím nem tartalmaz országot, toldjuk hozzá
    q = ", ".join([x for x in [a, c, "Magyarország"] if x])
    return q

def nominatim_geocode(query: str):
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
        "countrycodes": "hu",
    }
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=40)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    hit = data[0]
    return {
        "lat": float(hit["lat"]),
        "lon": float(hit["lon"]),
        "display_name": hit.get("display_name",""),
        "class": hit.get("class",""),
        "type": hit.get("type",""),
    }

def main():
    if not XLSX_PATH.exists():
        raise SystemExit(f"Nem találom: {XLSX_PATH}")

    df = pd.read_excel(XLSX_PATH)
    df = df.dropna(how="all")
    if df.empty:
        raise SystemExit("Az Excel üresnek tűnik.")

    col_company, col_address, col_city = guess_columns(df)
    if not col_address:
        raise SystemExit(
            "Nem találtam cím oszlopot. Legyen oszlopnév pl. 'address' vagy 'cím' vagy 'cim'."
        )

    # cache betöltés
    cache = {}
    if CACHE_JSON.exists():
        cache = json.loads(CACHE_JSON.read_text(encoding="utf-8"))

    features = []
    miss = 0
    hitn = 0

    for i, row in df.iterrows():
        company = clean_space(str(row[col_company])) if col_company else ""
        address = clean_space(str(row[col_address])) if col_address else ""
        city = clean_space(str(row[col_city])) if col_city and pd.notna(row[col_city]) else ""

        if not address or address.lower() in ("nan",):
            continue

        query = build_query(address, city if city else None)

        if query in cache:
            res = cache[query]
        else:
            # udvarias: 1 kérés / ~1.2s
            time.sleep(1.2)
            try:
                ge = nominatim_geocode(query)
            except Exception as e:
                ge = None
            res = ge
            cache[query] = res

        if not res:
            miss += 1
            continue

        hitn += 1
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [res["lon"], res["lat"]]},
            "properties": {
                "company": company,
                "address": address,
                "city": city,
                "q": query,
                "source": "Nominatim",
                "display_name": res.get("display_name",""),
                "osm_class": res.get("class",""),
                "osm_type": res.get("type",""),
            }
        })

    fc = {"type": "FeatureCollection", "features": features}
    OUT_GEOJSON.write_text(json.dumps(fc, ensure_ascii=False, indent=2), encoding="utf-8")
    CACHE_JSON.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"OK: {OUT_GEOJSON} készült. Pontok: {hitn} · Sikertelen: {miss}")
    print(f"Cache: {CACHE_JSON} (újrafuttatáskor gyorsabb)")

if __name__ == "__main__":
    main()
