"""Real inputs for the delivery simulation: daily weather and road distances.

Outputs (data/interim/logistics):
  weather_daily.csv     daily mean temperature and heating degree days at the depot (Open-Meteo archive)
  road_matrix.npz       driving miles and minutes between the depot and every service-area block group (OSRM)
"""

import time

import numpy as np
import pandas as pd
import requests

from src.extract.download import HEADERS
from src.logistics.service_area import DEALER_ID, OUT, geocode_dealers

OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
OSRM = "https://router.project-osrm.org/table/v1/driving/"
SEASON = ("2025-07-01", "2026-06-30")
HDD_BASE_F = 65
CHUNK = 50  # coordinates per side of each OSRM table request
METERS_PER_MILE = 1609.344


def depot() -> pd.Series:
    return geocode_dealers().set_index("dealer_id").loc[DEALER_ID]


def weather() -> pd.DataFrame:
    d = depot()
    params = {"latitude": d.latitude, "longitude": d.longitude, "start_date": SEASON[0], "end_date": SEASON[1],
              "daily": "temperature_2m_mean,temperature_2m_min", "temperature_unit": "fahrenheit",
              "timezone": "America/New_York"}
    resp = requests.get(OPEN_METEO, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    daily = resp.json()["daily"]
    w = pd.DataFrame({"date": pd.to_datetime(daily["time"]), "temp_mean_f": daily["temperature_2m_mean"],
                      "temp_min_f": daily["temperature_2m_min"]})
    w["hdd"] = (HDD_BASE_F - w["temp_mean_f"]).clip(lower=0).round(1)
    w.to_csv(OUT / "weather_daily.csv", index=False)
    print(f"  wrote weather_daily.csv: {len(w)} days, {w['hdd'].sum():,.0f} heating degree days")
    return w


def road_matrix() -> None:
    """Driving miles and minutes between all points. Index 0 is the depot."""
    area = pd.read_csv(OUT / "service_area.csv", dtype={"GEOID": str})
    d = depot()
    pts = [(d.longitude, d.latitude)] + list(zip(area["longitude"], area["latitude"]))
    n = len(pts)
    dist, dur = np.zeros((n, n)), np.zeros((n, n))
    for i0 in range(0, n, CHUNK):
        for j0 in range(0, n, CHUNK):
            src, dst = list(range(i0, min(i0 + CHUNK, n))), list(range(j0, min(j0 + CHUNK, n)))
            idx = sorted(set(src) | set(dst))
            coords = ";".join(f"{pts[k][0]:.6f},{pts[k][1]:.6f}" for k in idx)
            pos = {k: p for p, k in enumerate(idx)}
            params = {"sources": ";".join(str(pos[k]) for k in src),
                      "destinations": ";".join(str(pos[k]) for k in dst), "annotations": "distance,duration"}
            for attempt in range(4):
                resp = requests.get(OSRM + coords, params=params, headers=HEADERS, timeout=60)
                if resp.status_code == 200 and resp.json().get("code") == "Ok":
                    break
                time.sleep(5 * (attempt + 1))
            resp.raise_for_status()
            body = resp.json()
            dist[np.ix_(src, dst)] = np.array(body["distances"], dtype=float) / METERS_PER_MILE
            dur[np.ix_(src, dst)] = np.array(body["durations"], dtype=float) / 60
            time.sleep(1)  # be polite to the public demo server
    np.savez_compressed(OUT / "road_matrix.npz", miles=dist, minutes=dur, geoid=np.array(["depot"] + list(area["GEOID"])))
    print(f"  wrote road_matrix.npz: {n} x {n}, median trip {np.median(dist[dist > 0]):.1f} mi, "
          f"{np.median(dur[dur > 0]):.0f} min")


def run() -> None:
    weather()
    road_matrix()


if __name__ == "__main__":
    run()
