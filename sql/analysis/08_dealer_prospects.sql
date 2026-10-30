-- Q9: Which Connecticut dealers best fit a full-service software platform?
-- Top 25 by fit score (see vw_dealer_opportunity for the weights), with each
-- dealer's rank inside its planning region.
SELECT
    prospect_rank,
    name,
    town,
    region,
    CASE offers_hvac_service WHEN 1 THEN 'yes' ELSE 'no' END  AS hvac_service,
    years_licensed,
    region_homes_per_dealer,
    ROUND(100 * fit_score, 1)                                  AS fit_score,
    rank_in_region
FROM vw_dealer_opportunity
WHERE prospect_rank <= 25
ORDER BY prospect_rank;
