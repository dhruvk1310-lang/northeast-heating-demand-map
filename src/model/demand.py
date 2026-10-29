"""County monthly demand model for heating oil, propane, and AC.

For each county, fuel, and month:

    gallons = homes x (gal_per_hdd x HDD(county, month) + base_gal / 12)

gal_per_hdd turns RECS space heating use into gallons per heating degree day:
RECS reports use for 2020, so it is divided by 2020's degree days for the
same homes. Colder counties and colder winters then burn more fuel.

Gallons are calibrated to EIA SEDS state totals (see calibrate) and priced
with monthly state prices.

Cooling has no gallons, so it is an index:

    cooling_index = homes with AC x CDD(county, month)

Outputs (data/processed):
  fact_monthly_demand.csv   county x fuel x month
  fact_monthly_cooling.csv  county x month
  calibration.csv           state x fuel
"""

import pandas as pd

from src.config import (
    FIRST_SEASON, INTERIM, LAST_SEASON, MIN_RECS_SAMPLE, PROCESSED, RECS_YEAR, STATE_DIVISION,
)
from src.model import prices

FUELS = ["fuel_oil", "propane"]
DIVISION_NAMES = {1: "New England", 2: "Middle Atlantic"}
# SEDS series that match each ACS fuel category (ACS "fuel oil" includes kerosene).
SEDS_FUELS = {"fuel_oil": ["distillate_fuel_oil", "kerosene"], "propane": ["propane"]}


def season_label(year: pd.Series, month: pd.Series) -> pd.Series:
    start = year.where(month >= 7, year - 1)
    return start.astype(str) + "-" + ((start + 1) % 100).astype(str).str.zfill(2)


def load_inputs() -> dict[str, pd.DataFrame]:
    fips = {"county_fips": str}
    acs = pd.read_csv(INTERIM / "acs_households_by_fuel.csv", dtype=fips)
    dd = pd.read_csv(INTERIM / "degree_days_county.csv", dtype=fips)
    recs = pd.read_csv(INTERIM / "recs_fuel_use_per_home.csv")
    ac = pd.read_csv(INTERIM / "recs_ac_share.csv")
    seds = pd.read_csv(INTERIM / "eia_seds_residential.csv")
    return {"acs": acs, "dd": dd, "recs": recs, "ac": ac, "seds": seds}


def homes_long(acs: pd.DataFrame) -> pd.DataFrame:
    long = acs.melt(id_vars=["county_fips", "state_abbr"], value_vars=FUELS, var_name="fuel", value_name="homes")
    return long


def usage_per_home(recs: pd.DataFrame, homes: pd.DataFrame, dd: pd.DataFrame) -> pd.DataFrame:
    """Gallons per heating degree day and base gallons per home, by state and fuel."""
    ref = dd[dd["year"] == RECS_YEAR].groupby("county_fips", as_index=False)["hdd"].sum()
    ref = homes.merge(ref, on="county_fips")
    ref["division"] = ref["state_abbr"].map(STATE_DIVISION).map(DIVISION_NAMES)

    def weighted_hdd(by: str) -> pd.Series:
        g = ref.groupby([by, "fuel"])
        return g.apply(lambda d: (d["hdd"] * d["homes"]).sum() / d["homes"].sum(), include_groups=False)

    hdd_state, hdd_div = weighted_hdd("state_abbr"), weighted_hdd("division")

    rows = []
    for state, div_num in STATE_DIVISION.items():
        division = DIVISION_NAMES[div_num]
        for fuel in FUELS:
            st = recs[(recs["level"] == "state") & (recs["geography"] == state) & (recs["fuel"] == fuel)].iloc[0]
            use_division = st["sample_n"] < MIN_RECS_SAMPLE
            if use_division:
                src = recs[(recs["level"] == "division") & (recs["geography"] == division)
                           & (recs["fuel"] == fuel)].iloc[0]
                ref_hdd = hdd_div[(division, fuel)]
            else:
                src, ref_hdd = st, hdd_state[(state, fuel)]
            rows.append({
                "state_abbr": state,
                "fuel": fuel,
                "recs_source": division if use_division else state,
                "recs_sample_n": int(src["sample_n"]),
                "gal_space_heat": src["gal_space_heat"],
                "gal_base": src["gal_base"],
                "ref_hdd": round(ref_hdd, 0),
                "gal_per_hdd": src["gal_space_heat"] / ref_hdd,
            })
    return pd.DataFrame(rows)


def monthly_demand(homes: pd.DataFrame, usage: pd.DataFrame, dd: pd.DataFrame) -> pd.DataFrame:
    dd = dd.copy()
    dd["heating_season"] = season_label(dd["year"], dd["month"])
    seasons = [f"{y}-{(y + 1) % 100:02d}" for y in range(FIRST_SEASON, LAST_SEASON + 1)]
    dd = dd[dd["heating_season"].isin(seasons)]
    if dd.groupby("county_fips").size().nunique() != 1 or len(dd) != dd["county_fips"].nunique() * 12 * len(seasons):
        raise ValueError("Degree days are missing for some county-months in the model window")

    df = homes.merge(usage[["state_abbr", "fuel", "gal_per_hdd", "gal_base"]], on=["state_abbr", "fuel"])
    df = df.merge(dd[["county_fips", "year", "month", "heating_season", "hdd"]], on="county_fips")
    df["gal_space_heat"] = df["homes"] * df["gal_per_hdd"] * df["hdd"]
    df["gal_base"] = df["homes"] * df["gal_base"] / 12
    df["est_gallons_uncalibrated"] = df["gal_space_heat"] + df["gal_base"]
    return df.drop(columns=["gal_per_hdd"])


