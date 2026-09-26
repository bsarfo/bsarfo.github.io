"""Scenario network: airports, minimum connection times and a one-day timetable.

ILLUSTRATIVE DATA. Flight numbers, times, seat availability and fares below are
invented for the demo (block times and distances are realistic). Before the
final presentation, replace them with a documented timetable (e.g. the
airlines' published schedules for a chosen date) and cite the source.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

AIRPORTS = {
    # code: (name, lat, lon, minimum connection time in minutes, busyness percentile)
    "BOS": ("Boston Logan", 42.3656, -71.0096, 60, 0.85),
    "ZRH": ("Zürich", 47.4647, 8.5492, 40, 0.88),
    "FRA": ("Frankfurt", 50.0379, 8.5622, 45, 0.99),
    "MUC": ("Munich", 48.3538, 11.7861, 35, 0.96),
    "VIE": ("Vienna", 48.1103, 16.5697, 30, 0.90),
    "AMS": ("Amsterdam", 52.3105, 4.7683, 50, 0.99),
    "WAW": ("Warsaw Chopin", 52.1657, 20.9671, 35, 0.80),
    "KRK": ("Kraków", 50.0777, 19.7848, 30, 0.60),
}

# carriers that share a ticket / alliance with the passenger's original booking
PROTECTED = {"LX", "LH", "OS", "LO"}  # Star Alliance group in this scenario
CARRIER_NAMES = {"LX": "SWISS", "LH": "Lufthansa", "OS": "Austrian", "LO": "LOT", "KL": "KLM", "W6": "Wizz Air",
                 "AJ": "AlpenJet (fictional)"}


def distance_km(a: str, b: str) -> float:
    _, la1, lo1, *_ = AIRPORTS[a]
    _, la2, lo2, *_ = AIRPORTS[b]
    p1, p2, dl = math.radians(la1), math.radians(la2), math.radians(lo2 - lo1)
    c = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)
    return 6371 * math.acos(max(-1, min(1, c)))


def hhmm(m: int) -> str:
    d, m = divmod(int(m), 1440)
    return f"{m // 60:02d}:{m % 60:02d}" + (f" +{d}" if d else "")


@dataclass(frozen=True)
class Flight:
    id: str
    carrier: str
    origin: str
    dest: str
    dep: int          # minutes after midnight, local Central European Time (day of disruption)
    arr: int
    fare: float       # walk-up one-way fare if a new ticket is needed (illustrative, USD)
    seats: int       # seats left in the cabin when we rebook (illustrative; 0 = full)

    @property
    def distance(self) -> float:
        return distance_km(self.origin, self.dest)

    @property
    def protected(self) -> bool:
        return self.carrier in PROTECTED

    def label(self) -> str:
        return f"{self.id} {self.origin}-{self.dest} {hhmm(self.dep)}-{hhmm(self.arr)}"


def _t(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


_RAW = [
    # id, carrier, origin, dest, dep, arr, fare, seats left
    ("LX1346", "LX", "ZRH", "WAW", "08:25", "10:20", 420, 4),     # original connection
    ("LX1348", "LX", "ZRH", "WAW", "14:20", "16:15", 390, 2),     # next direct
    ("LO412", "LO", "ZRH", "WAW", "18:45", "20:40", 310, 9),
    ("LX1350", "LX", "ZRH", "WAW", "21:10", "23:05", 290, 14),
    ("LX1072", "LX", "ZRH", "FRA", "10:05", "11:05", 260, 6),
    ("LH1227", "LH", "ZRH", "FRA", "12:40", "13:40", 240, 5),
    ("LH1352", "LH", "FRA", "WAW", "12:05", "14:00", 330, 3),
    ("LH1354", "LH", "FRA", "WAW", "15:20", "17:10", 300, 7),
    ("LH1356", "LH", "FRA", "WAW", "19:55", "21:45", 280, 11),
    ("LX1112", "LX", "ZRH", "MUC", "10:30", "11:25", 230, 0),     # full: infeasible
    ("LH2372", "LH", "ZRH", "MUC", "13:15", "14:10", 220, 6),
    ("LH1614", "LH", "MUC", "WAW", "12:10", "13:45", 310, 2),
    ("LH1616", "LH", "MUC", "WAW", "16:35", "18:10", 290, 8),
    ("OS566", "OS", "ZRH", "VIE", "10:15", "11:40", 210, 5),
    ("OS568", "OS", "ZRH", "VIE", "14:05", "15:30", 200, 9),
    ("OS627", "OS", "VIE", "WAW", "12:30", "13:45", 190, 1),
    ("OS629", "OS", "VIE", "WAW", "16:20", "17:35", 180, 10),
    ("OS631", "OS", "VIE", "WAW", "20:15", "21:30", 170, 12),
    ("KL1956", "KL", "ZRH", "AMS", "10:50", "12:25", 280, 7),     # other alliance: new ticket
    ("KL1995", "KL", "AMS", "WAW", "14:10", "16:15", 310, 5),
    ("AJ811", "AJ", "ZRH", "WAW", "11:15", "13:10", 260, 3),      # fictional low-cost nonstop, separate ticket
    ("W63302", "W6", "ZRH", "KRK", "11:30", "13:15", 95, 12),     # low-cost, separate ticket
    ("LO3924", "LO", "KRK", "WAW", "15:00", "15:55", 120, 6),
    ("LX1352", "LX", "ZRH", "WAW", "07:05", "09:00", 390, 20),    # next morning (+1 day)
]

TIMETABLE: list[Flight] = []
for fid, c, o, d, dep, arr, fare, seats in _RAW:
    dep_m, arr_m = _t(dep), _t(arr)
    if fid == "LX1352":  # next-day departure
        dep_m, arr_m = dep_m + 1440, arr_m + 1440
    TIMETABLE.append(Flight(fid, c, o, d, dep_m, arr_m, fare, seats))


@dataclass
class Disruption:
    """A traveller stranded mid-journey."""
    origin_flight: str = "LX53 BOS-ZRH"
    at: str = "ZRH"
    destination: str = "WAW"
    scheduled_in: int = _t("07:25")      # scheduled arrival of the delayed inbound flight
    inbound_delay: int = 95              # minutes
    original_connection: str = "LX1346"
    planned_arrival: int = _t("10:20")   # originally promised arrival at destination
    checked_bag: bool = True
    month: int = 7
    dow: int = 5
    trip_origin: str = "BOS"

    @property
    def ready_time(self) -> int:
        """When the traveller can board a new flight at the hub."""
        return self.scheduled_in + self.inbound_delay + AIRPORTS[self.at][3] + (10 if self.checked_bag else 0)

    @property
    def journey_km(self) -> float:
        return distance_km(self.trip_origin, self.destination)
