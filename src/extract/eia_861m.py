"""EIA Form 861M: monthly residential electricity sales by state.

Used to check that the summer cooling index follows real electricity demand.

Output: data/interim/eia_861m_residential.csv (state x year x month)
"""

import pandas as pd

from src.config import INTERIM, STATE_NAMES
from src.extract.download import fetch


def run() -> pd.DataFrame:
    raw = pd.read_excel(fetch("eia_861m"), sheet_name="Monthly-States", header=None, skiprows=3)
    # The first eight columns are Year, Month, State, Data Status and the four residential measures.
    df = raw.iloc[:, :8]
    df.columns = ["year", "month", "state_abbr", "data_status",
                  "revenue_thousand_usd", "sales_mwh", "customers", "price_cents_kwh"]
    df = df[df["state_abbr"].isin(STATE_NAMES)].copy()
    for c in ["revenue_thousand_usd", "sales_mwh", "customers", "price_cents_kwh"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[["year", "month"]] = df[["year", "month"]].astype(int)
    df = df.sort_values(["state_abbr", "year", "month"]).reset_index(drop=True)

    dest = INTERIM / "eia_861m_residential.csv"
    df.to_csv(dest, index=False)
    first, last = df.iloc[0], df.sort_values(["year", "month"]).iloc[-1]
    print(f"  wrote {dest.name}: {len(df):,} rows, {first.year}-{first.month:02d} "
          f"to {last.year}-{last.month:02d}")
    return df


if __name__ == "__main__":
    run()
