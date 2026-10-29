-- Q1: Is the Northeast an "urban oil, rural propane" market?
-- Counties are split into four groups by housing density (homes per square mile),
-- then compared on how they heat.
WITH county_mix AS (
    SELECT
        h.county_fips,
        SUM(h.households)                                                      AS total_homes,
        SUM(CASE WHEN h.fuel_id = 'fuel_oil' THEN h.households ELSE 0 END)     AS oil_homes,
        SUM(CASE WHEN h.fuel_id = 'propane'  THEN h.households ELSE 0 END)     AS propane_homes,
        SUM(CASE WHEN h.fuel_id = 'utility_gas' THEN h.households ELSE 0 END)  AS gas_homes
    FROM fact_households_by_fuel AS h
    GROUP BY h.county_fips
),
banded AS (
    SELECT
        m.*,
        m.total_homes / c.land_area_sqmi                               AS homes_per_sqmi,
        NTILE(4) OVER (ORDER BY m.total_homes / c.land_area_sqmi)      AS density_quartile
    FROM county_mix AS m
    JOIN dim_county AS c ON c.county_fips = m.county_fips
)
SELECT
    density_quartile,
    CASE density_quartile
        WHEN 1 THEN 'Most rural'
        WHEN 2 THEN 'Rural'
        WHEN 3 THEN 'Suburban'
        ELSE 'Most urban'
    END                                                              AS density_group,
    COUNT(*)                                                         AS counties,
    ROUND(MIN(homes_per_sqmi), 0)                                    AS min_homes_per_sqmi,
    ROUND(MAX(homes_per_sqmi), 0)                                    AS max_homes_per_sqmi,
    SUM(oil_homes)                                                   AS oil_homes,
    SUM(propane_homes)                                               AS propane_homes,
    ROUND(100.0 * SUM(oil_homes) / SUM(total_homes), 1)              AS pct_oil,
    ROUND(100.0 * SUM(propane_homes) / SUM(total_homes), 1)          AS pct_propane,
    ROUND(100.0 * SUM(gas_homes) / SUM(total_homes), 1)              AS pct_utility_gas,
    ROUND(1.0 * SUM(propane_homes) / SUM(oil_homes), 2)              AS propane_per_oil_home
FROM banded
GROUP BY density_quartile
ORDER BY density_quartile;
