"""Layer 4 - agent workflow: detect -> find alternatives -> estimate risk -> optimize
-> retrieve policy -> explain -> propose (a human approves).

Each step is an ordinary, testable function call and is logged, so the agent is
auditable. The agent proposes; it never books.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import delay_model as D
from .graph import RiskOracle, enumerate_itineraries, search, still_catchable
from .rag import PolicyIndex, answer
from .scoring import (Assumptions, Profile, Scored, baseline_cheapest, baseline_earliest, baseline_same_carrier,
                      rank)
from .timetable import AIRPORTS, TIMETABLE, Disruption, hhmm


@dataclass
class AgentRun:
    steps: list[dict] = field(default_factory=list)
    ranked: list[Scored] = field(default_factory=list)
    catchable: list = field(default_factory=list)
    baselines: dict = field(default_factory=dict)
    search_stats: dict = field(default_factory=dict)
    explanation: str = ""
    citations: list = field(default_factory=list)
    engine: str = ""
    runtime_ms: float = 0.0

    @property
    def best(self) -> Scored | None:
        return self.ranked[0] if self.ranked else None

    def log(self, step: str, detail: str):
        self.steps.append({"step": len(self.steps) + 1, "action": step, "result": detail})


def facts_text(run: AgentRun, d: Disruption, profile: Profile, perspective: str) -> str:
    b = run.best
    fl = b.itinerary.flights
    lines = [
        f"Situation: {d.origin_flight} landed {d.inbound_delay} min late at {d.at}; original connection "
        f"{d.original_connection} to {d.destination} is missed. Promised arrival was {hhmm(d.planned_arrival)}.",
        f"Traveller profile: {profile.name}. Optimizing for: {perspective}.",
        f"Recommended: {b.itinerary.label} on {' + '.join(f.id for f in fl)}, departing {hhmm(fl[0].dep)}, "
        f"expected arrival {hhmm(b.arrival_if_ok)} if the plan works; probability the plan works "
        f"{b.p_success:.0%}; expected delay {b.expected_delay_min / 60:.1f} h; traveller pays ${b.traveller_cash:,.0f}.",
    ]
    if len(run.ranked) > 1:
        r2 = run.ranked[1]
        lines.append(f"Runner-up: {r2.itinerary.label} on {' + '.join(f.id for f in r2.itinerary.flights)} "
                     f"(P works {r2.p_success:.0%}, expected cost ${r2.total:,.0f} vs ${b.total:,.0f}).")
    if any(not f.protected for f in fl):
        lines.append("Note: the recommendation includes a separate, unprotected ticket.")
    if d.checked_bag:
        lines.append("The traveller has a checked bag.")
    return "\n".join(lines)


def run_agent(model: D.DelayModel, d: Disruption, profile: Profile, perspective: str = "traveller",
              assumptions: Assumptions = Assumptions(), question: str | None = None,
              index: PolicyIndex | None = None) -> AgentRun:
    t0 = time.perf_counter()
    run = AgentRun()
    oracle = RiskOracle(model, d)

    missed = d.scheduled_in + d.inbound_delay + AIRPORTS[d.at][3] > next(
        f.dep for f in TIMETABLE if f.id == d.original_connection)
    run.log("Detect disruption", f"Inbound {d.inbound_delay} min late; ready to board at {hhmm(d.ready_time)}; "
                                 f"original connection {'MISSED' if missed else 'still feasible'}.")

    run.catchable = still_catchable(oracle)
    for f, p in run.catchable:
        run.log("Watch original flight", f"{f.id} could still be caught only if it departs late enough: "
                                         f"{p:.0%} chance. Monitor live status; do not rely on it.")

    its = enumerate_itineraries(oracle)
    full = [f.id for f in TIMETABLE if f.seats == 0]
    run.log("Retrieve alternatives", f"{len(its)} feasible routes (max 3 legs, MCT respected); "
                                     f"excluded full flights: {', '.join(full) or 'none'}.")

    if its:
        risky = min(its, key=lambda i: i.p_success)
        run.log("Estimate risk", f"Delay model ({model.source}) scored {len(oracle._cache)} flights; riskiest route "
                                 f"{risky.label} via {' + '.join(f.id for f in risky.flights)} works "
                                 f"{risky.p_success:.0%} of the time.")

    run.ranked = rank(its, oracle, profile, perspective, assumptions)
    cash = (lambda f: 0.0 if f.protected else f.fare)
    dj = search(oracle, profile.value_of_time / 60, 200, cash, use_astar=False)
    ast = search(oracle, profile.value_of_time / 60, 200, cash, use_astar=True)
    run.search_stats = {"dijkstra_expanded": dj.expanded, "astar_expanded": ast.expanded,
                        "same_route": [f.id for f in dj.itinerary.flights] == [f.id for f in ast.itinerary.flights]
                        if dj.itinerary and ast.itinerary else None,
                        "search_route": dj.itinerary.label if dj.itinerary else None}
    if run.ranked:
        run.baselines = {"Earliest scheduled arrival": baseline_earliest(run.ranked),
                         "Lowest fare": baseline_cheapest(run.ranked),
                         "Next direct on original carrier": baseline_same_carrier(run.ranked, oracle)}
        run.log("Optimize", f"Ranked {len(run.ranked)} routes by expected {perspective} cost; best "
                            f"{run.best.itinerary.label} (${run.best.total:,.0f}). Dijkstra expanded "
                            f"{dj.expanded} nodes, A* {ast.expanded}.")
        index = index or PolicyIndex()
        q = question or ("What is the recommended rebooking, why, and what passenger rights and baggage "
                         "rules apply to this delay and connection?")
        run.explanation, hits, run.engine = answer(q, facts_text(run, d, profile, perspective), index)
        run.citations = [(c.id, c.heading, round(s, 3)) for c, s in hits]
        run.log("Retrieve policy & explain", f"{len(hits)} policy sections retrieved; explanation by {run.engine}.")
        run.log("Propose action", "Recommendation sent to agent for approval. Nothing is booked automatically.")
    else:
        run.log("Optimize", "No feasible route found; escalate to a human agent.")
    run.runtime_ms = (time.perf_counter() - t0) * 1000
    return run
