"""EIA State Energy Data System (SEDS): residential fuel oil and propane use.

Used later to calibrate the demand model against reported state totals.

Output: data/interim/eia_seds_residential.csv (state x year x fuel)
"""

import pandas as pd

from src.config import INTERIM, STATE_NAMES
from src.extract.download import fetch

START_YEAR = 2010
GALLONS_PER_BARREL = 42

# SEDS series codes: physical units are thousand barrels, Btu units are billion Btu.
SERIES = {
    "DFRCP": ("distillate_fuel_oil", "kbbl"),
    "KSRCP": ("kerosene", "kbbl"),
    "PQRCP": ("propane", "kbbl"),
    "DFRCB": ("distillate_fuel_oil", "billion_btu"),
    "KSRCB": ("kerosene", "billion_btu"),
    "PQRCB": ("propane", "billion_btu"),
}


def run() -> pd.DataFrame:
    seds = pd.read_csv(fetch("seds"), dtype={"Year": int})
    seds = seds[seds["MSN"].isin(SERIES) & seds["StateCode"].isin(STATE_NAMES) & (seds["Year"] >= START_YEAR)]

    seds = seds.assign(
        fuel=seds["MSN"].map(lambda m: SERIES[m][0]),
        unit=seds["MSN"].map(lambda m: SERIES[m][1]),
    )
    wide = seds.pivot_table(index=["StateCode", "Year", "fuel"], columns="unit", values="Data").reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={"StateCode": "state_abbr", "Year": "year"})
    wide["gallons"] = wide["kbbl"] * 1000 * GALLONS_PER_BARREL
    wide["data_status"] = seds["Data_Status"].iloc[0]
    wide = wide[["state_abbr", "year", "fuel", "kbbl", "gallons", "billion_btu", "data_status"]]
    wide = wide.sort_values(["state_abbr", "fuel", "year"]).reset_index(drop=True)

    dest = INTERIM / "eia_seds_residential.csv"
    wide.to_csv(dest, index=False)
    print(f"  wrote {dest.name}: {len(wide)} rows, {wide['year'].min()} to {wide['year'].max()}")
    return wide


if __name__ == "__main__":
    run()
