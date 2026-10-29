-- One row per state and month: demand, spend, cooling, and weather.
-- Degree days are weighted by where the homes are, so they describe the
-- weather those homes actually saw. Feeds the seasonality line chart.
DROP VIEW IF EXISTS vw_state_seasonality;
CREATE VIEW vw_state_seasonality AS
WITH heat AS (
    SELECT
        c.state_fips,
        f.date_key,
        SUM(CASE WHEN f.fuel_id = 'fuel_oil' THEN f.est_gallons END) AS oil_gallons,
        SUM(CASE WHEN f.fuel_id = 'propane'  THEN f.est_gallons END) AS propane_gallons,
        SUM(f.est_spend)                                             AS heating_spend,
        SUM(f.hdd * f.homes) / SUM(f.homes)                          AS hdd_weighted
    FROM fact_monthly_demand AS f
    JOIN dim_county AS c ON c.county_fips = f.county_fips
    GROUP BY c.state_fips, f.date_key
),
cool AS (
    SELECT
        c.state_fips,
        k.date_key,
        SUM(k.cooling_index)                    AS cooling_index,
        SUM(k.cdd * k.ac_homes) / SUM(k.ac_homes) AS cdd_weighted
    FROM fact_monthly_cooling AS k
    JOIN dim_county AS c ON c.county_fips = k.county_fips
    GROUP BY c.state_fips, k.date_key
)
SELECT
    s.state_abbr,
    s.state_name,
    d.date_key,
    d.year,
    d.month,
    d.month_name,
    d.heating_season,
    h.oil_gallons,
    h.propane_gallons,
    h.heating_spend,
    ROUND(h.hdd_weighted, 1)  AS hdd,
    ROUND(k.cdd_weighted, 1)  AS cdd,
    k.cooling_index
FROM heat AS h
JOIN cool AS k      ON k.state_fips = h.state_fips AND k.date_key = h.date_key
JOIN dim_state AS s ON s.state_fips = h.state_fips
JOIN dim_date  AS d ON d.date_key = h.date_key;
