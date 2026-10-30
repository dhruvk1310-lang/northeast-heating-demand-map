"""A dealer's service area and customer base, from public data.

1. Geocode every dealer registered in Connecticut (Census batch geocoder).
2. Load Connecticut block groups (neighborhoods) with their oil-heated homes (ACS B25040).
3. Share each block group's oil homes among nearby dealers with a Huff gravity model:
   closer dealers win more customers. A dealer's expected customers in a block group
   are its share times the oil homes there.

Outputs (data/interim/logistics):
  dealers_geocoded.csv     every registered dealer with coordinates
  service_area.csv         the chosen dealer's block groups and expected customers
"""

import io
import math

import geopandas as gpd
import pandas as pd
import requests

from src.config import INTERIM, RAW
from src.extract.download import HEADERS, download

OUT = INTERIM / "logistics"
GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
BG_SHAPES = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_09_bg_500k.zip"

DEALER_ID = 287233  # Densmore Oil, Stonington: the top prospect in the Connecticut pilot
SERVICE_RADIUS_MI = 20  # typical heating oil delivery radius around a depot
DECAY_MI = 8.0  # Huff distance decay: a dealer 8 miles further away is e (2.7x) less attractive
COMPETE_RADIUS_MI = 30  # dealers further than this do not compete for a block group
MIN_CUSTOMERS = 0.5  # drop block groups where the dealer would expect fewer customers


def miles(lat1, lon1, lat2, lon2):
    """Great-circle distance in miles (vectorized over pandas Series)."""
    import numpy as np
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dlmb = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(a))


def geocode_dealers() -> pd.DataFrame:
    path = OUT / "dealers_geocoded.csv"
    if path.exists():
        return pd.read_csv(path, dtype={"zip5": str})
    dealers = pd.read_csv(INTERIM / "ct_dealers.csv", dtype={"zip5": str})
    batch = dealers[["dealer_id", "address", "town", "state", "zip5"]].to_csv(index=False, header=False)
    resp = requests.post(GEOCODER, headers=HEADERS, timeout=300,
                         files={"addressFile": ("dealers.csv", batch, "text/csv")},
                         data={"benchmark": "Public_AR_Current"})
    resp.raise_for_status()
    cols = ["dealer_id", "input", "match", "match_type", "matched_address", "lonlat", "tiger_id", "side"]
    geo = pd.read_csv(io.StringIO(resp.text), header=None, names=cols, dtype=str)
    geo = geo[geo["match"] == "Match"].copy()
    geo[["longitude", "latitude"]] = geo["lonlat"].str.split(",", expand=True).astype(float)
    geo["dealer_id"] = geo["dealer_id"].astype(int)
    out = dealers.merge(geo[["dealer_id", "latitude", "longitude", "match_type"]], on="dealer_id", how="left")
    out.to_csv(path, index=False)
    print(f"  geocoded {out['latitude'].notna().sum()} of {len(out)} dealers")
    return out


def block_groups() -> gpd.GeoDataFrame:
    shapes = gpd.read_file(f"zip://{download(BG_SHAPES, RAW / 'census' / 'cb_2024_09_bg_500k.zip')}")
    acs = pd.read_csv(RAW / "census" / "acs5_2024_b25040.dat", sep="|", dtype={"GEO_ID": str},
                      usecols=["GEO_ID", "B25040_E001", "B25040_E003", "B25040_E005"])
    acs = acs[acs["GEO_ID"].str.startswith("1500000US09")].copy()
    acs["GEOID"] = acs["GEO_ID"].str[9:]
    acs = acs.rename(columns={"B25040_E001": "homes", "B25040_E003": "propane_homes", "B25040_E005": "oil_homes"})
    bg = shapes.merge(acs[["GEOID", "homes", "oil_homes", "propane_homes"]], on="GEOID")
    pts = bg.to_crs("EPSG:5070").geometry.representative_point().to_crs("EPSG:4326")
    bg["latitude"], bg["longitude"] = pts.y, pts.x
    return bg


def huff_share(bg: pd.DataFrame, dealers: pd.DataFrame, dealer_id: int) -> pd.Series:
    """The dealer's expected share of each block group's oil homes."""
    d = dealers.dropna(subset=["latitude"])
    cols = {}
    for row in d.itertuples():
        dist = miles(bg["latitude"], bg["longitude"], row.latitude, row.longitude)
        cols[row.dealer_id] = (dist <= COMPETE_RADIUS_MI) * (dist / DECAY_MI).mul(-1).map(math.exp)
    weights = pd.DataFrame(cols, index=bg.index)
    total = weights.sum(axis=1)
    return (weights[dealer_id] / total).where(total > 0, 0)


def run(dealer_id: int = DEALER_ID) -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    dealers = geocode_dealers()
    depot = dealers.set_index("dealer_id").loc[dealer_id]
    bg = block_groups()
    bg["miles_from_depot"] = miles(bg["latitude"], bg["longitude"], depot.latitude, depot.longitude)
    near = bg[bg["miles_from_depot"] <= SERVICE_RADIUS_MI].copy()
    near["dealer_share"] = huff_share(near, dealers, dealer_id)
    near["expected_customers"] = near["oil_homes"] * near["dealer_share"]
    area = near[near["expected_customers"] >= MIN_CUSTOMERS]
    area = pd.DataFrame(area.drop(columns="geometry"))[[
        "GEOID", "latitude", "longitude", "miles_from_depot", "homes", "oil_homes", "dealer_share",
        "expected_customers"]].round({"miles_from_depot": 2, "dealer_share": 4, "expected_customers": 2})
    area.sort_values("miles_from_depot").to_csv(OUT / "service_area.csv", index=False)
    print(f"  {depot['name']} ({depot.town}): {len(area)} block groups within {SERVICE_RADIUS_MI} mi, "
          f"{area['expected_customers'].sum():,.0f} expected oil customers "
          f"(of {area['oil_homes'].sum():,} oil homes there)")
    return area


if __name__ == "__main__":
    run()
