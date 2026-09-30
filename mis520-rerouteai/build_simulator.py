"""Build the standalone class-presentation simulator.

    python build_simulator.py      ->  simulator/ReRouteAI_Simulator.html

The browser simulator re-implements the decision engine in JavaScript so it runs
offline on any laptop. To keep it honest, this script embeds:
  * the delay-model probabilities for every scenario flight, month and weekday,
    produced by the trained Python model (the browser never invents risk numbers);
  * the timetable, airports and cost assumptions from the Python package;
  * 60 parity cases: the Python engine's answers for random scenarios. The page
    recomputes them on load and shows whether it matches.
"""

from __future__ import annotations

import json
import pathlib
import random

from rerouteai import delay_model as D
from rerouteai.graph import HOPE_WINDOW, RiskOracle, enumerate_itineraries, search
from rerouteai.scoring import EUR_TO_USD, PROFILES, Assumptions, Profile, rank
from rerouteai.timetable import AIRPORTS, CARRIER_NAMES, PROTECTED, TIMETABLE, Disruption

ROOT = pathlib.Path(__file__).resolve().parent
TEMPLATE = ROOT / "simulator" / "template.html"
OUT = ROOT / "simulator" / "ReRouteAI_Simulator.html"


def export() -> dict:
    model = D.load()
    dists = {}
    for month in range(1, 13):
        for dow in range(1, 8):
            o = RiskOracle(model, Disruption(month=month, dow=dow))
            dists[f"{month}-{dow}"] = {f.id: [round(float(x), 7) for x in o.dist(f)] for f in TIMETABLE}

    d0 = Disruption()
    a = Assumptions()
    data = {
        "source": model.source,
        "airports": {k: {"name": v[0], "lat": v[1], "lon": v[2], "mct": v[3], "busy": v[4]} for k, v in AIRPORTS.items()},
        "flights": [{"id": f.id, "carrier": f.carrier, "carrierName": CARRIER_NAMES.get(f.carrier, f.carrier),
                     "origin": f.origin, "dest": f.dest, "dep": f.dep, "arr": f.arr, "fare": f.fare,
                     "seats": f.seats, "protected": f.protected} for f in TIMETABLE],
        "protected": sorted(PROTECTED),
        "dists": dists,
        "edges": D.EDGES,
        "hopeWindow": HOPE_WINDOW,
        "eurToUsd": EUR_TO_USD,
        "disruption": {"originFlight": d0.origin_flight, "at": d0.at, "destination": d0.destination,
                       "scheduledIn": d0.scheduled_in, "plannedArrival": d0.planned_arrival,
                       "originalConnection": d0.original_connection, "journeyKm": d0.journey_km,
                       "tripOrigin": d0.trip_origin},
        "assumptions": {"hotel": a.hotel, "meals": a.meals, "interlineShare": a.interline_share,
                        "goodwill": a.airline_goodwill_per_hour},
        "profiles": {k: {"vot": p.value_of_time, "stop": p.stop_penalty, "note": p.note} for k, p in PROFILES.items()},
    }
    res = ROOT / "docs" / "results.json"
    if res.exists():
        r = json.loads(res.read_text(encoding="utf-8"))
        data["modelCard"] = {"prAuc": r["model"]["pr_auc"], "brier": r["model"]["brier"],
                             "testRows": r["model"]["test_rows"], "lateRate": r["model"]["late_rate_test"],
                             "retrieval": r["retrieval"]}
    data["parity"] = parity_cases(model)
    return data


def parity_cases(model, n: int = 60) -> list[dict]:
    rng = random.Random(520)
    cases = []
    while len(cases) < n:
        d = Disruption(inbound_delay=rng.choice([0, 30, 60, 95, 120, 150, 180, 210, 240, 270]),
                       month=rng.randint(1, 12), dow=rng.randint(1, 7), checked_bag=rng.random() < 0.6)
        vot = rng.choice([0, 12, 35, 80, 150, 250, 400])
        prof = Profile("case", float(vot), float(rng.choice([10, 25, 40])), "")
        persp = rng.choice(["traveller", "airline"])
        a = Assumptions(eu261_applies=rng.random() < 0.7, hotel=float(rng.choice([120, 180, 250])))
        o = RiskOracle(model, d)
        ranked = rank(enumerate_itineraries(o), o, prof, persp, a)
        cash = lambda f: 0.0 if f.protected else f.fare  # noqa: E731
        dj = search(o, vot / 60, 200, cash, False)
        ast = search(o, vot / 60, 200, cash, True)
        cases.append({
            "input": {"delay": d.inbound_delay, "month": d.month, "dow": d.dow, "bag": d.checked_bag,
                      "vot": vot, "stop": prof.stop_penalty, "perspective": persp, "eu261": a.eu261_applies,
                      "hotel": a.hotel},
            "n": len(ranked),
            "top": [{"flights": [f.id for f in s.itinerary.flights], "total": round(s.total, 4),
                     "p": round(s.p_success, 6)} for s in ranked[:5]],
            "dijkstra": {"flights": [f.id for f in dj.itinerary.flights] if dj.itinerary else [],
                         "expanded": dj.expanded},
            "astar": {"flights": [f.id for f in ast.itinerary.flights] if ast.itinerary else [],
                      "expanded": ast.expanded},
        })
    return cases


def main() -> None:
    data = export()
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__SIM_DATA__*/null", json.dumps(data, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB), {len(data['parity'])} parity cases, "
          f"delay data: {data['source']}")


if __name__ == "__main__":
    main()
