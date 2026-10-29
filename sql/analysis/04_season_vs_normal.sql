-- Q7: How much colder or warmer was each winter than normal, and how did demand respond?
-- Degree days are weighted by oil and propane homes; normal = 1991-2020 average.
WITH county_season AS (
    SELECT
        dd.county_fips,
        d.heating_season,
        SUM(dd.hdd)         AS hdd,
        SUM(dd.hdd_normal)  AS hdd_normal
    FROM fact_degree_days AS dd
    JOIN dim_date AS d ON d.date_key = dd.date_key
    WHERE d.heating_season IN (SELECT DISTINCT heating_season FROM fact_county_season)
    GROUP BY dd.county_fips, d.heating_season
),
fuel_homes AS (
    SELECT county_fips, SUM(households) AS homes
    FROM fact_households_by_fuel
    WHERE fuel_id IN ('fuel_oil', 'propane')
    GROUP BY county_fips
),
state_season AS (
    SELECT
        c.state_fips,
        cs.heating_season,
        SUM(cs.hdd * fh.homes) / SUM(fh.homes)         AS hdd,
        SUM(cs.hdd_normal * fh.homes) / SUM(fh.homes)  AS hdd_normal
    FROM county_season AS cs
    JOIN fuel_homes AS fh ON fh.county_fips = cs.county_fips
    JOIN dim_county AS c  ON c.county_fips = cs.county_fips
    GROUP BY c.state_fips, cs.heating_season
),
demand AS (
    SELECT
        c.state_fips,
        d.heating_season,
        SUM(f.est_gallons)  AS gallons,
        SUM(f.est_spend)    AS spend
    FROM fact_monthly_demand AS f
    JOIN dim_county AS c ON c.county_fips = f.county_fips
    JOIN dim_date   AS d ON d.date_key = f.date_key
    GROUP BY c.state_fips, d.heating_season
)
SELECT
    s.state_abbr,
    ss.heating_season,
    ROUND(ss.hdd, 0)                                           AS hdd,
    ROUND(ss.hdd_normal, 0)                                    AS hdd_normal,
    ROUND(100 * (ss.hdd / ss.hdd_normal - 1), 1)               AS pct_colder_than_normal,
    ROUND(dm.gallons / 1e6, 1)                                 AS gallons_m,
    ROUND(100 * (dm.gallons / LAG(dm.gallons) OVER w - 1), 1)  AS gallons_pct_change,
    ROUND(dm.spend / 1e6, 1)                                   AS spend_musd,
    ROUND(100 * (dm.spend / LAG(dm.spend) OVER w - 1), 1)      AS spend_pct_change
FROM state_season AS ss
JOIN demand AS dm   ON dm.state_fips = ss.state_fips AND dm.heating_season = ss.heating_season
JOIN dim_state AS s ON s.state_fips = ss.state_fips
WINDOW w AS (PARTITION BY ss.state_fips ORDER BY ss.heating_season)
ORDER BY s.state_abbr, ss.heating_season;
