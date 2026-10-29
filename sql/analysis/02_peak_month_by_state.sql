-- Q2 and Q3: In which month does demand peak, and how sharp is the peak in each state?
-- Peak-to-average ratio = peak month gallons / average monthly gallons, per heating season.
WITH monthly AS (
    SELECT
        s.state_abbr,
        d.heating_season,
        d.month,
        d.month_name,
        SUM(f.est_gallons) AS gallons
    FROM fact_monthly_demand AS f
    JOIN dim_county AS c ON c.county_fips = f.county_fips
    JOIN dim_state  AS s ON s.state_fips = c.state_fips
    JOIN dim_date   AS d ON d.date_key = f.date_key
    GROUP BY s.state_abbr, d.heating_season, d.month
),
stats AS (
    SELECT
        *,
        MAX(gallons) OVER (PARTITION BY state_abbr, heating_season) AS peak_gallons,
        AVG(gallons) OVER (PARTITION BY state_abbr, heating_season) AS avg_gallons,
        MIN(gallons) OVER (PARTITION BY state_abbr, heating_season) AS low_gallons
    FROM monthly
)
SELECT
    state_abbr,
    heating_season,
    month_name                             AS peak_month,
    ROUND(peak_gallons / 1e6, 1)           AS peak_month_mgal,
    ROUND(avg_gallons / 1e6, 1)            AS avg_month_mgal,
    ROUND(peak_gallons / avg_gallons, 2)   AS peak_to_average,
    ROUND(peak_gallons / low_gallons, 1)   AS peak_to_low
FROM stats
WHERE gallons = peak_gallons
ORDER BY state_abbr, heating_season;
