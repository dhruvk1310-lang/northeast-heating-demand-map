-- Q4 and Q5: Which counties are strong in both winter heating and summer cooling?
-- Measured per home, so big counties do not win on size alone. Latest heating season.
-- Winter = December to February fuel gallons; summer = June to August cooling index.
WITH latest AS (
    SELECT MAX(heating_season) AS season FROM fact_county_season
),
homes AS (
    SELECT county_fips, SUM(households) AS total_homes
    FROM fact_households_by_fuel
    GROUP BY county_fips
),
heat AS (
    SELECT
        f.county_fips,
        SUM(CASE WHEN d.month IN (12, 1, 2) THEN f.est_gallons ELSE 0 END) AS winter_gallons
    FROM fact_monthly_demand AS f
    JOIN dim_date AS d ON d.date_key = f.date_key
    JOIN latest       ON d.heating_season = latest.season
    GROUP BY f.county_fips
),
cool AS (
    SELECT
        k.county_fips,
        SUM(CASE WHEN d.month IN (6, 7, 8) THEN k.cooling_index ELSE 0 END) AS summer_cooling
    FROM fact_monthly_cooling AS k
    JOIN dim_date AS d ON d.date_key = k.date_key
    JOIN latest       ON d.heating_season = latest.season
    GROUP BY k.county_fips
),
scored AS (
    SELECT
        c.county_name,
        s.state_abbr,
        h.winter_gallons / homes.total_homes   AS winter_gal_per_home,
        k.summer_cooling / homes.total_homes   AS summer_cooling_per_home,
        PERCENT_RANK() OVER (ORDER BY h.winter_gallons / homes.total_homes) AS winter_pct,
        PERCENT_RANK() OVER (ORDER BY k.summer_cooling / homes.total_homes) AS summer_pct
    FROM heat AS h
    JOIN cool AS k       ON k.county_fips = h.county_fips
    JOIN homes           ON homes.county_fips = h.county_fips
    JOIN dim_county AS c ON c.county_fips = h.county_fips
    JOIN dim_state  AS s ON s.state_fips = c.state_fips
)
SELECT
    county_name,
    state_abbr,
    ROUND(winter_gal_per_home, 1)      AS winter_gal_per_home,
    ROUND(summer_cooling_per_home, 0)  AS summer_cooling_per_home,
    ROUND(winter_pct, 3)               AS winter_pct,
    ROUND(summer_pct, 3)               AS summer_pct,
    ROUND(MIN(winter_pct, summer_pct), 3) AS weaker_season_pct
FROM scored
WHERE winter_pct >= 0.5 AND summer_pct >= 0.5
ORDER BY weaker_season_pct DESC
LIMIT 25;
