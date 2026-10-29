-- One row per county and heating season: totals, scores, and quadrants.
-- Feeds Dashboard 2 (market overview) and Dashboard 3 (year-round opportunity).
DROP VIEW IF EXISTS vw_county_annual_summary;
CREATE VIEW vw_county_annual_summary AS
SELECT
    c.county_fips,
    c.county_name,
    s.state_abbr,
    s.census_division,
    c.latitude,
    c.longitude,
    cs.heating_season,
    cs.total_occupied,
    cs.oil_homes,
    cs.propane_homes,
    ROUND(1.0 * (cs.oil_homes + cs.propane_homes) / cs.total_occupied, 3) AS oil_propane_share,
    ROUND(cs.total_occupied / c.land_area_sqmi, 1)                         AS homes_per_sqmi,
    cs.oil_gallons,
    cs.propane_gallons,
    cs.oil_spend,
    cs.propane_spend,
    cs.heating_spend,
    ROUND(cs.heating_spend / cs.total_occupied, 2)                         AS heating_spend_per_home,
    cs.ac_homes,
    cs.cooling_index,
    cs.peak_month,
    cs.heating_pct,
    cs.cooling_pct,
    cs.year_round_score,
    cs.year_round_rank,
    cs.quadrant,
    cs.year_round_score_per_home,
    cs.year_round_rank_per_home,
    cs.quadrant_per_home
FROM fact_county_season AS cs
JOIN dim_county AS c ON c.county_fips = cs.county_fips
JOIN dim_state  AS s ON s.state_fips = c.state_fips;
