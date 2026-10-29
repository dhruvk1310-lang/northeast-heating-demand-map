-- Q9: How close is the uncalibrated model to EIA's reported state consumption?
-- Compares calendar years that both the model and EIA SEDS fully cover.
WITH full_years AS (
    SELECT d.year
    FROM fact_monthly_demand AS f
    JOIN dim_date AS d ON d.date_key = f.date_key
    GROUP BY d.year
    HAVING COUNT(DISTINCT d.month) = 12
       AND d.year IN (SELECT year FROM fact_reported_consumption)
),
modeled AS (
    SELECT
        c.state_fips,
        f.fuel_id,
        SUM(f.est_gallons_uncalibrated) AS modeled_gallons
    FROM fact_monthly_demand AS f
    JOIN dim_county AS c ON c.county_fips = f.county_fips
    JOIN dim_date   AS d ON d.date_key = f.date_key
    WHERE d.year IN (SELECT year FROM full_years)
    GROUP BY c.state_fips, f.fuel_id
),
reported AS (
    SELECT state_fips, fuel_id, SUM(gallons) AS reported_gallons
    FROM fact_reported_consumption
    WHERE year IN (SELECT year FROM full_years)
    GROUP BY state_fips, fuel_id
)
SELECT
    s.state_abbr,
    m.fuel_id,
    (SELECT MIN(year) || '-' || MAX(year) FROM full_years)            AS years,
    ROUND(m.modeled_gallons / 1e6, 1)                                 AS modeled_mgal,
    ROUND(r.reported_gallons / 1e6, 1)                                AS reported_mgal,
    ROUND(100 * (m.modeled_gallons / r.reported_gallons - 1), 1)      AS pct_error,
    ROUND(r.reported_gallons / m.modeled_gallons, 3)                  AS calibration_factor,
    RANK() OVER (PARTITION BY m.fuel_id
                 ORDER BY ABS(m.modeled_gallons / r.reported_gallons - 1)) AS accuracy_rank
FROM modeled AS m
JOIN reported AS r  ON r.state_fips = m.state_fips AND r.fuel_id = m.fuel_id
JOIN dim_state AS s ON s.state_fips = m.state_fips
ORDER BY m.fuel_id, accuracy_rank;
