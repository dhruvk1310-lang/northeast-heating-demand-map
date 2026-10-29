"""County summary for the latest heating season, year-round score, and sensitivity check.

year_round_score = w_heat x percentile(heating spend) + w_cool x percentile(cooling index)

The baseline scores market size (totals), as the README plans. Because both
totals grow with the number of homes, a per-home variant is also tested to
show how much of the ranking is just county size.

Outputs (data/processed):
  county_season_summary.csv  county x heating season, with both scores
  sensitivity_scores.csv     one row per scenario
"""

import pandas as pd

from src.config import INTERIM, LAST_SEASON, PROCESSED, SCORE_WEIGHTS

TOP_N = 25
QUADRANT_CUTOFF = 0.5


def season_summary() -> pd.DataFrame:
    fips = {"county_fips": str}
    demand = pd.read_csv(PROCESSED / "fact_monthly_demand.csv", dtype=fips)
    cool = pd.read_csv(PROCESSED / "fact_monthly_cooling.csv", dtype=fips)
    counties = pd.read_csv(INTERIM / "counties_ne.csv", dtype=fips)[["county_fips", "county_name"]]
    acs = pd.read_csv(INTERIM / "acs_households_by_fuel.csv", dtype=fips)[["county_fips", "total_occupied"]]

    keys = ["county_fips", "state_abbr", "heating_season"]
    fuel = demand.pivot_table(index=keys, columns="fuel", values=["homes", "est_gallons", "est_spend"],
                              aggfunc={"homes": "first", "est_gallons": "sum", "est_spend": "sum"})
    fuel.columns = [f"{fuel_name}_{measure}" for measure, fuel_name in fuel.columns]
    fuel = fuel.reset_index()
    fuel["heating_spend"] = fuel["fuel_oil_est_spend"] + fuel["propane_est_spend"]
    cooling = cool.groupby(keys, as_index=False).agg(ac_homes=("ac_homes", "first"),
                                                     cooling_index=("cooling_index", "sum"))
    peak = demand.groupby(keys + ["month"], as_index=False)["est_gallons"].sum()
    peak = peak.loc[peak.groupby(keys)["est_gallons"].idxmax(), keys + ["month"]].rename(
        columns={"month": "peak_month"})

    s = fuel.merge(cooling, on=keys).merge(peak, on=keys).merge(counties, on="county_fips").merge(acs, on="county_fips")
    s = s.rename(columns={"fuel_oil_homes": "oil_homes", "propane_homes": "propane_homes",
                          "fuel_oil_est_gallons": "oil_gallons", "propane_est_gallons": "propane_gallons",
                          "fuel_oil_est_spend": "oil_spend", "propane_est_spend": "propane_spend"})
    s["oil_propane_share"] = (s["oil_homes"] + s["propane_homes"]) / s["total_occupied"]
    return s


def add_scores(s: pd.DataFrame, w_heat: float, w_cool: float, per_home: bool = False) -> pd.DataFrame:
    s = s.copy()
    heat, cool = s["heating_spend"], s["cooling_index"]
    if per_home:
        heat, cool = heat / s["total_occupied"], cool / s["total_occupied"]
    by = s["heating_season"]
    s["heating_pct"] = heat.groupby(by).rank(pct=True)
    s["cooling_pct"] = cool.groupby(by).rank(pct=True)
    s["year_round_score"] = w_heat * s["heating_pct"] + w_cool * s["cooling_pct"]
    s["year_round_rank"] = s.groupby(by)["year_round_score"].rank(ascending=False, method="min").astype(int)
    hi_h, hi_c = s["heating_pct"] >= QUADRANT_CUTOFF, s["cooling_pct"] >= QUADRANT_CUTOFF
    s["quadrant"] = "Low demand"
    s.loc[hi_h & ~hi_c, "quadrant"] = "Winter only"
    s.loc[~hi_h & hi_c, "quadrant"] = "Summer only"
    s.loc[hi_h & hi_c, "quadrant"] = "Year-round"
    return s


def sensitivity(s: pd.DataFrame) -> pd.DataFrame:
    latest = s[s["heating_season"] == f"{LAST_SEASON}-{(LAST_SEASON + 1) % 100:02d}"]
    base = add_scores(latest, SCORE_WEIGHTS["heating"], SCORE_WEIGHTS["cooling"]).set_index("county_fips")
    base_top = set(base.nsmallest(TOP_N, "year_round_rank").index)

    rows = []
    for per_home in [False, True]:
        for w_heat in [0.5, 0.6, 0.7, 0.8, 1.0]:
            sc = add_scores(latest, w_heat, round(1 - w_heat, 1), per_home).set_index("county_fips")
            top = set(sc.nsmallest(TOP_N, "year_round_rank").index)
            rows.append({
                "basis": "per_home" if per_home else "total",
                "w_heating": w_heat, "w_cooling": round(1 - w_heat, 1),
                # Spearman correlation, computed as Pearson on ranks to avoid a SciPy dependency.
                "spearman_vs_baseline": round(
                    sc["year_round_score"].rank().corr(base["year_round_score"].rank()), 3),
                f"top{TOP_N}_overlap": len(top & base_top),
                "top_county": sc["year_round_score"].idxmax() + " " + sc.loc[sc["year_round_score"].idxmax(), "county_name"],
            })
    return pd.DataFrame(rows)


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    w_heat, w_cool = SCORE_WEIGHTS["heating"], SCORE_WEIGHTS["cooling"]
    s = add_scores(season_summary(), w_heat, w_cool)
    per_home = add_scores(s, w_heat, w_cool, per_home=True)
    for col in ["heating_pct", "cooling_pct", "year_round_score", "year_round_rank", "quadrant"]:
        s[f"{col}_per_home"] = per_home[col]
    s = s.sort_values(["heating_season", "year_round_rank"]).reset_index(drop=True)
    money = ["oil_spend", "propane_spend", "heating_spend", "oil_gallons", "propane_gallons", "cooling_index"]
    s[money] = s[money].round(0)
    s = s.round({c: 3 for c in s.columns if c.endswith(("_pct", "_score", "_pct_per_home", "_score_per_home"))}
                | {"oil_propane_share": 3})
    s.to_csv(PROCESSED / "county_season_summary.csv", index=False)
    print(f"  wrote county_season_summary.csv: {len(s):,} rows")

    sens = sensitivity(s)
    sens.to_csv(PROCESSED / "sensitivity_scores.csv", index=False)
    print(f"  wrote sensitivity_scores.csv: {len(sens)} scenarios")
    return s, sens


if __name__ == "__main__":
    run()
