"""Evaluate ReRouteAI (deck slide 9: model, decision, ROI, retrieval).

1. Delay model   - time-based hold-out (train Jan-Sep, test Oct-Dec): PR-AUC, Brier,
                   log loss vs. simple baselines, calibration by decile.
2. Decisions     - simulate many disruptions; compare ReRouteAI with the deck's
                   baselines (earliest arrival, lowest fare, next direct on the
                   same carrier) on *realised* cost, sampled leg by leg.
                   Robustness: repeat with delays 50% worse than the model believes.
3. Sensitivity   - how the recommendation changes with the value of time.
4. Retrieval     - hit@3 on a labelled set of traveller questions.
5. ROI scenario  - savings per disrupted traveller x volume - operating cost.

Run:  python evaluate.py      (writes docs/results.md, docs/results.json, models/delay_model.pkl)
"""

from __future__ import annotations

import json
import pathlib
import time
from dataclasses import replace

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss

from rerouteai import delay_model as D
from rerouteai.bts import get_history
from rerouteai.graph import RiskOracle, enumerate_itineraries, fallback
from rerouteai.rag import PolicyIndex
from rerouteai.scoring import (PROFILES, Assumptions, baseline_cheapest, baseline_earliest, baseline_same_carrier,
                               eu261_compensation_eur, rank, EUR_TO_USD)
from rerouteai.timetable import AIRPORTS, Disruption

ROOT = pathlib.Path(__file__).resolve().parent
RNG = np.random.default_rng(2026)

# ROI scenario assumptions (state on the slide, change here)
DISRUPTED_PAX_PER_YEAR = 50_000     # misconnecting passengers per year at one mid-size hub (assumption)
AGENT_MINUTES_SAVED = 6             # agent handling time saved per passenger (to be measured in user tests)
AGENT_COST_PER_HOUR = 45.0
OPERATING_COST_PER_YEAR = 250_000   # hosting, data licences, maintenance, 1 FTE (assumption)


