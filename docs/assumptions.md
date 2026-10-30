# Assumptions

## Unit Conversions

| Quantity | Value | Note |
|---|---|---|
| Heating oil (No. 2) | 138,500 Btu per gallon | EIA |
| Propane | 91,500 Btu per gallon | EIA |
| Barrel | 42 gallons | Used to convert SEDS thousand barrels to gallons |
| Square mile | 2,589,988.11 square meters | Used for county land area |

## Data Collection

- **Census data comes from the ACS summary file, not the API.** The Census API now requires a key, and the bulk summary file holds the same B25040 estimates without one.
- **Connecticut planning regions.** Since 2022 the Census reports Connecticut by 9 planning regions instead of 8 counties, while NOAA still uses the old counties. Each planning region gets the area-weighted average of the old counties it overlaps (`ct_region_county_crosswalk`). Weighting by population would be more precise; area is used because degree days are a property of place, and neighboring old counties differ by only a few percent.
- **Degree days are county-level.** NOAA's nClimDiv publishes heating and cooling degree days for every county, so the model can use county weather instead of the statewide figures the README first planned.
- **The study area is 218 counties** (including Connecticut's 9 planning regions), not "about 300" as first estimated.

## Demand Model

- **Formula.** For each county, fuel, and month:
  `gallons = homes x (gal_per_hdd x HDD(county, month) + base_gal / 12)`.
- **Gallons per degree day.** RECS reports each home's space heating use for 2020. Dividing it by 2020's heating degree days for the same homes (weighted by where those homes are) gives gallons per degree day. Multiplying by each county's actual degree days means colder counties and colder winters burn more fuel. This replaces the README's first draft, which spread a fixed yearly total across months and so gave every winter the same total.
- **Fuel use per home comes from RECS 2020 microdata**, averaged with survey weights over homes whose main heating fuel is oil or propane.
- **Small samples fall back to the division.** When fewer than 30 homes were surveyed for a state and fuel, the New England or Middle Atlantic average is used instead. This applies to propane in CT, MA, RI (New England) and NJ (Middle Atlantic). `data/interim/model_usage_per_home.csv` shows the source for each pair.
- **Base load** is total use minus space heating (water heating, cooking, dryers, other), spread evenly over 12 months.
- **Homes are held constant** at the ACS 2020-2024 average across all five seasons.
- **Heating seasons run July to June** (for example 2025-26 is July 2025 to June 2026). The model covers 2021-22 to 2025-26.
- **Prices.** Weekly state prices are averaged to months. Months without a survey value (37% of the window, mostly May to August) are filled by linear interpolation along each state's price series. `price_source` marks which is which.
- **Cooling index** = homes with AC x cooling degree days. Homes with AC = occupied homes x the state's RECS AC share. It is relative, not dollars.

## Calibration

- Modeled gallons are compared with EIA SEDS residential consumption over 2022 to 2024, the calendar years both cover. Fuel oil is compared with SEDS distillate plus kerosene, because the ACS "fuel oil" category includes kerosene.
- **Before calibration the model is low** for 16 of 18 state-fuel pairs: heating oil by 8% to 40%, propane by up to 42%. Only New Jersey and New York propane come out high (36% and 14%). This is expected. SEDS counts all residential use, including homes that burn oil or propane as a backup or only for water heating and cooking, while the ACS counts a home only under its main heating fuel. Small RECS samples (New Jersey oil: 33 homes) add noise.
- **What calibration means here.** `est_gallons` is scaled so each state matches SEDS: it estimates the full residential market a dealer sells into, shared out to counties by their modeled heating demand. `est_gallons_uncalibrated` keeps the main-heat-only estimate. Factors range from 0.73 to 1.72 (`data/processed/calibration.csv`).

## Database and SQL

- **Degree-day normals** are the 1991-2020 average for each county and calendar month, computed when the database is built.
- **Price analysis uses surveyed October to April months only.** Interpolated months are kept in `fact_fuel_prices` (marked `price_source = 'interpolated'`) because the model used them, but they are left out of the price trend query. Summer surveys are too uneven across years to compare.
- **Standard deviation** is computed as sqrt(avg(x²) - avg(x)²), because SQLite has no `STDDEV` function.
- **Density groups** in query 6 split the 218 counties into four equal groups by homes per square mile of land.

## Tableau

- **Thermal load** (the map's color) = heating gallons per home, scaled to 0-1, minus cooling index per home, scaled to 0-1, for each county and month. Each part is divided by its 99th percentile across all county-months and capped at 1, so a few extreme counties do not wash out the color scale. +1 means all heating load, -1 all cooling load.
- **The dashboards show the 2025-26 season.** All five seasons are in the data files; the season is set in `build_tableau_workbook.py`.
- **Headline numbers** on The Thermal Year are written into the dashboard as text when the workbook is built, from `tableau/data/kpis.csv`.

## Connecticut Dealers

- **Dealer list** = active Home Heating Fuel Dealer registrations in the state license registry (data.ct.gov, dataset ngch-56tr). Connecticut requires this registration to sell heating oil or propane to homes, so the list is close to complete. It includes 53 out-of-state companies that deliver into Connecticut; they are kept in `dim_dealer` but have no region and are left out of regional counts.
- **Planning region** comes from the dealer's ZIP code: each ZIP is assigned to the town holding most of its land (Census 2020 ZCTA-to-county-subdivision file), and each town to its planning region (Census 2024 gazetteer). One dealer whose ZIP did not match was placed by town name. A dealer's address is its office, not its whole delivery area.
- **Offers HVAC service** = the business also appears on an active Heating, Piping & Cooling contractor license, matched on business name or DBA (ignoring Inc, LLC, Co, punctuation) or on the same street address and ZIP. Name matches can miss a dealer whose HVAC license is under a different company name, so 20% is a floor.
- **Years licensed** counts from the registration's first issue date. 154 of the 468 Connecticut dealers have no issue date in the registry (mostly long-standing companies), so they get a neutral tenure score of 0.5.
- **Not collected:** company size, website, and online payment or customer portal. None of these are in a public record; they would need each dealer's website to be checked by hand, so the original schema columns for them were dropped rather than left empty.
- **Fit score** = 0.5 x offers HVAC service + 0.3 x percentile of the region's oil and propane homes per dealer + 0.2 x percentile of years licensed. It favors established full-service dealers in regions with less competition, the profile most likely to need dispatch, routing, and service software.

## Scoring Weights

- Year-round score = 0.6 x heating spend percentile + 0.4 x cooling index percentile, computed per heating season across all 218 counties.
- **The weights barely matter.** Any mix from 50/50 to 80/20 keeps a Spearman rank correlation of 0.98 or more with the 60/40 baseline, and 23 or more of the same top 25 counties (`data/processed/sensitivity_scores.csv`).
- **The basis matters a lot.** On totals, both heating spend and the cooling index grow with the number of homes, so the score mostly measures county size. Scored per home, the ranking changes almost completely (Spearman 0.19 with the baseline). Both are saved: `year_round_score` (market size, the README's plan) and `year_round_score_per_home` (market intensity).
- Quadrants split each percentile at 0.5: Year-round, Winter only, Summer only, Low demand.
