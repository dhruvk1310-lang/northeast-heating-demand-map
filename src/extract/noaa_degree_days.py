"""NOAA nClimDiv monthly heating and cooling degree days, by county and by state.

Outputs:
  data/interim/noaa_degree_days_county.csv  county x year x month
  data/interim/noaa_degree_days_state.csv   state x year x month

NOAA still reports Connecticut by its 8 pre-2022 counties. The transform step
src/transform/ct_planning_regions.py maps them to the planning regions that
the Census now uses.
"""

import pandas as pd

from src.config import DEGREE_DAY_START_YEAR, FIPS_TO_ABBR, INTERIM, NCEI_TO_FIPS, NOAA_CLIMDIV, RAW
from src.extract.download import download, latest_climdiv_file

MISSING = -9999.0
MONTH_COLS = list(range(1, 13))


def _read(element: str) -> pd.DataFrame:
    name = latest_climdiv_file(element)
    path = download(NOAA_CLIMDIV + name, RAW / "noaa" / f"{name}.txt")
    df = pd.read_csv(path, sep=r"\s+", header=None, names=["code", *MONTH_COLS], dtype={"code": str})
    return df


def _tidy(df: pd.DataFrame, id_col: str, value_name: str) -> pd.DataFrame:
    long = df.melt(id_vars=[id_col, "year"], value_vars=MONTH_COLS, var_name="month", value_name=value_name)
    long = long[long[value_name] != MISSING]  # months not yet published
    long["month"] = long["month"].astype(int)
    return long


def county(element: str, value_name: str) -> pd.DataFrame:
    # Code layout: NCEI state (2) + county FIPS (3) + element (2) + year (4).
    df = _read(element)
    df["ncei_state"] = df["code"].str[:2]
    df = df[df["ncei_state"].isin(NCEI_TO_FIPS)].copy()
    df["county_fips"] = df["ncei_state"].map(NCEI_TO_FIPS) + df["code"].str[2:5]
    df["year"] = df["code"].str[7:11].astype(int)
    df = df[df["year"] >= DEGREE_DAY_START_YEAR]
    return _tidy(df, "county_fips", value_name)


def state(element: str, value_name: str) -> pd.DataFrame:
    # Code layout: NCEI state (3) + division (1, 0 = statewide) + element (2) + year (4).
    df = _read(element)
    df["ncei_state"] = df["code"].str[1:3]
    df = df[df["ncei_state"].isin(NCEI_TO_FIPS) & (df["code"].str[0] == "0")].copy()
    df["state_fips"] = df["ncei_state"].map(NCEI_TO_FIPS)
    df["year"] = df["code"].str[6:10].astype(int)
    df = df[df["year"] >= DEGREE_DAY_START_YEAR]
    return _tidy(df, "state_fips", value_name)


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = ["year", "month"]

    cty = county("hddccy", "hdd").merge(county("cddccy", "cdd"), on=["county_fips", *keys], how="outer")
    cty["state_abbr"] = cty["county_fips"].str[:2].map(FIPS_TO_ABBR)
    cty = cty[["county_fips", "state_abbr", *keys, "hdd", "cdd"]].sort_values(["county_fips", *keys])

    st = state("hddcst", "hdd").merge(state("cddcst", "cdd"), on=["state_fips", *keys], how="outer")
    st["state_abbr"] = st["state_fips"].map(FIPS_TO_ABBR)
    st = st[["state_fips", "state_abbr", *keys, "hdd", "cdd"]].sort_values(["state_fips", *keys])

    for df, name in [(cty, "noaa_degree_days_county.csv"), (st, "noaa_degree_days_state.csv")]:
        df.to_csv(INTERIM / name, index=False)
        latest = df.sort_values(keys).iloc[-1]
        print(f"  wrote {name}: {len(df):,} rows, through {int(latest.year)}-{int(latest.month):02d}")
    return cty, st


if __name__ == "__main__":
    run()
