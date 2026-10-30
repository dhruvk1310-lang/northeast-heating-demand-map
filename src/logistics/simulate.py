"""Simulate a heating oil dealer's 2025-26 season: K-factor auto-delivery and daily routing.

Each account burns oil every day by its K-factor (gallons per heating degree day) plus a
steady base load (hot water). When the forecast says a tank will reach the reorder level
within the lookahead window, it goes on that day's delivery list. Each day's list is then
routed two ways:

  hand-sequenced  stops in zone order (census tract, then block group), trucks filled in
                  list order: how a dispatcher sequences stops by hand today
  optimized       capacitated vehicle routing with OR-Tools, minimizing trucks then miles

More runs cap the fleet (FLEET_CAPS trucks) to measure run-out risk in a cold snap:
when the day's list doesn't fit, the emptiest tanks go first and the rest wait.

Outputs (data/processed/logistics):
  daily_dispatch.csv    one row per day: weather, deliveries, gallons, trucks, miles, hours by method
  routes_<date>.csv     every stop of every truck on the coldest day, both methods
  accounts.csv          the simulated accounts: location, K-factor, deliveries, gallons
"""

import math

import numpy as np
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.config import PROCESSED
from src.logistics.service_area import OUT as IN

OUT = PROCESSED / "logistics"
SEED = 42

# Usage per oil-heated home in Connecticut, from the Phase 3 model (RECS 2020 x the EIA SEDS calibration).
K_FACTOR = 0.09612 * 1.1603   # gallons per heating degree day
BASE_PER_DAY = 111.8 * 1.1603 / 365  # hot water and other steady use, gallons per day
HOME_VARIATION = 0.25  # lognormal spread between houses

TANK = 275             # standard indoor oil tank, gallons
FILL_TO = 250          # fill to about 90% of the tank
REORDER_AT = 0.25 * TANK  # schedule when the tank is forecast to drop to 25%
LOOKAHEAD_DAYS = 3

TRUCK_GALLONS = 2800   # typical heating oil delivery truck
DAY_MINUTES = 9 * 60   # driver day
STOP_MINUTES = 12      # hook up, pump, ticket
FLEET_CAPS = [1, 2]    # fleet sizes for the run-out risk scenarios
SOLVE_SECONDS = 2


def accounts(rng: np.random.Generator) -> pd.DataFrame:
    area = pd.read_csv(IN / "service_area.csv", dtype={"GEOID": str})
    rows = []
    for node, r in enumerate(area.itertuples(), start=1):
        n = int(r.expected_customers) + int(rng.random() < r.expected_customers % 1)
        for _ in range(n):
            rows.append((node, r.GEOID, r.latitude, r.longitude))
    a = pd.DataFrame(rows, columns=["node", "GEOID", "latitude", "longitude"])
    spread = rng.lognormal(-HOME_VARIATION ** 2 / 2, HOME_VARIATION, len(a))  # mean 1
    a["k_factor"] = K_FACTOR * spread
    a["base_per_day"] = BASE_PER_DAY * spread
    a["start_level"] = rng.uniform(REORDER_AT + 30, FILL_TO, len(a))
    a.insert(0, "account_id", range(1, len(a) + 1))
    return a


