"""Layer 1 - search: a time-expanded flight graph, searched with Dijkstra and A* (Class 4).

Nodes   = "the traveller has just landed at airport X at time t" (one per flight,
          plus the start node: stranded at the hub, ready at time t0).
Edges   = take flight f, allowed only if f departs after the traveller can make
          it (arrival + minimum connection time). Infeasible connections simply
          have no edge (Class 4: "cost of stairs = infinity").
Weights = a generalised cost that stays *additive*, so Dijkstra/A* remain exact:
          value of time x minutes  +  cash cost  +  lambda x (-ln P(edge works)).
          Using -ln P turns the product of connection probabilities along a route
          into a sum, which is what shortest-path algorithms need.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from . import delay_model as D
from .timetable import AIRPORTS, TIMETABLE, Disruption, Flight

HOPE_WINDOW = 120  # how far back to look for a scheduled departure that may still be catchable if delayed


@dataclass
class Leg:
    flight: Flight
    p: float             # P(traveller makes this flight and it operates | reached its origin in time)
    delay_dist: list     # predicted arrival-delay bucket probabilities for this flight


@dataclass
class Itinerary:
    legs: list[Leg] = field(default_factory=list)

    @property
    def flights(self) -> list[Flight]:
        return [l.flight for l in self.legs]

    @property
    def label(self) -> str:
        return " → ".join([self.legs[0].flight.origin] + [l.flight.dest for l in self.legs])

    @property
    def p_success(self) -> float:
        return math.prod(l.p for l in self.legs)


class RiskOracle:
    """Caches delay-distribution predictions for scenario flights."""

    def __init__(self, model: D.DelayModel, disruption: Disruption):
        self.model, self.d, self._cache = model, disruption, {}

    def dist(self, f: Flight):
        if f.id not in self._cache:
            self._cache[f.id] = self.model.predict_flight(
                self.d.month, self.d.dow + (f.dep // 1440), (f.dep % 1440) // 60, f.distance,
                AIRPORTS[f.origin][4], AIRPORTS[f.dest][4])
        return self._cache[f.id]

    def p_make_first(self, f: Flight) -> float:
        """P(we can board f from the hub). Certain if it leaves after we are ready;
        otherwise we need f itself to be delayed enough (dep delay ~ arr delay)."""
        need = self.d.ready_time - f.dep
        if need <= 0:
            return 1.0 - self.dist(f)[D.CANCELLED]
        return max(0.0, 1.0 - D.prob_delay_at_most(self.dist(f), need) - self.dist(f)[D.CANCELLED])

    def p_connect(self, prev: Flight, nxt: Flight) -> float:
        """P(prev lands early enough to make nxt) x P(nxt operates)."""
        slack = nxt.dep - prev.arr - AIRPORTS[nxt.origin][3] - (10 if self.d.checked_bag else 0)
        return D.prob_delay_at_most(self.dist(prev), slack) * (1 - self.dist(nxt)[D.CANCELLED])


def successors(node: Flight | None, oracle: RiskOracle, timetable=TIMETABLE):
    """Flights reachable from a node (None = the start node at the hub)."""
    d = oracle.d
    if node is None:
        for f in timetable:
            if f.origin == d.at and f.dep >= d.ready_time and f.seats > 0:
                p = oracle.p_make_first(f)
                if p > 0.01:
                    yield f, p
        return
    for f in timetable:
        if (f.origin == node.dest and f.dest != d.at and f.seats > 0
                and f.dep >= node.arr + AIRPORTS[f.origin][3]):
            p = oracle.p_connect(node, f)
            if p > 0.01:
                yield f, p


def still_catchable(oracle: RiskOracle) -> list[tuple[Flight, float]]:
    """Flights scheduled to leave before the traveller is ready that could still be
    caught if they are delayed (e.g. the original connection). These are not plans:
    the agent watches their live status while rebooking."""
    d = oracle.d
    return [(f, oracle.p_make_first(f)) for f in TIMETABLE
            if f.origin == d.at and f.dest == d.destination and d.ready_time - HOPE_WINDOW <= f.dep < d.ready_time]


def enumerate_itineraries(oracle: RiskOracle, max_legs: int = 3) -> list[Itinerary]:
    """All feasible routes to the destination (the network is small enough)."""
    out: list[Itinerary] = []

    def dfs(node, legs, seen):
        if legs and legs[-1].flight.dest == oracle.d.destination:
            out.append(Itinerary(list(legs)))
            return
        if len(legs) == max_legs:
            return
        for f, p in successors(node, oracle):
            if f.dest in seen:
                continue
            legs.append(Leg(f, p, list(oracle.dist(f))))
            dfs(f, legs, seen | {f.dest})
            legs.pop()

    dfs(None, [], {oracle.d.at})
    return out


# ------------------------------------------------------------------ Dijkstra / A*
@dataclass
class SearchResult:
    itinerary: Itinerary | None
    cost: float
    expanded: int


def edge_weight(prev_time: int, f: Flight, p: float, vot_per_min: float, lam: float, cash: float) -> float:
    return vot_per_min * (f.arr - prev_time) + cash + lam * -math.log(max(p, 1e-6))


def min_time_to(dest: str, timetable=TIMETABLE) -> dict[str, float]:
    """Admissible heuristic: fastest possible remaining block time (no waiting)."""
    best = {dest: 0.0}
    for _ in range(len(AIRPORTS)):  # Bellman-Ford relaxation on the airport graph
        for f in timetable:
            if f.dest in best:
                cand = best[f.dest] + (f.arr - f.dep)
                if cand < best.get(f.origin, math.inf):
                    best[f.origin] = cand
    return best


def search(oracle: RiskOracle, vot_per_min: float, lam: float, cash_cost, use_astar: bool) -> SearchResult:
    """Dijkstra (use_astar=False) or A* over the time-expanded graph."""
    d = oracle.d
    h = min_time_to(d.destination) if use_astar else {}
    heur = lambda airport: vot_per_min * h.get(airport, 0.0) if use_astar else 0.0  # noqa: E731
    start_time = d.scheduled_in + d.inbound_delay
    counter = 0
    frontier = [(heur(d.at), counter, 0.0, None, start_time, [])]
    done: set[str] = set()
    expanded = 0
    while frontier:
        f_score, _, g, node, t, path = heapq.heappop(frontier)
        key = node.id if node else "START"
        if key in done:
            continue
        done.add(key)
        expanded += 1
        if node is not None and node.dest == d.destination:
            return SearchResult(Itinerary(path), g, expanded)
        for f, p in successors(node, oracle):
            if f.id in done:
                continue
            g2 = g + edge_weight(t, f, p, vot_per_min, lam, cash_cost(f))
            counter += 1
            heapq.heappush(frontier, (g2 + heur(f.dest), counter, g2, f, f.arr,
                                      path + [Leg(f, p, list(oracle.dist(f)))]))
    return SearchResult(None, math.inf, expanded)


def fallback(oracle: RiskOracle, at: str, t: int) -> tuple[float, float]:
    """What happens if a plan fails at airport `at` at time t: the traveller is
    re-accommodated on the next protected option with seats (a cascade: each
    option works with its operating and connection probability).
    Returns (expected arrival minute, probability of an overnight stay).
    Simplification: options are treated as independent; any probability mass left
    after the last same-day option arrives next day around noon."""
    d = oracle.d
    options: list[tuple[int, float]] = []
    for f in TIMETABLE:
        if f.origin != at or not f.protected or f.seats == 0 or f.dep < t + AIRPORTS[at][3]:
            continue
        p_f = 1 - oracle.dist(f)[D.CANCELLED]
        if f.dest == d.destination:
            options.append((f.arr, p_f))
            continue
        for g in TIMETABLE:
            if (g.origin == f.dest and g.dest == d.destination and g.protected and g.seats > 0
                    and g.dep >= f.arr + AIRPORTS[g.origin][3]):
                options.append((g.arr, p_f * oracle.p_connect(f, g)))
    remaining, exp_arr, p_night = 1.0, 0.0, 0.0
    for arr, p in sorted(options):
        exp_arr += remaining * p * arr
        p_night += remaining * p * (arr >= 1440)
        remaining *= 1 - p
    exp_arr += remaining * (1440 + 12 * 60)
    p_night += remaining
    return exp_arr, p_night
