"""Connecticut heating fuel dealers, from the state's license registry (data.ct.gov).

Every company that sells home heating oil or propane in Connecticut must hold a
Home Heating Fuel Dealer registration with the Department of Consumer
Protection. Active Heating, Piping & Cooling contractor licenses from the same
registry show which dealers also do HVAC work (a "full-service" dealer).

Each dealer is placed in a Connecticut planning region by its ZIP code
(ZIP -> town -> planning region, from Census relationship files), falling back
to the town name.

Output: data/interim/ct_dealers.csv, one row per active dealer registration.
"""

import re
from string import capwords

import pandas as pd

from src.config import INTERIM, RAW
from src.extract.download import download

REGISTRY = "https://data.ct.gov/resource/ngch-56tr.csv"
DEALER = "HOME HEATING FUEL DEALER"
HVAC_CONTRACTORS = ["HEATING, PIPING & COOLING LIMITED CONTRACTOR", "HEATING, PIPING & COOLING UNLIMITED CONTRACTOR"]
GAZETTEER = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_gaz_cousubs_09.txt"
ZCTA_TOWN = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_cousub20_natl.txt"
CT_FIPS = "09"

# Words dropped before comparing business names.
NAME_NOISE = {"INC", "LLC", "L L C", "CO", "CORP", "CORPORATION", "COMPANY", "THE", "LTD", "AND", "OF"}
STREET_ABBR = {"STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "DRIVE": "DR", "LANE": "LN", "BOULEVARD": "BLVD",
               "TURNPIKE": "TPKE", "HIGHWAY": "HWY", "PLACE": "PL", "COURT": "CT", "CIRCLE": "CIR", "PARKWAY": "PKWY"}


def registry_query(credentials: list[str]) -> str:
    quoted = ", ".join("'" + c.replace("&", "%26") + "'" for c in credentials)
    return f"{REGISTRY}?$limit=50000&$where=active='1' AND credential in({quoted})"


def norm_name(s) -> str:
    if not isinstance(s, str):
        return ""
    s = re.sub(r"[^A-Z0-9 ]", " ", s.upper().replace("&", " AND "))
    words = [w for w in s.split() if w not in NAME_NOISE]
    return " ".join(words)


def norm_address(street, zip_code) -> str:
    if not isinstance(street, str) or not isinstance(zip_code, str):
        return ""
    words = re.sub(r"[^A-Z0-9 ]", " ", street.upper()).split()
    words = [STREET_ABBR.get(w, w) for w in words]
    return " ".join(words) + " " + zip_code[:5]


