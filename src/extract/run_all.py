"""Download every source and write the tidy interim tables.

Run from the project root:
    python -m src.extract.run_all
Raw downloads are cached in data/raw; delete a file there to fetch it again.
"""

from src.config import INTERIM
from src.extract import (
    census_acs, census_tiger, ct_dealers, eia_861m, eia_prices, eia_recs, eia_seds, noaa_degree_days,
)
from src.transform import ct_planning_regions

STEPS = [
    ("Census ACS B25040 (homes by heating fuel)", census_acs.run),
    ("Census county boundaries", census_tiger.run),
    ("NOAA degree days", noaa_degree_days.run),
    ("Connecticut planning region crosswalk", ct_planning_regions.run),
    ("EIA RECS fuel use per home", eia_recs.run),
    ("EIA SHOPP fuel prices", eia_prices.run),
    ("EIA SEDS residential consumption", eia_seds.run),
    ("EIA 861M residential electricity", eia_861m.run),
    ("Connecticut heating fuel dealers", ct_dealers.run),
]


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    for i, (label, step) in enumerate(STEPS, 1):
        print(f"[{i}/{len(STEPS)}] {label}")
        step()
    print("Done.")


if __name__ == "__main__":
    main()
