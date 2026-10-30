"""Shape the model outputs into the files the Tableau workbook reads.

Every table carries county_key (e.g. "CT-09110"), a text key Tableau will not
mistake for a number, so Connecticut's leading zero survives the join to the
map file.

Run from the project root (after src.load.build_database):
    python -m src.load.export_tableau

Outputs (tableau/data):
  counties.geojson      simplified county shapes
  county_month.csv      county x month: demand, cooling, thermal load
  seasonal_pulse.csv    region x month x kind: each month's share of the season's heating
                        (positive) or cooling (negative)
  county_scores.csv     county x scoring basis (Total, Per home), latest season
  kpis.csv              headline numbers per heating season, formatted for display
  ct_regions.csv        Connecticut planning region x dealer density (from SQL query 7)
  ct_prospects.csv      Connecticut dealers with fit score and rank (from vw_dealer_opportunity)
"""

import geopandas as gpd
import pandas as pd

from src.config import INTERIM, PROCESSED, ROOT

OUT = ROOT / "tableau" / "data"
FIPS = {"county_fips": str}
SIMPLIFY_DEG = 0.004  # about 400 m; keeps coastlines recognizable at region scale
NORM_PCTL = 0.99  # thermal load is scaled to this percentile, so a few outliers do not wash out the map
SEASON_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
LABELS_PER_BASIS = 6


def key(df: pd.DataFrame) -> pd.Series:
    return df["state_abbr"] + "-" + df["county_fips"]


def counties() -> None:
    gdf = gpd.read_file(INTERIM / "counties_ne.geojson")
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)
    gdf["county_key"] = key(gdf)
    gdf = gdf[["county_key", "county_name", "state_abbr", "geometry"]]
    path = OUT / "counties.geojson"
    gdf.to_file(path, driver="GeoJSON")
    print(f"  wrote {path.name}: {len(gdf)} counties, {path.stat().st_size / 1e6:.1f} MB")


def county_month(homes: pd.Series) -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "tableau" / "vw_county_month_demand.csv", dtype=FIPS)
    df["county_key"] = key(df)
    df["month_date"] = pd.to_datetime(dict(year=df["year"], month=df["month"], day=1))
    df["total_homes"] = df["county_fips"].map(homes)
    df["heating_gallons"] = df["oil_gallons"] + df["propane_gallons"]
    df["heating_gal_per_home"] = df["heating_gallons"] / df["total_homes"]
    df["cooling_per_home"] = df["cooling_index"] / df["total_homes"]
    heat = (df["heating_gal_per_home"] / df["heating_gal_per_home"].quantile(NORM_PCTL)).clip(upper=1)
    cool = (df["cooling_per_home"] / df["cooling_per_home"].quantile(NORM_PCTL)).clip(upper=1)
    # +1 = all heating load, -1 = all cooling load, 0 = neither (spring and fall).
    df["thermal_load"] = (heat - cool).round(3)
    # Matches the dashboard's Month parameter values, e.g. "January 2026".
    df["month_label"] = df["month_date"].dt.strftime("%B %Y")
    cols = ["county_key", "county_name", "state_abbr", "month_date", "heating_season", "month_name",
            "total_homes", "oil_homes", "propane_homes", "oil_gallons", "propane_gallons", "heating_gallons",
            "heating_spend", "hdd", "cdd", "cooling_index", "heating_gal_per_home", "cooling_per_home",
            "thermal_load", "month_label"]
    df = df[cols].round({"heating_gal_per_home": 2, "cooling_per_home": 1})
    df.to_csv(OUT / "county_month.csv", index=False)
    print(f"  wrote county_month.csv: {len(df):,} rows")
    return df


def seasonal_pulse(cm: pd.DataFrame) -> None:
    g = cm.assign(month=cm["month_date"].dt.month).groupby(["heating_season", "month", "month_name"], as_index=False)[
        ["heating_gallons", "heating_spend", "cooling_index"]].sum()
    by = g.groupby("heating_season")
    g["heating_share"] = (g["heating_gallons"] / by["heating_gallons"].transform("sum")).round(4)
    # Negative so the cooling bars hang below the axis, mirroring the heating bars.
    g["cooling_share"] = -(g["cooling_index"] / by["cooling_index"].transform("sum")).round(4)
    g["month_order"] = g["month"].map({m: i for i, m in enumerate(SEASON_MONTHS, 1)})
    g["month_abbr"] = g["month_name"].str[:3]
    start_year = g["heating_season"].str[:4].astype(int)
    g["month_date"] = pd.to_datetime(dict(year=start_year.where(g["month"] >= 7, start_year + 1),
                                          month=g["month"], day=1))
    # Long format: one row per month and kind, so Tableau needs only one measure and a color.
    long = pd.concat([
        g.assign(kind="Heating", share=g["heating_share"]),
        g.assign(kind="Cooling", share=g["cooling_share"]),
    ])
    long["month_label"] = long["month_date"].dt.strftime("%B %Y")
    long = long[["heating_season", "month_date", "month_order", "month_abbr", "kind", "share",
                 "heating_gallons", "heating_spend", "cooling_index", "month_label"]]
    long = long.sort_values(["heating_season", "month_order", "kind"])
    long.to_csv(OUT / "seasonal_pulse.csv", index=False)
    print(f"  wrote seasonal_pulse.csv: {len(long)} rows")


