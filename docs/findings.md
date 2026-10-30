# Findings

I wanted to answer three things: where and when the Northeast needs heating fuel and AC, how big that market is, and which dealers are worth calling first. Here's what the data says.

Everything here is modeled from public data (Census, NOAA, EIA, and Connecticut's license registry). It's good for patterns and relative size, not exact gallons. The details are in [assumptions.md](assumptions.md), and the query results are in `data/processed/analysis/`.

## The short version

1. **It's a $16.8B market.** That's what the 9 states spent on home heating oil and propane in 2025-26.
2. **January runs everything.** December to February is about half the year's gallons.
3. **Weather moves gallons, price moves dollars.** In 2022-23 people burned less oil but spent more.
4. **Big counties win on size, oil towns win per home.** The best markets change almost completely depending on how you rank them.
5. **Connecticut's dealers are spread unevenly.** Western CT has more than twice as many oil and propane homes per dealer as the Lower CT River Valley.

## 1. How big is it

- In the 2025-26 season the 9 states spent about **$16.8B** on home heating oil and propane: about **3.2B gallons of oil** and **1.0B gallons of propane**.
- New York is the biggest state ($4.7B), then Pennsylvania ($2.9B) and Massachusetts ($2.8B).
- The biggest single counties are Suffolk NY ($686M), Worcester MA ($574M), Middlesex MA ($499M), and Connecticut's Capitol region ($472M).
- 4.1M Northeast homes heat with oil. That's about 80% of every oil-heated home in the US.

## 2. When it happens

- Demand peaks in **January** almost every year, and December to February is about half the year's gallons.
- The peak month is about 2x an average month and 8 to 18x the slowest one. For a dealer, that means trucks and staff get sized for winter, and summer needs other work.
- 2022-23 was the exception. It peaked in December because January 2023 was unusually warm.

## 3. Weather vs. price

- 4 of the last 5 winters were warmer than normal (2023-24 by 13%). 2025-26 was the first one close to normal, and spend jumped 17%.
- Price can matter more than weather. In 2022-23 oil hit **$4.79 a gallon**, so spend went up 9% even though people burned 4% fewer gallons.
- Oil prices swing about twice as much as propane inside a season (7.7% vs. 3.4%).

## 4. Who heats with what

- "Cities use oil, rural areas use propane" is only half true. Rural counties do use more propane (15% of homes vs. 3% in the most urban ones), but they also use more oil (38% vs. 14%). Cities mostly run on gas.
- Oil homes still cluster in cities just because that's where the homes are. The most urban quarter of counties holds 2.2M of the 4.1M oil homes.

## 5. Where the year-round money is

- Rank by total market and the big New York City and Boston counties win every time, because heating and cooling both grow with the number of homes. Changing the score weights barely moves that.
- Rank per home and it's a different list: oil-heavy places outside the cities with warm summers, like Sussex NJ, Northeastern Connecticut, Putnam NY, and Newport RI. Those are the best fit for a dealer who sells fuel in winter and AC service in summer.

## 6. Connecticut: who to call first

- Connecticut has **468 licensed heating fuel dealers**. Only 1 in 5 (20%) also holds an HVAC contractor license, so most are fuel-only.
- Coverage is uneven. **Western CT has 2,206 oil and propane homes per dealer** (about $7.3M of heating spend each). The Lower CT River Valley has 922.
- The top prospects are established full-service dealers in under-served regions: **Densmore Oil** (Stonington), **Brunelli Energy** (Bozrah), **Patterson Oil** (Torrington), and **Miller Fuel** (Burlington). Western CT has 8 of the top 25.

## How much to trust this

- The cooling index lines up with real summer electricity sales: 0.83 to 0.99 correlation in every state except Maine (0.56), where few homes have AC.
- Before calibration the model came in 8 to 40% under EIA's reported oil totals. That's expected, because EIA also counts homes that use oil as a backup or just for hot water. I scaled to EIA's totals and kept both versions.
- The SQL results match the Python model exactly.
- Some things I couldn't get: dealer size, websites, and online payment. None of it is in a public record, so I left it out instead of guessing.

## What I'd do next

- Add dealer registries for the other 8 states where they're public, so the dealer view isn't Connecticut only.
- Re-run it every fall when new prices and weather come in. The whole pipeline rebuilds from one set of commands.
- Test the fit score against real wins and losses if a dealer software company would share that data.
