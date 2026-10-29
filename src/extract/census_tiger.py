"""Census cartographic boundary files for Northeast counties.

Two vintages are saved:
  - current (2024), with Connecticut's 9 planning regions, matching the ACS
  - 2020, with Connecticut's 8 old counties, matching NOAA's degree days

Outputs:
  data/interim/counties_ne.geojson
  data/interim/counties_ct_legacy.geojson
  data/interim/counties_ne.csv  (attributes and centroids, no geometry)
"""

import geopandas as gpd
import pandas as pd

from src.config import FIPS_TO_ABBR, INTERIM
from src.extract.download import fetch

EQUAL_AREA = "EPSG:5070"  # CONUS Albers, for areas and centroids


def _load(key: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(f"zip://{fetch(key)}")
    gdf = gdf[gdf["STATEFP"].isin(FIPS_TO_ABBR)].copy()
    gdf = gdf.rename(columns={"GEOID": "county_fips", "STATEFP": "state_fips", "NAMELSAD": "county_name"})
    gdf["state_abbr"] = gdf["state_fips"].map(FIPS_TO_ABBR)
    projected = gdf.to_crs(EQUAL_AREA)
    gdf["land_area_sqmi"] = (gdf["ALAND"] / 2_589_988.11).round(1)
    centroids = projected.geometry.representative_point().to_crs("EPSG:4326")
    gdf["latitude"] = centroids.y.round(5)
    gdf["longitude"] = centroids.x.round(5)
    cols = ["county_fips", "state_fips", "state_abbr", "county_name",
            "land_area_sqmi", "latitude", "longitude", "geometry"]
    return gdf[cols].sort_values("county_fips").reset_index(drop=True)


def run() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    current = _load("tiger_county")
    legacy_ct = _load("tiger_county_ct_legacy")
    legacy_ct = legacy_ct[legacy_ct["state_abbr"] == "CT"].reset_index(drop=True)

    current.to_file(INTERIM / "counties_ne.geojson", driver="GeoJSON")
    legacy_ct.to_file(INTERIM / "counties_ct_legacy.geojson", driver="GeoJSON")
    pd.DataFrame(current.drop(columns="geometry")).to_csv(INTERIM / "counties_ne.csv", index=False)
    print(f"  wrote counties_ne.geojson and counties_ne.csv: {len(current)} counties")
    print(f"  wrote counties_ct_legacy.geojson: {len(legacy_ct)} old Connecticut counties")
    return current, legacy_ct


if __name__ == "__main__":
    run()