def route(stops: list[tuple[int, int]], miles: np.ndarray, minutes: np.ndarray) -> list[list[int]]:
    """OR-Tools CVRP. stops: (matrix node, gallons). Returns routes as lists of stop indexes."""
    n = len(stops)
    nodes = [0] + [s[0] for s in stops]
    demand = [0] + [s[1] for s in stops]
    vehicles = max(1, math.ceil(sum(demand) / TRUCK_GALLONS) + 3)
    manager = pywrapcp.RoutingIndexManager(n + 1, vehicles, 0)
    model = pywrapcp.RoutingModel(manager)

    def dist_cb(i, j):
        return int(miles[nodes[manager.IndexToNode(i)], nodes[manager.IndexToNode(j)]] * 100)

    def time_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(minutes[nodes[a], nodes[b]] + (STOP_MINUTES if b else 0))

    dist_idx = model.RegisterTransitCallback(dist_cb)
    model.SetArcCostEvaluatorOfAllVehicles(dist_idx)
    model.SetFixedCostOfAllVehicles(1_000_000)  # fewer trucks first, then fewer miles
    demand_idx = model.RegisterUnaryTransitCallback(lambda i: demand[manager.IndexToNode(i)])
    model.AddDimensionWithVehicleCapacity(demand_idx, 0, [TRUCK_GALLONS] * vehicles, True, "gallons")
    time_idx = model.RegisterTransitCallback(time_cb)
    model.AddDimension(time_idx, 0, DAY_MINUTES, True, "minutes")

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = SOLVE_SECONDS
    solution = model.SolveWithParameters(params)
    if solution is None:
        raise RuntimeError(f"No route found for {n} stops")
    routes = []
    for v in range(vehicles):
        i, r = model.Start(v), []
        while not model.IsEnd(i):
            node = manager.IndexToNode(i)
            if node:
                r.append(node - 1)
            i = solution.Value(model.NextVar(i))
        if r:
            routes.append(r)
    return routes


def hand_sequence(stops: list[tuple[int, int]], zone: list[str], minutes: np.ndarray) -> list[list[int]]:
    """Zone order, filling each truck in list order until it is full or out of time."""
    order = sorted(range(len(stops)), key=lambda k: zone[k])
    routes, cur, gal, mins, last = [], [], 0, 0.0, 0
    for k in order:
        node, g = stops[k]
        add = minutes[last, node] + STOP_MINUTES
        if cur and (gal + g > TRUCK_GALLONS or mins + add + minutes[node, 0] > DAY_MINUTES):
            routes.append(cur)
            cur, gal, mins, last = [], 0, 0.0, 0
            add = minutes[0, node] + STOP_MINUTES
        cur.append(k)
        gal, mins, last = gal + g, mins + add, node
    if cur:
        routes.append(cur)
    return routes


def measure(routes, stops, miles, minutes) -> tuple[float, float]:
    total_mi = total_min = 0.0
    for r in routes:
        path = [0] + [stops[k][0] for k in r] + [0]
        total_mi += sum(miles[a, b] for a, b in zip(path, path[1:]))
        total_min += sum(minutes[a, b] for a, b in zip(path, path[1:])) + STOP_MINUTES * len(r)
    return total_mi, total_min


def season(fleet_cap: int | None, rng_seed: int = SEED, keep_routes_on: str | None = None):
    rng = np.random.default_rng(rng_seed)
    acc = accounts(rng)
    weather = pd.read_csv(IN / "weather_daily.csv", parse_dates=["date"])
    m = np.load(IN / "road_matrix.npz")
    miles, minutes = m["miles"], m["minutes"]
    zone_of_node = {i + 1: g for i, g in enumerate(m["geoid"][1:])}

    level = acc["start_level"].to_numpy().copy()
    k, base = acc["k_factor"].to_numpy(), acc["base_per_day"].to_numpy()
    hdd = weather["hdd"].to_numpy()
    deliveries = np.zeros(len(acc), dtype=int)
    gallons_in = np.zeros(len(acc))
    days, kept = [], {}

    for d in range(len(weather)):
        # Forecast use over the next LOOKAHEAD_DAYS (actual weather stands in for a good forecast).
        ahead = hdd[d:d + LOOKAHEAD_DAYS].sum()
        projected = level - (k * ahead + base * LOOKAHEAD_DAYS)
        due = np.where(projected <= REORDER_AT)[0]
        # Most urgent first: fewest days of oil left.
        days_left = level[due] / np.maximum(k[due] * max(hdd[d], 1) + base[due], 1e-6)
        due = due[np.argsort(days_left)]
        if fleet_cap is not None:
            budget, chosen, used = fleet_cap * TRUCK_GALLONS * 0.97, [], 0.0
            for i in due:
                g = FILL_TO - level[i]
                if used + g > budget:
                    break
                chosen.append(i)
                used += g
            due = np.array(chosen, dtype=int)

        row = {"date": weather["date"].iloc[d].date(), "hdd": hdd[d], "temp_mean_f": weather["temp_mean_f"].iloc[d],
               "deliveries": len(due)}
        if len(due):
            stops = [(int(acc["node"].iloc[i]), int(round(FILL_TO - level[i]))) for i in due]
            zones = [zone_of_node[s[0]] for s in stops]
            opt = route(stops, miles, minutes)
            hand = hand_sequence(stops, zones, minutes)
            if fleet_cap is not None and len(opt) > fleet_cap:
                opt = opt[:fleet_cap]  # what does not fit waits for tomorrow
                served = {k_ for r in opt for k_ in r}
                due = np.array([due[j] for j in range(len(due)) if j in served], dtype=int)
                stops = [stops[j] for j in sorted(served)]
                opt = route(stops, miles, minutes)
            om, ot = measure(opt, stops, miles, minutes)
            hm, ht = measure(hand, stops, miles, minutes)
            row.update(gallons=sum(s[1] for s in stops), trucks_opt=len(opt), miles_opt=om, hours_opt=ot / 60,
                       trucks_hand=len(hand), miles_hand=hm, hours_hand=ht / 60)
            if keep_routes_on and str(row["date"]) == keep_routes_on:
                kept = {"optimized": opt, "hand-sequenced": hand, "stops": stops}
            level[due] = FILL_TO
            deliveries[due] += 1
            gallons_in[due] += [s[1] for s in stops]
        level -= k * hdd[d] + base
        row["runouts"] = int((level <= 0).sum())
        row["below_10pct"] = int((level <= 0.10 * TANK).sum())
        level = np.maximum(level, 0)  # an empty tank stays empty until filled
        days.append(row)

    acc["deliveries"] = deliveries
    acc["gallons_delivered"] = gallons_in.round(0)
    return pd.DataFrame(days).fillna(0), acc, kept


