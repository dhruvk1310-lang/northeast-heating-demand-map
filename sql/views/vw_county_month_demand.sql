-- One row per county and month: both fuels side by side, plus weather and cooling.
-- Feeds Dashboard 1 (seasonal demand map with a month slider).
DROP VIEW IF EXISTS vw_county_month_demand;
CREATE VIEW vw_county_month_demand AS
SELECT
    c.county_fips,
    c.county_name,
    s.state_abbr,
    c.latitude,
    c.longitude,
    d.date_key,
    d.year,
    d.month,
    d.month_name,
    d.heating_season,
    MAX(CASE WHEN f.fuel_id = 'fuel_oil' THEN f.homes END)        AS oil_homes,
    MAX(CASE WHEN f.fuel_id = 'propane'  THEN f.homes END)        AS propane_homes,
    SUM(CASE WHEN f.fuel_id = 'fuel_oil' THEN f.est_gallons END)  AS oil_gallons,
    SUM(CASE WHEN f.fuel_id = 'propane'  THEN f.est_gallons END)  AS propane_gallons,
    SUM(CASE WHEN f.fuel_id = 'fuel_oil' THEN f.est_spend END)    AS oil_spend,
    SUM(CASE WHEN f.fuel_id = 'propane'  THEN f.est_spend END)    AS propane_spend,
    SUM(f.est_spend)                                              AS heating_spend,
    MAX(f.hdd)                                                    AS hdd,
    MAX(k.cdd)                                                    AS cdd,
    MAX(k.ac_homes)                                               AS ac_homes,
    MAX(k.cooling_index)                                          AS cooling_index
FROM fact_monthly_demand AS f
JOIN dim_county AS c ON c.county_fips = f.county_fips
JOIN dim_state  AS s ON s.state_fips = c.state_fips
JOIN dim_date   AS d ON d.date_key = f.date_key
JOIN fact_monthly_cooling AS k ON k.county_fips = f.county_fips AND k.date_key = f.date_key
GROUP BY c.county_fips, d.date_key;
