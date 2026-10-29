"""Monthly residential fuel prices by state.

Weekly state prices are averaged to months. Months the survey skips (mostly
May to August) are filled by linear interpolation along each state's series.

Output: data/interim/fuel_prices_monthly.csv
"""

import pandas as pd

from src.config import INTERIM

FUELS = {"heating_oil": "fuel_oil", "propane": "propane"}  # EIA name -> model name


def run(start: str, end: str) -> pd.DataFrame:
    """Return state x fuel x month prices covering start to end (YYYY-MM)."""
    raw = pd.read_csv(INTERIM / "eia_fuel_prices.csv", parse_dates=["date"])
    raw = raw[raw["level"] == "state"]
    raw["period"] = raw["date"].dt.to_period("M")
    surveyed = raw.groupby(["fuel", "geography", "period"])["price_per_gallon"].mean()

    # Interpolate on the full surveyed history so the window edges have neighbors on both sides.
    first, last = surveyed.index.get_level_values("period").min(), surveyed.index.get_level_values("period").max()
    months = pd.period_range(first, last, freq="M")
    frames = []
    for (fuel, state), s in surveyed.groupby(level=["fuel", "geography"]):
        s = s.droplevel(["fuel", "geography"]).reindex(months)
        filled = s.interpolate(method="linear", limit_area="inside")
        frames.append(pd.DataFrame({
            "fuel": FUELS[fuel],
            "state_abbr": state,
            "period": months,
            "price_per_gallon": filled.round(3),
            "price_source": s.notna().map({True: "surveyed", False: "interpolated"}),
        }))
    out = pd.concat(frames, ignore_index=True)
    out = out[(out["period"] >= pd.Period(start, "M")) & (out["period"] <= pd.Period(end, "M"))]
    if out["price_per_gallon"].isna().any():
        raise ValueError("Some months in the model window have no price, even after interpolation")
    out["year"], out["month"] = out["period"].dt.year, out["period"].dt.month
    out = out.drop(columns="period")[["state_abbr", "fuel", "year", "month", "price_per_gallon", "price_source"]]

    out.to_csv(INTERIM / "fuel_prices_monthly.csv", index=False)
    share = (out["price_source"] == "interpolated").mean()
    print(f"  wrote fuel_prices_monthly.csv: {len(out)} rows, {share:.0%} interpolated")
    return out