def routes_table(kept: dict, day: str) -> pd.DataFrame:
    area = pd.read_csv(IN / "service_area.csv", dtype={"GEOID": str})
    from src.logistics.inputs import depot
    d = depot()
    coords = {0: (d.latitude, d.longitude)}
    coords.update({i + 1: (r.latitude, r.longitude) for i, r in enumerate(area.itertuples())})
    rows = []
    for method in ["optimized", "hand-sequenced"]:
        for t, r in enumerate(kept[method], start=1):
            path = [0] + [kept["stops"][k][0] for k in r] + [0]
            gal = [0] + [kept["stops"][k][1] for k in r] + [0]
            for seq, (node, g) in enumerate(zip(path, gal)):
                lat, lon = coords[node]
                rows.append((day, method, t, seq, node, lat, lon, g))
    return pd.DataFrame(rows, columns=["date", "method", "truck", "stop_seq", "node", "latitude", "longitude",
                                       "gallons"])


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    weather = pd.read_csv(IN / "weather_daily.csv", parse_dates=["date"])
    coldest = str(weather.loc[weather["hdd"].idxmax(), "date"].date())

    daily, acc, kept = season(None, keep_routes_on=coldest)
    daily.round(2).to_csv(OUT / "daily_dispatch.csv", index=False)
    acc.round(4).to_csv(OUT / "accounts.csv", index=False)
    routes_table(kept, coldest).to_csv(OUT / f"routes_{coldest}.csv", index=False)

    for cap in FLEET_CAPS:
        capped, _, _ = season(cap)
        capped.round(2).to_csv(OUT / f"daily_dispatch_fleet{cap}.csv", index=False)
        print(f"  {cap}-truck fleet: worst day {int(capped.runouts.max())} tanks empty, "
              f"{int((capped.runouts > 0).sum())} days with run-outs")

    t = daily.sum(numeric_only=True)
    print(f"  {len(acc)} accounts, {int(t.deliveries):,} deliveries, {t.gallons:,.0f} gallons")
    print(f"  miles: hand {t.miles_hand:,.0f} vs optimized {t.miles_opt:,.0f} "
          f"({1 - t.miles_opt / t.miles_hand:.0%} fewer); driver hours {t.hours_hand:,.0f} vs {t.hours_opt:,.0f}")
    print(f"  peak trucks: hand {daily.trucks_hand.max():.0f}, optimized {daily.trucks_opt.max():.0f}; "
          f"run-outs with an unlimited fleet {int(daily.runouts.max())}")


if __name__ == "__main__":
    run()
