"""EIA Residential Energy Consumption Survey (RECS) 2020 microdata.

Builds weighted averages of annual fuel use per home for homes whose main
heating fuel is fuel oil or propane, split by end use, plus the share of
homes with air conditioning.

RECS samples few propane homes in some Northeast states, so the same figures
are also given for the two Census divisions. sample_n lets the model fall
back to the division value when a state's sample is too small.

Outputs:
  data/interim/recs_fuel_use_per_home.csv  geography x fuel
  data/interim/recs_ac_share.csv           geography
"""

import pandas as pd

from src.config import FIPS_TO_ABBR, INTERIM, STATE_DIVISION
from src.extract.download import fetch

# RECS FUELHEAT codes for the main space heating fuel.
FUELS = {
    "fuel_oil": {"code": 3, "prefix": "GALLONFO"},
    "propane": {"code": 2, "prefix": "GALLONLP"},
}
DIVISION_NAMES = {1: "New England", 2: "Middle Atlantic"}  # RECS stores DIVISION as these names


def _weighted(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    w = df["NWEIGHT"]
    out = {c: (df[c] * w).sum() / w.sum() for c in cols}
    out["sample_n"] = len(df)
    out["weighted_homes"] = w.sum()
    return pd.Series(out)


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = fetch("recs_2020")
    cols = ["STATE_FIPS", "DIVISION", "NWEIGHT", "FUELHEAT", "AIRCOND"]
    for f in FUELS.values():
        p = f["prefix"]
        cols += [p, f"{p}SPH", f"{p}WTH"]
    recs = pd.read_csv(path, usecols=cols)
    recs["state_fips"] = recs["STATE_FIPS"].astype(int).astype(str).str.zfill(2)
    recs = recs[recs["state_fips"].isin(FIPS_TO_ABBR)].copy()
    recs["state_abbr"] = recs["state_fips"].map(FIPS_TO_ABBR)

    # Every Northeast state must sit in the division config expects.
    check = recs.groupby("state_abbr")["DIVISION"].first().to_dict()
    assert all(check[s] == DIVISION_NAMES[STATE_DIVISION[s]] for s in check), check

    groups = [("state", "state_abbr"), ("division", "DIVISION")]

    rows = []
    for fuel, f in FUELS.items():
        p = f["prefix"]
        homes = recs[recs["FUELHEAT"] == f["code"]]
        for level, col in groups:
            g = homes.groupby(col).apply(_weighted, cols=[p, f"{p}SPH", f"{p}WTH"], include_groups=False)
            g = g.rename(columns={p: "gal_total", f"{p}SPH": "gal_space_heat", f"{p}WTH": "gal_water_heat"})
            g["level"] = level
            g["fuel"] = fuel
            rows.append(g.reset_index(names="geography"))
    use = pd.concat(rows, ignore_index=True)
    # Base load: everything that is not space heating (water heating, cooking, dryers, other).
    use["gal_base"] = use["gal_total"] - use["gal_space_heat"]
    use = use[["level", "geography", "fuel", "sample_n", "weighted_homes",
               "gal_total", "gal_space_heat", "gal_water_heat", "gal_base"]]
    use = use.round({"weighted_homes": 0, "gal_total": 1, "gal_space_heat": 1, "gal_water_heat": 1, "gal_base": 1})

    ac_rows = []
    for level, col in groups:
        g = recs.groupby(col).apply(
            lambda d: pd.Series({
                "sample_n": len(d),
                "ac_share": (d["NWEIGHT"] * (d["AIRCOND"] == 1)).sum() / d["NWEIGHT"].sum(),
            }),
            include_groups=False,
        )
        g["level"] = level
        ac_rows.append(g.reset_index(names="geography"))
    ac = pd.concat(ac_rows, ignore_index=True)[["level", "geography", "sample_n", "ac_share"]]
    ac["sample_n"] = ac["sample_n"].astype(int)
    ac["ac_share"] = ac["ac_share"].round(3)

    use.to_csv(INTERIM / "recs_fuel_use_per_home.csv", index=False)
    ac.to_csv(INTERIM / "recs_ac_share.csv", index=False)
    print(f"  wrote recs_fuel_use_per_home.csv: {len(use)} rows")
    print(f"  wrote recs_ac_share.csv: {len(ac)} rows")
    return use, ac


if __name__ == "__main__":
    run()
