import pathlib
import sys
from dataclasses import replace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rerouteai import delay_model as D  # noqa: E402
from rerouteai.agent import run_agent  # noqa: E402
from rerouteai.bts import generate_synthetic_bts  # noqa: E402
from rerouteai.graph import RiskOracle, enumerate_itineraries, search  # noqa: E402
from rerouteai.rag import PolicyIndex  # noqa: E402
from rerouteai.scoring import PROFILES, Assumptions, eu261_compensation_eur, rank  # noqa: E402
from rerouteai.timetable import AIRPORTS, Disruption  # noqa: E402


@pytest.fixture(scope="module")
def model():
    return D.train(generate_synthetic_bts(n=40_000, seed=3), "synthetic test")


@pytest.fixture(scope="module")
def oracle(model):
    return RiskOracle(model, Disruption())


def test_distribution_is_valid(model):
    p = model.predict_flight(7, 5, 18, 1000, 0.9, 0.8)
    assert abs(p.sum() - 1) < 1e-6
    assert D.prob_delay_at_most(p, 10) <= D.prob_delay_at_most(p, 60) <= 1 - p[D.CANCELLED] + 1e-9


def test_routes_respect_mct_and_seats(oracle):
    d = oracle.d
    for it in enumerate_itineraries(oracle):
        fl = it.flights
        assert fl[0].dep >= d.ready_time and fl[-1].dest == d.destination
        assert all(f.seats > 0 for f in fl)
        for a, b in zip(fl, fl[1:]):
            assert b.dep - a.arr >= AIRPORTS[b.origin][3]


def test_full_flight_never_offered(oracle):
    assert all("LX1112" not in [f.id for f in it.flights] for it in enumerate_itineraries(oracle))


def test_astar_matches_dijkstra_with_fewer_expansions(oracle):
    cash = lambda f: 0 if f.protected else f.fare  # noqa: E731
    for vot in (0.2, 2.5, 6.0):
        dj, ast = search(oracle, vot, 200, cash, False), search(oracle, vot, 200, cash, True)
        assert [f.id for f in dj.itinerary.flights] == [f.id for f in ast.itinerary.flights]
        assert abs(dj.cost - ast.cost) < 1e-6 and ast.expanded <= dj.expanded


def test_priorities_change_the_answer(oracle):
    its = enumerate_itineraries(oracle)
    student = rank(its, oracle, PROFILES["Student (cost first)"])[0]
    urgent = rank(its, oracle, PROFILES["Urgent (medical / family)"])[0]
    assert student.traveller_cash <= urgent.traveller_cash
    assert urgent.expected_delay_min <= student.expected_delay_min


def test_eu261_step_function():
    km = 6600
    assert eu261_compensation_eur(179, km) == 0
    assert eu261_compensation_eur(200, km) == 300
    assert eu261_compensation_eur(250, km) == 600
    assert eu261_compensation_eur(200, 1000) == 250


def test_weather_exemption_lowers_airline_cost(oracle):
    its = enumerate_itineraries(oracle)
    p = PROFILES["Leisure traveller"]
    with_eu = rank(its, oracle, p, "airline", Assumptions(eu261_applies=True))[0].total
    without = rank(its, oracle, p, "airline", Assumptions(eu261_applies=False))[0].total
    assert without <= with_eu


def test_no_delay_means_no_disruption(model):
    run = run_agent(model, Disruption(inbound_delay=0), PROFILES["Leisure traveller"])
    assert "still feasible" in run.steps[0]["result"]


def test_retrieval_finds_compensation_rules():
    ids = [c.id for c, _ in PolicyIndex().search("am I owed compensation for a long delay", 3)]
    assert "eu261_passenger_rights#3" in ids


def test_agent_never_books(model):
    run = run_agent(model, Disruption(), replace(PROFILES["Business traveller"]))
    assert run.steps[-1]["action"] == "Propose action" and "Nothing is booked" in run.steps[-1]["result"]