# ------------------------------------------------------------------ 1. model
def evaluate_model(df: pd.DataFrame, source: str) -> tuple[dict, D.DelayModel]:
    train, test = df[df["Month"] <= 9], df[df["Month"] >= 10]
    m = D.train(train, source)
    X = D.features(test, m.busy)
    P = m.predict_buckets(X)
    y = D.bucketize(test["ArrDelay"], test["Cancelled"])
    late = ((y >= 2)).astype(int)                         # arrival delay >= 15 min or cancelled
    p_late = P[:, 2:].sum(axis=1)

    # baseline 1: historical late rate by scheduled departure hour (what a lookup table gives)
    tr_late = (D.bucketize(train["ArrDelay"], train["Cancelled"]) >= 2).astype(int)
    by_hour = pd.Series(tr_late).groupby((train["CRSDepTime"] // 100).to_numpy()).mean()
    p_hour = (test["CRSDepTime"] // 100).map(by_hour).fillna(tr_late.mean()).to_numpy()
    # baseline 2: climatology (overall bucket frequencies)
    clim = np.bincount(D.bucketize(train["ArrDelay"], train["Cancelled"]), minlength=len(D.LABELS))
    clim = clim / clim.sum()

    deciles = pd.qcut(p_late, 10, labels=False, duplicates="drop")
    calib = pd.DataFrame({"predicted": p_late, "actual": late}).groupby(deciles).mean().round(3)
    res = {
        "source": source, "train_rows": int(len(train)), "test_rows": int(len(test)),
        "late_rate_test": float(late.mean()),
        "pr_auc": {"gradient boosting": float(average_precision_score(late, p_late)),
                   "hour-of-day lookup": float(average_precision_score(late, p_hour)),
                   "no skill": float(late.mean())},
        "brier": {"gradient boosting": float(brier_score_loss(late, p_late)),
                  "hour-of-day lookup": float(brier_score_loss(late, p_hour))},
        "log_loss_buckets": {"gradient boosting": float(log_loss(y, P, labels=range(len(D.LABELS)))),
                             "climatology": float(log_loss(y, np.tile(clim, (len(y), 1)), labels=range(len(D.LABELS))))},
        "calibration": calib.to_dict(orient="records"),
    }
    return res, m


# ------------------------------------------------------------------ 2. decisions
def sample_delay(p: np.ndarray, rng, worse: float) -> float:
    """Draw an arrival delay (minutes, inf = cancelled) from bucket probabilities.
    worse > 0 shifts mass toward longer delays to mimic a model that is too optimistic."""
    q = p.copy()
    if worse:
        q[1:] *= 1 + worse
        q[0] = max(1 - q[1:].sum(), 0.01)
        q /= q.sum()
    b = rng.choice(len(q), p=q)
    if b == D.CANCELLED:
        return np.inf
    lows, highs = [-10] + D.EDGES, D.EDGES + [480]
    return float(rng.uniform(max(lows[b], 0), highs[b]))


def realise(scored, oracle, profile, a: Assumptions, rng, worse: float) -> dict:
    d = oracle.d
    legs = scored.itinerary.legs
    arrival, failed = None, False
    delay_prev = None
    for i, leg in enumerate(legs):
        f = leg.flight
        if i > 0:
            prev = legs[i - 1].flight
            slack = f.dep - prev.arr - AIRPORTS[f.origin][3] - (10 if d.checked_bag else 0)
            if delay_prev > slack:
                failed = True
        dl = sample_delay(np.array(leg.delay_dist), rng, worse)
        if failed or dl == np.inf:
            exp_arr, p_night = fallback(oracle, f.origin, max(f.dep, d.ready_time))
            arrival, failed = exp_arr, True
            break
        delay_prev = dl
    if arrival is None:
        arrival = legs[-1].flight.arr + delay_prev
    delay = max(arrival - d.planned_arrival, 0)
    comp = eu261_compensation_eur(delay, d.journey_km) * EUR_TO_USD if a.eu261_applies else 0
    trav = scored.traveller_cash + profile.value_of_time * delay / 60 + profile.stop_penalty * (len(legs) - 1)
    airline = scored.airline_cash + scored.traveller_cash + comp + a.hotel * (arrival >= 1440) + \
        a.airline_goodwill_per_hour * delay / 60
    return {"traveller_cost": trav, "airline_cost": airline, "delay_h": delay / 60,
            "within_3h": delay < 180, "failed": failed}


def evaluate_decisions(m: D.DelayModel, n: int = 240, draws: int = 30) -> dict:
    out = {}
    a = Assumptions()
    for worse, tag in [(0.0, "model is right"), (0.5, "delays 50% worse than model")]:
        rows = []
        for _ in range(n):
            d = Disruption(inbound_delay=int(RNG.integers(60, 241)), month=int(RNG.integers(1, 13)),
                           dow=int(RNG.integers(1, 8)), checked_bag=bool(RNG.random() < 0.7))
            prof = PROFILES[RNG.choice(list(PROFILES))]
            persp = "traveller" if RNG.random() < 0.5 else "airline"
            o = RiskOracle(m, d)
            its = enumerate_itineraries(o)
            if not its:
                continue
            ranked = rank(its, o, prof, persp, a)
            strategies = {"ReRouteAI": ranked[0], "Earliest arrival": baseline_earliest(ranked),
                          "Lowest fare": baseline_cheapest(ranked),
                          "Next direct, same carrier": baseline_same_carrier(ranked, o) or ranked[-1]}
            for name, s in strategies.items():
                sims = [realise(s, o, prof, a, RNG, worse) for _ in range(draws)]
                key = "traveller_cost" if persp == "traveller" else "airline_cost"
                rows.append({"perspective": persp, "strategy": name, "cost": np.mean([x[key] for x in sims]),
                             "delay_h": np.mean([x["delay_h"] for x in sims]),
                             "within_3h": np.mean([x["within_3h"] for x in sims]),
                             "failed": np.mean([x["failed"] for x in sims])})
        df = pd.DataFrame(rows)
        for persp, part in df.groupby("perspective"):
            g = part.drop(columns="perspective").groupby("strategy").mean()
            g["cost_vs_ReRouteAI_$"] = g["cost"] - g.loc["ReRouteAI", "cost"]
            out[f"{persp} cases, {tag}"] = g.round(3).reset_index().to_dict(orient="records")
    return out


# ------------------------------------------------------------------ 3. sensitivity
def sensitivity(m: D.DelayModel) -> list[dict]:
    d = Disruption()
    o = RiskOracle(m, d)
    its = enumerate_itineraries(o)
    rows = []
    for vot in [0, 10, 25, 50, 75, 100, 150, 200, 300, 400]:
        prof = replace(PROFILES["Leisure traveller"], value_of_time=float(vot), name=f"VOT ${vot}/h")
        best = rank(its, o, prof, "traveller")[0]
        rows.append({"value_of_time_$per_h": vot, "recommended": best.itinerary.label,
                     "flights": " + ".join(f.id for f in best.itinerary.flights),
                     "p_works": round(best.p_success, 2), "traveller_pays_$": best.traveller_cash})
    for applies in [True, False]:
        best = rank(its, o, PROFILES["Leisure traveller"], "airline", Assumptions(eu261_applies=applies))[0]
        rows.append({"value_of_time_$per_h": f"airline view, EU261 {'applies' if applies else 'exempt (weather)'}",
                     "recommended": best.itinerary.label, "flights": " + ".join(f.id for f in best.itinerary.flights),
                     "p_works": round(best.p_success, 2), "traveller_pays_$": best.traveller_cash})
    return rows


# ------------------------------------------------------------------ 4. retrieval
RETRIEVAL_SET = [
    ("Am I owed compensation for arriving 4 hours late in Warsaw?", "eu261_passenger_rights#3"),
    ("Do I get a hotel if I am stuck overnight?", "eu261_passenger_rights#5"),
    ("Will my checked bag follow me if I buy a separate low-cost ticket?", "connections_and_baggage#4"),
    ("The delay was caused by a storm, do I still get money?", "eu261_passenger_rights#4"),
    ("Can the airline put me on a different airline?", "rebooking_policy_illustrative#2"),
    ("What is the minimum connection time?", "connections_and_baggage#1"),
    ("Who gets rebooked first when seats are scarce?", "rebooking_policy_illustrative#4"),
    ("Does the regulation apply to my Boston to Zurich flight on SWISS?", "eu261_passenger_rights#1"),
    ("Is delay measured at Zurich or at my final destination?", "eu261_passenger_rights#2"),
    ("Do I need to go through passport control in Zurich?", "connections_and_baggage#2"),
    ("Can I ask for a refund instead of a new flight?", "eu261_passenger_rights#6"),
    ("Will a person check the recommendation before my ticket is changed?", "rebooking_policy_illustrative#5"),
]


def evaluate_retrieval() -> dict:
    ix = PolicyIndex()
    hits1 = hits3 = 0
    misses = []
    for q, gold in RETRIEVAL_SET:
        ids = [c.id for c, _ in ix.search(q, 3)]
        hits1 += bool(ids) and ids[0] == gold
        hits3 += gold in ids
        if gold not in ids:
            misses.append(q)
    return {"questions": len(RETRIEVAL_SET), "hit@1": hits1 / len(RETRIEVAL_SET),
            "hit@3": hits3 / len(RETRIEVAL_SET), "misses": misses}


# ------------------------------------------------------------------ 5. ROI
def roi(decisions: dict) -> dict:
    # airline cash only: traveller value-of-time is not money the airline saves
    rows = {r["strategy"]: r for r in decisions["airline cases, model is right"]}
    saving_vs_default = rows["Next direct, same carrier"]["cost"] - rows["ReRouteAI"]["cost"]
    labour = AGENT_MINUTES_SAVED / 60 * AGENT_COST_PER_HOUR
    annual = (saving_vs_default + labour) * DISRUPTED_PAX_PER_YEAR - OPERATING_COST_PER_YEAR
    return {"expected_saving_per_pax_vs_default_$": round(saving_vs_default, 2),
            "agent_labour_saving_per_pax_$": round(labour, 2),
            "disrupted_pax_per_year": DISRUPTED_PAX_PER_YEAR, "operating_cost_per_year_$": OPERATING_COST_PER_YEAR,
            "net_annual_value_$": round(annual)}


def main() -> dict:
    df, source = get_history()
    model_res, _ = evaluate_model(df, source)
    full = D.train(df, source)          # deploy on all history
    D.save(full)
    t = time.perf_counter()
    decisions = evaluate_decisions(full)
    sim_s = time.perf_counter() - t
    res = {"model": model_res, "decisions": decisions, "sensitivity": sensitivity(full),
           "retrieval": evaluate_retrieval(), "roi": roi(decisions), "simulation_seconds": round(sim_s, 1)}
    write_report(res)
    return res


def _table(rows: list[dict]) -> list[str]:
    cols = list(rows[0])
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(f"{v:,.3f}" if isinstance(v, float) else str(v) for v in r.values()) + " |")
    return out


def write_report(r: dict) -> None:
    m = r["model"]
    L = ["# ReRouteAI - evaluation results", "",
         f"Delay data: **{m['source']}**. Regenerate with `python evaluate.py`. "
         "If the source says synthetic, these numbers only prove the pipeline works; re-run on real BTS files "
         "before presenting them as results.", "",
         "## 1. Delay model (train Jan-Sep, test Oct-Dec)", "",
         f"Test flights: {m['test_rows']:,}; late (>= 15 min) or cancelled: {m['late_rate_test']:.1%}.", "",
         "| Metric | Gradient boosting | Baseline |", "|---|---|---|",
         f"| PR-AUC (late >= 15 min) | {m['pr_auc']['gradient boosting']:.3f} | hour-of-day lookup "
         f"{m['pr_auc']['hour-of-day lookup']:.3f}; no skill {m['pr_auc']['no skill']:.3f} |",
         f"| Brier score (lower is better) | {m['brier']['gradient boosting']:.4f} | hour-of-day lookup "
         f"{m['brier']['hour-of-day lookup']:.4f} |",
         f"| Log loss, 11 delay buckets | {m['log_loss_buckets']['gradient boosting']:.4f} | climatology "
         f"{m['log_loss_buckets']['climatology']:.4f} |", "",
         "Calibration (deciles of predicted P(late)):", ""] + _table(m["calibration"])
    for tag, rows in r["decisions"].items():
        L += ["", f"## 2. Decision quality - simulated disruptions ({tag})", "",
              "Traveller cases: fares paid + value of time + connections. Airline cases: rebooking + EU261 + "
              "care + goodwill. Each strategy is replayed with delays sampled leg by leg.", ""]
        L += _table(rows)
    L += ["", "## 3. Sensitivity - the recommendation depends on the objective", ""] + _table(r["sensitivity"])
    rt = r["retrieval"]
    L += ["", "## 4. Policy retrieval", "",
          f"{rt['questions']} labelled questions: hit@1 {rt['hit@1']:.0%}, hit@3 {rt['hit@3']:.0%}."]
    if rt["misses"]:
        L += ["Missed: " + "; ".join(rt["misses"])]
    ro = r["roi"]
    L += ["", "## 5. ROI scenario (assumptions to be validated)", "",
          f"- Expected airline cost saved per disrupted passenger vs. 'next direct, same carrier': "
          f"${ro['expected_saving_per_pax_vs_default_$']:,.2f}",
          f"- Agent time saved per passenger: ${ro['agent_labour_saving_per_pax_$']:,.2f}",
          f"- x {ro['disrupted_pax_per_year']:,} disrupted passengers/yr - ${ro['operating_cost_per_year_$']:,} "
          f"operating cost = **${ro['net_annual_value_$']:,} net per year**",
          "", f"Simulation runtime: {r['simulation_seconds']} s."]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "results.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (ROOT / "docs" / "results.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
    print((ROOT / "docs" / "results.md").read_text(encoding="utf-8"))
