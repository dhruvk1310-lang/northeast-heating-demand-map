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

- **Fuel use per home comes from RECS 2020 microdata**, averaged with survey weights over homes whose main heating fuel is oil or propane.
- **Small samples fall back to the division.** RECS surveyed few propane homes in some states (3 in Rhode Island, 6 in New Jersey, 16 in Connecticut, 17 in Massachusetts). Planned rule: when `sample_n` is under 30, use the New England or Middle Atlantic average instead of the state's.
- **Base load** is total use minus space heating (water heating, cooking, dryers, other), spread evenly over 12 months.
- **Summer fuel prices are sparse.** The state price survey covers October to March every year, but June to August only for 2024, and the regional monthly file skips May to August. Summer fuel use is base load only, so missing May to August prices will be filled by linear interpolation between each state's April and September prices.

## Calibration

- Modeled state totals will be compared with EIA SEDS residential consumption. Fuel oil is compared with SEDS distillate plus kerosene, because the ACS "fuel oil" category includes kerosene.
- An early check is encouraging. Connecticut: about 520,000 oil-heated homes × 634 gallons per home ≈ 330 million gallons, against 339 million reported by SEDS for 2020.

## Scoring Weights

- Year-round score = 0.6 × heating spend percentile + 0.4 × cooling index percentile. These are starting weights and will get a sensitivity check.
