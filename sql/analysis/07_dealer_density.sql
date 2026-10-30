-- Q8: How many fuel dealers serve each Connecticut planning region, relative to
-- the number of oil and propane homes? Starts from the regions and LEFT JOINs the
-- dealers, so a region with no dealers would still appear (with 0).
WITH latest AS (
    SELECT MAX(heating_season) AS season FROM fact_county_season
),
region_homes AS (
    SELECT
        h.county_fips,
        SUM(CASE WHEN h.fuel_id = 'fuel_oil' THEN h.households ELSE 0 END) AS oil_homes,
        SUM(CASE WHEN h.fuel_id = 'propane'  THEN h.households ELSE 0 END) AS propane_homes
    FROM fact_households_by_fuel AS h
    GROUP BY h.county_fips
),
region_dealers AS (
    SELECT
        county_fips,
        COUNT(*)                  AS dealers,
        SUM(offers_hvac_service)  AS hvac_dealers
    FROM dim_dealer
    WHERE county_fips IS NOT NULL
    GROUP BY county_fips
)
SELECT
    REPLACE(c.county_name, ' Planning Region', '')                      AS region,
    rh.oil_homes,
    rh.propane_homes,
    COALESCE(rd.dealers, 0)                                              AS dealers,
    COALESCE(rd.hvac_dealers, 0)                                         AS hvac_dealers,
    ROUND(100.0 * rd.hvac_dealers / rd.dealers, 0)                       AS pct_full_service,
    ROUND(1.0 * (rh.oil_homes + rh.propane_homes) / NULLIF(rd.dealers, 0), 0) AS homes_per_dealer,
    ROUND(cs.heating_spend / NULLIF(rd.dealers, 0) / 1e6, 2)            AS spend_per_dealer_musd,
    RANK() OVER (ORDER BY 1.0 * (rh.oil_homes + rh.propane_homes) / NULLIF(rd.dealers, 0) DESC) AS underserved_rank
FROM dim_county AS c
JOIN dim_state AS s           ON s.state_fips = c.state_fips AND s.state_abbr = 'CT'
JOIN region_homes AS rh       ON rh.county_fips = c.county_fips
JOIN fact_county_season AS cs ON cs.county_fips = c.county_fips
JOIN latest                   ON cs.heating_season = latest.season
LEFT JOIN region_dealers AS rd ON rd.county_fips = c.county_fips
ORDER BY underserved_rank;