def town_regions() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(zip5 -> region, town name -> region) for Connecticut."""
    gaz = pd.read_csv(download(GAZETTEER, RAW / "census" / "gaz_cousubs_2024_09.txt"), sep="\t", dtype=str)
    gaz.columns = gaz.columns.str.strip()
    gaz["cousub"] = gaz["GEOID"].str[5:]
    gaz["region_fips"] = gaz["GEOID"].str[:5]
    gaz["town"] = gaz["NAME"].str.replace(r" (town|city|borough)$", "", regex=True).str.upper()

    rel = pd.read_csv(download(ZCTA_TOWN, RAW / "census" / "zcta520_cousub20_natl.txt"), sep="|", dtype=str,
                      usecols=["GEOID_ZCTA5_20", "GEOID_COUSUB_20", "AREALAND_PART"], encoding="utf-8-sig")
    rel = rel.dropna(subset=["GEOID_ZCTA5_20"])
    rel = rel[rel["GEOID_COUSUB_20"].str.startswith(CT_FIPS)].copy()
    rel["cousub"] = rel["GEOID_COUSUB_20"].str[5:]
    rel["area"] = rel["AREALAND_PART"].astype(float)
    # Each ZIP goes to the town holding most of its land.
    rel = rel.sort_values("area", ascending=False).drop_duplicates("GEOID_ZCTA5_20")
    by_zip = rel.merge(gaz[["cousub", "region_fips", "town"]], on="cousub")[["GEOID_ZCTA5_20", "region_fips", "town"]]
    by_zip = by_zip.rename(columns={"GEOID_ZCTA5_20": "zip5", "town": "zip_town"})
    by_town = gaz[["town", "region_fips"]].drop_duplicates("town")
    return by_zip, by_town


def run() -> pd.DataFrame:
    raw_dir = RAW / "ct"
    dealers = pd.read_csv(download(registry_query([DEALER]), raw_dir / "home_heating_fuel_dealers.csv"), dtype=str)
    hvac = pd.read_csv(download(registry_query(HVAC_CONTRACTORS), raw_dir / "hvac_contractors.csv"), dtype=str)

    # HVAC match keys: the contractor's DBA, business name, and business address.
    hvac_names = set()
    for col in ["dba", "businessname"]:
        hvac_names |= {n for n in hvac[col].map(norm_name) if len(n) >= 4}
    hvac_addresses = {a for a in (norm_address(s, z) for s, z in zip(hvac["address"], hvac["zip"])) if a}

    d = dealers.copy()
    # capwords, not str.title(), so "LEAHY'S" becomes "Leahy's" rather than "Leahy'S".
    d["display_name"] = d["dba"].fillna(d["businessname"]).fillna(d["name"]).str.strip().map(capwords)
    d["city"] = d["city"].str.strip().map(capwords)
    name_keys = d[["name", "businessname", "dba"]].apply(lambda r: {norm_name(v) for v in r} - {""}, axis=1)
    by_name = name_keys.map(lambda keys: bool(keys & hvac_names))
    by_address = [norm_address(s, z) in hvac_addresses for s, z in zip(d["address"], d["zip"])]
    d["offers_hvac_service"] = (by_name | pd.Series(by_address, index=d.index)).astype(int)
    d["hvac_match"] = "none"
    d.loc[pd.Series(by_address, index=d.index), "hvac_match"] = "address"
    d.loc[by_name, "hvac_match"] = "name"

    upper = d["display_name"].str.upper()
    has_oil = upper.str.contains(r"\bOIL\b|\bFUEL\b|\bENERGY\b|\bPETROLEUM\b")
    has_lp = upper.str.contains(r"PROPANE|\bLP\b|BOTTLED GAS")
    d["fuels_in_name"] = ""
    d.loc[has_oil, "fuels_in_name"] = "oil"
    d.loc[has_lp, "fuels_in_name"] = "propane"
    d.loc[has_oil & has_lp, "fuels_in_name"] = "oil, propane"

    d["zip5"] = d["zip"].str[:5]
    d["in_ct"] = (d["state"] == "CT").astype(int)
    by_zip, by_town = town_regions()
    d = d.merge(by_zip, on="zip5", how="left")
    d["town_key"] = d["city"].str.upper().str.strip()
    fallback = d["region_fips"].isna() & (d["in_ct"] == 1)
    d.loc[fallback, "region_fips"] = d.loc[fallback, "town_key"].map(by_town.set_index("town")["region_fips"])
    d.loc[d["in_ct"] == 0, "region_fips"] = None
    d["region_source"] = "zip"
    d.loc[fallback, "region_source"] = "town"
    d.loc[d["in_ct"] == 0, "region_source"] = "out of state"

    d["license_issued"] = pd.to_datetime(d["issuedate"]).dt.date
    d["years_licensed"] = ((pd.Timestamp.today() - pd.to_datetime(d["issuedate"])).dt.days / 365.25).round(1)

    out = d.rename(columns={"credentialid": "dealer_id", "city": "town", "credentialnumber": "registration"})[[
        "dealer_id", "registration", "display_name", "address", "town", "state", "zip5", "in_ct", "region_fips",
        "region_source", "offers_hvac_service", "hvac_match", "fuels_in_name", "license_issued", "years_licensed"]]
    out = out.rename(columns={"display_name": "name"}).sort_values("dealer_id").reset_index(drop=True)
    out.to_csv(INTERIM / "ct_dealers.csv", index=False)

    ct = out[out["in_ct"] == 1]
    print(f"  wrote ct_dealers.csv: {len(out)} active dealers, {len(ct)} in Connecticut, "
          f"{ct['region_fips'].isna().sum()} without a region, "
          f"{out['offers_hvac_service'].mean():.0%} also licensed for HVAC")
    return out


if __name__ == "__main__":
    run()
