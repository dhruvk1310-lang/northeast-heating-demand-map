-- One row per Connecticut heating fuel dealer, with its region's market and a fit score
-- for a full-service dealer software platform. Feeds Dashboard 3 and query 8.
--
-- fit_score = 0.5 x offers HVAC service (1 or 0)
--           + 0.3 x percentile of its region's oil and propane homes per dealer (less competition)
--           + 0.2 x percentile of years licensed (established business; unknown = 0.5)
DROP VIEW IF EXISTS vw_dealer_opportunity;
CREATE VIEW vw_dealer_opportunity AS
WITH region AS (
    SELECT
        d.county_fips,
        COUNT(*)  AS dealers,
        (SELECT SUM(h.households) FROM fact_households_by_fuel AS h
          WHERE h.county_fips = d.county_fips AND h.fuel_id IN ('fuel_oil', 'propane')) AS fuel_homes
    FROM dim_dealer AS d
    WHERE d.county_fips IS NOT NULL
    GROUP BY d.county_fips
),
region_scored AS (
    SELECT
        *,
        1.0 * fuel_homes / dealers                                  AS homes_per_dealer,
        PERCENT_RANK() OVER (ORDER BY 1.0 * fuel_homes / dealers)   AS region_pct
    FROM region
),
tenure AS (
    SELECT dealer_id, PERCENT_RANK() OVER (ORDER BY years_licensed) AS tenure_pct
    FROM dim_dealer
    WHERE county_fips IS NOT NULL AND years_licensed IS NOT NULL
),
scored AS (
    SELECT
        d.dealer_id,
        d.name,
        d.town,
        d.county_fips,
        REPLACE(c.county_name, ' Planning Region', '')     AS region,
        d.offers_hvac_service,
        d.hvac_match,
        d.fuels_in_name,
        d.years_licensed,
        ROUND(r.homes_per_dealer, 0)                        AS region_homes_per_dealer,
        ROUND(r.region_pct, 3)                              AS region_pct,
        ROUND(COALESCE(t.tenure_pct, 0.5), 3)               AS tenure_pct,
        0.5 * d.offers_hvac_service + 0.3 * r.region_pct + 0.2 * COALESCE(t.tenure_pct, 0.5) AS fit_score
    FROM dim_dealer AS d
    JOIN region_scored AS r ON r.county_fips = d.county_fips
    JOIN dim_county AS c    ON c.county_fips = d.county_fips
    LEFT JOIN tenure AS t   ON t.dealer_id = d.dealer_id
)
SELECT
    *,
    ROW_NUMBER() OVER (ORDER BY fit_score DESC, years_licensed DESC, name) AS prospect_rank,
    ROW_NUMBER() OVER (PARTITION BY county_fips ORDER BY fit_score DESC, years_licensed DESC, name) AS rank_in_region
FROM scored;
