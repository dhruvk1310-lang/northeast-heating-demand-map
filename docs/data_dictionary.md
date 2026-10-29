# Data Dictionary

Interim tables are written to `data/interim/` by `python -m src.extract.run_all`, with raw downloads cached in `data/raw/`. Neither folder is committed; run the command to rebuild them.

Model outputs are written to `data/processed/` by `python -m src.model.run_all` and are committed, so Tableau and SQL can use them directly. They are listed after the interim tables.

The SQLite database (`data/northeast_demand.db`, built by `python -m src.load.build_database`) holds the same data as a star schema. Its tables and columns are documented in [`sql/schema/01_create_tables.sql`](../sql/schema/01_create_tables.sql) and summarized in the README. That script also writes `data/processed/analysis/` (one CSV per query in `sql/analysis/`) and `data/processed/tableau/` (one CSV per view in `sql/views/`).

FIPS codes are stored as text with leading zeros (`09110`, not `9110`).

| Table | Column | Type | Description | Source |
|-------|--------|------|-------------|--------|
| acs_households_by_fuel | county_fips | text | 5-digit county FIPS (Connecticut uses planning regions, 09110 to 09190) | Census ACS B25040 |
| acs_households_by_fuel | state_fips, state_abbr | text | State FIPS code and postal abbreviation | Census ACS B25040 |
| acs_households_by_fuel | total_occupied | int | Occupied housing units | Census ACS B25040 line 1 |
| acs_households_by_fuel | utility_gas, propane, electricity, fuel_oil, coal, wood, solar, other_fuel, no_fuel | int | Occupied homes by main heating fuel; they add up to total_occupied | Census ACS B25040 lines 2 to 10 |
| acs_households_by_fuel | propane_moe, fuel_oil_moe | int | 90% margin of error for propane and fuel oil homes | Census ACS B25040 |
| acs_households_by_fuel | acs_year | text | ACS 5-year period, e.g. 2020-2024 | Census ACS |
| counties_ne (.csv, .geojson) | county_fips, state_fips, state_abbr | text | County and state identifiers | Census cartographic boundaries 2024 |
| counties_ne | county_name | text | Full name, e.g. "Fairfield County" or "Capitol Planning Region" | Census cartographic boundaries 2024 |
| counties_ne | land_area_sqmi | float | Land area in square miles | Census cartographic boundaries 2024 |
| counties_ne | latitude, longitude | float | A point guaranteed inside the county, for map labels | Computed |
| counties_ct_legacy (.geojson) | county_fips, county_name | text | Connecticut's 8 counties before 2022, matching NOAA | Census cartographic boundaries 2020 |
| ct_region_county_crosswalk | region_fips | text | Connecticut planning region FIPS | Computed |
| ct_region_county_crosswalk | legacy_county_fips | text | Old Connecticut county it overlaps | Computed |
| ct_region_county_crosswalk | area_share | float | Share of the region's area inside that old county; sums to 1 per region | Computed |
| noaa_degree_days_county | county_fips, state_abbr | text | County as NOAA reports it (old Connecticut counties) | NOAA nClimDiv |
| noaa_degree_days_county | year, month | int | Calendar month, 1991 onward | NOAA nClimDiv |
| noaa_degree_days_county | hdd, cdd | float | Heating and cooling degree days, base 65°F | NOAA nClimDiv |
| degree_days_county | (same columns) | | As above, but Connecticut is on planning regions so it joins to the ACS | Computed from NOAA |
| noaa_degree_days_state | state_fips, state_abbr, year, month, hdd, cdd | | Statewide degree days | NOAA nClimDiv |
| recs_fuel_use_per_home | level | text | `state` or `division` | EIA RECS 2020 |
| recs_fuel_use_per_home | geography | text | State abbreviation, or `New England` / `Middle Atlantic` | EIA RECS 2020 |
| recs_fuel_use_per_home | fuel | text | `fuel_oil` or `propane`: homes whose main heating fuel it is | EIA RECS 2020 |
| recs_fuel_use_per_home | sample_n | int | Surveyed homes behind the average | EIA RECS 2020 |
| recs_fuel_use_per_home | weighted_homes | int | Homes those responses represent | EIA RECS 2020 |
| recs_fuel_use_per_home | gal_total | float | Average gallons per home per year, all uses | EIA RECS 2020 |
| recs_fuel_use_per_home | gal_space_heat | float | Gallons for space heating (weather-driven) | EIA RECS 2020 |
| recs_fuel_use_per_home | gal_water_heat | float | Gallons for water heating | EIA RECS 2020 |
| recs_fuel_use_per_home | gal_base | float | gal_total minus gal_space_heat: the part that is steady year-round | Computed |
| recs_ac_share | level, geography, sample_n | | As above | EIA RECS 2020 |
| recs_ac_share | ac_share | float | Weighted share of homes with air conditioning | EIA RECS 2020 |
| eia_fuel_prices | date | date | Survey date | EIA SHOPP |
| eia_fuel_prices | level, geography | text | `state` + abbreviation, or `padd` + `PADD 1A` / `PADD 1B` | EIA SHOPP |
| eia_fuel_prices | fuel | text | `heating_oil` (No. 2) or `propane` | EIA SHOPP |
| eia_fuel_prices | frequency | text | `weekly` (state file) or `monthly` (regional file) | EIA SHOPP |
| eia_fuel_prices | price_per_gallon | float | Residential price, dollars per gallon, taxes included | EIA SHOPP |
| eia_seds_residential | state_abbr, year | | State and year, 2010 onward | EIA SEDS |
| eia_seds_residential | fuel | text | `distillate_fuel_oil`, `kerosene`, or `propane` | EIA SEDS |
| eia_seds_residential | kbbl | float | Residential consumption, thousand barrels | EIA SEDS (DFRCP, KSRCP, PQRCP) |
| eia_seds_residential | gallons | float | kbbl × 1,000 × 42 | Computed |
| eia_seds_residential | billion_btu | float | Residential consumption, billion Btu | EIA SEDS (DFRCB, KSRCB, PQRCB) |
| eia_861m_residential | state_abbr, year, month, data_status | | State and month, 2010 onward; recent months are `Preliminary` | EIA Form 861M |
| eia_861m_residential | revenue_thousand_usd, sales_mwh, customers, price_cents_kwh | float | Residential electricity revenue, sales, customer count and average price | EIA Form 861M |
| fuel_prices_monthly (interim) | state_abbr, fuel, year, month | | State, `fuel_oil` or `propane`, month | Computed from EIA SHOPP |
| fuel_prices_monthly (interim) | price_per_gallon | float | Monthly average residential price | Computed from EIA SHOPP |
| fuel_prices_monthly (interim) | price_source | text | `surveyed` or `interpolated` | Computed |
| model_usage_per_home (interim) | recs_source | text | State used for RECS averages, or the division it fell back to | Computed |
| model_usage_per_home (interim) | ref_hdd | float | 2020 heating degree days for this state's homes on this fuel | Computed from NOAA |
| model_usage_per_home (interim) | gal_per_hdd | float | Space heating gallons per home per heating degree day | Computed |
| fact_monthly_demand | county_fips, state_abbr, fuel, year, month, heating_season | | County, `fuel_oil` or `propane`, month, season (July to June, e.g. 2025-26) | Model |
| fact_monthly_demand | homes | int | Homes whose main heating fuel is this fuel | Census ACS |
| fact_monthly_demand | hdd | float | County heating degree days that month | NOAA |
| fact_monthly_demand | est_gallons_uncalibrated | float | Gallons burned by homes that heat with this fuel | Model |
| fact_monthly_demand | est_gallons | float | Calibrated to EIA SEDS: the county's share of all residential use | Model |
| fact_monthly_demand | price_per_gallon, price_source | | Monthly state price and whether it was surveyed or interpolated | EIA SHOPP |
| fact_monthly_demand | est_spend | float | est_gallons x price_per_gallon, dollars | Model |
| fact_monthly_cooling | county_fips, state_abbr, year, month, heating_season | | County and month | Model |
| fact_monthly_cooling | ac_homes | float | Occupied homes x state AC share | ACS, RECS |
| fact_monthly_cooling | cdd | float | County cooling degree days that month | NOAA |
| fact_monthly_cooling | cooling_index | float | ac_homes x cdd; relative, not dollars | Model |
| county_season_summary | county_fips, state_abbr, county_name, heating_season | | County and season | Model |
| county_season_summary | oil_homes, propane_homes, total_occupied, oil_propane_share | | Homes on each fuel and their combined share | Census ACS |
| county_season_summary | oil_gallons, propane_gallons, oil_spend, propane_spend, heating_spend | float | Season totals (calibrated gallons, dollars) | Model |
| county_season_summary | ac_homes, cooling_index | float | Homes with AC and season cooling index | Model |
| county_season_summary | peak_month | int | Month with the most fuel demand | Model |
| county_season_summary | heating_pct, cooling_pct | float | Percentile among the 218 counties that season | Model |
| county_season_summary | year_round_score, year_round_rank, quadrant | | 0.6 x heating_pct + 0.4 x cooling_pct, its rank, and quadrant | Model |
| county_season_summary | *_per_home columns | | Same, but scored on spend and cooling per home | Model |
| calibration | state_abbr, fuel, years | | State, fuel, calendar years compared | Model |
| calibration | modeled_gallons, seds_gallons | float | Uncalibrated model total vs. EIA SEDS total | Model, EIA SEDS |
| calibration | factor, pct_error_before | float | SEDS / model, and the model's error before scaling | Model |
| sensitivity_scores | basis, w_heating, w_cooling | | Scenario: `total` or `per_home`, and weights | Model |
| sensitivity_scores | spearman_vs_baseline, top25_overlap, top_county | | Rank agreement with the 60/40 total baseline | Model |