def calibrate(demand: pd.DataFrame, seds: pd.DataFrame) -> pd.DataFrame:
    """Scale factor per state and fuel: SEDS gallons / modeled gallons, over shared calendar years."""
    model_years = demand.groupby("year")["month"].nunique()
    full_years = set(model_years[model_years == 12].index) & set(seds["year"])
    if not full_years:
        raise ValueError("No calendar year is covered by both the model and SEDS")

    modeled = (demand[demand["year"].isin(full_years)]
               .groupby(["state_abbr", "fuel"])["est_gallons_uncalibrated"].sum())
    rows = []
    for fuel, seds_fuels in SEDS_FUELS.items():
        reported = seds[seds["fuel"].isin(seds_fuels) & seds["year"].isin(full_years)].groupby("state_abbr")["gallons"].sum()
        for state, gallons in reported.items():
            m = modeled[(state, fuel)]
            rows.append({
                "state_abbr": state, "fuel": fuel,
                "years": f"{min(full_years)}-{max(full_years)}",
                "modeled_gallons": round(m), "seds_gallons": round(gallons),
                "factor": gallons / m,
            })
    cal = pd.DataFrame(rows)
    cal["pct_error_before"] = ((cal["modeled_gallons"] / cal["seds_gallons"] - 1) * 100).round(1)
    cal["factor"] = cal["factor"].round(4)
    return cal


def cooling(acs: pd.DataFrame, ac: pd.DataFrame, dd: pd.DataFrame) -> pd.DataFrame:
    share = ac[ac["level"] == "state"].set_index("geography")["ac_share"]
    df = acs[["county_fips", "state_abbr", "total_occupied"]].copy()
    df["ac_homes"] = (df["total_occupied"] * df["state_abbr"].map(share)).round(0)
    dd = dd.copy()
    dd["heating_season"] = season_label(dd["year"], dd["month"])
    seasons = [f"{y}-{(y + 1) % 100:02d}" for y in range(FIRST_SEASON, LAST_SEASON + 1)]
    df = df.merge(dd[dd["heating_season"].isin(seasons)][["county_fips", "year", "month", "heating_season", "cdd"]],
                  on="county_fips")
    df["cooling_index"] = df["ac_homes"] * df["cdd"]
    return df[["county_fips", "state_abbr", "year", "month", "heating_season", "ac_homes", "cdd", "cooling_index"]]


def run() -> dict[str, pd.DataFrame]:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    inp = load_inputs()
    homes = homes_long(inp["acs"])
    usage = usage_per_home(inp["recs"], homes, inp["dd"])
    usage.round({"gal_per_hdd": 5}).to_csv(INTERIM / "model_usage_per_home.csv", index=False)
    print(f"  usage per home: {(usage['recs_source'].str.len() > 2).sum()} state-fuel pairs use the division average")

    demand = monthly_demand(homes, usage, inp["dd"])
    cal = calibrate(demand, inp["seds"])
    demand = demand.merge(cal[["state_abbr", "fuel", "factor"]], on=["state_abbr", "fuel"])
    demand["est_gallons"] = demand["est_gallons_uncalibrated"] * demand["factor"]

    start = f"{FIRST_SEASON}-07"
    end = f"{LAST_SEASON + 1}-06"
    price = prices.run(start, end)
    demand = demand.merge(price, on=["state_abbr", "fuel", "year", "month"], how="left")
    demand["est_spend"] = demand["est_gallons"] * demand["price_per_gallon"]

    cols = ["county_fips", "state_abbr", "fuel", "year", "month", "heating_season", "homes", "hdd",
            "est_gallons_uncalibrated", "est_gallons", "price_per_gallon", "price_source", "est_spend"]
    demand = demand[cols].sort_values(["county_fips", "fuel", "year", "month"]).reset_index(drop=True)
    demand = demand.round({"est_gallons_uncalibrated": 0, "est_gallons": 0, "est_spend": 0})
    cool = cooling(inp["acs"], inp["ac"], inp["dd"]).sort_values(["county_fips", "year", "month"])

    demand.to_csv(PROCESSED / "fact_monthly_demand.csv", index=False)
    cool.to_csv(PROCESSED / "fact_monthly_cooling.csv", index=False)
    cal.to_csv(PROCESSED / "calibration.csv", index=False)
    print(f"  wrote fact_monthly_demand.csv: {len(demand):,} rows")
    print(f"  wrote fact_monthly_cooling.csv: {len(cool):,} rows")
    print(f"  wrote calibration.csv: factors {cal['factor'].min():.2f} to {cal['factor'].max():.2f}")
    return {"demand": demand, "cooling": cool, "calibration": cal, "usage": usage}


if __name__ == "__main__":
    run()
