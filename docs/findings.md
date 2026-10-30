# Findings

Results from the demand model (Phase 3), the SQL analysis (Phase 4), and the Connecticut dealer pilot (Phase 6). Query results are in `data/processed/analysis/`; dashboards come in Phase 5. All figures are modeled estimates; see [assumptions.md](assumptions.md).

## Market size

- The nine Northeast states spend an estimated **$16.8 billion** on residential heating oil and propane in the 2025-26 season: about **3.2 billion gallons** of heating oil and **1.0 billion gallons** of propane.
- New York is the largest state market ($4.7 billion), followed by Pennsylvania ($2.9 billion) and Massachusetts ($2.8 billion).
- The largest county markets are Suffolk County, NY ($686 million), Worcester County, MA ($574 million), Middlesex County, MA ($499 million), and Connecticut's Capitol Planning Region ($472 million).

## Seasonality

- Demand usually peaks in **January**: it did in every state in four of the five seasons, and in every county in 2025-26. December to February account for about half of the year's gallons. In each state the peak month runs 1.8 to 2.6 times the average month, and 8 to 18 times the quietest month (query 2).
- The exception was 2022-23, which peaked in **December** in seven states because January 2023 was unusually warm.

## Weather and prices

- Four of the last five winters were warmer than the 1991-2020 normal, by up to 13% (2023-24). 2025-26 was the first close-to-normal winter, and region-wide estimated gallons rose 6% and spend 17% over the year before (query 4).
- Price can outweigh weather. In 2022-23 heating oil averaged **$4.79 a gallon**, up from $3.74, so region-wide spend rose 9% even though gallons fell 4%.
- Heating oil prices are about twice as volatile as propane within a season: an average swing of 7.7% vs. 3.4% (query 5).

## Who heats with what

- "Urban oil, rural propane" is only half right (query 6). Propane's share does rise in rural counties (3% of homes in the most urban quarter of counties vs. 15% in the most rural), but so does oil's (14% vs. 38%). Cities mostly heat with utility gas. Oil homes are concentrated in urban counties only because that is where most homes are: the most urban quarter holds 2.2 million of the region's 4.1 million oil homes.

## Year-round opportunity

- Scored on totals, the best year-round markets are the big counties around New York City and Boston, because both heating and cooling demand grow with the number of homes.
- Scored per home, the leaders are oil-heavy counties outside the big cities with warm summers: Sussex County, NJ; Northeastern Connecticut; Putnam County, NY; and the Lower Connecticut River Valley. Query 3, which compares winter (December to February) fuel use with summer (June to August) cooling per home, agrees: Sussex, Newport RI, and Putnam lead, and four Connecticut planning regions make the top eight. This matters for the Connecticut dealer pilot.

## Connecticut dealer pilot

- Connecticut has **468 licensed heating fuel dealers** (521 active registrations including out-of-state companies that deliver into the state). About **1 in 5 (20%)** also holds an HVAC contractor license, so is a full-service dealer.
- Dealer coverage is uneven (query 7). **Western Connecticut** has the most oil and propane homes per dealer, **2,206**, and about $7.3 million of yearly heating spend per dealer. The **Lower Connecticut River Valley** has the fewest, 922 homes and $3.1 million per dealer. Southeastern Connecticut (1,745) and the Northwest Hills (1,671) are also under-served.
- Greater Bridgeport has the highest share of full-service dealers (30%); Northeastern Connecticut the lowest (12%).
- The top prospects for a full-service dealer platform (query 8) are established full-service dealers in under-served regions: **Densmore Oil** (Stonington), **Brunelli Energy** (Bozrah), **Patterson Oil** (Torrington), and **Miller Fuel** (Burlington). Western Connecticut supplies 8 of the top 25, Southeastern Connecticut 7.

## Model checks

- The cooling index tracks actual summer residential electricity sales (EIA 861M), with month-to-month correlations of 0.83 to 0.99 in every state except Maine (0.56), where few homes have air conditioning.
- Before calibration, the model is 8% to 40% below EIA's reported state totals for heating oil, which is expected because those totals include homes that use oil only as a backup or for hot water. It is closest in New Hampshire and Maine (within 10%) and furthest in New Jersey, where RECS sampled only 33 oil homes (query 9).
- The SQL results match the Python model exactly: the same total spend and gallons, and calibration factors equal to three decimal places.
