-- Star schema for the Northeast Heating & Cooling Demand Map (SQLite).
-- Dimensions describe where, when, and which fuel; facts hold the measurements.
-- Built by: python -m src.load.build_database

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_reported_consumption;
DROP TABLE IF EXISTS fact_county_season;
DROP TABLE IF EXISTS fact_monthly_cooling;
DROP TABLE IF EXISTS fact_monthly_demand;
DROP TABLE IF EXISTS fact_fuel_prices;
DROP TABLE IF EXISTS fact_degree_days;
DROP TABLE IF EXISTS fact_consumption_per_home;
DROP TABLE IF EXISTS fact_households_by_fuel;
DROP TABLE IF EXISTS dim_dealer;
DROP TABLE IF EXISTS dim_fuel;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_county;
DROP TABLE IF EXISTS dim_state;

-- Dimensions -----------------------------------------------------------------

CREATE TABLE dim_state (
    state_fips       TEXT PRIMARY KEY,
    state_abbr       TEXT NOT NULL UNIQUE,
    state_name       TEXT NOT NULL,
    census_division  TEXT NOT NULL          -- New England or Middle Atlantic
);

CREATE TABLE dim_county (
    county_fips      TEXT PRIMARY KEY,      -- Connecticut uses planning regions (09110 to 09190)
    state_fips       TEXT NOT NULL REFERENCES dim_state (state_fips),
    county_name      TEXT NOT NULL,
    land_area_sqmi   REAL,
    latitude         REAL,
    longitude        REAL
);

CREATE TABLE dim_date (
    date_key          INTEGER PRIMARY KEY,  -- YYYYMM
    year              INTEGER NOT NULL,
    month             INTEGER NOT NULL,
    month_name        TEXT NOT NULL,
    heating_season    TEXT NOT NULL,        -- July to June, e.g. 2025-26
    is_heating_month  INTEGER NOT NULL      -- 1 for October to April
);

CREATE TABLE dim_fuel (
    fuel_id          TEXT PRIMARY KEY,      -- fuel_oil, propane, utility_gas, ...
    fuel_name        TEXT NOT NULL,
    btu_per_gallon   INTEGER,               -- only for the two modeled fuels
    unit             TEXT,
    is_modeled       INTEGER NOT NULL       -- 1 for fuel_oil and propane
);

-- Connecticut heating fuel dealers (Phase 6), from the state license registry.
CREATE TABLE dim_dealer (
    dealer_id            INTEGER PRIMARY KEY,   -- registry credential id
    registration         TEXT NOT NULL,         -- Home Heating Fuel Dealer registration number
    name                 TEXT NOT NULL,
    address              TEXT,
    town                 TEXT,
    state                TEXT,
    zip5                 TEXT,
    county_fips          TEXT REFERENCES dim_county (county_fips),  -- planning region; NULL outside CT
    region_source        TEXT,                  -- zip, town, or out of state
    offers_hvac_service  INTEGER NOT NULL,      -- 1 if the business also holds an HVAC contractor license
    hvac_match           TEXT NOT NULL,         -- name, address, or none
    fuels_in_name        TEXT,                  -- oil and/or propane, when the business name says so
    license_issued       TEXT,                  -- first issue date of the dealer registration
    years_licensed       REAL
);

-- Facts ----------------------------------------------------------------------

-- Grain: county x heating fuel (ACS 5-year period)
CREATE TABLE fact_households_by_fuel (
    county_fips            TEXT NOT NULL REFERENCES dim_county (county_fips),
    fuel_id                TEXT NOT NULL REFERENCES dim_fuel (fuel_id),
    acs_year               TEXT NOT NULL,
    households             INTEGER NOT NULL,
    margin_of_error        INTEGER,         -- only for fuel_oil and propane
    share_of_county_homes  REAL NOT NULL,
    PRIMARY KEY (county_fips, fuel_id, acs_year)
);

-- Grain: state x modeled fuel x end use
CREATE TABLE fact_consumption_per_home (
    state_fips        TEXT NOT NULL REFERENCES dim_state (state_fips),
    fuel_id           TEXT NOT NULL REFERENCES dim_fuel (fuel_id),
    end_use           TEXT NOT NULL,        -- space_heat or base
    gallons_per_home  REAL NOT NULL,
    mmbtu_per_home    REAL NOT NULL,
    recs_source       TEXT NOT NULL,        -- the state, or the division it fell back to
    recs_sample_n     INTEGER NOT NULL,
    PRIMARY KEY (state_fips, fuel_id, end_use)
);

