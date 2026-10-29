"""Shared settings: paths, study area, and source URLs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

# Nine Northeast states: postal code -> (Census FIPS, NOAA NCEI state code).
# NCEI numbers states alphabetically (01 = Alabama), which is not the same as FIPS.
STATES = {
    "CT": ("09", "06"),
    "ME": ("23", "17"),
    "MA": ("25", "19"),
    "NH": ("33", "27"),
    "NJ": ("34", "28"),
    "NY": ("36", "30"),
    "PA": ("42", "36"),
    "RI": ("44", "37"),
    "VT": ("50", "43"),
}
STATE_FIPS = {abbr: fips for abbr, (fips, _) in STATES.items()}
FIPS_TO_ABBR = {fips: abbr for abbr, fips in STATE_FIPS.items()}
NCEI_TO_FIPS = {ncei: fips for fips, ncei in STATES.values()}
STATE_NAMES = {
    "CT": "Connecticut", "ME": "Maine", "MA": "Massachusetts", "NH": "New Hampshire",
    "NJ": "New Jersey", "NY": "New York", "PA": "Pennsylvania", "RI": "Rhode Island",
    "VT": "Vermont",
}
# Census divisions: 1 = New England, 2 = Middle Atlantic.
STATE_DIVISION = {
    "CT": 1, "ME": 1, "MA": 1, "NH": 1, "RI": 1, "VT": 1,
    "NJ": 2, "NY": 2, "PA": 2,
}

# Raw file names under data/raw, keyed like URLS below.
RAW_FILES = {
    "acs_b25040": "census/acs5_2024_b25040.dat",
    "recs_2020": "eia/recs2020_public_v7.csv",
    "shopp_heating_oil": "eia/shopp_heating_oil_weekly.xls",
    "shopp_propane": "eia/shopp_propane_weekly.xls",
    "shopp_heating_oil_monthly": "eia/shopp_heating_oil_monthly.xls",
    "shopp_propane_monthly": "eia/shopp_propane_monthly.xls",
    "seds": "eia/seds_complete.csv",
    "eia_861m": "eia/eia861m_sales_revenue.xlsx",
    "tiger_county": "census/cb_2024_us_county_500k.zip",
    "tiger_county_ct_legacy": "census/cb_2020_us_county_500k.zip",
}

# Degree days are kept from this year on: enough for 1991-2020 normals
# plus every recent heating season.
DEGREE_DAY_START_YEAR = 1991

# Model window: heating seasons run July to June, labeled like "2025-26".
FIRST_SEASON = 2021  # 2021-22
LAST_SEASON = 2025  # 2025-26
RECS_YEAR = 2020  # the year RECS fuel use describes
MIN_RECS_SAMPLE = 30  # below this, use the Census division average
SCORE_WEIGHTS = {"heating": 0.6, "cooling": 0.4}

ACS_YEAR = 2024  # ACS 5-year release (2020-2024)
TIGER_YEAR = 2024
# 2020 boundaries still have Connecticut's 8 old counties, which NOAA uses.
TIGER_CT_LEGACY_YEAR = 2020

NOAA_CLIMDIV = "https://www.ncei.noaa.gov/monitoring-content/data/us/climdiv/monthly/current/"

URLS = {
    "acs_b25040": (
        "https://www2.census.gov/programs-surveys/acs/summary_file/"
        f"{ACS_YEAR}/table-based-SF/data/5YRData/acsdt5y{ACS_YEAR}-b25040.dat"
    ),
    "recs_2020": "https://www.eia.gov/consumption/residential/data/2020/csv/recs2020_public_v7.csv",
    "shopp_heating_oil": "https://www.eia.gov/dnav/pet/xls/PET_PRI_WFR_A_EPD2F_PRS_DPGAL_W.xls",
    "shopp_propane": "https://www.eia.gov/dnav/pet/xls/PET_PRI_WFR_A_EPLLPA_PRS_DPGAL_W.xls",
    # Monthly files fill in the April to September gap in the weekly survey.
    "shopp_heating_oil_monthly": "https://www.eia.gov/dnav/pet/xls/PET_PRI_WFR_A_EPD2F_PRS_DPGAL_M.xls",
    "shopp_propane_monthly": "https://www.eia.gov/dnav/pet/xls/PET_PRI_WFR_A_EPLLPA_PRS_DPGAL_M.xls",
    "seds": "https://www.eia.gov/state/seds/CDF/Complete_SEDS.csv",
    "eia_861m": "https://www.eia.gov/electricity/data/eia861m/xls/sales_revenue.xlsx",
    "tiger_county": (
        f"https://www2.census.gov/geo/tiger/GENZ{TIGER_YEAR}/shp/cb_{TIGER_YEAR}_us_county_500k.zip"
    ),
    "tiger_county_ct_legacy": (
        f"https://www2.census.gov/geo/tiger/GENZ{TIGER_CT_LEGACY_YEAR}/shp/"
        f"cb_{TIGER_CT_LEGACY_YEAR}_us_county_500k.zip"
    ),
}
