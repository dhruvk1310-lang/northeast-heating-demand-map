"""Put NOAA degree days on the same county geography as the ACS.

Since 2022 the Census reports Connecticut by 9 planning regions instead of
its 8 old counties, but NOAA still uses the old counties. Each planning region
gets the area-weighted average degree days of the old counties it overlaps.

Outputs:
  data/interim/ct_region_county_crosswalk.csv
  data/interim/degree_days_county.csv  NOAA county degree days with CT on planning regions
"""

import geopandas as gpd
import pandas as pd

from src.config import INTERIM
from src.extract.census_tiger import EQUAL_AREA

MIN_SHARE = 0.001  # drop slivers from boundary mismatches


def crosswalk() -> pd.DataFrame:
    regions = gpd.read_file(INTERIM / "counties_ne.geojson", columns=["county_fips", "state_abbr", "geometry"])
    regions = regions[regions["state_abbr"] == "CT"][["county_fips", "geometry"]].rename(
        columns={"county_fips": "region_fips"})
    legacy = gpd.read_file(INTERIM / "counties_ct_legacy.geojson", columns=["county_fips", "geometry"]).rename(
        columns={"county_fips": "legacy_county_fips"})

    regions, legacy = regions.to_crs(EQUAL_AREA), legacy.to_crs(EQUAL_AREA)
    pieces = gpd.overlay(regions, legacy, how="intersection", keep_geom_type=True)
    pieces["area"] = pieces.geometry.area
    pieces["area_share"] = pieces["area"] / pieces.groupby("region_fips")["area"].transform("sum")
    xw = pieces[pieces["area_share"] >= MIN_SHARE][["region_fips", "legacy_county_fips", "area_share"]].copy()
    xw["area_share"] = xw["area_share"] / xw.groupby("region_fips")["area_share"].transform("sum")
    return xw.sort_values(["region_fips", "area_share"], ascending=[True, False]).reset_index(drop=True)


def run() -> pd.DataFrame:
    xw = crosswalk()
    xw.round({"area_share": 4}).to_csv(INTERIM / "ct_region_county_crosswalk.csv", index=False)
    print(f"  wrote ct_region_county_crosswalk.csv: {xw['region_fips'].nunique()} regions, {len(xw)} links")

    dd = pd.read_csv(INTERIM / "noaa_degree_days_county.csv", dtype={"county_fips": str})
    ct = dd[dd["state_abbr"] == "CT"].merge(xw, left_on="county_fips", right_on="legacy_county_fips")
    for col in ["hdd", "cdd"]:
        ct[col] = ct[col] * ct["area_share"]
    ct = ct.groupby(["region_fips", "year", "month"], as_index=False)[["hdd", "cdd"]].sum()
    ct = ct.rename(columns={"region_fips": "county_fips"}).assign(state_abbr="CT")
    ct[["hdd", "cdd"]] = ct[["hdd", "cdd"]].round(0)

    out = pd.concat([dd[dd["state_abbr"] != "CT"], ct[dd.columns]], ignore_index=True)
    out = out.sort_values(["county_fips", "year", "month"]).reset_index(drop=True)
    out.to_csv(INTERIM / "degree_days_county.csv", index=False)
    print(f"  wrote degree_days_county.csv: {out['county_fips'].nunique()} counties, {len(out):,} rows")
    return out


if __name__ == "__main__":
    run()
