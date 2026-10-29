-- Q1 and Q6: Which counties have the largest estimated heating oil and propane spend?
-- Latest heating season, top 25, with each county's share of the nine-state market.
WITH latest AS (
    SELECT MAX(heating_season) AS season FROM fact_county_season
),
ranked AS (
    SELECT
        RANK() OVER (ORDER BY cs.heating_spend DESC)           AS spend_rank,
        c.county_name,
        s.state_abbr,
        cs.oil_homes,
        cs.propane_homes,
        cs.oil_spend,
        cs.propane_spend,
        cs.heating_spend,
        cs.heating_spend / SUM(cs.heating_spend) OVER ()       AS share_of_market
    FROM fact_county_season AS cs
    JOIN latest            ON cs.heating_season = latest.season
    JOIN dim_county AS c   ON c.county_fips = cs.county_fips
    JOIN dim_state  AS s   ON s.state_fips = c.state_fips
)
SELECT
    spend_rank,
    county_name,
    state_abbr,
    oil_homes,
    propane_homes,
    ROUND(oil_spend / 1e6, 1)              AS oil_spend_musd,
    ROUND(propane_spend / 1e6, 1)          AS propane_spend_musd,
    ROUND(heating_spend / 1e6, 1)          AS heating_spend_musd,
    ROUND(100 * share_of_market, 2)        AS pct_of_market,
    ROUND(100 * SUM(share_of_market) OVER (ORDER BY spend_rank), 1) AS cumulative_pct
FROM ranked
WHERE spend_rank <= 25
ORDER BY spend_rank;
