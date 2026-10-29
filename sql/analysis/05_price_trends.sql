-- Q7: How have heating oil and propane prices moved, and how volatile are they?
-- Uses surveyed October to April months only (summer surveys are too uneven to
-- compare), for complete heating seasons from 2015-16 through the model's last season.
-- SQLite has no STDDEV, so it is computed as sqrt(avg(x^2) - avg(x)^2).
WITH seasonal AS (
    SELECT
        s.state_abbr,
        p.fuel_id,
        d.heating_season,
        AVG(p.avg_price_per_gallon)                              AS avg_price,
        MIN(p.avg_price_per_gallon)                              AS low_price,
        MAX(p.avg_price_per_gallon)                              AS high_price,
        SQRT(AVG(p.avg_price_per_gallon * p.avg_price_per_gallon)
             - AVG(p.avg_price_per_gallon) * AVG(p.avg_price_per_gallon)) AS price_stddev,
        COUNT(*)                                                 AS months_surveyed
    FROM fact_fuel_prices AS p
    JOIN dim_state AS s ON s.state_fips = p.state_fips
    JOIN dim_date  AS d ON d.date_key = p.date_key
    WHERE p.price_source = 'surveyed'
      AND d.is_heating_month = 1
      AND d.heating_season >= '2015-16'
      AND d.heating_season <= (SELECT MAX(heating_season) FROM fact_county_season)
    GROUP BY s.state_abbr, p.fuel_id, d.heating_season
)
SELECT
    state_abbr,
    fuel_id,
    heating_season,
    months_surveyed,
    ROUND(avg_price, 3)                                         AS avg_price,
    ROUND(low_price, 3)                                         AS low_price,
    ROUND(high_price, 3)                                        AS high_price,
    ROUND(price_stddev, 3)                                      AS price_stddev,
    ROUND(100 * price_stddev / avg_price, 1)                    AS volatility_pct,
    ROUND(AVG(avg_price) OVER (PARTITION BY state_abbr, fuel_id ORDER BY heating_season
                               ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 3) AS avg_price_3yr,
    ROUND(100 * (avg_price / LAG(avg_price) OVER (PARTITION BY state_abbr, fuel_id
                                                  ORDER BY heating_season) - 1), 1) AS pct_change
FROM seasonal
ORDER BY fuel_id, state_abbr, heating_season;
