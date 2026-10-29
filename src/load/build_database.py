"""Build the SQLite star schema, run the analysis queries, and export Tableau files.

Needs the outputs of src.extract.run_all and src.model.run_all. Run from the project root:
    python -m src.load.build_database

Outputs:
  data/northeast_demand.db               the database (not committed; rebuild with this script)
  data/processed/analysis/<query>.csv    results of each query in sql/analysis
  data/processed/tableau/<view>.csv      each view in sql/views, for Tableau Public
"""

import calendar
import sqlite3
from pathlib import Path

import pandas as pd

from src.config import (
    INTERIM, PROCESSED, ROOT, STATE_DIVISION, STATE_FIPS, STATE_NAMES,
)

DB_PATH = ROOT / "data" / "northeast_demand.db"
SQL = ROOT / "sql"
FIPS = {"county_fips": str, "state_fips": str}
DIVISION_NAMES = {1: "New England", 2: "Middle Atlantic"}
FIRST_DATE, LAST_DATE = (1990, 1), (2026, 12)
NORMALS = (1991, 2020)

# ACS heating fuel columns -> dim_fuel rows.
FUELS = [
    # fuel_id, fuel_name, btu_per_gallon, unit, is_modeled
    ("fuel_oil", "Fuel oil and kerosene", 138_500, "gallon", 1),
    ("propane", "Propane (bottled, tank, or LP gas)", 91_500, "gallon", 1),
    ("utility_gas", "Utility gas", None, None, 0),
    ("electricity", "Electricity", None, None, 0),
    ("wood", "Wood", None, None, 0),
    ("coal", "Coal or coke", None, None, 0),
    ("solar", "Solar energy", None, None, 0),
    ("other_fuel", "Other fuel", None, None, 0),
    ("no_fuel", "No fuel used", None, None, 0),
]
BTU = {f[0]: f[2] for f in FUELS if f[2]}
EIA_FUEL = {"heating_oil": "fuel_oil", "propane": "propane"}
SEDS_FUEL = {"distillate_fuel_oil": "fuel_oil", "kerosene": "fuel_oil", "propane": "propane"}


def date_key(year, month):
    return year * 100 + month


def season(year: int, month: int) -> str:
    start = year if month >= 7 else year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def dims() -> dict[str, pd.DataFrame]:
    state = pd.DataFrame([
        {"state_fips": STATE_FIPS[a], "state_abbr": a, "state_name": STATE_NAMES[a],
         "census_division": DIVISION_NAMES[STATE_DIVISION[a]]}
        for a in STATE_FIPS
    ])
    county = pd.read_csv(INTERIM / "counties_ne.csv", dtype=FIPS)[
        ["county_fips", "state_fips", "county_name", "land_area_sqmi", "latitude", "longitude"]]
    months = pd.period_range(f"{FIRST_DATE[0]}-{FIRST_DATE[1]:02d}", f"{LAST_DATE[0]}-{LAST_DATE[1]:02d}", freq="M")
    date = pd.DataFrame({"year": months.year, "month": months.month})
    date.insert(0, "date_key", date_key(date["year"], date["month"]))
    date["month_name"] = date["month"].map(lambda m: calendar.month_name[m])
    date["heating_season"] = [season(y, m) for y, m in zip(date["year"], date["month"])]
    date["is_heating_month"] = date["month"].isin([10, 11, 12, 1, 2, 3, 4]).astype(int)
    fuel = pd.DataFrame(FUELS, columns=["fuel_id", "fuel_name", "btu_per_gallon", "unit", "is_modeled"])
    return {"dim_state": state, "dim_county": county, "dim_date": date, "dim_fuel": fuel}