-- Grain: county x month, 1991 onward
CREATE TABLE fact_degree_days (
    county_fips  TEXT NOT NULL REFERENCES dim_county (county_fips),
    date_key     INTEGER NOT NULL REFERENCES dim_date (date_key),
    hdd          REAL NOT NULL,
    cdd          REAL NOT NULL,
    hdd_normal   REAL NOT NULL,             -- 1991-2020 average for this county and month
    cdd_normal   REAL NOT NULL,
    PRIMARY KEY (county_fips, date_key)
);

-- Grain: state x modeled fuel x month
CREATE TABLE fact_fuel_prices (
    state_fips            TEXT NOT NULL REFERENCES dim_state (state_fips),
    fuel_id               TEXT NOT NULL REFERENCES dim_fuel (fuel_id),
    date_key              INTEGER NOT NULL REFERENCES dim_date (date_key),
    avg_price_per_gallon  REAL NOT NULL,
    price_source          TEXT NOT NULL,    -- surveyed or interpolated
    PRIMARY KEY (state_fips, fuel_id, date_key)
);

-- Grain: county x modeled fuel x month (model output)
CREATE TABLE fact_monthly_demand (
    county_fips               TEXT NOT NULL REFERENCES dim_county (county_fips),
    fuel_id                   TEXT NOT NULL REFERENCES dim_fuel (fuel_id),
    date_key                  INTEGER NOT NULL REFERENCES dim_date (date_key),
    homes                     INTEGER NOT NULL,
    hdd                       REAL NOT NULL,
    est_gallons_uncalibrated  REAL NOT NULL,
    est_gallons               REAL NOT NULL,
    price_per_gallon          REAL NOT NULL,
    est_spend                 REAL NOT NULL,
    PRIMARY KEY (county_fips, fuel_id, date_key)
);

-- Grain: county x month (model output)
CREATE TABLE fact_monthly_cooling (
    county_fips    TEXT NOT NULL REFERENCES dim_county (county_fips),
    date_key       INTEGER NOT NULL REFERENCES dim_date (date_key),
    ac_homes       REAL NOT NULL,
    cdd            REAL NOT NULL,
    cooling_index  REAL NOT NULL,
    PRIMARY KEY (county_fips, date_key)
);

-- Grain: county x heating season (model output: totals, scores, quadrants)
CREATE TABLE fact_county_season (
    county_fips                TEXT NOT NULL REFERENCES dim_county (county_fips),
    heating_season             TEXT NOT NULL,
    oil_homes                  INTEGER,
    propane_homes              INTEGER,
    total_occupied             INTEGER,
    oil_gallons                REAL,
    propane_gallons            REAL,
    oil_spend                  REAL,
    propane_spend              REAL,
    heating_spend              REAL,
    ac_homes                   REAL,
    cooling_index              REAL,
    peak_month                 INTEGER,
    heating_pct                REAL,
    cooling_pct                REAL,
    year_round_score           REAL,
    year_round_rank            INTEGER,
    quadrant                   TEXT,
    year_round_score_per_home  REAL,
    year_round_rank_per_home   INTEGER,
    quadrant_per_home          TEXT,
    PRIMARY KEY (county_fips, heating_season)
);

-- Grain: state x modeled fuel x year (EIA SEDS, for calibration)
CREATE TABLE fact_reported_consumption (
    state_fips  TEXT NOT NULL REFERENCES dim_state (state_fips),
    fuel_id     TEXT NOT NULL REFERENCES dim_fuel (fuel_id),
    year        INTEGER NOT NULL,
    gallons     REAL NOT NULL,              -- fuel_oil = distillate + kerosene
    PRIMARY KEY (state_fips, fuel_id, year)
);

CREATE INDEX ix_demand_date ON fact_monthly_demand (date_key);
CREATE INDEX ix_cooling_date ON fact_monthly_cooling (date_key);
CREATE INDEX ix_degree_days_date ON fact_degree_days (date_key);
CREATE INDEX ix_county_state ON dim_county (state_fips);
