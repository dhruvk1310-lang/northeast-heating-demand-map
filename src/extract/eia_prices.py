"""EIA State Heating Oil and Propane Program (SHOPP) residential prices.

The weekly file reports each state, weekly from October to March. Summer
coverage is thin: April and September have some state data, and June to
August only exists for 2024. The monthly files give regional averages
(PADD 1A New England, PADD 1B Central Atlantic) for September to April, a
fallback when a state value is missing. May to August prices are filled in
the model step (see docs/assumptions.md).

Output: data/interim/eia_fuel_prices.csv
  (date, level, geography, fuel, frequency, price per gallon)
"""

import warnings

import pandas as pd

from src.config import INTERIM, STATE_DIVISION, STATE_NAMES
from src.extract.download import fetch

SOURCES = [
    ("shopp_heating_oil", "heating_oil", "weekly"),
    ("shopp_propane", "propane", "weekly"),
    ("shopp_heating_oil_monthly", "heating_oil", "monthly"),
    ("shopp_propane_monthly", "propane", "monthly"),
]
# Census division -> EIA PADD subdistrict used for monthly regional prices.
PADD = {1: ("PADD 1A", "New England (PADD 1A)"), 2: ("PADD 1B", "Central Atlantic (PADD 1B)")}


def padd_for_state(abbr: str) -> str:
    """The PADD subdistrict whose monthly prices stand in for a state in summer."""
    return PADD[STATE_DIVISION[abbr]][0]


def _read(key: str) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # xlrd deprecation notice
        df = pd.read_excel(fetch(key), sheet_name="Data 1", header=2)
    return df


def run() -> pd.DataFrame:
    frames = []
    for key, fuel, freq in SOURCES:
        df = _read(key)
        if freq == "weekly":
            targets = [("state", abbr, name) for abbr, name in STATE_NAMES.items()]
        else:
            targets = [("padd", code, label) for code, label in PADD.values()]
        for level, geo, label in targets:
            matches = [c for c in df.columns if c.startswith(f"Weekly {label} ") or c.startswith(f"{label} ")]
            if len(matches) != 1:
                raise ValueError(f"{key}: expected one column for {label}, found {matches}")
            part = df[["Date", matches[0]]].rename(columns={"Date": "date", matches[0]: "price_per_gallon"})
            frames.append(part.assign(level=level, geography=geo, fuel=fuel, frequency=freq))

    out = pd.concat(frames, ignore_index=True).dropna(subset=["price_per_gallon"])
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out = out[["date", "level", "geography", "fuel", "frequency", "price_per_gallon"]]
    out = out.sort_values(["fuel", "level", "geography", "date"]).reset_index(drop=True)

    dest = INTERIM / "eia_fuel_prices.csv"
    out.to_csv(dest, index=False)
    span = out.groupby("frequency")["date"].agg(["min", "max"])
    print(f"  wrote {dest.name}: {len(out):,} rows")
    for freq, r in span.iterrows():
        print(f"    {freq}: {r['min']} to {r['max']}")
    return out


if __name__ == "__main__":
    run()