def facts() -> dict[str, pd.DataFrame]:
    abbr_to_fips = STATE_FIPS
    out = {}

    acs = pd.read_csv(INTERIM / "acs_households_by_fuel.csv", dtype=FIPS)
    hh = acs.melt(id_vars=["county_fips", "acs_year", "total_occupied"], value_vars=[f[0] for f in FUELS],
                  var_name="fuel_id", value_name="households")
    moe = acs.melt(id_vars="county_fips", value_vars=["fuel_oil_moe", "propane_moe"],
                   var_name="fuel_id", value_name="margin_of_error")
    moe["fuel_id"] = moe["fuel_id"].str.replace("_moe", "")
    hh = hh.merge(moe, on=["county_fips", "fuel_id"], how="left")
    hh["share_of_county_homes"] = (hh["households"] / hh["total_occupied"]).round(4)
    out["fact_households_by_fuel"] = hh[["county_fips", "fuel_id", "acs_year", "households",
                                         "margin_of_error", "share_of_county_homes"]]

    use = pd.read_csv(INTERIM / "model_usage_per_home.csv")
    use = use.melt(id_vars=["state_abbr", "fuel", "recs_source", "recs_sample_n"],
                   value_vars=["gal_space_heat", "gal_base"], var_name="end_use", value_name="gallons_per_home")
    use["end_use"] = use["end_use"].map({"gal_space_heat": "space_heat", "gal_base": "base"})
    use["state_fips"] = use["state_abbr"].map(abbr_to_fips)
    use["fuel_id"] = use["fuel"]
    use["mmbtu_per_home"] = (use["gallons_per_home"] * use["fuel_id"].map(BTU) / 1e6).round(2)
    out["fact_consumption_per_home"] = use[["state_fips", "fuel_id", "end_use", "gallons_per_home",
                                            "mmbtu_per_home", "recs_source", "recs_sample_n"]]

    dd = pd.read_csv(INTERIM / "degree_days_county.csv", dtype=FIPS)
    base = dd[dd["year"].between(*NORMALS)]
    normals = base.groupby(["county_fips", "month"], as_index=False)[["hdd", "cdd"]].mean().round(1)
    dd = dd.merge(normals.rename(columns={"hdd": "hdd_normal", "cdd": "cdd_normal"}), on=["county_fips", "month"])
    dd["date_key"] = date_key(dd["year"], dd["month"])
    out["fact_degree_days"] = dd[["county_fips", "date_key", "hdd", "cdd", "hdd_normal", "cdd_normal"]]

    # Prices: every surveyed month on record, plus the interpolated months the model used.
    raw = pd.read_csv(INTERIM / "eia_fuel_prices.csv", parse_dates=["date"])
    raw = raw[raw["level"] == "state"]
    surveyed = (raw.assign(year=raw["date"].dt.year, month=raw["date"].dt.month)
                .groupby(["geography", "fuel", "year", "month"], as_index=False)["price_per_gallon"].mean())
    surveyed = surveyed.rename(columns={"geography": "state_abbr"})
    surveyed["fuel"] = surveyed["fuel"].map(EIA_FUEL)
    surveyed["price_source"] = "surveyed"
    filled = pd.read_csv(INTERIM / "fuel_prices_monthly.csv")
    filled = filled[filled["price_source"] == "interpolated"]
    prices = pd.concat([surveyed, filled], ignore_index=True)
    prices["state_fips"] = prices["state_abbr"].map(abbr_to_fips)
    prices["date_key"] = date_key(prices["year"], prices["month"])
    prices = prices.rename(columns={"fuel": "fuel_id", "price_per_gallon": "avg_price_per_gallon"})
    prices["avg_price_per_gallon"] = prices["avg_price_per_gallon"].round(3)
    out["fact_fuel_prices"] = prices[["state_fips", "fuel_id", "date_key", "avg_price_per_gallon", "price_source"]]

    demand = pd.read_csv(PROCESSED / "fact_monthly_demand.csv", dtype=FIPS)
    demand["date_key"] = date_key(demand["year"], demand["month"])
    out["fact_monthly_demand"] = demand.rename(columns={"fuel": "fuel_id"})[
        ["county_fips", "fuel_id", "date_key", "homes", "hdd", "est_gallons_uncalibrated",
         "est_gallons", "price_per_gallon", "est_spend"]]

    cool = pd.read_csv(PROCESSED / "fact_monthly_cooling.csv", dtype=FIPS)
    cool["date_key"] = date_key(cool["year"], cool["month"])
    out["fact_monthly_cooling"] = cool[["county_fips", "date_key", "ac_homes", "cdd", "cooling_index"]]

    cs = pd.read_csv(PROCESSED / "county_season_summary.csv", dtype=FIPS)
    cols = ["county_fips", "heating_season", "oil_homes", "propane_homes", "total_occupied", "oil_gallons",
            "propane_gallons", "oil_spend", "propane_spend", "heating_spend", "ac_homes", "cooling_index",
            "peak_month", "heating_pct", "cooling_pct", "year_round_score", "year_round_rank", "quadrant",
            "year_round_score_per_home", "year_round_rank_per_home", "quadrant_per_home"]
    out["fact_county_season"] = cs[cols]

    seds = pd.read_csv(INTERIM / "eia_seds_residential.csv")
    seds["fuel_id"] = seds["fuel"].map(SEDS_FUEL)
    seds = seds.groupby(["state_abbr", "fuel_id", "year"], as_index=False)["gallons"].sum()
    seds["state_fips"] = seds["state_abbr"].map(abbr_to_fips)
    out["fact_reported_consumption"] = seds[["state_fips", "fuel_id", "year", "gallons"]]
    return out


def run_sql_file(con: sqlite3.Connection, path: Path) -> None:
    con.executescript(path.read_text())


def build() -> sqlite3.Connection:
    DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    for path in sorted((SQL / "schema").glob("*.sql")):
        run_sql_file(con, path)

    tables = {**dims(), **facts()}
    for name, df in tables.items():
        cols = ", ".join(df.columns)
        marks = ", ".join("?" for _ in df.columns)
        rows = df.astype(object).where(df.notna(), None).itertuples(index=False, name=None)
        con.executemany(f"INSERT INTO {name} ({cols}) VALUES ({marks})", rows)
        print(f"  loaded {name}: {len(df):,} rows")
    con.commit()

    bad = con.execute("PRAGMA foreign_key_check").fetchall()
    if bad:
        raise ValueError(f"Foreign key violations: {bad[:5]}")

    for path in sorted((SQL / "views").glob("*.sql")):
        run_sql_file(con, path)
    return con


def export(con: sqlite3.Connection) -> None:
    for folder, sub in [("analysis", "analysis"), ("views", "tableau")]:
        dest = PROCESSED / sub
        dest.mkdir(parents=True, exist_ok=True)
        for path in sorted((SQL / folder).glob("*.sql")):
            query = path.read_text() if folder == "analysis" else f"SELECT * FROM {path.stem}"
            df = pd.read_sql_query(query, con)
            df.to_csv(dest / f"{path.stem}.csv", index=False)
            print(f"  wrote {sub}/{path.stem}.csv: {len(df):,} rows")


def main() -> None:
    print("[1/2] Building database")
    con = build()
    print("[2/2] Running analysis queries and exporting views")
    export(con)
    con.close()
    print(f"Done. Database: {DB_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