def county_scores() -> None:
    s = pd.read_csv(PROCESSED / "county_season_summary.csv", dtype=FIPS)
    s = s[s["heating_season"] == s["heating_season"].max()].copy()
    s["county_key"] = key(s)
    common = ["county_key", "county_name", "state_abbr", "heating_season", "total_occupied", "oil_homes",
              "propane_homes", "oil_propane_share", "heating_spend", "cooling_index"]
    frames = []
    for basis, suffix in [("Total", ""), ("Per home", "_per_home")]:
        f = s[common].copy()
        f["basis"] = basis
        f["heating_pct"] = s[f"heating_pct{suffix}"]
        f["cooling_pct"] = s[f"cooling_pct{suffix}"]
        f["year_round_score"] = s[f"year_round_score{suffix}"]
        f["year_round_rank"] = s[f"year_round_rank{suffix}"]
        f["quadrant"] = s[f"quadrant{suffix}"]
        f["label"] = f["county_name"].str.replace(" Planning Region", "", regex=False).str.replace(
            " County", "", regex=False) + ", " + f["state_abbr"]
        f.loc[f["year_round_rank"] > LABELS_PER_BASIS, "label"] = ""
        frames.append(f)
    out = pd.concat(frames, ignore_index=True)
    out["heating_spend_per_home"] = (out["heating_spend"] / out["total_occupied"]).round(0)
    out.to_csv(OUT / "county_scores.csv", index=False)
    print(f"  wrote county_scores.csv: {len(out)} rows")


def kpis(cm: pd.DataFrame) -> None:
    g = cm.groupby("heating_season")
    k = pd.DataFrame({
        "total_spend_b": (g["heating_spend"].sum() / 1e9).round(1),
        "oil_gallons_b": (g["oil_gallons"].sum() / 1e9).round(2),
        "propane_gallons_b": (g["propane_gallons"].sum() / 1e9).round(2),
        "oil_homes_m": (g["oil_homes"].sum() / 12 / 1e6).round(2),
    }).reset_index()
    peak = cm.groupby(["heating_season", "month_name"], as_index=False)["heating_gallons"].sum()
    peak = peak.loc[peak.groupby("heating_season")["heating_gallons"].idxmax(), ["heating_season", "month_name"]]
    k = k.merge(peak.rename(columns={"month_name": "peak_month"}), on="heating_season")
    # One row per headline number, already formatted, so the dashboard shows them as a strip.
    rows = []
    for r in k.itertuples():
        rows += [
            (r.heating_season, 1, f"${r.total_spend_b:.1f}B", "heating oil + propane spend"),
            (r.heating_season, 2, f"{r.oil_gallons_b:.1f}B gal", "of heating oil"),
            (r.heating_season, 3, f"{r.propane_gallons_b:.1f}B gal", "of propane"),
            (r.heating_season, 4, r.peak_month[:3], "peak month for fuel demand"),
        ]
    out = pd.DataFrame(rows, columns=["heating_season", "kpi_order", "kpi_value", "kpi_label"])
    out.to_csv(OUT / "kpis.csv", index=False)
    print(f"  wrote kpis.csv: {len(out)} rows")


def ct_dealers() -> None:
    def short_region(s: pd.Series) -> pd.Series:
        return s.str.replace("Connecticut", "CT", regex=False)

    regions = pd.read_csv(PROCESSED / "analysis" / "07_dealer_density.csv")
    regions["region"] = short_region(regions["region"])
    regions.to_csv(OUT / "ct_regions.csv", index=False)
    p = pd.read_csv(PROCESSED / "tableau" / "vw_dealer_opportunity.csv")
    p["region"] = short_region(p["region"])
    p["fit_score"] = (p["fit_score"] * 100).round(1)
    short_name = p["name"].str.replace(r"\s+(Inc|Llc|Co|Corp|Company|Corporation)\.?$", "", regex=True)
    p["label"] = p["prospect_rank"].astype(str) + ". " + short_name + ", " + p["town"]
    p = p[["prospect_rank", "label", "name", "town", "region", "offers_hvac_service", "years_licensed",
           "region_homes_per_dealer", "fit_score"]].sort_values("prospect_rank")
    p.to_csv(OUT / "ct_prospects.csv", index=False)
    print(f"  wrote ct_regions.csv: {len(regions)} regions; ct_prospects.csv: {len(p)} dealers")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    acs = pd.read_csv(INTERIM / "acs_households_by_fuel.csv", dtype=FIPS)
    homes = acs.set_index("county_fips")["total_occupied"]
    counties()
    cm = county_month(homes)
    seasonal_pulse(cm)
    county_scores()
    kpis(cm)
    ct_dealers()


if __name__ == "__main__":
    main()
