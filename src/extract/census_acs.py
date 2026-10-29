"""Census ACS table B25040 (House Heating Fuel) for Northeast counties.

Reads the ACS table-based summary file, which needs no API key.
Output: data/interim/acs_households_by_fuel.csv, one row per county.
"""

import pandas as pd

from src.config import ACS_YEAR, FIPS_TO_ABBR, INTERIM
from src.extract.download import fetch

# B25040 line numbers -> column names.
FUEL_LINES = {
    "001": "total_occupied",
    "002": "utility_gas",
    "003": "propane",  # bottled, tank, or LP gas
    "004": "electricity",
    "005": "fuel_oil",  # fuel oil, kerosene, etc.
    "006": "coal",
    "007": "wood",
    "008": "solar",
    "009": "other_fuel",
    "010": "no_fuel",
}


def run() -> pd.DataFrame:
    path = fetch("acs_b25040")
    raw = pd.read_csv(path, sep="|", dtype={"GEO_ID": str})

    counties = raw[raw["GEO_ID"].str.startswith("0500000US")].copy()
    counties["county_fips"] = counties["GEO_ID"].str[-5:]
    counties["state_fips"] = counties["county_fips"].str[:2]
    counties = counties[counties["state_fips"].isin(FIPS_TO_ABBR)]

    out = counties[["county_fips", "state_fips"]].copy()
    out["state_abbr"] = out["state_fips"].map(FIPS_TO_ABBR)
    for line, name in FUEL_LINES.items():
        out[name] = counties[f"B25040_E{line}"].astype(int)
    # Margins of error for the two fuels this project models.
    out["propane_moe"] = counties["B25040_M003"].astype(int)
    out["fuel_oil_moe"] = counties["B25040_M005"].astype(int)
    out["acs_year"] = f"{ACS_YEAR - 4}-{ACS_YEAR}"

    fuel_cols = [n for n in FUEL_LINES.values() if n != "total_occupied"]
    mismatch = out[out[fuel_cols].sum(axis=1) != out["total_occupied"]]
    if not mismatch.empty:
        raise ValueError(f"Fuel lines do not add up to the total for {len(mismatch)} counties")

    out = out.sort_values("county_fips").reset_index(drop=True)
    dest = INTERIM / "acs_households_by_fuel.csv"
    out.to_csv(dest, index=False)
    print(f"  wrote {dest.name}: {len(out)} counties")
    return out


if __name__ == "__main__":
    run()
