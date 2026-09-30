"""Decision model: the expected cost of each recovery option (Class 4, VectorDash).

    Expected cost = cash cost
                  + value of time x expected delay vs. the promised arrival
                  + expected cost of the plan failing (missed connection / no seat)
                  + inconvenience per extra stop
                  [+ airline view: expected EU261 compensation + duty-of-care costs]

Every probability comes from the delay model; every dollar value is an explicit,
adjustable assumption. Changing who the traveller is (value of time) or whose
money it is (traveller vs. airline) changes the optimal route - the Class 4
lesson that different priorities lead to different optimal solutions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import delay_model as D
from .graph import Itinerary, RiskOracle, fallback
from .timetable import hhmm

EUR_TO_USD = 1.10  # assumption


@dataclass(frozen=True)
class Profile:
    name: str
    value_of_time: float      # $ per hour of late arrival
    stop_penalty: float       # $ inconvenience per connection
    note: str


PROFILES = {
    "Student (cost first)": Profile("Student (cost first)", 12, 10, "Pays out of pocket; flexible schedule."),
    "Leisure traveller": Profile("Leisure traveller", 35, 25, "Moderate value of time."),
    "Business traveller": Profile("Business traveller", 150, 40, "Meeting on arrival; employer pays fares."),
    "Urgent (medical / family)": Profile("Urgent (medical / family)", 400, 20, "Arrival time dominates."),
}


@dataclass(frozen=True)
class Assumptions:
    hotel: float = 180.0                 # overnight cost (duty of care)
    meals: float = 30.0                  # meal vouchers when waiting > 2h
    interline_share: float = 0.60        # share of walk-up fare the airline pays another carrier
    eu261_applies: bool = True           # carrier-controllable delay on a covered journey
    airline_goodwill_per_hour: float = 20.0  # long-run customer cost the airline attaches to delay


def eu261_compensation_eur(delay_min: float, journey_km: float) -> float:
    """Regulation (EC) 261/2004 as interpreted by the CJEU (Sturgeon C-402/07; Folkerts C-11/11):
    >= 3h late at the FINAL destination triggers compensation by journey distance; the amount
    can be halved when re-routing keeps the delay under 2/3/4 hours. Simplified: verify before use."""
    if delay_min < 180:
        return 0.0
    if journey_km <= 1500:
        return 250.0
    if journey_km <= 3500:
        return 400.0
    return 300.0 if delay_min < 240 else 600.0


@dataclass
class Scored:
    itinerary: Itinerary
    p_success: float
    arrival_if_ok: float
    expected_arrival: float
    expected_delay_min: float
    traveller_cash: float
    airline_cash: float
    expected_eu261_usd: float
    breakdown: dict
    total: float

    def row(self) -> dict:
        return {
            "Route": self.itinerary.label,
            "Flights": " + ".join(f.id for f in self.itinerary.flights),
            "Departs": hhmm(self.itinerary.flights[0].dep),
            "Expected arrival if plan works": hhmm(self.arrival_if_ok),
            "P(plan works)": round(self.p_success, 3),
            "Expected delay (h)": round(self.expected_delay_min / 60, 2),
            "Traveller pays ($)": round(self.traveller_cash),
            "Airline pays ($)": round(self.airline_cash),
            "Expected cost ($)": round(self.total),
        }


def score(it: Itinerary, oracle: RiskOracle, profile: Profile, perspective: str = "traveller",
          a: Assumptions = Assumptions()) -> Scored:
    d = oracle.d
    km = d.journey_km
    fl = it.flights
    last = it.legs[-1]
    dist_last = np.array(last.delay_dist)

    # distribution of arrival delay (vs. promised arrival) when the plan works
    base = fl[-1].arr - d.planned_arrival
    exp_delay_ok = base + D.expected_delay(dist_last)
    p_ok = it.p_success

    def eu261_expected_when_ok() -> float:
        # compensation is a step function of delay: integrate over the delay distribution
        p_lt_180 = D.prob_delay_at_most(dist_last, 180 - base) if base < 180 else 0.0
        p_lt_240 = D.prob_delay_at_most(dist_last, 240 - base) if base < 240 else 0.0
        operate = 1 - dist_last[D.CANCELLED]
        full = eu261_compensation_eur(10_000, km)
        half = eu261_compensation_eur(200, km)
        return (max(p_lt_240 - p_lt_180, 0) * half + max(operate - p_lt_240, 0) * full) / max(operate, 1e-9)

    # failure branches: fail at leg i -> fallback from that leg's origin
    fail_terms = []
    reach = 1.0
    for leg in it.legs:
        p_fail_here = reach * (1 - leg.p)
        if p_fail_here > 0:
            arr_fb, p_night = fallback(oracle, leg.flight.origin, max(leg.flight.dep, d.ready_time))
            fail_terms.append((p_fail_here, arr_fb - d.planned_arrival, p_night))
        reach *= leg.p

    exp_delay = p_ok * exp_delay_ok + sum(p * dl for p, dl, _ in fail_terms)
    p_overnight = sum(p * pn for p, _, pn in fail_terms) + (p_ok if fl[-1].arr >= 1440 else 0)
    exp_arrival = d.planned_arrival + exp_delay

    # cash
    traveller_cash = sum(f.fare for f in fl if not f.protected)
    airline_cash = sum(f.fare * a.interline_share for f in fl if f.protected and f.carrier != "LX")
    # own-metal seat: displacement cost rises as the cabin fills (last seats could be sold)
    airline_cash += sum(f.fare * (0.5 if f.seats <= 2 else 0.1) for f in fl if f.carrier == "LX")

    eu_ok = eu261_expected_when_ok() if a.eu261_applies else 0.0
    eu_fail = sum(p * eu261_compensation_eur(dl, km) for p, dl, _ in fail_terms) if a.eu261_applies else 0.0
    exp_eu261 = (p_ok * eu_ok + eu_fail) * EUR_TO_USD
    care = a.hotel * p_overnight + a.meals * (1.0 if exp_delay > 120 else 0.0)

    stops = len(fl) - 1
    if perspective == "traveller":
        breakdown = {
            "Out-of-pocket fares": traveller_cash,
            "Value of time": profile.value_of_time * max(exp_delay, 0) / 60,
            "Connections (inconvenience)": profile.stop_penalty * stops,
            "Overnight risk (self-paid if uncovered)": 0.0 if a.eu261_applies else a.hotel * p_overnight,
        }
    else:
        breakdown = {
            "Rebooking / interline cost": airline_cash,
            "Expected EU261 compensation": exp_eu261,
            "Duty of care (meals, hotel)": care,
            "Customer goodwill": a.airline_goodwill_per_hour * max(exp_delay, 0) / 60,
            "Reimbursing a separate ticket": traveller_cash,
        }
    return Scored(it, p_ok, fl[-1].arr + D.expected_delay(dist_last), exp_arrival, exp_delay,
                  traveller_cash, airline_cash, exp_eu261, breakdown, sum(breakdown.values()))


def rank(its: list[Itinerary], oracle: RiskOracle, profile: Profile, perspective: str = "traveller",
         a: Assumptions = Assumptions()) -> list[Scored]:
    return sorted((score(i, oracle, profile, perspective, a) for i in its), key=lambda s: s.total)


# ------------------------------------------------------------- baselines (deck slide 5)
def baseline_earliest(scored: list[Scored]) -> Scored:
    """Earliest scheduled arrival, ignoring risk (what a timetable search shows)."""
    return min(scored, key=lambda s: (s.itinerary.flights[-1].arr, s.traveller_cash))


def baseline_cheapest(scored: list[Scored]) -> Scored:
    """Lowest out-of-pocket cost, then earliest."""
    return min(scored, key=lambda s: (s.traveller_cash, s.itinerary.flights[-1].arr))


def baseline_same_carrier(scored: list[Scored], oracle: RiskOracle) -> Scored | None:
    """Agent default: next direct flight on the original carrier that departs after we are ready."""
    c = [s for s in scored if len(s.itinerary.flights) == 1 and s.itinerary.flights[0].carrier == "LX"
         and s.itinerary.flights[0].dep >= oracle.d.ready_time]
    return min(c, key=lambda s: s.itinerary.flights[0].dep) if c else None
